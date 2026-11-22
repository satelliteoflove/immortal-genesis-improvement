#!/usr/bin/env python3
"""Play the patched ROM in RetroArch, and log what the game is doing for later study.

    tools/play_retroarch.py [genesis_plus_gx|picodrive|blastem] [--no-fight-deaths] [--original] [--port N]

Starts RetroArch on build/immortal-patched.md (or the original ROM with --original) with the
named core, Genesis Plus GX if none is named. The core is taken from RetroArch's own cores
directory, ~/.config/retroarch/cores, so the test runs on what players download.

RetroArch is started with a small extra config that turns on its network commands and puts
screenshots in the session's directory. It also turns off saving the config on exit, so none
of this ends up in retroarch.cfg. Battery saves go wherever RetroArch normally keeps them.

While the game runs, the script reads the game's RAM through RetroArch's READ_CORE_RAM
command about 30 times a second and logs the level, room, position, health, retries, fights,
text boxes, deaths and late ticks. A tick is late when it starts more than 5 frames after the
one before; gaps of 12 or more are pauses (a text box, a fight, a death), not lateness.

--no-fight-deaths keeps the wizard from losing a fight. While one is on, his strength in it
(FF10A8) is put back to what it started at whenever a blow lowers it, so he still has to win
the fight, but can't lose it. Traps and everything else can still kill him. The log notes each
top-up.

Type a note in this terminal and press Enter at any moment. It goes in the log with the game's
state at that moment, and RetroArch takes a screenshot. An empty Enter just takes the
screenshot and logs where you are.

Everything goes in scratch/sessions/<date-time>/, which git ignores: log.txt to read, events.jsonl
for scripts, and the screenshots.
"""
import argparse
import json
import os
import queue
import signal
import socket
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import romcheck

CORES = os.path.expanduser('~/.config/retroarch/cores')
PATCHED = os.path.join(ROOT, 'build', 'immortal-patched.md')

# The game's RAM, as offsets from FF0000. See tools/harness/route/common.py.
COUNT, DEADLINE = 0x9624, 0x12E6        # vertical blanks; when the next tick may start
BLOCK = 0x0600                          # one read from here covers everything below
BLOCK_END = 0x1100
TEXT_ADDRESS = 0x0600                   # the text box's text in the ROM, low byte first
WIZARD_X, WIZARD_Y, HEALTH = 0x08BC, 0x08D0, 0x090C
LEVEL, ROOM = 0x1070, 0x1071
LEVEL_OVER, GAME_OVER, RETRIES = 0x106F, 0x1072, 0x109A
OPPONENT, ENEMY_HEALTH, FIGHT_HEALTH = 0x10AE, 0x10A7, 0x10A8

POLL = 1 / 30
PAUSE = 12


class RetroArch:
    def __init__(self, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(0.5)
        self.addr = ('127.0.0.1', port)

    def ask(self, command):
        self.sock.sendto(command.encode(), self.addr)
        try:
            return self.sock.recv(65536).decode(errors='replace').strip()
        except socket.timeout:
            return None

    def tell(self, command):
        self.sock.sendto(command.encode(), self.addr)

    def ram(self, address, length):
        """Bytes of the game's RAM from FF0000 + address, or None if RetroArch didn't answer.

        RetroArch hands over the RAM as the cores keep it, in 16-bit words with their two bytes
        swapped (all three cores alike), so reads are of whole words and swapped back here."""
        assert address % 2 == 0 and length % 2 == 0
        answer = self.ask(f'READ_CORE_RAM {address:x} {length}')
        if not answer:
            return None
        parts = answer.split()
        if len(parts) < 3 or parts[2] == '-1':
            return None
        try:
            raw = bytes(int(p, 16) for p in parts[2:2 + length])
        except ValueError:
            return None
        if len(raw) != length:
            return None
        swapped = bytearray(length)
        swapped[0::2], swapped[1::2] = raw[1::2], raw[0::2]
        return bytes(swapped)


class Log:
    def __init__(self, directory):
        self.text = open(os.path.join(directory, 'log.txt'), 'a', buffering=1)
        self.json = open(os.path.join(directory, 'events.jsonl'), 'a', buffering=1)
        self.start = time.time()

    def __call__(self, kind, message, quiet=False, **data):
        t = time.time() - self.start
        stamp = f'{int(t // 3600)}:{int(t // 60) % 60:02}:{t % 60:04.1f}'
        line = f'[{stamp}] {message}'
        self.text.write(line + '\n')
        self.json.write(json.dumps({'t': round(t, 2), 'kind': kind, 'message': message, **data}) + '\n')
        if not quiet:
            print(line, flush=True)


def word(b, at):
    return b[at] << 8 | b[at + 1]


def read_state(ra):
    """The parts of the game's state the log follows, or None if RetroArch didn't answer."""
    counts = ra.ram(COUNT, 4)
    deadline = ra.ram(DEADLINE, 4)
    block = ra.ram(BLOCK, BLOCK_END - BLOCK)
    if not counts or not deadline or not block:
        return None

    def at(a):
        return block[a - BLOCK]
    return {
        'count': int.from_bytes(counts, 'big'),
        'deadline': int.from_bytes(deadline, 'big'),
        'level': at(LEVEL) + 1, 'room': at(ROOM),
        'x': at(WIZARD_X), 'y': at(WIZARD_Y), 'health': at(HEALTH) >> 4,
        'retries': at(RETRIES), 'level_over': at(LEVEL_OVER), 'game_over': at(GAME_OVER),
        'opponent': at(OPPONENT), 'enemy_health': at(ENEMY_HEALTH), 'fight_health': at(FIGHT_HEALTH),
        'text': at(TEXT_ADDRESS) | at(TEXT_ADDRESS + 1) << 8,
    }


def where(s):
    return f"level {s['level']}, room {s['room']}, at ({s['x']}, {s['y']}), health {s['health']}, " \
           f"retries {s['retries']}"


class Rooms:
    """Late ticks, counted for each stay in a room."""

    def __init__(self, log):
        self.log = log
        self.key = None
        self.ticks = self.late = self.worst = self.lost = 0
        self.totals = [0, 0, 0]

    def enter(self, key):
        self.flush()
        self.key = key
        self.ticks = self.late = self.worst = self.lost = 0

    def tick(self, gap):
        self.ticks += 1
        self.totals[0] += 1
        if gap > 5:
            self.late += 1
            self.lost += gap - 5
            self.worst = max(self.worst, gap)
            self.totals[1] += 1
            self.totals[2] += gap - 5

    def flush(self):
        if self.key and self.ticks:
            self.log('ticks', f'  left level {self.key[0]} room {self.key[1]}: {self.ticks} ticks, '
                     f'{self.late} late ({100 * self.late / self.ticks:.0f}%), {self.lost} frames lost, '
                     f'worst gap {self.worst or 5}', quiet=True,
                     level=self.key[0], room=self.key[1], ticks=self.ticks, late=self.late,
                     lost=self.lost, worst=self.worst)


def watch(ra, log, notes, proc, no_fight_deaths=False):
    last = None
    rooms = Rooms(log)
    strength = None                     # the wizard's strength when the fight began
    while proc.poll() is None:
        time.sleep(POLL)
        s = read_state(ra)
        while not notes.empty():
            note = notes.get()
            ra.tell('SCREENSHOT')
            at = f'{where(s)}, frame {s["count"]}' if s else 'game state not readable'
            log('note', f'NOTE: {note or "(screenshot)"} -- {at}', note=note, state=s)
        if s is None:
            continue

        if no_fight_deaths:
            if not s['opponent']:
                strength = None
            elif s['fight_health']:
                strength = max(strength or 0, s['fight_health'])
                if s['fight_health'] < strength:
                    # one byte; RetroArch's addresses have each word's two bytes swapped
                    ra.tell(f'WRITE_CORE_RAM {FIGHT_HEALTH ^ 1:x} {strength:02x}')
                    log('cheat', f'  fight strength {s["fight_health"]} put back to {strength}',
                        quiet=True, state=s)

        if last is None:
            log('start', f'game running: {where(s)}', state=s)
            last = s
            rooms.enter((s['level'], s['room']))
            continue

        # ticks: the deadline moves by 5 when on time, more when late
        if s['deadline'] != last['deadline']:
            gap = s['deadline'] - last['deadline']
            frames = s['count'] - last['count']
            if 0 < gap < PAUSE and frames < 10:     # frames < 10: two ticks can't hide in one poll
                rooms.tick(gap)
                if gap >= 8:
                    log('late', f'  slow tick: {gap} frames, {where(s)}', quiet=True, gap=gap, state=s)

        if (s['level'], s['room']) != (last['level'], last['room']):
            rooms.enter((s['level'], s['room']))
            kind = 'level' if s['level'] != last['level'] else 'room'
            log(kind, f'{"LEVEL" if kind == "level" else "room"}: {where(s)}', state=s)

        if s['opponent'] and not last['opponent']:
            log('fight', f'fight begins: {where(s)}, enemy health {s["enemy_health"]}', state=s)
        if last['opponent'] and not s['opponent']:
            log('fight', f'fight over: {where(s)}', state=s)

        if s['health'] == 0 and last['health'] != 0:
            log('death', f'DEATH: {where(s)}', state=s)
        elif s['health'] != last['health'] and not s['opponent']:
            log('health', f'  health {last["health"]} -> {s["health"]}: {where(s)}', quiet=True, state=s)
        if s['retries'] != last['retries']:
            log('retries', f'retries {last["retries"]} -> {s["retries"]}: {where(s)}', state=s)
        if s['level_over'] and not last['level_over']:
            log('level_over', f'LEVEL OVER: {where(s)}', state=s)
        if s['game_over'] and not last['game_over']:
            log('game_over', f'GAME OVER: {where(s)}', state=s)
        if s['text'] != last['text']:
            log('text', f'  text box at {s["text"]:04x}: {where(s)}', quiet=True, text=s['text'])

        if s['count'] < last['count']:
            log('reset', '  frame count went back: a reset, a loaded state, or the title restarting',
                quiet=True, state=s)
        last = s
    rooms.flush()
    t = rooms.totals
    if t[0]:
        log('summary', f'session: {t[0]} ticks, {t[1]} late ({100 * t[1] / t[0]:.1f}%), {t[2]} frames lost',
            ticks=t[0], late=t[1], lost=t[2])


def main():
    parser = argparse.ArgumentParser(description='Play in RetroArch and log what the game does.')
    parser.add_argument('core', nargs='?', default='genesis_plus_gx',
                        choices=['genesis_plus_gx', 'picodrive', 'blastem'])
    parser.add_argument('--original', action='store_true', help='play the original ROM instead')
    parser.add_argument('--no-fight-deaths', action='store_true', help="the wizard can't lose a fight")
    parser.add_argument('--port', type=int, default=55399, help='RetroArch network command port')
    parser.add_argument('--extra-config', help='more RetroArch settings to add, for testing')
    args = parser.parse_args()

    core = os.path.join(CORES, f'{args.core}_libretro.so')
    if not os.path.exists(core):
        sys.exit(f'{core} is missing: download it with RetroArch\'s core updater first')
    rom = romcheck.find_rom() if args.original else PATCHED
    if not os.path.exists(rom):
        sys.exit(f'{rom} is missing: run tools/build_rom.py first')

    directory = os.path.join(ROOT, 'scratch', 'sessions', time.strftime('%Y-%m-%d-%H%M%S'))
    os.makedirs(directory)
    config = os.path.join(directory, 'retroarch-extra.cfg')
    with open(config, 'w') as f:
        f.write(f'network_cmd_enable = "true"\nnetwork_cmd_port = "{args.port}"\n'
                f'screenshot_directory = "{directory}"\nconfig_save_on_exit = "false"\n')
        if args.extra_config:
            f.write(open(args.extra_config).read())

    log = Log(directory)
    log('session', f'core {args.core}, ROM {os.path.basename(rom)}, log in {directory}'
        + (', no deaths in fights' if args.no_fight_deaths else ''),
        core=args.core, rom=rom, no_fight_deaths=args.no_fight_deaths)
    print('Type a note and press Enter at any time; Enter alone takes a screenshot.\n', flush=True)

    proc = subprocess.Popen(['retroarch', '--appendconfig', config, '-L', core, rom],
                            stdout=subprocess.DEVNULL, stderr=open(os.path.join(directory, 'retroarch.log'), 'w'))
    ra = RetroArch(args.port)
    for _ in range(40):
        status = ra.ask('GET_STATUS')
        if status:
            log('status', f'RetroArch: {status}', status=status)
            break
        if proc.poll() is not None:
            sys.exit(f'RetroArch exited; see {directory}/retroarch.log')
        time.sleep(0.25)
    else:
        log('status', 'RetroArch never answered on the network port; only notes will be logged')

    notes = queue.Queue()

    def read_notes():
        for line in sys.stdin:
            notes.put(line.strip())
    threading.Thread(target=read_notes, daemon=True).start()

    def stop(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    try:
        watch(ra, log, notes, proc, args.no_fight_deaths)
    except KeyboardInterrupt:
        log('session', 'stopped from the terminal')
        proc.terminate()
        proc.wait()
    log('session', 'RetroArch closed')


if __name__ == '__main__':
    main()

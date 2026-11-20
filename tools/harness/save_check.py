#!/usr/bin/env python3
"""Check the battery saves, the level picker and the second try at Game Over.

    tools/harness/save_check.py [--core blastem|picodrive|genesis_plus_gx]

Plays short scripted runs on a libretro core, BlastEm's unless --core names another,
keeping the cartridge's battery RAM in a file between them (the runner's -B), and reads the
68000's RAM at the end of each. The cores keep battery RAM differently: BlastEm packs the
odd bytes the game uses into a 256-byte file, PicoDrive keeps a byte for each address in
512 bytes, and Genesis Plus GX keeps 64 KB, filled with FF when new. The checks read and
write it as the game sees it, the odd bytes in order, and every run that starts without a
save starts from zeros.
A level is ended by setting the game's own "level over" byte, and Game Over is reached by
setting its "out of retries" byte, so nothing here depends on playing well.

What is checked:

  - the original and the patched ROM make the same certificate at a level's end
  - the patched ROM writes it to that level's place in battery RAM and nowhere else
  - a certificate typed into either ROM starts the same level with the same things as
    loading the save does
  - with saves present the game offers them; the picker steps through the saved levels,
    goes round at the ends and passes over a damaged save
  - reaching a level again replaces its save
  - Game Over: YES starts the level again with what its certificate gives, or a new game
    on the first level; NO goes on to the game's usual prompts
  - winning the game, which ends by way of Game Over with the wizard alive on the last level,
    gets the original's "Play again?", not the offer to try the level again

Everything is written under scratch/save-check, which git ignores.
"""
import argparse
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import compare_cores as cc

sys.path.insert(0, os.path.join(cc.ROOT, 'tools'))
import build_rom as B
import romcheck

CORES = {   # path, runner options, how battery RAM is kept, its file's size
    'blastem': (os.path.join(cc.ROOT, 'build', 'cores', 'blastem', 'blastem_libretro.so'),
                ['-b', '0,8,11'], 'packed', 256),
    'picodrive': (os.path.join(cc.ROOT, 'build', 'picodrive', 'picodrive_libretro.so'), [], 'odd', 512),
    'genesis_plus_gx': (os.path.join(cc.ROOT, 'build', 'cores', 'genesis_plus_gx', 'genesis_plus_gx_libretro.so'),
                        [], 'odd', 65536),
}
CORE = 'blastem'                        # set from --core
OUT = os.path.join(cc.ROOT, 'scratch', 'save-check')    # a directory for each core is made under it
PATCHED = os.path.join(cc.ROOT, 'build', 'immortal-patched.md')
A4 = 0x300                              # the game's variables are addressed from here
LEVEL, ITEMS, ITEM_COUNT = A4 + 0xD70, A4 + 0x7EE, 42
LEVEL_OVER, NO_RETRIES, ROOM = 'ff106f', 'ff1072', 'ff1071'
FIELDS = A4 + B.CERTIFICATE
SLOT = 16                               # bytes of battery RAM, as the core keeps it, for each level
TITLE = ['700 0 START', '706 0 -']
FIRST = 800                             # the first prompt after the title is up by now


def answer(frame, yes):
    """The game's YES and NO: hold a direction and press a button, then let go of both.

    A direction still held when the certificate screen comes up after NO types a 0 there, in
    the original too. On PicoDrive the patched ROM's screen comes up about 4 frames sooner,
    and holding LEFT 12 frames past the C was enough for it."""
    way = 'RIGHT' if yes else 'LEFT'
    return [f'{frame} 0 {way}', f'{frame + 12} 0 {way}+C', f'{frame + 18} 0 -']


def tap(frame, button, hold=6):
    return [f'{frame} 0 {button}', f'{frame + hold} 0 -']


def typed(certificate, frame):
    """Type a certificate on the game's entry screen: RIGHT adds a 0, UP and DOWN change it.

    Returns the events and the frame they end on."""
    events = []
    for letter in certificate:
        value = int(letter, 16)
        events += tap(frame, 'RIGHT', 4)
        frame += 20
        for _ in range(min(value, 16 - value)):
            events += tap(frame, 'UP' if value <= 8 else 'DOWN', 2)
            frame += 20
    return events + tap(frame + 40, 'START'), frame + 46


def to_file(data):
    """Battery RAM as the game sees it, in the core's own layout."""
    _, _, layout, size = CORES[CORE]
    if layout == 'packed':
        return bytes(data) + bytes(size - len(data))
    raw = bytearray(size)
    raw[1:2 * len(data):2] = data
    return bytes(raw)


def from_file(raw):
    return raw if CORES[CORE][2] == 'packed' else raw[1::2]


class Run:
    def __init__(self, name, frames, events, pokes=(), battery=None, rom=PATCHED):
        self.name, self.frames, self.events, self.pokes, self.rom = name, frames, events, pokes, rom
        self.battery = os.path.join(OUT, (battery or name) + '.srm')
        self.ram_path = os.path.join(OUT, name + '.ram')

    def go(self):
        core, extra, _, _ = CORES[CORE]
        script = os.path.join(OUT, self.name + '.txt')
        with open(script, 'w') as f:
            f.write('\n'.join(sorted(TITLE + self.events, key=lambda e: int(e.split()[0]))) + '\n')
        command = [os.path.join(cc.ROOT, 'build', 'runner'), core, self.rom, '-q', '-n', str(self.frames), *extra,
                   '-i', script, '-m', self.ram_path]
        if self.rom == PATCHED:
            if not os.path.exists(self.battery):
                with open(self.battery, 'wb') as f:
                    f.write(to_file(b''))
            command += ['-B', self.battery]
        for poke in self.pokes:
            command += ['-p', poke]
        done = subprocess.run(command, capture_output=True, text=True)
        if done.returncode:
            sys.exit(f'{self.name}: {done.stderr[-300:]}')
        with open(self.ram_path, 'rb') as f:
            self.ram = f.read()
        return self

    level = property(lambda self: self.ram[LEVEL])
    items = property(lambda self: self.ram[ITEMS:ITEMS + ITEM_COUNT])
    fields = property(lambda self: self.ram[FIELDS:FIELDS + 13])
    said = property(lambda self: self.ram[B.TEXT_BUFFER:].split(b'\0')[0].decode('ascii', 'replace'))

    def saves(self):
        with open(self.battery, 'rb') as f:
            return from_file(f.read())


def together(*runs):
    with ThreadPoolExecutor(os.cpu_count()) as pool:
        return list(pool.map(Run.go, runs))


def battery(name, data):
    with open(os.path.join(OUT, name + '.srm'), 'wb') as f:
        f.write(to_file(data))


def main():
    global CORE, OUT
    parser = argparse.ArgumentParser(description='Check the battery saves, the level picker and Game Over.')
    parser.add_argument('--core', choices=CORES, default='blastem')
    CORE = parser.parse_args().core
    OUT = os.path.join(OUT, CORE)
    print('core:', CORE)
    os.makedirs(OUT, exist_ok=True)
    for name in os.listdir(OUT):
        if name.endswith('.srm'):
            os.remove(os.path.join(OUT, name))
    original = romcheck.find_rom()
    good = True

    def report(what, ok):
        nonlocal good
        good &= bool(ok)
        print(f'  {what}: {"yes" if ok else "NO"}')

    # A level ends. The same again for two other levels, to have three saves to pick from.
    new_game = answer(FIRST, True)
    end = [f'1100:{LEVEL_OVER}=1']
    first, there, plain, *others = together(
        Run('end-original', 1400, new_game, end, rom=original),
        Run('end', 1400, new_game, end),
        Run('plain', 1100, new_game),
        *(Run(f'end-{level}', 1400, new_game, [f'1100:ff1070={level - 1:02x}'] + end) for level in (3, 7)))
    saved = there.saves()
    print('A level ends')
    report('the patched ROM makes the same certificate as the original', there.fields == first.fields)
    report('it is in battery RAM, in the place for its level', saved[SLOT:SLOT + 13] == there.fields)
    report('nothing else in battery RAM is touched', not any(saved[:SLOT]) and not any(saved[2 * SLOT:]))
    certificate = there.fields.hex()[1::2]

    # Loading it, against typing it.
    keys, typed_end = typed(certificate, 1000)
    battery('load', saved)
    battery('typed', bytes(len(saved)))
    by_hand, by_hand_patched, loaded = together(
        Run('typed-original', typed_end + 300, answer(FIRST, False) + keys, rom=original),
        Run('typed', typed_end + 300, answer(FIRST, False) + keys),
        Run('load', 1300, answer(FIRST, True) + tap(1000, 'START')))
    print(f'Certificate {certificate}')
    report('typed into the original, it starts level 2', by_hand.level == 1)
    report('typed into the patched ROM, it starts the same level with the same things',
           (by_hand_patched.level, by_hand_patched.items) == (by_hand.level, by_hand.items))
    report('the game offers the save', loaded.said.startswith('Up or Down selects a level.'))
    report('loading the save does the same as typing it', (loaded.level, loaded.items) == (by_hand.level, by_hand.items))
    report('typing a certificate leaves battery RAM alone', not any(by_hand_patched.saves()))

    # Picking among three saves, one of them damaged in the second set.
    three = bytearray(saved)
    for run, level in zip(others, (3, 7)):
        three[SLOT * level:SLOT * (level + 1)] = run.saves()[SLOT * level:SLOT * (level + 1)]
    damaged = bytearray(three)
    damaged[SLOT * 3 + 7] ^= 1
    steps = (('first', ()), ('down', ('DOWN',)), ('down-down', ('DOWN', 'DOWN')), ('round', ('DOWN', 'DOWN', 'DOWN')),
             ('up', ('UP',)))
    picks = []
    for kind, data in (('three', three), ('damaged', damaged)):
        for name, presses in steps:
            battery(f'{kind}-{name}', data)
            keys = [e for i, p in enumerate(presses) for e in tap(1000 + 40 * i, p)]
            picks.append(Run(f'{kind}-{name}', 1500, answer(FIRST, True) + keys + tap(1200, 'START')))
    levels = [run.level + 1 for run in together(*picks)]
    print('Picking a level')
    report(f'with levels 2, 4 and 8 saved, the list starts at 8 and goes round: {levels[:5]}', levels[:5] == [8, 4, 2, 8, 2])
    report(f'with the save for level 4 damaged it is passed over: {levels[5:]}', levels[5:] == [8, 2, 8, 2, 2])

    # Reaching level 2 again, by a different route through the first level.
    battery('replace', saved)
    again = Run('replace', 1700, answer(FIRST, False) + answer(1000, True), [f'1400:{ROOM}=5a', f'1400:{LEVEL_OVER}=1']).go()
    print('Reaching a level again')
    report('its save is replaced', again.saves()[SLOT:SLOT + 13] == again.fields != saved[SLOT:SLOT + 13])

    # Game Over.
    over = 'Game Over&&Try this level again?%'
    for name in ('again-2', 'end-2'):
        battery(name, saved)
    to_level_2 = answer(FIRST, True) + tap(1000, 'START')
    again_2, end_2, again_1, end_1 = together(
        Run('again-2', 2000, to_level_2 + answer(1600, True), [f'1300:{NO_RETRIES}=1']),
        Run('end-2', 2000, to_level_2 + answer(1600, False), [f'1300:{NO_RETRIES}=1']),
        Run('again-1', 1800, new_game + answer(1400, True), [f'1100:{NO_RETRIES}=1']),
        Run('end-1', 2100, new_game + answer(1400, False) + answer(1700, True), [f'1100:{NO_RETRIES}=1']))
    print('Game Over')
    report('on level 2, YES starts it again with what its certificate gives',
           again_2.said == over and (again_2.level, again_2.items) == (loaded.level, loaded.items))
    report('on level 2, NO goes on to the saved games', end_2.said == B.SAVE_MESSAGES['continue'])
    report('on level 1, YES starts a new game', again_1.said == over and (again_1.level, again_1.items) == (0, plain.items))
    report('on level 1 with nothing saved, NO goes on to "New game?"',
           end_1.said == over and (end_1.level, end_1.items) == (0, plain.items))
    report('a second try has three lives', again_2.ram[A4 + 0xD9A] == again_1.ram[A4 + 0xD9A] == 2)

    # The last level, reached as the harness reaches any level: load it from the fields.
    last = [f'1100:{FIELDS + 0xFF0000 + 5:x}=7', '1100:ff1088=1', '1100:ff1073=1']
    won, lost = together(
        Run('won', 1900, new_game, last + [f'1700:{NO_RETRIES}=1']),
        Run('lost', 1900, new_game, last + [f'1700:{NO_RETRIES}=1', f'1700:{A4 + B.WIZARD_HEALTH + 0xFF0000:x}=0']))
    print('The end of the game')
    report('on the last level, Game Over with the wizard alive leaves the original message', won.level == 7 and won.said == '')
    report('with the wizard dead it offers the level again', lost.level == 7 and lost.said == over)
    sys.exit(0 if good else 1)


if __name__ == '__main__':
    main()

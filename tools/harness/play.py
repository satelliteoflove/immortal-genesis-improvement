#!/usr/bin/env python3
"""Play the game from a script that can see what the game is doing.

    from play import Game
    g = Game()                          # the patched ROM; Game(original()) for the original
    g.start_level('cddff10006f70')      # or g.new_game()
    g.step(5, 'UP+RIGHT')               # five frames with those buttons held
    g.var(0xD70)                        # a byte of the game's variables, here the level
    g.keep(1); ...; g.back(1)           # remember the machine's state, and return to it
    g.shot('scratch/x.png')

The game runs on BlastEm's libretro core inside build/runner, in its command mode (-I).
After every step the 68000's whole RAM is here to read, so a script can decide each press
from where things are, not from a frame count. That is what lets one script play the
original and the patched ROM alike, though they run at different speeds.

`docs/playthrough.md` has what's known about the game's memory and how routes are written.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import romcheck

RUNNER = os.path.join(ROOT, 'build', 'runner')
CORE = os.environ.get('PLAY_CORE') or os.path.join(ROOT, 'build', 'cores', 'blastem', 'blastem_libretro.so')
PATCHED = os.path.join(ROOT, 'build', 'immortal-patched.md')
A4 = 0x300                              # the game's variables are addressed from FF0300


def original():
    return romcheck.find_rom()


class Game:
    def __init__(self, rom=PATCHED, battery=None):
        command = [RUNNER, CORE, rom, '-q', '-b', '0,8,11', '-I']
        if battery:
            command += ['-B', battery]
        self.rom = rom
        self.runner = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.DEVNULL)
        self.frame = 0
        self.kept = {}
        self.ram = bytes(0x10000)

    # --- the machine ---

    def _send(self, text):
        self.runner.stdin.write(text.encode() + b'\n')
        self.runner.stdin.flush()

    def _answer(self, text):
        self._send(text)
        answer = self.runner.stdout.readline().strip()
        if answer != b'ok':
            raise RuntimeError(f'{text}: {answer[:40]!r}')

    def step(self, frames=1, buttons=''):
        """Run frames with pad 1 holding buttons, such as 'UP+RIGHT' or 'B'. Reads RAM after."""
        self._send(f'step {frames} {buttons or "-"}')
        ram = self.runner.stdout.read(0x10000)
        if len(ram) != 0x10000:
            raise RuntimeError('the runner has gone')
        self.ram = ram
        self.frame += frames
        return self

    def poke(self, address, value):
        """Set a byte of RAM, address as FFxxxx or just xxxx."""
        self._answer(f'poke {address & 0xFFFF | 0xFF0000:x} {value & 0xFF:x}')
        self._send('ram')
        self.ram = self.runner.stdout.read(0x10000)

    def keep(self, slot=0):
        self._answer(f'keep {slot}')
        self.kept[slot] = self.frame

    def back(self, slot=0):
        self._answer(f'back {slot}')
        self.frame = self.kept[slot]
        self._send('ram')
        self.ram = self.runner.stdout.read(0x10000)

    def save(self, path):
        self._answer(f'save {os.path.abspath(path)}')

    def load(self, path):
        self._answer(f'load {os.path.abspath(path)}')
        self._send('ram')
        self.ram = self.runner.stdout.read(0x10000)

    def shot(self, path):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._answer(f'shot {os.path.abspath(path)}')

    def close(self):
        if self.runner.poll() is None:
            self._send('quit')
            self.runner.wait(timeout=10)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # --- reading RAM ---

    def byte(self, address):
        return self.ram[address & 0xFFFF]

    def word(self, address):
        return int.from_bytes(self.ram[address & 0xFFFF:][:2], 'big')

    def long(self, address):
        return int.from_bytes(self.ram[address & 0xFFFF:][:4], 'big')

    def var(self, offset):
        """A byte of the game's variables, by its offset from a4 as the disassembly shows it."""
        return self.ram[A4 + offset]

    def bytes(self, address, count):
        return self.ram[address & 0xFFFF:][:count]

    # --- the game ---

    level = property(lambda self: self.var(0xD70))          # 0 to 7
    room = property(lambda self: self.ram[0x1051])
    retries = property(lambda self: self.var(0xD9A))
    things = property(lambda self: [b for b in self.bytes(A4 + 0x7EE, 42) if b != 0xFF])

    def press(self, buttons, hold=6, after=6):
        """A press and a release."""
        self.step(hold, buttons)
        return self.step(after)

    def until(self, test, buttons='', limit=3000, every=1):
        """Step until test(self) is true. Returns the frames it took, or raises."""
        start = self.frame
        while not test(self):
            if self.frame - start >= limit:
                raise TimeoutError(f'still waiting after {limit} frames, at frame {self.frame}')
            self.step(every, buttons)
        return self.frame - start

    def new_game(self):
        """From power-on to the first room, with the opening message waiting."""
        self.step(700)
        self.press('START')
        self.step(94)
        self.step(12, 'RIGHT')
        self.step(12, 'RIGHT+C')            # YES at "New game?"
        self.step(12, 'RIGHT')
        self.step(260)
        return self

    def start_level(self, certificate):
        """Start the level a certificate is for, as the game does between levels.

        The digits go into the certificate's fields and the game is told to load from them,
        so nothing is typed. tools/harness/save_check.py shows that comes to the same thing.
        """
        assert len(certificate) == 13
        self.new_game()
        for place, letter in enumerate(certificate):
            self.poke(A4 + 0xD8C + place, int(letter, 16))
        self.poke(A4 + 0xD8B, 13)
        self.poke(A4 + 0xD88, 1)            # load from the fields
        self.poke(A4 + 0xD73, 1)            # start a level
        want = int(certificate[5], 16)
        self.until(lambda g: g.level == want and not g.var(0xD73), limit=600)
        return self.step(120)

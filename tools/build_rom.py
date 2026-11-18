#!/usr/bin/env python3
"""Build the patched ROM from your own copy of the game.

    tools/build_rom.py           writes build/immortal-patched.md
    tools/build_rom.py --check   also proves every unpacked tile against the game's decoder

Everything the patch needs from the game is read from the ROM when this runs, so
nothing of the game is stored here. What it changes:

  * Object graphics. The game unpacks each object tile from a bit-by-bit compressed
    form every time it's needed. The tiles are unpacked here instead, into a new
    second megabyte, and the routine at 02E3E4 just copies them.
  * The wall torch. A slip in the game's tile search decodes one tile wrongly, which
    takes the top off the flame. The unpacked table holds the right tile.
  * The boot check at 0FFFB0, which halts the game if the first megabyte has changed.

--check builds two test ROMs that boot straight into a small test. One runs the game's
own, unmodified decoder on every tile number and compares the result with this script's
unpacking. The other calls the new routine and checks its output, and that it leaves
every register as it found it. They need the BlastEm fork
(tools/harness/build_blastem_fork.sh).
"""
import bisect
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romcheck

ROOT = romcheck.ROOT
BUILD = os.path.join(ROOT, 'build')
OUTPUT = os.path.join(BUILD, 'immortal-patched.md')
CHECK_ROM = os.path.join(BUILD, 'tile-check.md')
ROUTINE_CHECK_ROM = os.path.join(BUILD, 'routine-check.md')
BLASTEM = os.path.join(BUILD, 'blastem-fork', 'blastem')

ROM_SIZE = 0x200000             # 2 MB, which leaves 200000 free for save RAM later
TILES = 0x100000                # where the unpacked tiles go

# In the original game
INDEX = 0x2DCEC                 # runs of tiles: bits per tile, first tile, bit offset
INDEX_LAST = 0xDD               # the search's highest entry; one more ends the table
PACKED = 0x6EED0                # the packed tile data
TREE = 0x2E6D6                  # the decoder, a tree of bit tests written as code
TREE_DONE = 0x2F4D0             # where each decoded byte branches to
ROUTINE = 0x2E3E4               # the object graphics routine
ROUTINE_RTS = 0x2F4E0           # its final rts
BOOT_CHECK_BRANCH = 0xFFFD0     # the branch taken when the boot check fails
OUTPUT_TILES = 0xFF2000         # where the routine puts its tiles


def word(rom, at):
    return int.from_bytes(rom[at:at + 2], 'big')


def signed(value):
    return value - 0x10000 if value & 0x8000 else value


class Tiles:
    def __init__(self, rom):
        self.rom = rom
        self.runs = []
        for i in range(INDEX_LAST + 2):
            at = INDEX + 8 * i
            self.runs.append((word(rom, at), word(rom, at + 2), int.from_bytes(rom[at + 4:at + 8], 'big')))
        self.firsts = [run[1] for run in self.runs]
        self.count = self.firsts[-1]    # the last entry only marks the end
        sys.setrecursionlimit(5000)
        self.root = self.node(TREE)

    def leaf(self, at):
        assert word(self.rom, at) == 0x12FC and word(self.rom, at + 4) == 0x6000
        assert at + 6 + signed(word(self.rom, at + 6)) == TREE_DONE
        return self.rom[at + 3]

    def node(self, at):
        """Read one tst.b (a0)+ / bne.w pair of the decoder, and what follows it."""
        assert word(self.rom, at) == 0x4A18 and word(self.rom, at + 2) == 0x6600, hex(at)
        one = at + 4 + signed(word(self.rom, at + 4))
        zero = at + 6
        return tuple(self.leaf(p) if word(self.rom, p) == 0x12FC else self.node(p) for p in (zero, one))

    def run_by_game(self, n):
        """The game's search. It accepts a tile equal to the next run's first tile."""
        low, high = 0, INDEX_LAST
        while True:
            middle = (low + high) >> 1
            first = self.firsts[middle]
            if n >= first:
                low = middle + 1
                if n <= self.firsts[middle + 1]:
                    return middle
            else:
                high = middle - 1

    def run_correct(self, n):
        return min(bisect.bisect_right(self.firsts, n) - 1, INDEX_LAST)

    def unpack(self, n, run):
        if n == 0:
            return bytes(32)
        bits, first, offset = self.runs[run]
        if bits == 0x100:
            start = PACKED + (offset >> 3) + (n - first) * 32
            return self.rom[start:start + 32]
        position = offset + (n - first) * bits
        out = bytearray()
        while len(out) < 32:
            node = self.root
            while isinstance(node, tuple):
                node = node[(self.rom[PACKED + (position >> 3)] >> (position & 7)) & 1]
                position += 1
            out.append(node)
        return bytes(out)


class Code:
    """Just enough of an assembler: 68000 words, labels and branches."""

    def __init__(self, origin):
        self.origin, self.data, self.labels, self.fixes = origin, bytearray(), {}, []

    def words(self, *values):
        for value in values:
            self.data += value.to_bytes(2, 'big')

    def label(self, name):
        self.labels[name] = self.origin + len(self.data)

    def short(self, opcode, target):
        self.fixes.append((len(self.data), target, False))
        self.words(opcode)

    def long(self, opcode, target):
        self.words(opcode)
        self.fixes.append((len(self.data), target, True))
        self.words(0)

    def finish(self):
        for at, target, is_long in self.fixes:
            address = self.labels.get(target, target)
            if is_long:
                self.data[at:at + 2] = ((address - self.origin - at) & 0xFFFF).to_bytes(2, 'big')
            else:
                distance = address - self.origin - at - 2
                assert -128 <= distance < 128 and distance
                self.data[at + 1] = distance & 0xFF
        return bytes(self.data)


def object_graphics():
    """Copy each listed tile to the output buffer. Takes and leaves what the original did."""
    c = Code(ROUTINE)
    c.words(0x48E7, 0xC164)                         # movem.l d0-d1/d7/a1-a2/a5,-(sp)
    c.words(0x4BF8, 0x92FA)                         # lea     $92FA.w,a5        list of tiles
    c.words(0x43F9, OUTPUT_TILES >> 16 | 0xFF00, OUTPUT_TILES & 0xFFFF)  # lea $FFFF2000,a1
    c.words(0x3038, 0x92F6)                         # move.w  $92F6.w,d0        next free slot
    c.words(0xEB48)                                 # lsl.w   #5,d0
    c.words(0xD2C0)                                 # adda.w  d0,a1
    c.words(0x3E38, 0x931A)                         # move.w  $931A.w,d7        how many
    c.words(0x5347)                                 # subq.w  #1,d7
    c.words(0x223C, TILES >> 16, TILES & 0xFFFF)    # move.l  #TILES,d1
    c.label('loop')
    c.words(0x7000)                                 # moveq   #0,d0
    c.words(0x301D)                                 # move.w  (a5)+,d0
    c.words(0xE058)                                 # ror.w   #8,d0
    c.short(0x6700, 'blank')                        # beq.s   blank
    c.words(0xEB88)                                 # lsl.l   #5,d0
    c.words(0xD081)                                 # add.l   d1,d0
    c.words(0x2440)                                 # movea.l d0,a2
    c.words(*[0x22DA] * 8)                          # move.l  (a2)+,(a1)+ eight times
    c.label('next')
    c.words(0x5278, 0x92F6)                         # addq.w  #1,$92F6.w
    c.long(0x51CF, 'loop')                          # dbra    d7,loop
    c.words(0x4CDF, 0x2683)                         # movem.l (sp)+,d0-d1/d7/a1-a2/a5
    c.long(0x6000, ROUTINE_RTS)                     # bra.w   the original rts
    c.label('blank')
    c.words(*[0x22C0] * 8)                          # move.l  d0,(a1)+ eight times
    c.short(0x6000, 'next')                         # bra.s   next
    return c.finish()


def tile_check(count):
    """Run the game's decoder on tiles 1 to count-1, comparing with the table.

    FF0000 counts mismatches, FF0004 holds the last bad tile, FF0008 counts tiles
    checked, and FF000C becomes 600DF00D at the end.
    """
    c = Code(0x1F0000)
    c.words(0x7C01)                                 # moveq   #1,d6
    c.label('tile')
    c.words(0x4278, 0x92F6)                         # clr.w   $92F6.w
    c.words(0x31FC, 1, 0x931A)                      # move.w  #1,$931A.w
    c.words(0x3006, 0xE058, 0x31C0, 0x92FA)         # the tile number, as the game stores it
    c.words(0x4EB9, ROUTINE >> 16, ROUTINE & 0xFFFF)  # jsr the original routine
    c.words(0x7000, 0x3006, 0xEB88)                 # moveq #0,d0 / move.w d6,d0 / lsl.l #5,d0
    c.words(0x0680, TILES >> 16, TILES & 0xFFFF, 0x2040)  # addi.l #TILES,d0 / movea.l d0,a0
    c.words(0x43F9, 0xFFFF, 0x2000, 0x7207)         # lea $FFFF2000,a1 / moveq #7,d1
    c.label('compare')
    c.words(0xB388)                                 # cmpm.l  (a0)+,(a1)+
    c.long(0x56C9, 'compare')                       # dbne    d1,compare
    c.short(0x6700, 'same')                         # beq.s   same
    c.words(0x52B9, 0xFFFF, 0x0000)                 # addq.l  #1,$FFFF0000
    c.words(0x33C6, 0xFFFF, 0x0004)                 # move.w  d6,$FFFF0004
    c.label('same')
    c.words(0x52B9, 0xFFFF, 0x0008)                 # addq.l  #1,$FFFF0008
    c.words(0x5246, 0x0C46, count)                  # addq.w #1,d6 / cmpi.w #count,d6
    c.short(0x6600, 'tile')                         # bne.s   tile
    c.words(0x23FC, 0x600D, 0xF00D, 0xFFFF, 0x000C)  # move.l #$600DF00D,$FFFF000C
    c.words(0x60FE)                                 # bra.s   *
    return c.origin, c.finish()


def finish_rom(rom, path):
    rom = bytearray(rom)
    rom[0x1A4:0x1A8] = (ROM_SIZE - 1).to_bytes(4, 'big')
    total = sum(word(rom, i) for i in range(0x200, len(rom), 2)) & 0xFFFF
    rom[0x18E:0x190] = total.to_bytes(2, 'big')
    with open(path, 'wb') as f:
        f.write(rom)


def with_tiles(rom, table):
    out = bytearray(rom) + table
    return out + b'\xff' * (ROM_SIZE - len(out))


def routine_check(tile_list):
    """Call the new routine with known registers, saving them afterwards at FF0100."""
    pattern_at = 0x1F0100
    pattern = b''.join((0xA1B2C300 + i).to_bytes(4, 'big') for i in range(15))
    c = Code(0x1F0000)
    c.words(0x4278, 0x92F6)                         # clr.w   $92F6.w
    for i, n in enumerate(tile_list):               # the list, as the game stores it
        c.words(0x31FC, (n >> 8 | n << 8) & 0xFFFF, 0x92FA + 2 * i)
    c.words(0x31FC, len(tile_list), 0x931A)         # move.w  #count,$931A.w
    c.words(0x41F9, pattern_at >> 16, pattern_at & 0xFFFF)  # lea pattern,a0
    c.words(0x4CD0, 0x7FFF)                         # movem.l (a0),d0-d7/a0-a6
    c.words(0x4EB9, ROUTINE >> 16, ROUTINE & 0xFFFF)  # jsr the new routine
    c.words(0x48F9, 0x7FFF, 0xFFFF, 0x0100)         # movem.l d0-d7/a0-a6,$FFFF0100
    c.words(0x23FC, 0x600D, 0xF00D, 0xFFFF, 0x000C)  # move.l #$600DF00D,$FFFF000C
    c.words(0x60FE)                                 # bra.s   *
    return c.origin, c.finish(), pattern_at, pattern


def peek(path, addresses, frames=3000):
    """Run a test ROM in the BlastEm fork and read bytes of RAM near the end."""
    if not os.path.exists(BLASTEM):
        sys.exit('--check needs the fork: tools/harness/build_blastem_fork.sh')
    script, init = path + '.script', path + '.init'
    with open(script, 'w') as f:
        f.writelines(f'{frames - 100} peek {a:x}\n' for a in addresses)
    with open(init, 'w') as f:
        f.write(f'script {script}\n')
    home = os.path.join(BUILD, 'blastem-home')
    os.makedirs(home, exist_ok=True)
    out = subprocess.run([BLASTEM, '-b', str(frames), path], capture_output=True, text=True, errors='replace',
                         timeout=120, env={**os.environ, 'HOME': home, 'SDL_VIDEODRIVER': 'dummy',
                                           'SDL_AUDIODRIVER': 'dummy', 'BLASTEM_NO_GUI': '1',
                                           'BLASTEM_KIT_INIT': init}).stdout
    values = [line.split()[-1] for line in out.splitlines() if ' peek ' in line]
    if len(values) != len(addresses):
        sys.exit(f'{os.path.basename(path)} gave no result')
    return bytes.fromhex(''.join(values))


def boot_into(rom, origin, code, path):
    test = bytearray(rom)
    test[origin:origin + len(code)] = code
    test[4:8] = origin.to_bytes(4, 'big')
    finish_rom(test, path)


def check_decoder(rom, count, table):
    origin, code = tile_check(count)
    boot_into(with_tiles(rom, table), origin, code, CHECK_ROM)
    got = peek(CHECK_ROM, [0xFF0000 + i for i in (0, 1, 2, 3, 8, 9, 10, 11, 12, 13, 14, 15)])
    bad, checked, done = (int.from_bytes(got[a:a + 4], 'big') for a in (0, 4, 8))
    print(f'game decoder against this script: {checked} tiles checked, {bad} different')
    if bad or checked != count - 1 or done != 0x600DF00D:
        sys.exit('tile check FAILED')


def check_routine(patched, table):
    tile_list = [0x1234, 0, 25793, 1]
    origin, code, pattern_at, pattern = routine_check(tile_list)
    test = bytearray(patched)
    test[pattern_at:pattern_at + len(pattern)] = pattern
    boot_into(test, origin, code, ROUTINE_CHECK_ROM)
    size = 32 * len(tile_list)
    addresses = [*range(0xFF0100, 0xFF0100 + 60), *range(OUTPUT_TILES, OUTPUT_TILES + size), 0xFF92F6, 0xFF92F7,
                 *range(0xFF000C, 0xFF0010)]
    got = peek(ROUTINE_CHECK_ROM, addresses, 200)
    registers, tiles, slot, done = got[:60], got[60:60 + size], got[60 + size:62 + size], got[62 + size:]
    wanted = b''.join(table[n * 32:n * 32 + 32] for n in tile_list)
    results = {'registers kept': registers == pattern, 'tiles right': tiles == wanted,
               'slot count right': int.from_bytes(slot, 'big') == len(tile_list),
               'finished': done == bytes.fromhex('600DF00D')}
    print('new routine:', ', '.join(f'{k}: {"yes" if v else "NO"}' for k, v in results.items()))
    if not all(results.values()):
        sys.exit('routine check FAILED')


def main():
    rom = open(romcheck.find_rom(), 'rb').read()
    tiles = Tiles(rom)
    count = tiles.count + 1             # the game's search also accepts the end marker
    as_game = [tiles.unpack(n, tiles.run_by_game(n)) for n in range(count)]
    table = list(as_game)
    fixed = []
    for n in range(tiles.count):
        right = tiles.unpack(n, tiles.run_correct(n))
        if right != as_game[n]:
            table[n] = right
            fixed.append(n)
    check = '--check' in sys.argv[1:]
    if check:
        check_decoder(rom, count, b''.join(as_game))
    out = with_tiles(rom, b''.join(table))
    code = object_graphics()
    out[ROUTINE:ROUTINE + len(code)] = code
    out[BOOT_CHECK_BRANCH:BOOT_CHECK_BRANCH + 2] = b'\x4e\x71'      # nop
    os.makedirs(BUILD, exist_ok=True)
    finish_rom(out, OUTPUT)
    if check:
        check_routine(out, b''.join(table))
    print(f'{count} tiles unpacked, {len(fixed)} corrected {fixed}; new routine is {len(code)} bytes')
    print(f'wrote {os.path.relpath(OUTPUT, ROOT)}')


if __name__ == '__main__':
    main()

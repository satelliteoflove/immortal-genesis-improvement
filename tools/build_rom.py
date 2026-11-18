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
  * Background tiles. Each time the camera crosses an 8-pixel step, the game sent every
    tile on screen to video memory again. Now only tiles new to the screen are sent, and
    the scan of the 2,048-entry tile table is much cheaper.
  * The boot check at 0FFFB0, which halts the game if the first megabyte has changed.

--check builds test ROMs that boot straight into a small test. One runs the game's own,
unmodified decoder on every tile number and compares the result with this script's
unpacking. One calls the new object routine and checks its output, and that it leaves
every register as it found it. One feeds random screens to the background routines, old
and new, and requires the same RAM and the same video memory from both. They need the
BlastEm fork (tools/harness/build_blastem_fork.sh).
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
BACKGROUND_CHECK_ROM = os.path.join(BUILD, 'background-check.md')
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
TABLE_RESET = 0x13AE2           # empties the background tile table
MAP_TILES = 0x13B16             # gives each cell on screen a slot in video memory
MAP_TILES_SIZE = 0x62
TILE_SYNC = 0x13B78             # frees unused slots and sends tiles to video memory
BACKGROUND_TILES = 0x3D9B2      # the background tile graphics
TILE_TABLE = 0xFFFF7612         # one word per background tile: its slot, plus two flags
TILE_SYNC_NEW = 0x2E480         # the new TILE_SYNC, in space the old object code left free


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


def map_tiles():
    """As the original, except that only a newly allocated tile is marked to be sent."""
    c = Code(MAP_TILES)
    c.words(0x48E7, 0xFFF0)                         # movem.l d0-d7/a0-a3,-(sp)
    c.words(0x363C, 0x3FFF, 0x3C3C, 0x07FF)         # move.w #$3FFF,d3 / move.w #$7FF,d6
    c.words(0x41F9, 0xFFFF, 0x6C82)                 # lea     $FFFF6C82,a0      cells wanted
    c.words(0x43F9, 0xFFFF, 0x7612)                 # lea     TILE_TABLE,a1
    c.words(0x2478, 0x8ADA)                         # movea.l $8ADA.w,a2        free slots
    c.words(0x47F9, 0xFFFF, 0x714A)                 # lea     $FFFF714A,a3      cells out
    c.words(0x303C, 0x0263)                         # move.w  #611,d0
    c.label('cell')
    c.words(0x3218, 0x3401, 0xC246, 0xD241)         # move.w (a0)+,d1 / d1,d2 / and d6,d1 / add d1,d1
    c.words(0x3831, 0x1000)                         # move.w  (a1,d1.w),d4
    c.short(0x6B00, 'marked')                       # bmi.s   marked            seen this pass
    c.words(0xB644)                                 # cmp.w   d4,d3
    c.short(0x6600, 'has_slot')                     # bne.s   has_slot
    c.words(0x3822, 0x0044, 0x4000)                 # move.w -(a2),d4 / ori.w #$4000,d4
    c.label('has_slot')
    c.words(0x0044, 0x8000, 0x3384, 0x1000)         # ori.w #$8000,d4 / move.w d4,(a1,d1.w)
    c.label('marked')
    c.words(0xC843, 0x0242, 0xF800, 0x8444, 0x36C2)  # slot, plus the cell's flip bits, out
    c.long(0x51C8, 'cell')                          # dbra    d0,cell
    c.words(0x21CA, 0x8ADA, 0x4CDF, 0x0FFF, 0x4E75)  # save a2, restore, rts
    code = c.finish()
    assert len(code) <= MAP_TILES_SIZE
    return code


def tile_sync():
    """Walk the table in the original's order, sending only tiles marked as new."""
    c = Code(TILE_SYNC_NEW)
    c.words(0x48E7, 0xE0F8, 0x40E7, 0x007C, 0x0700)  # movem.l d0-d2/a0-a4,-(sp), mask interrupts
    c.words(0x323C, 0x3FFF, 0x2878, 0x8ADA)         # move.w #$3FFF,d1 / movea.l $8ADA.w,a4
    c.words(0x41F9, TILE_TABLE >> 16, TILE_TABLE & 0xFFFF)  # lea TILE_TABLE,a0
    c.words(0x247C, 0x00C0, 0x0004)                 # movea.l #$C00004,a2
    c.words(0x267C, 0x00C0, 0x0000)                 # movea.l #$C00000,a3
    c.words(0x303C, 0x07FF)                         # move.w  #2047,d0
    c.label('scan')
    c.words(0x3418, 0xB441)                         # move.w (a0)+,d2 / cmp.w d1,d2
    c.long(0x56C8, 'scan')                          # dbne    d0,scan           skip empty entries
    c.short(0x6700, 'done')                         # beq.s   done
    c.words(0x4A42)                                 # tst.w   d2
    c.short(0x6B00, 'used')                         # bmi.s   used
    c.words(0xC441, 0x38C2, 0x3141, 0xFFFE)         # not used: push its slot, mark it empty
    c.short(0x6000, 'next')                         # bra.s   next
    c.label('used')
    c.words(0xC368, 0xFFFE, 0x0802, 0x000E)         # and.w d1,-2(a0) / btst #14,d2
    c.short(0x6700, 'next')                         # beq.s   next              already there
    c.words(0x0282, 0, 0x3FFF, 0xEF8A, 0xE44A, 0x4842)  # the slot, as a video memory address
    c.words(0x0082, 0x4000, 0, 0x2482)              # ori.l #$40000000,d2 / move.l d2,(a2)
    c.words(0x2408, 0x0482, TILE_TABLE >> 16, (TILE_TABLE + 2) & 0xFFFF, 0xE98A)  # entry number * 32
    c.words(0x0682, BACKGROUND_TILES >> 16, BACKGROUND_TILES & 0xFFFF, 0x2242)  # its graphics, in a1
    c.words(*[0x2699] * 8)                          # move.l  (a1)+,(a3) eight times
    c.label('next')
    c.long(0x51C8, 'scan')                          # dbra    d0,scan
    c.label('done')
    c.words(0x21CC, 0x8ADA, 0x46DF, 0x4CDF, 0x1F07, 0x4E75)  # save a4, restore all, rts
    return c.finish()


def background_check():
    """Run the two background routines on 24 passes of random screens.

    FF0100 receives the registers after the last pass, FF0200 a checksum of the tables, the
    free list and video memory after every pass, and FF000C becomes 600DF00D at the end.
    """
    pattern_at = 0x1F0200
    pattern = b''.join((0xA1B2C300 + i).to_bytes(4, 'big') for i in range(15))
    c = Code(0x1F0000)
    for register in (0x8004, 0x8134, 0x8C81, 0x8F02, 0x9001):     # Genesis mode, display off
        c.words(0x33FC, register, 0x00C0, 0x0004)
    c.words(0x23FC, 0x4000, 0, 0x00C0, 0x0004, 0x303C, 0x263F)  # clear the video memory we read
    c.label('clear')
    c.words(0x33FC, 0, 0x00C0, 0)                   # move.w #0,data port
    c.long(0x51C8, 'clear')
    c.words(0x4EB9, TABLE_RESET >> 16, TABLE_RESET & 0xFFFF)
    c.words(0x2A3C, 0x1234, 0x5679, 0x7C00, 0x7E00)  # d5 random, d6 pass, d7 checksum
    c.label('pass')
    c.words(0x41F9, 0xFFFF, 0x6C82, 0x303C, 0x0263)  # lea cells,a0 / move.w #611,d0
    c.label('cell')
    c.words(0x2205, 0x740D, 0xE5A9, 0xB385)         # xorshift d5
    c.words(0x2205, 0x7411, 0xE4A9, 0xB385)
    c.words(0x2205, 0xEB89, 0xB385)
    c.words(0x4A46)                                 # tst.w   d6
    c.short(0x6700, 'take')                         # the first pass fills every cell
    c.words(0x3205, 0x0241, 0x0007)                 # later ones change about one in eight
    c.short(0x6600, 'keep')
    c.label('take')
    c.words(0x2205, 0x4841, 0x3081)                 # move.l d5,d1 / swap d1 / move.w d1,(a0)
    c.label('keep')
    c.words(0x5488)                                 # addq.l  #2,a0
    c.long(0x51C8, 'cell')
    c.words(0x48F9, 0x00E0, 0xFFFF, 0x0300)         # keep d5-d7
    c.words(0x41F9, pattern_at >> 16, pattern_at & 0xFFFF, 0x4CD0, 0x7FFF)  # known registers
    c.words(0x4EB9, MAP_TILES >> 16, MAP_TILES & 0xFFFF)
    c.words(0x4EB9, TILE_SYNC >> 16, TILE_SYNC & 0xFFFF)
    c.words(0x48F9, 0x7FFF, 0xFFFF, 0x0100)         # save them
    c.words(0x4CF9, 0x00E0, 0xFFFF, 0x0300)         # d5-d7 back
    for area, count in ((0x714A, 0x264), (0x7612, 0x800), (0x8612, 0x264)):
        name = f'sum{area:x}'
        c.words(0x41F8, area, 0x303C, count - 1)    # lea area.w,a0 / move.w #count-1,d0
        c.label(name)
        c.words(0xE39F, 0xDE58)                     # rol.l #1,d7 / add.w (a0)+,d7
        c.long(0x51C8, name)
    c.words(0xDEB8, 0x8ADA)                         # add.l   $8ADA.w,d7
    c.label('settle')                               # let queued writes reach video memory
    c.words(0x3039, 0x00C0, 0x0004, 0x0240, 0x0200)  # move.w status,d0 / andi.w #$200,d0
    c.short(0x6700, 'settle')                       # beq.s   settle
    c.words(0x23FC, 0, 0, 0x00C0, 0x0004, 0x303C, 0x263F)  # read video memory from 0
    c.label('vram')
    c.words(0xE39F, 0xDE79, 0x00C0, 0x0000)         # rol.l #1,d7 / add.w data port,d7
    c.long(0x51C8, 'vram')
    c.words(0x5246, 0x0C46, 24)                     # addq.w #1,d6 / cmpi.w #24,d6
    c.long(0x6600, 'pass')
    c.words(0x23C7, 0xFFFF, 0x0200)                 # move.l  d7,$FFFF0200
    c.words(0x23FC, 0x600D, 0xF00D, 0xFFFF, 0x000C, 0x60FE)
    return c.origin, c.finish(), pattern_at, pattern


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


def check_background(rom, patched):
    origin, code, pattern_at, pattern = background_check()
    addresses = [*range(0xFF0100, 0xFF0100 + 60), *range(0xFF0200, 0xFF0204), *range(0xFF000C, 0xFF0010)]
    results = []
    for source, label in ((with_tiles(rom, b''), 'original'), (patched, 'patched')):
        test = bytearray(source)
        test[pattern_at:pattern_at + len(pattern)] = pattern
        boot_into(test, origin, code, BACKGROUND_CHECK_ROM)
        got = peek(BACKGROUND_CHECK_ROM, addresses, 3000)
        if got[64:] != bytes.fromhex('600DF00D'):
            sys.exit(f'background check did not finish on the {label} routines')
        results.append(got)
    same = results[0][60:64] == results[1][60:64]
    kept = results[1][:60] == pattern
    print(f'background routines, old against new: same RAM and video memory: {"yes" if same else "NO"}, '
          f'registers kept: {"yes" if kept else "NO"}')
    if not (same and kept and results[0][:60] == pattern):
        sys.exit('background check FAILED')


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
    code = map_tiles()
    out[MAP_TILES:MAP_TILES + len(code)] = code
    code = tile_sync()
    out[TILE_SYNC_NEW:TILE_SYNC_NEW + len(code)] = code
    out[TILE_SYNC:TILE_SYNC + 6] = b'\x4e\xf9' + TILE_SYNC_NEW.to_bytes(4, 'big')  # jmp
    out[BOOT_CHECK_BRANCH:BOOT_CHECK_BRANCH + 2] = b'\x4e\x71'      # nop
    os.makedirs(BUILD, exist_ok=True)
    finish_rom(out, OUTPUT)
    if check:
        check_routine(out, b''.join(table))
        check_background(rom, out)
    print(f'{count} tiles unpacked, {len(fixed)} corrected {fixed}')
    print(f'wrote {os.path.relpath(OUTPUT, ROOT)}')


if __name__ == '__main__':
    main()

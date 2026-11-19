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
    the scan of the 2,048-entry tile table skips the parts that are empty.
  * Screen cells. The routine that works out what's on screen after a camera step is
    rewritten to do the same thing with far less work per row.
  * The sound link. Its two 48-byte copies through Z80 memory, made every frame, are
    written out in full in place of loops.
  * Sprite masking. Hiding the parts of a sprite behind scenery shifted eight mask rows
    a bit at a time for every tile. The shifted masks are now worked out here, and tiles
    with nothing in front of them are skipped early.
  * Mask edges. The game's shift put half of each mask one bit out of line, leaving stray
    miscoloured pixels where a sprite passes behind scenery. The tables line it up.
  * The boot check at 0FFFB0, which halts the game if the first megabyte has changed.

--check builds test ROMs that boot straight into a small test. One runs the game's own,
unmodified decoder on every tile number and compares the result with this script's
unpacking. One calls the new object routine and checks its output, and that it leaves
every register as it found it. One feeds random screens to the background routines, old
and new, and requires the same RAM and the same video memory from both. One does the same
for sprite masking, with random sprites and scenery, one for the screen cells, with
random maps, and one for the sound link, playing six songs. They need the BlastEm fork
(tools/harness/build_blastem_fork.sh).
"""
import bisect
import os
import random
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
MASK_CHECK_ROM = os.path.join(BUILD, 'mask-check.md')
CELL_CHECK_ROM = os.path.join(BUILD, 'cell-check.md')
SOUND_CHECK_ROM = os.path.join(BUILD, 'sound-check.md')
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
MAP_TILES_NEW = 0x2E540         # the new MAP_TILES, also in that space
TABLE_RESET_TAIL = 0x13B10      # TABLE_RESET's last two instructions
TABLE_RESET_NEW = 0x2E5C0       # their replacement
TILE_COUNTS = 0x9660            # 64 bytes: how many of each 32 table entries are in use
TILE_SYNC = 0x13B78             # frees unused slots and sends tiles to video memory
BACKGROUND_TILES = 0x3D9B2      # the background tile graphics
TILE_TABLE = 0xFFFF7612         # one word per background tile: its slot, plus two flags
TILE_SYNC_NEW = 0x2E480         # the new TILE_SYNC, in space the old object code left free
CELLS = 0x13D34                 # works out the 612 cells on screen from the level's block maps
CELLS_END = 0x13F5E
CELL_DATA = 0x13C80             # five 8 by 4 blocks of mask shapes, then a table choosing between them
CELL_DATA_COPY = 0x1EA000       # those bytes as they were, for the new routine to read
CELL_DATA_SIZE = 0x1C0
BLOCKS = 0x3ABF2                # 64 bytes of cells for each kind of block
CELL_PASSES = 300               # for --check: passes of random maps and cameras
CELL_RECORDS = 0x100000
CELL_MAPS = 0x110000
CELL_MAP_SETS = 8
SOUND_LINK = 0x1624E            # once a frame: fetches 48 bytes from the Z80, runs the music, sends them back
SOUND_LINK_END = 0x16304
SOUND_LINK_NEW = 0x2E600
SOUND_PASSES = 1792             # for --check: 256 frames of each of six songs, then 256 of silence
SOUND_RECORDS = 0x100000
MASK = 0x1428C                  # hides the parts of sprites that are behind scenery
MASK_END = 0x14508              # the first byte after its rts
MASK_SHAPES = 0x141CC           # 16 shapes of 32 bytes; only the first 6 are data
MASK_TABLES = 0x1E8000          # the shapes shifted ahead of time: left parts, right parts at +$1000
MASK_PASSES = 400               # for --check: passes of random sprites and scenery
MASK_RECORDS = 0x100000         # and where a test ROM keeps them
MASK_EXTRA = 0x180000
MASK_TILES = 0x190000


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
    """As the original, except that only a newly allocated tile is marked to be sent.

    It also counts the allocation in TILE_COUNTS, so that tile_sync can skip the parts of
    the table that are empty.
    """
    c = Code(MAP_TILES_NEW)
    c.words(0x48E7, 0xFFF4)                         # movem.l d0-d7/a0-a3/a5,-(sp)
    c.words(0x363C, 0x3FFF, 0x3C3C, 0x07FF)         # move.w #$3FFF,d3 / move.w #$7FF,d6
    c.words(0x41F9, 0xFFFF, 0x6C82)                 # lea     $FFFF6C82,a0      cells wanted
    c.words(0x43F9, 0xFFFF, 0x7612)                 # lea     TILE_TABLE,a1
    c.words(0x2478, 0x8ADA)                         # movea.l $8ADA.w,a2        free slots
    c.words(0x47F9, 0xFFFF, 0x714A)                 # lea     $FFFF714A,a3      cells out
    c.words(0x4BF8, TILE_COUNTS)                    # lea     TILE_COUNTS.w,a5
    c.words(0x3E3C, 0xF800)                         # move.w  #$F800,d7         a cell's flip bits
    c.words(0x3A3C, 0x8000)                         # move.w  #$8000,d5         seen this pass
    c.words(0x303C, 0x0263)                         # move.w  #611,d0
    c.label('cell')
    c.words(0x3218, 0x3401, 0xC246, 0xD241)         # move.w (a0)+,d1 / d1,d2 / and d6,d1 / add d1,d1
    c.words(0x3831, 0x1000)                         # move.w  (a1,d1.w),d4
    c.short(0x6B00, 'marked')                       # bmi.s   marked            seen this pass
    c.words(0xB644)                                 # cmp.w   d4,d3
    c.short(0x6600, 'has_slot')                     # bne.s   has_slot
    c.words(0x3801, 0xEC4C, 0x5235, 0x4000)         # one more in use in this entry's group of 32
    c.words(0x3822, 0x0044, 0x4000)                 # move.w -(a2),d4 / ori.w #$4000,d4
    c.label('has_slot')
    c.words(0x8845, 0x3384, 0x1000)                 # or.w d5,d4 / move.w d4,(a1,d1.w)
    c.label('marked')
    c.words(0xC843, 0xC447, 0x8444, 0x36C2)         # slot, plus the cell's flip bits, out
    c.long(0x51C8, 'cell')                          # dbra    d0,cell
    c.words(0x21CA, 0x8ADA, 0x4CDF, 0x2FFF, 0x4E75)  # save a2, restore, rts
    return c.finish()


def tile_sync():
    """Walk the table in the original's order, sending only tiles marked as new.

    The table is taken 32 entries at a time, and a group with nothing in use is skipped.
    """
    c = Code(TILE_SYNC_NEW)
    c.words(0x48E7, 0xF0FC, 0x40E7, 0x007C, 0x0700)  # movem.l d0-d3/a0-a5,-(sp), mask interrupts
    c.words(0x323C, 0x3FFF, 0x2878, 0x8ADA)         # move.w #$3FFF,d1 / movea.l $8ADA.w,a4
    c.words(0x41F9, TILE_TABLE >> 16, TILE_TABLE & 0xFFFF)  # lea TILE_TABLE,a0
    c.words(0x247C, 0x00C0, 0x0004)                 # movea.l #$C00004,a2
    c.words(0x267C, 0x00C0, 0x0000)                 # movea.l #$C00000,a3
    c.words(0x4BF8, TILE_COUNTS, 0x763F)            # lea TILE_COUNTS.w,a5 / moveq #63,d3
    c.label('group')
    c.words(0x4A1D)                                 # tst.b   (a5)+
    c.short(0x6600, 'in_use')                       # bne.s   in_use
    c.words(0x41E8, 0x0040)                         # lea     64(a0),a0         nothing here
    c.long(0x51CB, 'group')                         # dbra    d3,group
    c.short(0x6000, 'done')
    c.label('in_use')
    c.words(0x701F)                                 # moveq   #31,d0
    c.label('scan')
    c.words(0x3418, 0xB441)                         # move.w (a0)+,d2 / cmp.w d1,d2
    c.long(0x56C8, 'scan')                          # dbne    d0,scan           skip empty entries
    c.short(0x6700, 'group_done')                   # beq.s   group_done
    c.words(0x4A42)                                 # tst.w   d2
    c.short(0x6B00, 'used')                         # bmi.s   used
    c.words(0xC441, 0x38C2, 0x3141, 0xFFFE)         # not used: push its slot, mark it empty
    c.words(0x532D, 0xFFFF)                         # subq.b  #1,-1(a5)         one fewer in this group
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
    c.label('group_done')
    c.long(0x51CB, 'group')                         # dbra    d3,group
    c.label('done')
    c.words(0x21CC, 0x8ADA, 0x46DF, 0x4CDF, 0x3F0F, 0x4E75)  # save a4, restore all, rts
    code = c.finish()
    assert TILE_SYNC_NEW + len(code) <= MAP_TILES_NEW
    return code


def table_reset_tail():
    """The end of TABLE_RESET, which now also zeroes TILE_COUNTS."""
    c = Code(TABLE_RESET_NEW)
    c.words(0x41F8, TILE_COUNTS, 0x720F)            # lea TILE_COUNTS.w,a0 / moveq #15,d1
    c.label('clear')
    c.words(0x4298)                                 # clr.l   (a0)+
    c.long(0x51C9, 'clear')                         # dbra    d1,clear
    c.words(0x4CDF, 0x0103, 0x4E75)                 # movem.l (sp)+,d0-d1/a0 / rts, as before
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


def cells(origin=CELLS):
    """Work out the screen's cells and mask shapes from the level's block maps. Same results."""
    c = Code(origin)
    w, s, l = c.words, c.short, c.long
    table = CELL_DATA_COPY + 0xA0
    w(0x48E7, 0xFFFE)                               # movem.l d0-d7/a0-a6,-(sp)
    w(0x2C6C, 0x1164, 0x246C, 0x1168, 0x266C, 0x1170)  # a6, a2, a3 = the level's three block maps
    w(0x21CB, 0x8D4E)                               # move.l  a3,$8D4E.w
    w(0x1E38, 0x8D44, 0xE90F, 0x8E38, 0x8D42, 0x11C7, 0x8D52)  # $8D52 = the room the wizard is in
    w(0xE641, 0xE642, 0x31C1, 0x8D46, 0x31C2, 0x8D48)  # $8D46, $8D48 = the camera, in cells
    w(0x7400)                                       # moveq   #0,d2             row on screen
    c.label('band')
    w(0x7200)                                       # moveq   #0,d1             column on screen
    c.label('block')
    w(0x3601, 0xD678, 0x8D46, 0x3A03, 0xE643)       # d3 = block column, d5 = column in the level
    w(0x3802, 0xD878, 0x8D48, 0x3C04, 0xE444)       # d4 = block row, d6 = row in the level
    w(0x0245, 0x0007, 0x0246, 0x0003)               # d5, d6 = column and row within the block
    w(0x7E00, 0x7000)                               # moveq #0,d7 / moveq #0,d0
    w(0x0C43, 0x0014); l(0x6400, 'have')            # off the map: an empty block
    w(0x0C44, 0x0080); l(0x6400, 'have')
    w(0x3004, 0xE548, 0x3E00, 0xD044, 0xE548, 0xD043)  # d0 = block row * 20 + block column
    w(0x1E32, 0x0000)                               # move.b  (a2,d0.w),d7      which block
    # d7 still holds block row * 4 above its low byte, as in the game, where it only
    # matters from block row 64 down: there it sends the cells astray.
    w(0x1633, 0x0000)                               # move.b  (a3,d0.w),d3      which room it belongs to
    w(0x0C03, 0x00FF); s(0x6700, 'keep')            # $FF: every room
    w(0x4A03); s(0x6A00, 'plain')
    w(0x1833, 0x0014, 0x0203, 0x007F)               # a doorway: d4 = the room below it
    w(0xB638, 0x8D52); s(0x6700, 'door')
    w(0xB838, 0x8D52); s(0x6600, 'blank')
    c.label('door')                                 # d3 = its block seen from below, and from above
    for block, pair in ((0x1D, 0x0506), (0x27, 0x0504), (0x25, 0x0708), (0x4A, 0x0702), (0x2F, 0x0501)):
        w(0x363C, pair, 0x0C07, block); s(0x6700, 'pick')
    w(0x363C, 0x0703)
    c.label('pick')
    w(0xB838, 0x8D52); s(0x6600, 'other')
    w(0xE04B)                                       # lsr.w   #8,d3
    c.label('other')
    w(0x7E00, 0x1E03); s(0x6000, 'keep')            # moveq #0,d7 / move.b d3,d7
    c.label('plain')
    w(0x0C03, 0x0062); s(0x6600, 'plain2')
    w(0x0C38, 0x004A, 0x8D52); s(0x6700, 'keep')
    c.label('plain2')
    w(0xB638, 0x8D52); s(0x6700, 'keep')
    c.label('blank')
    w(0x7E00)                                       # another room's: an empty block
    c.label('keep')
    w(0x1036, 0x0000, 0x0240, 0x00FF)               # d0 = its mask kind, from the third map
    w(0xED8F)                                       # lsl.l   #6,d7
    c.label('have')
    w(0x4A47); s(0x6600, 'kind')
    w(0x7002)                                       # an empty block has mask kind 2
    c.label('kind')
    w(0x41F9, table >> 16, table & 0xFFFF, 0x1030, 0x0000)  # move.b (table,d0.w),d0
    w(0x43F9, CELL_DATA_COPY >> 16, CELL_DATA_COPY & 0xFFFF, 0xD2C0)  # a1 = its block of mask shapes
    w(0x41F9, BLOCKS >> 16, BLOCKS & 0xFFFF, 0xD1C7)  # a0 = its block of cells
    w(0x3006, 0xE748, 0xD045)                       # d0 = row in block * 8 + column in block
    w(0xD2C0, 0xD0C0, 0xD0C0)                       # start there in both
    w(0x3002, 0xEB48, 0xD042, 0xD042, 0xD041)       # d0 = row * 34 + column
    w(0x49F8, 0x8ADE, 0xD8C0)                       # a4 = where its mask shapes go
    w(0x4BF9, 0xFFFF, 0x6C82, 0xDAC0, 0xDAC0)       # a5 = where its cells go
    w(0x4445, 0x5045, 0x7022, 0x9041, 0xBA40); s(0x6F00, 'wide')
    w(0x3A00)                                       # d5 = columns to copy: to the block's or the screen's edge
    c.label('wide')
    w(0x4446, 0x5846, 0x7012, 0x9042, 0xBC40); s(0x6F00, 'tall')
    w(0x3C00)                                       # d6 = rows to copy, likewise
    c.label('tall')
    w(0x5346)                                       # subq.w  #1,d6
    w(0x7608, 0x9645, 0x7822, 0x9845)               # d3 = 8 - columns, d4 = 34 - columns
    w(0x3003, 0xE548)                               # d0 = how far into the copies below to start
    c.label('row')
    w(0x4EFB, 0x0002)                               # jmp     2(pc,d0.w)
    w(*[0x3AD8, 0x18D9] * 8)                        # move.w (a0)+,(a5)+ / move.b (a1)+,(a4)+
    w(0xD2C3, 0xD0C3, 0xD0C3, 0xD8C4, 0xDAC4, 0xDAC4)  # on to the next row in all four
    l(0x51CE, 'row')
    w(0xD245, 0x0C41, 0x0022); l(0x6D00, 'block')   # next block across
    w(0x3002, 0xD078, 0x8D48, 0x0240, 0x0003, 0x5842, 0x9440)  # next band of blocks down
    w(0x0C42, 0x0012); l(0x6D00, 'band')
    w(0x4CDF, 0x7FFF, 0x4E75)
    code = c.finish()
    assert origin != CELLS or len(code) <= CELLS_END - CELLS, len(code)
    return code

def cell_test_data():
    """Random block maps, rooms and camera positions, on and off the map."""
    rnd = random.Random(1334)
    rooms = [rnd.randint(0, 0x7F) for _ in range(6)] + [0x4A, 0x62, 0x64]
    special = [0x1D, 0x27, 0x25, 0x4A, 0x2F]
    maps = bytearray()
    for _ in range(CELL_MAP_SETS):
        kinds = bytes(rnd.randint(0, 19) if rnd.random() < .97 else rnd.randint(20, 255) for _ in range(3072))
        blocks = bytes(rnd.choice(special) if rnd.random() < .2 else rnd.randint(0, 182) if rnd.random() < .97
                       else rnd.randint(183, 255) for _ in range(3072))
        owner = bytearray()
        for _ in range(3072):
            r = rnd.random()
            owner.append(0xFF if r < .15 else rnd.choice(rooms) | (0x80 if r < .45 else 0) if r < .95 else rnd.randint(0, 255))
        maps += kinds + blocks + owner
    records = bytearray()
    for _ in range(CELL_PASSES):
        x = rnd.randint(-300, 1500) if rnd.random() < .8 else rnd.randint(-32768, 32767)
        y = rnd.randint(-200, 4300) if rnd.random() < .8 else rnd.randint(-32768, 32767)
        room = rnd.choice(rooms)
        at = CELL_MAPS + rnd.randrange(CELL_MAP_SETS) * 9216
        records += (x & 0xFFFF).to_bytes(2, 'big') + (y & 0xFFFF).to_bytes(2, 'big') + bytes([room >> 4, room & 15])
        records += at.to_bytes(4, 'big') + (at + 3072).to_bytes(4, 'big') + (at + 6144).to_bytes(4, 'big')
    return bytes(records), bytes(maps)

def cell_test(pattern_at):
    """Run the cell routine on every record, adding its output and registers to a checksum."""
    c = Code(0x1F0000)
    w, l = c.words, c.long
    w(0x41F9, 0xFFFF, 0x0000, 0x303C, 0x3EFF)
    c.label('clear'); w(0x4298); l(0x51C8, 'clear')
    w(0x23FC, CELL_RECORDS >> 16, CELL_RECORDS & 0xFFFF, 0xFFFF, 0x0208)
    c.label('pass')
    w(0x2079, 0xFFFF, 0x0208)
    w(0x33D8, 0xFFFF, 0x0210, 0x33D8, 0xFFFF, 0x0212)   # camera x, y
    w(0x11D8, 0x8D44, 0x11D8, 0x8D42)                   # the room, in two halves
    w(0x23D8, 0xFFFF, 0x1464, 0x23D8, 0xFFFF, 0x1468, 0x23D8, 0xFFFF, 0x1470)  # the three maps
    w(0x23C8, 0xFFFF, 0x0208)
    w(0x41F9, pattern_at >> 16, pattern_at & 0xFFFF, 0x4CD0, 0x7FFF)
    w(0x3239, 0xFFFF, 0x0210, 0x3439, 0xFFFF, 0x0212)
    w(0x4EB9, CELLS >> 16, CELLS & 0xFFFF)
    w(0x48F9, 0x7FFF, 0xFFFF, 0x0100)
    w(0x2E39, 0xFFFF, 0x0200)
    for area, longs in ((0xFFFF0100, 15), (0xFFFF6C82, 306), (0xFFFF8ADE, 153), (0xFFFF8D4E, 1)):
        name = f'sum{area:x}'
        w(0x41F9, area >> 16, area & 0xFFFF, 0x303C, longs - 1)
        c.label(name); w(0xE39F, 0xDE98); l(0x51C8, name)
    w(0x7000, 0x1038, 0x8D52, 0xDE80)                   # and the room byte
    w(0x23C7, 0xFFFF, 0x0200)
    w(0x5279, 0xFFFF, 0x0204, 0x0C79, CELL_PASSES, 0xFFFF, 0x0204)
    l(0x6600, 'pass')
    w(0x23FC, 0x600D, 0xF00D, 0xFFFF, 0x000C, 0x60FE)
    return c.finish()

def check_cells(rom, patched):
    pattern_at = 0x1F0400
    registers = [0xA1B2C300 + i for i in range(15)]
    registers[12] = 0xFFFF0300                      # a4, the game's base for its variables
    records, maps = cell_test_data()
    code = cell_test(pattern_at)
    results = []
    for source in (with_tiles(rom, b''), patched):
        test = bytearray(source)
        for at, data in ((CELL_RECORDS, records), (CELL_MAPS, maps),
                         (pattern_at, b''.join(r.to_bytes(4, 'big') for r in registers))):
            test[at:at + len(data)] = data
        boot_into(test, 0x1F0000, code, CELL_CHECK_ROM)
        got = peek(CELL_CHECK_ROM, [*range(0xFF0200, 0xFF0206), *range(0xFF000C, 0xFF0010)], 1500)
        if int.from_bytes(got[4:6], 'big') != CELL_PASSES or got[6:] != bytes.fromhex('600DF00D'):
            sys.exit('screen cell check did not finish')
        results.append(got[:4])
    same = results[0] == results[1]
    print(f'screen cells, old against new on {CELL_PASSES} random maps: same cells, shapes and registers: '
          f'{"yes" if same else "NO"}')
    if not same:
        sys.exit('screen cell check FAILED')


def sound_link(rom, origin=SOUND_LINK_NEW, count_in=48, count_out=48):
    """The sound link with its two 48-byte copies written out in full, in place of loops.

    Everything else is the original's own instructions, in the original order. The copies
    go through Z80 memory, which the 68000 can only reach a byte at a time. The counts are
    parameters so that a test can get them wrong on purpose.
    """
    def old(start, end):
        return bytes(rom[start:end])
    assert old(0x1626A, 0x16270) == bytes.fromhex('12D851C8FFFC')   # move.b (a0)+,(a1)+ / dbra d0
    assert old(0x162B6, 0x162BC) == bytes.fromhex('10D951C8FFFC')   # move.b (a1)+,(a0)+ / dbra d0
    assert old(0x16280, 0x16282) == bytes.fromhex('6100')           # bsr.w, to the music
    assert old(0x162A4, 0x162A6) == bytes.fromhex('6716')           # beq.s, past the copy back
    code = old(SOUND_LINK, 0x1626A) + bytes.fromhex('12D8') * count_in
    code += bytes.fromhex('303CFFFF')                               # move.w #$FFFF,d0, as the loop left it
    code += old(0x16270, 0x16280) + bytes.fromhex('4EB900015E4A')   # jsr in place of the bsr
    code += old(0x16284, 0x162A4) + bytes([0x67, 16 + 2 * count_out]) + old(0x162A6, 0x162B6)
    code += bytes.fromhex('10D9') * count_out + old(0x162BC, SOUND_LINK_END)
    assert code[-2:] == bytes.fromhex('4E75') and origin + len(code) <= ROUTINE_RTS
    return code


def sound_test(pattern_at):
    """Play six songs for 256 frames each through the sound link, with the Z80 parked.

    Then the music is stopped for 256 frames, which is when the link skips its copy back.
    Before each call the 48 bytes on the Z80's side are set at random, as if the Z80 had
    changed them. After it, the registers, the 68000's sound memory and the Z80's memory
    all go into a checksum.
    """
    c = Code(0x1F0000)
    w, s, l = c.words, c.short, c.long

    def take_bus(name):
        w(0x33FC, 0x0100, 0x00A1, 0x1100)                           # move.w #$100,$A11100
        c.label(name)
        w(0x0839, 0x0000, 0x00A1, 0x1100)                           # btst #0,$A11100
        s(0x6600, name)

    def give_bus():
        w(0x33FC, 0x0000, 0x00A1, 0x1100)

    w(0x41F9, 0xFFFF, 0x0000, 0x303C, 0x3EFF)
    c.label('clear')
    w(0x4298)
    l(0x51C8, 'clear')
    w(0x33FC, 0x0100, 0x00A1, 0x1200)                               # let the Z80 out of reset
    take_bus('bus0')
    for at, byte in enumerate((0xF3, 0x18, 0xFE)):                  # its program: di / jr to itself
        w(0x13FC, byte, 0x00A0, at)
    w(0x33FC, 0x0000, 0x00A1, 0x1200, 0x707F)                       # reset it, and wait a moment
    c.label('hold')
    l(0x51C8, 'hold')
    w(0x33FC, 0x0100, 0x00A1, 0x1200)
    give_bus()
    w(0x21FC, SOUND_RECORDS >> 16, SOUND_RECORDS & 0xFFFF, 0x8008)  # where the random bytes are
    c.label('pass')
    w(0x7000, 0x3038, 0x8004, 0x4A00)                               # every 256 passes, the next song
    s(0x6600, 'same_song')
    w(0xE048, 0x0C40, 0x0006)                                       # lsr.w #8,d0 / cmpi.w #6,d0
    s(0x6600, 'start')
    w(0x4EB9, 0x0001, 0x5E10)                                       # jsr stop_music
    s(0x6000, 'same_song')
    c.label('start')
    w(0x4EB9, 0x0001, 0x5D10)                                       # jsr start_song
    c.label('same_song')
    take_bus('bus1')
    w(0x2078, 0x8008, 0x43F9, 0x00A0, 0x0229, 0x702F)
    c.label('random')
    w(0x12D8)
    l(0x51C8, 'random')
    w(0x21C8, 0x8008)
    give_bus()
    w(0x41F9, pattern_at >> 16, pattern_at & 0xFFFF, 0x4CD0, 0x7FFF)
    w(0x4EB9, SOUND_LINK >> 16, SOUND_LINK & 0xFFFF)
    w(0x48F9, 0x7FFF, 0xFFFF, 0x8100)                               # the registers it left
    w(0x2E38, 0x8000)                                               # move.l $8000.w,d7
    for area, longs in ((0xFFFF8100, 15), (0xFFFF0000, 0x240 // 4)):
        name = f'sum{area:x}'
        w(0x41F9, area >> 16, area & 0xFFFF, 0x303C, longs - 1)
        c.label(name)
        w(0xE39F, 0xDE98)
        l(0x51C8, name)
    take_bus('bus2')
    w(0x41F9, 0x00A0, 0x0000, 0x303C, 0x02FF)
    c.label('z80')
    w(0x7200, 0x1218, 0xE39F, 0xDE81)                               # each byte of Z80 memory in turn
    l(0x51C8, 'z80')
    give_bus()
    w(0x21C7, 0x8000, 0x5278, 0x8004, 0x0C78, SOUND_PASSES, 0x8004)
    l(0x6600, 'pass')
    w(0x21FC, 0x600D, 0xF00D, 0x800C, 0x60FE)
    return c.finish()


def check_sound(rom, patched):
    pattern_at = 0x1F0400
    rnd = random.Random(1990)
    records = bytes(rnd.randrange(256) for _ in range(SOUND_PASSES * 48))
    registers = b''.join((0xA1B2C300 + i).to_bytes(4, 'big') for i in range(15))
    code = sound_test(pattern_at)
    results = []
    for source in (with_tiles(rom, b''), patched):
        test = bytearray(source)
        test[SOUND_RECORDS:SOUND_RECORDS + len(records)] = records
        test[pattern_at:pattern_at + len(registers)] = registers
        boot_into(test, 0x1F0000, code, SOUND_CHECK_ROM)
        got = peek(SOUND_CHECK_ROM, [*range(0xFF8000, 0xFF8006), *range(0xFF800C, 0xFF8010)], 1500)
        if int.from_bytes(got[4:6], 'big') != SOUND_PASSES or got[6:] != bytes.fromhex('600DF00D'):
            sys.exit('sound link check did not finish')
        results.append(got[:4])
    same = results[0] == results[1]
    print(f'sound link, old against new on {SOUND_PASSES} frames of music and silence: same memory on both sides and '
          f'registers: {"yes" if same else "NO"}')
    if not same:
        sys.exit('sound link check FAILED')


def mask_tables(rom, as_game=False):
    """Every mask shape at every horizontal shift.

    The game shifts the right-hand cell's shape by 31 minus the offset, which leaves it one
    bit out of line and miscolours stray pixels along mask edges. 32 lines it up. as_game
    keeps the 31, for proving the routine against the original.

    Shapes 6 to 15 are whatever bytes follow the six real ones, which is the old routine's
    own code. They're kept as they were, in case a cell ever names one.
    """
    right_shift = 31 if as_game else 32
    left, right = bytearray(), bytearray()
    for shape in range(16):
        rows = [int.from_bytes(rom[MASK_SHAPES + shape * 32 + 4 * r:][:4], 'big') for r in range(8)]
        for shift in range(0, 32, 4):
            for row in rows:
                left += ((row << shift) & 0xFFFFFFFF).to_bytes(4, 'big')
                right += (row >> (right_shift - shift)).to_bytes(4, 'big')
    return bytes(left + right)

def sprite_mask(origin=MASK):
    """The masking routine, reading shifted shapes from MASK_TABLES. Same inputs and output."""
    c = Code(origin)
    w, s, l = c.words, c.short, c.long
    w(0x48E7, 0xFFFE)                               # movem.l d0-d7/a0-a6,-(sp)
    w(0x3E38, 0x92F4)                               # move.w  $92F4.w,d7        sprites
    l(0x6700, 'exit')                               # beq.w   exit
    w(0x5347)                                       # subq.w  #1,d7
    w(0x41F8, 0x8D54)                               # lea     $8D54.w,a0        sprite list
    w(0x43F9, 0xFFFF, 0x2000)                       # lea     $FFFF2000,a1      their tiles
    w(0x45F9, MASK_TABLES >> 16, MASK_TABLES & 0xFFFF)  # lea MASK_TABLES,a2
    w(0x47F8, 0x8ADE)                               # lea     $8ADE.w,a3        shape of each cell
    w(0x7007, 0xC06C, 0x1160)                       # moveq #7,d0 / and.w $1160(a4),d0
    w(0x363C, 0x0098, 0x9640, 0x31C3, 0x95E6)       # $95E6 = $98 - (camera x & 7)
    w(0x362C, 0x1162)                               # move.w  $1162(a4),d3      camera y
    w(0x31C3, 0x95EA)                               # move.w  d3,$95EA.w
    w(0x7007, 0xC043)                               # moveq #7,d0 / and.w d3,d0
    w(0x383C, 0x0098, 0x9840, 0x31C4, 0x95E8)       # $95E8 = $98 - (camera y & 7)
    w(0x9640, 0x0643, 0x0020, 0x31C3, 0x95A4)       # $95A4 = camera y - (camera y & 7) + $20
    w(0x49F8, 0x9254)                               # lea     $9254.w,a4        depth of each sprite
    c.label('sprite')
    w(0x4847)                                       # swap    d7
    w(0x301C)                                       # move.w  (a4)+,d0
    w(0x1C28, 0x0002, 0x3E06)                       # move.b 2(a0),d6 / move.w d6,d7
    w(0x0246, 0x0003, 0x31C6, 0x95E4)               # andi.w #3,d6 / move.w d6,$95E4.w   rows - 1
    w(0xE44F, 0x0247, 0x0003)                       # lsr.w #2,d7 / andi.w #3,d7         columns - 1
    w(0x4A40)                                       # tst.w   d0
    s(0x6A00, 'masked')                             # bpl.s   masked
    w(0x5246, 0x5247, 0xCCC7, 0xEB4E, 0xD2C6)       # not masked: step over its tiles
    l(0x6000, 'next_sprite')
    c.label('masked')
    w(0xD078, 0x95EA, 0x31C0, 0x95A6)               # $95A6 = depth + camera y
    w(0x3228, 0x0006, 0x9278, 0x95E6)               # d1 = x within the cell grid
    w(0x3410, 0x9478, 0x95E8)                       # d2 = y within the cell grid
    c.label('column')
    w(0x3F02)                                       # move.w  d2,-(sp)
    w(0x3C38, 0x95E4)                               # move.w  $95E4.w,d6
    w(0x7007, 0xC041, 0xEB48, 0x31C0, 0x95A8)       # $95A8 = (x & 7) * 32, the shift's tables
    w(0x3001, 0xE648, 0x31C0, 0x95AA)               # $95AA = x / 8, the cell column
    c.label('tile')
    w(0x3002, 0xE648, 0x3600, 0xEB48, 0xD043, 0xD043)  # d0 = (y / 8) * 34
    w(0xD078, 0x95AA)                               # add.w   $95AA.w,d0
    w(0x4BF3, 0x0000)                               # lea     (a3,d0.w),a5      the four cells under it
    w(0x1015, 0x802D, 0x0001, 0x802D, 0x0022, 0x802D, 0x0023)  # or the four together
    l(0x6700, 'no_mask')                            # beq.w   no_mask
    w(0x1815, 0xE14C, 0x182D, 0x0001)               # d4 = top left, top right
    w(0x1A2D, 0x0022, 0xE14D, 0x1A2D, 0x0023)       # d5 = bottom left, bottom right
    w(0x3602, 0xD678, 0x95A4, 0x3003)               # d3 = y + $95A4, kept in d0
    w(0x0243, 0xFFE0, 0x0643, 0x0018, 0xB678, 0x95A6)  # the top cells' depth against the sprite's
    s(0x6E00, 'top_low')                            # bgt.s   top_low
    w(0xE84C)                                       # lsr.w   #4,d4             use their high halves
    c.label('top_low')
    w(0x5040, 0x0240, 0xFFE0, 0x0640, 0x0018, 0xB078, 0x95A6)  # and the row below
    s(0x6E00, 'bottom_low')
    w(0xE84D)                                       # lsr.w   #4,d5
    c.label('bottom_low')
    w(0x0244, 0x0F0F, 0x0245, 0x0F0F)               # andi.w #$0F0F,d4 / andi.w #$0F0F,d5
    w(0x3004, 0x8045)                               # move.w d4,d0 / or.w d5,d0
    l(0x6700, 'no_mask')
    w(0x0C44, 0x0505)                               # cmpi.w  #$0505,d4
    s(0x6600, 'shape')
    w(0x0C45, 0x0505)
    s(0x6600, 'shape')
    w(0x7000, *[0x22C0] * 8)                        # all hidden: clear the tile
    l(0x6000, 'next')
    c.label('shape')
    w(0x7607, 0xC642)                               # d3 = y & 7
    w(0x3003, 0xD040, 0xD040, 0xD078, 0x95A8)       # d0 = (y & 7) * 4 + the shift's tables
    w(0x4DF2, 0x0000)                               # lea     (a2,d0.w),a6
    w(0x3004, 0x4200, 0x4BF6, 0x0000)               # a5 = left part of the top left shape
    w(0xE14C, 0x4DEE, 0x1000, 0xDCC4)               # a6 = right part of the top right shape
    w(0xD643, 0x3003, 0xD643, 0xD640)               # d3 = (y & 7) * 6
    w(0x4EFB, 0x3002)                               # jmp     2(pc,d3.w)        rows from the top cells
    w(*[0x201D, 0x809E, 0xC199] * 8)                # move.l (a5)+,d0 / or.l (a6)+,d0 / and.l d0,(a1)+
    w(0x4443)                                       # neg.w   d3
    s(0x6700, 'next')                               # beq.s   next              no rows from below
    w(0x0643, 0x0030)                               # addi.w  #48,d3
    w(0x3038, 0x95A8, 0x4DF2, 0x0000)               # the same for the bottom cells
    w(0x3005, 0x4200, 0x4BF6, 0x0000)
    w(0xE14D, 0x4DEE, 0x1000, 0xDCC5)
    w(0x4EFB, 0x3002)
    w(*[0x201D, 0x809E, 0xC199] * 8)
    c.label('next')
    w(0x5042)                                       # addq.w  #8,d2
    l(0x51CE, 'tile')                               # dbra    d6,tile
    w(0x341F, 0x5041)                               # move.w (sp)+,d2 / addq.w #8,d1
    l(0x51CF, 'column')                             # dbra    d7,column
    c.label('next_sprite')
    w(0x5048, 0x4847)                               # addq.w #8,a0 / swap d7
    l(0x51CF, 'sprite')                             # dbra    d7,sprite
    c.label('exit')
    w(0x4CDF, 0x7FFF, 0x4E75)                       # movem.l (sp)+,d0-d7/a0-a6 / rts
    c.label('no_mask')
    w(0x43E9, 0x0020)                               # lea     32(a1),a1
    l(0x6000, 'next')
    code = c.finish()
    assert origin != MASK or len(code) <= MASK_END - MASK, len(code)
    return code

def random_cell_half(rnd, mode):
    r = rnd.random()
    if mode == 0: return 0 if r < .9 else rnd.randint(1, 5)
    if mode == 1: return 5 if r < .7 else rnd.randint(0, 5)
    if r < .45: return 0
    return rnd.randint(1, 5) if r < .95 else rnd.randint(6, 15)

def random_cells(rnd, n, mode):
    return bytes(random_cell_half(rnd, mode) << 4 | random_cell_half(rnd, mode) for _ in range(n))

def mask_test_data():
    """Random sprites, depths and scenery for each pass, plus cells for sprites off the grid."""
    rnd = random.Random(1428)
    records = bytearray()
    for i in range(MASK_PASSES):
        mode = i % 4 if i % 4 < 2 else 2
        count = rnd.randint(1, 16)
        camera_y = rnd.randint(0, 1023)
        records += count.to_bytes(2, 'big') + rnd.randint(0, 1023).to_bytes(2, 'big') + camera_y.to_bytes(2, 'big')
        sprites, depths = bytearray(), bytearray()
        for _ in range(16):
            if rnd.random() < .7:
                y, x = rnd.randint(152, 152 + 143), rnd.randint(152, 152 + 271)
            else:
                y, x = rnd.randint(0x60, 0x25F), rnd.randint(0x60, 0x25F)
            depth = min(max(y - 96 + rnd.randint(-64, 64), 0), 0x7FFF) | (0x8000 if rnd.random() < .15 else 0)
            sprites += y.to_bytes(2, 'big') + bytes([rnd.randint(0, 255), rnd.randint(0, 255)]) + \
                rnd.randbytes(2) + x.to_bytes(2, 'big')
            depths += depth.to_bytes(2, 'big')
        records += depths + sprites + random_cells(rnd, 612, mode)
    return bytes(records), random_cells(rnd, 0x5000, 2), rnd.randbytes(0x2000)

def mask_test(pattern_at):
    """Run the masking routine on every record, adding its tiles and registers to a checksum.

    FF0200 holds the checksum, FF0204 the passes done, and FF000C becomes 600DF00D at the end.
    """
    c = Code(0x1F0000)
    w, l = c.words, c.long
    w(0x41F9, 0xFFFF, 0x0000, 0x303C, 0x3EFF)       # clear RAM below the stack
    c.label('clear'); w(0x4298); l(0x51C8, 'clear')
    w(0x41F9, MASK_EXTRA >> 16, MASK_EXTRA & 0xFFFF, 0x43F9, 0xFFFF, 0xA000, 0x303C, 0x13FF)
    c.label('extra'); w(0x22D8); l(0x51C8, 'extra')  # random cells at $A000-$EFFF
    w(0x23FC, MASK_RECORDS >> 16, MASK_RECORDS & 0xFFFF, 0xFFFF, 0x0208)
    c.label('pass')
    w(0x2079, 0xFFFF, 0x0208)                       # movea.l $FFFF0208,a0      this pass's record
    w(0x31D8, 0x92F4, 0x33D8, 0xFFFF, 0x1460, 0x33D8, 0xFFFF, 0x1462)  # count, camera x, camera y
    for dest, words in ((0x9254, 16), (0x8D54, 64), (0x8ADE, 306)):
        name = f'copy{dest:x}'
        w(0x43F8, dest, 0x303C, words - 1)
        c.label(name); w(0x32D8); l(0x51C8, name)
    w(0x23C8, 0xFFFF, 0x0208)
    w(0x41F9, MASK_TILES >> 16, MASK_TILES & 0xFFFF, 0x43F9, 0xFFFF, 0x2000, 0x303C, 0x07FF)
    c.label('tiles'); w(0x22D8); l(0x51C8, 'tiles')
    w(0x41F9, pattern_at >> 16, pattern_at & 0xFFFF, 0x4CD0, 0x7FFF)   # known registers
    w(0x4EB9, MASK >> 16, MASK & 0xFFFF)            # jsr     the routine
    w(0x48F9, 0x7FFF, 0xFFFF, 0x0100)               # movem.l d0-d7/a0-a6,$FFFF0100
    w(0x2E39, 0xFFFF, 0x0200)                       # move.l  $FFFF0200,d7      running checksum
    w(0x41F9, 0xFFFF, 0x0100, 0x700E)
    c.label('sum_regs'); w(0xE39F, 0xDE98); l(0x51C8, 'sum_regs')
    w(0x41F9, 0xFFFF, 0x2000, 0x303C, 0x07FF)
    c.label('sum_tiles'); w(0xE39F, 0xDE98); l(0x51C8, 'sum_tiles')
    w(0x23C7, 0xFFFF, 0x0200)
    w(0x5279, 0xFFFF, 0x0204, 0x0C79, MASK_PASSES, 0xFFFF, 0x0204)
    l(0x6600, 'pass')
    w(0x23FC, 0x600D, 0xF00D, 0xFFFF, 0x000C, 0x60FE)
    return c.finish()

def check_mask(rom, patched):
    pattern_at = 0x1F0400
    registers = [0xA1B2C300 + i for i in range(15)]
    registers[12] = 0xFFFF0300                      # a4, the game's base for its variables
    records, extra, tiles = mask_test_data()
    code = mask_test(pattern_at)
    results = []
    exact = bytearray(patched)                      # the new routine with the game's own shift
    exact[MASK_TABLES:MASK_TABLES + 0x2000] = mask_tables(rom, as_game=True)
    for source in (with_tiles(rom, b''), exact):
        test = bytearray(source)
        for at, data in ((MASK_RECORDS, records), (MASK_EXTRA, extra), (MASK_TILES, tiles),
                         (pattern_at, b''.join(r.to_bytes(4, 'big') for r in registers))):
            test[at:at + len(data)] = data
        boot_into(test, 0x1F0000, code, MASK_CHECK_ROM)
        got = peek(MASK_CHECK_ROM, [*range(0xFF0200, 0xFF0206), *range(0xFF000C, 0xFF0010)], 4000)
        if int.from_bytes(got[4:6], 'big') != MASK_PASSES or got[6:] != bytes.fromhex('600DF00D'):
            sys.exit('sprite masking check did not finish')
        results.append(got[:4])
    same = results[0] == results[1]
    print(f'sprite masking, old against new on {MASK_PASSES} random scenes: same tiles and registers: '
          f'{"yes" if same else "NO"}')
    if not same:
        sys.exit('sprite masking check FAILED')


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
    for old, new, code in ((MAP_TILES, MAP_TILES_NEW, map_tiles()), (TILE_SYNC, TILE_SYNC_NEW, tile_sync()),
                           (TABLE_RESET_TAIL, TABLE_RESET_NEW, table_reset_tail())):
        out[new:new + len(code)] = code
        out[old:old + 6] = b'\x4e\xf9' + new.to_bytes(4, 'big')    # jmp
    assert rom[TABLE_RESET_TAIL:TABLE_RESET_TAIL + 6] == bytes.fromhex('4CDF01034E75')
    out[CELL_DATA_COPY:CELL_DATA_COPY + CELL_DATA_SIZE] = rom[CELL_DATA:CELL_DATA + CELL_DATA_SIZE]
    code = cells()
    out[CELLS:CELLS + len(code)] = code
    tables = mask_tables(rom)
    out[MASK_TABLES:MASK_TABLES + len(tables)] = tables
    code = sound_link(rom)
    out[SOUND_LINK_NEW:SOUND_LINK_NEW + len(code)] = code
    out[SOUND_LINK:SOUND_LINK + 6] = b'\x4e\xf9' + SOUND_LINK_NEW.to_bytes(4, 'big')   # jmp
    code = sprite_mask()
    out[MASK:MASK + len(code)] = code
    out[BOOT_CHECK_BRANCH:BOOT_CHECK_BRANCH + 2] = b'\x4e\x71'      # nop
    os.makedirs(BUILD, exist_ok=True)
    finish_rom(out, OUTPUT)
    if check:
        check_routine(out, b''.join(table))
        check_background(rom, out)
        check_mask(rom, out)
        check_cells(rom, out)
        check_sound(rom, out)
    print(f'{count} tiles unpacked, {len(fixed)} corrected {fixed}')
    print(f'wrote {os.path.relpath(OUTPUT, ROOT)}')


if __name__ == '__main__':
    main()

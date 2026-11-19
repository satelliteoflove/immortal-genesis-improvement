#!/usr/bin/env python3
"""Build the patched ROM from your own copy of the game.

    tools/build_rom.py           writes build/immortal-patched.md
    tools/build_rom.py --check   also tests each changed routine in the emulator

The patched ROM is 1 MB, the size of the original, and uses the game's own packed graphics.

Everything the patch needs from the game is read from the ROM when this runs, so
nothing of the game is stored here. What it changes:

  * Object graphics. The game unpacks each object tile from a bit-by-bit compressed
    form every time it's needed. The new routine keeps the last 512 tiles it unpacked
    in RAM the game leaves alone, so most requests are a plain copy. The game's own
    decoder still does the unpacking.
  * The wall torch. A slip in the game's tile search decodes one tile wrongly, which
    takes the top off the flame. The new object routine does that search itself, and
    gets it right.
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
    miscolored pixels where a sprite passes behind scenery. The tables line it up.
  * The boot check at 0FFFB0, which halts the game if the first megabyte has changed.

--check builds test ROMs that boot straight into a small test. They get a second megabyte
to hold the test and its data. One runs the game's own, unmodified decoder on every tile
number and compares the result with this script's unpacking. One asks the new object
routine for every tile, so that each is unpacked, found again, pushed out and unpacked
again, and compares them all with this script's unpacking, corrected for the torch. One
checks that the routine leaves every register as it found it. One feeds random screens to the background routines, old
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
MEMORY_CHECK_ROM = os.path.join(BUILD, 'memory-check.md')
ROUTINE_CHECK_ROM = os.path.join(BUILD, 'routine-check.md')
BACKGROUND_CHECK_ROM = os.path.join(BUILD, 'background-check.md')
MASK_CHECK_ROM = os.path.join(BUILD, 'mask-check.md')
CELL_CHECK_ROM = os.path.join(BUILD, 'cell-check.md')
SOUND_CHECK_ROM = os.path.join(BUILD, 'sound-check.md')
BLASTEM = os.path.join(BUILD, 'blastem-fork', 'blastem')

TEST_SIZE = 0x200000            # test ROMs get a second megabyte for the test and its data
TILES = 0x100000                # where a test ROM keeps this script's unpacking of every tile
FREE = 0xFD65C                  # unused in the original, all FF, up to the boot check:
FREE_END = 0xFFFB0              #   everything the patch adds goes here
PATCH_RAM = 0x9760              # FF9760 to FFF7FF: RAM the game only touches while starting up

# In the original game
INDEX = 0x2DCEC                 # runs of tiles: bits per tile, first tile, bit offset
INDEX_LAST = 0xDD               # the search's highest entry; one more ends the table
PACKED = 0x6EED0                # the packed tile data
TREE = 0x2E6D6                  # the decoder, a tree of bit tests written as code
TREE_DONE = 0x2F4D0             # where each decoded byte branches to
ROUTINE = 0x2E3E4               # the object graphics routine
DECODE = 0x2E48E                # inside its loop, after the search: unpacks tile d4 of the run at d5(a0) to (a1)+
RAW_DONE = 0x2E4C2              # where the loop carries on after a tile stored unpacked,
PACKED_DONE = 0x2F4D4           #   and after a packed one
SPREAD = 0x2D4EC                # a table the decoder wants in a3
RUN_STARTS = 0xFFEC8            # a byte for each 128 tile numbers: the run the first of them is in
TILE_MEMORY = 0xFFBA6           # the new routine
MEMORY_SETS = 128               # it remembers tiles in sets, chosen by the low 7 bits of the tile number,
MEMORY_WAYS = 5                 #   of this many tiles each
MEMORY_TAGS = 0x9800            # which tile each place holds, as the game stores the number; 0 for none.
                                #   16 bytes for each set, of which the first MEMORY_WAYS words are used
MEMORY_TURNS = 0xA000           # a byte for each set: which of its places is replaced next
MEMORY_TILES = 0xA080           # the tiles: 4,096 bytes holding every set's first place, then the
                                #   same for its second, and so on
BOOT_CHECK_BRANCH = 0xFFFD0     # the branch taken when the boot check fails
OUTPUT_TILES = 0xFF2000         # where the routine puts its tiles
TABLE_RESET = 0x13AE2           # empties the background tile table
MAP_TILES = 0x13B16             # gives each cell on screen a slot in video memory
MAP_TILES_NEW = 0xFF8CA         # the new MAP_TILES
TABLE_RESET_TAIL = 0x13B10      # TABLE_RESET's last two instructions
TABLE_RESET_NEW = 0xFF938       # their replacement
TILE_COUNTS = 0x9760            # 64 bytes: how many of each 32 table entries are in use
TILE_SYNC = 0x13B78             # frees unused slots and sends tiles to video memory
BACKGROUND_TILES = 0x3D9B2      # the background tile graphics
TILE_TABLE = 0xFFFF7612         # one word per background tile: its slot, plus two flags
TILE_SYNC_NEW = 0xFF820         # the new TILE_SYNC
CELLS = 0x13D34                 # works out the 612 cells on screen from the level's block maps
CELLS_END = 0x13F5E
CELL_DATA = 0x13C80             # five 8 by 4 blocks of mask shapes, then a table choosing between them
CELL_DATA_COPY = 0xFF660        # those bytes as they were, for the new routine to read
CELL_DATA_SIZE = 0x1C0
BLOCKS = 0x3ABF2                # 64 bytes of cells for each kind of block
CELL_PASSES = 300               # for --check: passes of random maps and cameras
CELL_RECORDS = 0x100000
CELL_MAPS = 0x110000
CELL_MAP_SETS = 8
SOUND_LINK = 0x1624E            # once a frame: fetches 48 bytes from the Z80, runs the music, sends them back
SOUND_LINK_END = 0x16304
SOUND_LINK_NEW = 0xFF94A
SOUND_PASSES = 1792             # for --check: 256 frames of each of six songs, then 256 of silence
SOUND_RECORDS = 0x100000
FIGHT_PASS_DRAW = 0x11694       # a fight's main loop: its drawing call and the one after
FIGHT_STEP_DRAW = 0x11772       # a fight's animation loop: its drawing call and the wait after
FIGHT_PASS_FRAMES = 6           # frames from one picture to the next in the original, as measured
FIGHT_STEP_FRAMES = 8
FIGHT_PACE = 0xFFABA            # the routines that hold fights to that pace
FIGHT_SHOWN = 0x97A0            # the frame count when a fight's last picture went up
SONG_REQUEST = 0x15D44          # asks the sound driver to start a song at the next frame
SONG_END = 0x15E10              # a song that has run out asks the driver to go quiet
MUSIC_KEEP = 0xFFAFE            # the new versions of both
SOUNDING = 0x97A4               # the song playing when the waiting request was made (a long)
SILENT = 0x97A8                 # set once a song has run out and nothing has been started since
TEXT_WAIT = 0x13452             # message text: called once for each unit of waiting
TEXT_NO_WAIT = 0xCEC0           # the branch that skips all waiting while two buttons are held
TEXT_WAIT_NEW = 0xFFB56         # the new TEXT_WAIT
TEXT_LETTER_UNITS = 5           # the wait after a letter, in units
TEXT_TYPING_UNITS = 0x0D        # waits of up to this many units are typing; longer ones are pauses
TEXT_TURN = 0x97A9              # flips each time a held button meets a letter's wait
LEVEL_END = 0x11266             # a level is over: the calls that make its certificate and show it
GAME_OVER_TEXT = 0x12646        # the end of the Game Over routine: its message, then rts
LOADER = 0x12A74                # starts a game: from a certificate's fields, a typed certificate or nothing
LOADER_FROM_FIELDS = 0x12AB0    #   where it starts the level the fields describe
LOADER_ASK = 0x12A8E            #   where it asks "New game?"
LOADER_NEW = 0x12C82            #   where it starts a new game
CERTIFICATE = 0xD8C             # (a4): the certificate's 13 digits, a byte each: 4 of check, then 9
CERTIFICATE_LEVEL = 0xD91       # (a4): the digit that is the level, 1 for the second
MAKE_CERTIFICATE = 0x12876      # fills the fields from the game as it stands
CHECK_CERTIFICATE = 0x12804     # works out the check digits of the fields, into $304-$307(a4)
DIGIT_LETTERS = 0x12A50         # the 16 letters a certificate is shown in
PRINT = 0x13362                 # draws the letter in d0 at the text cursor
WIZARD_HEALTH = 0x60C           # (a4): the wizard's health, in the high four bits
SAY = 0xCD56                    # shows message d1 in a new box
SAY_FIRST = 0xCE0E              # the same, expecting more to follow
SAY_LOOP = 0xCF2A               # inside the message routine, past where it has found its text
SHOW = 0x15738                  # a frame's wait that puts what's drawn on the screen, unless $9642 is set
NEW_BOX = 0x131E4               # clears the box and puts the cursor at its top
ANSWER = 0x1370A                # after a message that asks: carry set for NO
PAD = 0x962A                    # pad 1 as last read: up, down, left, right in bits 0-3, buttons above
SAVE_HEADER = 0x1B0             # the header's field for battery RAM, blank in the original
SAVE_RAM = 0x200001             # the battery RAM: odd bytes from here
SAVE_RAM_END = 0x2001FF
SAVES = 0xFFCCA                 # the new routines
SAVE_TEXT = 0x2E3EA             # their messages, in the old object routine's unused start
SAVE_TEXT_END = 0x2E48E
TEXT_BUFFER = 0x97B0            # a message is copied here to be shown: the game finds text by 16-bit address
AGAIN = 0x97AA                  # set to start a new game without asking, for "try again" on the first level
SAVE_MESSAGES = {'over': 'Game Over&&Try this level again?%',
                 'continue': 'Continue a saved game?%',
                 'pick': 'Up or Down selects a level.&Press Start or A when done.&&         Level $=',
                 'saved': '&Game saved.@'}
RETRY_MESSAGE = 0x81F4          # after a death with a retry left: "Prepare to continue..."
PREPARE_TEXT = 0x42F9           # its text, which ended in three short pauses
DEATH_PAUSE = TILE_SYNC + 6     # the new routine, in the old tile sync's body, never run now
DEATH_PAUSE_END = 0x13BF6
DEATH_PAUSE_FRAMES = 180        # how long the message stays up unless a button is pressed
FRAME_WAIT = 0x14E3A            # waits for the next frame
MASK = 0x1428C                  # hides the parts of sprites that are behind scenery
MASK_END = 0x14508              # the first byte after its rts
MASK_SHAPES = 0x141CC           # 16 shapes of 32 bytes; only the first 6 are data
MASK_TABLES = 0xFD660           # the shapes shifted ahead of time: left parts, right parts at +$1000
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
                assert -128 <= distance < 128 and distance, (target, distance)
                self.data[at + 1] = distance & 0xFF
        return bytes(self.data)


def tile_memory():
    """Put each listed tile in the output buffer, as the original did, but remember them.

    A tile is looked for among those kept for its set. If it's there it is copied. If not,
    the game's own decoder unpacks it to the output, and it is copied from there into the
    place whose turn it is. A place's tag is zero until the tile is all there, so a reset
    in the middle can't leave half a tile that looks whole.

    The decoder is called as a subroutine, after its search for the run of tiles the number
    belongs to. That search is done here instead. RUN_STARTS gives a run to start from, a
    step or two short at most, where the game halved its way through the whole index each
    time. And it doesn't have the game's slip of taking a run's last number plus one as part
    of the run. Returns the code and where its rts is.
    """
    assert MEMORY_SETS == 128 and 2 <= MEMORY_WAYS <= 8
    assert MEMORY_TILES + 32 * MEMORY_SETS * MEMORY_WAYS <= 0xF800
    c = Code(TILE_MEMORY)
    w, s, l = c.words, c.short, c.long
    w(0x48E7, 0xFFFE)                               # movem.l d0-d7/a0-a6,-(sp)
    w(0x47F9, SPREAD >> 16, SPREAD & 0xFFFF)        # lea     SPREAD,a3         both for the decoder,
    w(0x4DF9, PACKED >> 16, PACKED & 0xFFFF)        # lea     PACKED,a6         which leaves them alone
    w(0x4BF8, 0x92FA)                               # lea     $92FA.w,a5        list of tiles
    w(0x43F9, OUTPUT_TILES >> 16 | 0xFF00, OUTPUT_TILES & 0xFFFF)  # lea $FFFF2000,a1
    w(0x3038, 0x92F6, 0xEB48, 0xD2C0)               # a1 += 32 times the next free slot
    w(0x3E38, 0x931A, 0x5347)                       # d7 = how many, less one
    w(0x41F8, MEMORY_TAGS)                          # lea     tags,a0
    c.label('loop')
    w(0x7000, 0x1015)                               # moveq #0,d0 / move.b (a5),d0   the number's low byte
    w(0x381D)                                       # move.w  (a5)+,d4          the number as it's stored
    s(0x6700, 'blank')                              # beq.s   blank
    w(0xD000, 0xE748)                               # add.b d0,d0 / lsl.w #3,d0      16 times its set
    w(0x45F0, 0x0000)                               # lea     (a0,d0.w),a2      the set's tags
    w(0xD040)                                       # add.w   d0,d0             32 times its set
    for way in range(MEMORY_WAYS - 1):
        w(0xB85A)                                   # cmp.w   (a2)+,d4
        s(0x6700, f'found{way}')                    # beq.s
    w(0xB85A)                                       # cmp.w   (a2)+,d4
    s(0x6600, 'miss')                               # bne.s   miss
    for way in reversed(range(MEMORY_WAYS)):
        if way < MEMORY_WAYS - 1:
            c.label(f'found{way}')
        w(0x45F8, MEMORY_TILES + 0x1000 * way)      # lea     this place in every set,a2
        if way:
            s(0x6000, 'found')                      # bra.s   found
    c.label('found')
    w(0xD4C0)                                       # adda.w  d0,a2             in this set
    w(*[0x22DA] * 8)                                # move.l  (a2)+,(a1)+ eight times
    c.label('count')
    w(0x5278, 0x92F6)                               # addq.w  #1,$92F6.w
    l(0x51CF, 'loop')                               # dbra    d7,loop
    w(0x4CDF, 0x7FFF)                               # movem.l (sp)+,d0-d7/a0-a6
    c.label('rts')
    w(0x4E75)                                       # rts
    c.label('blank')
    w(*[0x22C0] * 8)                                # move.l  d0,(a1)+ eight times: all of d0 is zero
    s(0x6000, 'count')                              # bra.s   count
    c.label('miss')
    w(0x45F8, MEMORY_TURNS, 0x3A00, 0xEA4D, 0xD4C5)  # a2 = the set's turn
    w(0x7200, 0x1212)                               # moveq #0,d1 / move.b (a2),d1   whose turn it is
    w(0x5212, 0x0C12, MEMORY_WAYS, 0x6602, 0x4212)  # and the next one's after, going round
    w(0x3A00, 0xE24D, 0xDA41, 0xDA41)               # d5 = 16 times the set + 2 times the place: its tag
    w(0x4270, 0x5000)                               # clr.w   (a0,d5.w)         nothing there until it's whole
    w(0x4870, 0x5000)                               # pea     (a0,d5.w)         keep where the tag is,
    w(0xE859, 0x45F8, MEMORY_TILES, 0xD4C1, 0xD4C0)  # a2 = the place: tiles + 4096 * place + 32 * set
    w(0x2F0A)                                       # move.l  a2,-(sp)          and the place
    w(0xE05C)                                       # ror.w   #8,d4             the tile number itself
    w(0x3A04, 0xEE4D)                               # move.w d4,d5 / lsr.w #7,d5     which 128 it's in
    w(0x41F9, RUN_STARTS >> 16, RUN_STARTS & 0xFFFF)  # lea   RUN_STARTS,a0
    w(0x7200, 0x1230, 0x5000, 0xE749)               # d1 = 8 times the run to start from
    w(0x41F9, INDEX >> 16, INDEX & 0xFFFF)          # lea     INDEX,a0
    c.label('run')
    w(0xB870, 0x100A)                               # cmp.w   10(a0,d1.w),d4    the next run's first tile
    s(0x6500, 'unpack')                             # bcs.s   unpack            is past it: this is the run
    w(0x5041)                                       # addq.w  #8,d1
    s(0x6000, 'run')                                # bra.s   run
    c.label('unpack')
    w(0x3A01)                                       # move.w  d1,d5
    w(0x4EB9, DECODE >> 16, DECODE & 0xFFFF)        # jsr     DECODE            32 bytes to (a1)+
    w(0x245F, 0x285F)                               # movea.l (sp)+,a2 / movea.l (sp)+,a4
    w(0x41E9, 0xFFE0)                               # lea     -32(a1),a0        the tile just unpacked
    w(*[0x24D8] * 8)                                # move.l  (a0)+,(a2)+ eight times
    w(0x38AD, 0xFFFE)                               # move.w  -2(a5),(a4)       now the place holds this tile
    w(0x41F8, MEMORY_TAGS)                          # lea     tags,a0
    l(0x6000, 'count')                              # bra.w   count
    return c.finish(), c.labels['rts']


def run_starts(tiles):
    """For each 128 tile numbers, the run that the first of them belongs to."""
    blocks = (tiles.count >> 7) + 1                 # enough for every tile number the index has
    return bytes(max(0, min(bisect.bisect_right(tiles.firsts, 128 * block) - 1, INDEX_LAST)) for block in range(blocks))


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
    for source in (test_rom(rom), test_rom(patched)):
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


def sound_link(rom, count_in=48, count_out=48):
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
    assert code[-2:] == bytes.fromhex('4E75')
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
    for source in (test_rom(rom), test_rom(patched)):
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


def fight_pace():
    """Hold a fight's two loops to the pace they ran at in the original.

    A fight has no clock. Each loop draws and goes around again, so it ran as fast as the
    drawing allowed, and the faster object graphics made fights nearly three times too fast.
    Each drawing call now waits until the frame before its picture is due, counted from the
    last picture, and then draws as before. Returns the code and where its two routines start.
    """
    c = Code(FIGHT_PACE)
    starts = []
    for frames, draw, after in ((FIGHT_PASS_FRAMES, 0x15738, 0x158EC), (FIGHT_STEP_FRAMES, 0x15768, 0x14E3A)):
        starts.append(FIGHT_PACE + len(c.data))
        c.words(0x2F00, 0x2038, FIGHT_SHOWN, 0x5080 | ((frames - 1) << 9))  # d0 = last picture + frames - 1
        c.label(f'wait{frames}')
        c.words(0xB0B8, 0x9624); c.short(0x6E00, f'wait{frames}')           # not there yet
        c.words(0x201F, 0x4EB9, draw >> 16, draw & 0xFFFF)
        c.words(0x21F8, 0x9624, FIGHT_SHOWN)
        c.words(0x4EF9, after >> 16, after & 0xFFFF)
    code = c.finish()
    return code, starts


def music_keep():
    """Stop the level's song starting over when nothing has really interrupted it.

    At about twenty places the game asks for another song, does something, and then asks for
    the level's song back. A request only takes effect at the next frame. When the something
    turns out to be nothing, both requests land in one frame, the other song is never heard,
    and the level's song starts again from the top. The original does this constantly.

    The new request routine notices a request made while another is still waiting. If it
    asks for the song that's playing anyway, both are dropped and the music carries on.
    Everything else goes through as before. Returns the code and where the two routines start.
    """
    c = Code(MUSIC_KEEP)
    w, s = c.words, c.short
    w(0x0C39, 0x0001, 0xFFFF, 0x0230); s(0x6600, 'fresh')       # is a request waiting?
    w(0xB0B8, SOUNDING); s(0x6600, 'request')                   # for the song that's playing anyway?
    w(0x23C0, 0xFFFF, 0x01E8, 0x4239, 0xFFFF, 0x0230, 0x4E75)   # then forget both
    c.label('fresh')
    w(0x4A38, SILENT); s(0x6600, 'quiet')
    w(0x21F9, 0xFFFF, 0x01E8, SOUNDING); s(0x6000, 'request')   # note what's playing now
    c.label('quiet')
    w(0x21FC, 0xFFFF, 0xFFFF, SOUNDING)                         # nothing is
    c.label('request')
    w(0x51F8, SILENT, 0x23C0, 0xFFFF, 0x01E8, 0x13FC, 0x0001, 0xFFFF, 0x0230, 0x4E75)
    end = MUSIC_KEEP + len(c.data)
    w(0x13FC, 0x0001, 0xFFFF, 0x022F, 0x50F8, SILENT, 0x4E75)   # a song ran out: remember it's quiet
    code = c.finish()
    return code, (MUSIC_KEEP, end)


def saves():
    """Battery saves, and a second try after Game Over.

    A save is a level's certificate, kept in battery RAM when the game makes it at the end
    of the level before. There's a place for each of levels 2 to 8, so a save replaces the
    one made the last time that level was reached. Loading one puts it back in the
    certificate's fields and starts the level from them, which is what the game itself does
    between levels. A save is believed only if its digits and the game's own check agree.

    Returns the code, where its three entries are, and the messages with their addresses.
    """
    text, places = bytearray(), {}
    for name, words in SAVE_MESSAGES.items():
        places[name] = SAVE_TEXT + len(text)
        text += words.encode('ascii') + b'\0'
    assert SAVE_TEXT + len(text) <= SAVE_TEXT_END and max(len(m) for m in SAVE_MESSAGES.values()) < 0x50
    c = Code(SAVES)
    w, s, l = c.words, c.short, c.long
    starts = {}
    all_mine, back = (0x48E7, 0x07C0), (0x4CDF, 0x03E0)     # movem.l d5-d7/a0-a1 to and from the stack

    def say(name, routine):
        w(0x41F9, places[name] >> 16, places[name] & 0xFFFF)   # lea the message,a0
        l(0x6100, routine)                                      # bsr

    # Show the message at a0 in a new box, with d0 as its number. Flags as the game's routine leaves them.
    c.label('say')
    s(0x6100, 'copy')
    w(0x1940, 0x0940)                               # move.b  d0,$940(a4)       the number a message can show
    w(0x42AC, 0x0948)                               # clr.l   $948(a4)          the four bytes the game clears
    w(0x4EB9, NEW_BOX >> 16, NEW_BOX & 0xFFFF)
    c.label('say on')                               # as the game's routine starts, but with our text
    w(0x103C, 0x0000, 0x4278, 0x9644)               # move.b #0,d0 / clr.w $9644.w
    w(0x1940, 0x0945, 0x3F01, 0x1942, 0x0944)       # move.b d0,$945(a4) / move.w d1,-(sp) / move.b d2,$944(a4)
    w(0x396C, 0x0300, 0x0942)                       # keep the text address the game had
    w(0x397C, (TEXT_BUFFER & 0xFF) << 8 | TEXT_BUFFER >> 8, 0x0300)    # ours, low byte first
    w(0x4202)                                       # clr.b   d2
    w(0x4EF9, SAY_LOOP >> 16, SAY_LOOP & 0xFFFF)    # the game's routine carries on, and returns for us
    c.label('say more')                             # the same, after what's in the box already
    s(0x6100, 'copy')
    w(0x1940, 0x0940)
    s(0x6000, 'say on')
    c.label('copy')
    w(0x43F8, TEXT_BUFFER)                          # lea     TEXT_BUFFER.w,a1
    c.label('letter')
    w(0x12D8)                                       # move.b  (a0)+,(a1)+
    s(0x6600, 'letter')
    w(0x4E75)

    # a1 = the place in battery RAM for level d6
    c.label('place')
    w(0x13FC, 0x0001, 0x00A1, 0x30F1)               # move.b  #1,$A130F1        battery RAM on, for boards that ask
    w(0x43F9, SAVE_RAM >> 16, SAVE_RAM & 0xFFFF)    # lea     SAVE_RAM,a1
    w(0x7000, 0x1006, 0xEB48, 0xD2C0)               # 32 bytes of address, so 16 of RAM, for each level
    w(0x41EC, CERTIFICATE, 0x7E0C)                  # lea CERTIFICATE(a4),a0 / moveq #12,d7
    w(0x4E75)

    # Put level d6's save in the certificate's fields. Z set if it's a real one.
    c.label('fetch')
    s(0x6100, 'place')
    c.label('digit')
    w(0x1011, 0x0C00, 0x0010)                       # move.b (a1),d0 / cmpi.b #16,d0
    s(0x6400, 'no')                                 # bcc.s   no                not a digit
    w(0x10C0, 0x5489)                               # move.b d0,(a0)+ / addq.l #2,a1
    l(0x51CF, 'digit')
    w(0xBC2C, CERTIFICATE_LEVEL)                    # cmp.b   CERTIFICATE_LEVEL(a4),d6
    s(0x6600, 'no')                                 # bne.s   no                for some other level
    w(0x197C, 13, 0x0D8B, 0x700D)                   # 13 digits, in the field and in d0
    w(0x4EB9, CHECK_CERTIFICATE >> 16, CHECK_CERTIFICATE & 0xFFFF)
    w(0x2E2C, 0x0304, 0xBEAC, CERTIFICATE)          # move.l $304(a4),d7 / cmp.l CERTIFICATE(a4),d7
    w(0x4E75)
    c.label('no')
    w(0x7001, 0x4E75)                               # moveq #1,d0 / rts

    # A level has ended: make its certificate, save it, show it, and say so if the save kept.
    starts['level end'] = SAVES + len(c.data)
    w(0x4EB9, MAKE_CERTIFICATE >> 16, MAKE_CERTIFICATE & 0xFFFF)
    w(*all_mine)
    w(0x7C00, 0x1C2C, CERTIFICATE_LEVEL)            # moveq #0,d6 / move.b CERTIFICATE_LEVEL(a4),d6
    s(0x6100, 'place')
    c.label('write')
    w(0x1298, 0x5489)                               # move.b (a0)+,(a1) / addq.l #2,a1
    l(0x51CF, 'write')
    w(0x123C, 0x00D7, 0x4EB9, SAY_FIRST >> 16, SAY_FIRST & 0xFFFF)  # "End of level! Here is your certificate:"
    w(0x4202)                                       # clr.b   d2
    c.label('show')                                 # its 13 letters, as the game's routine does it
    w(0x41EC, CERTIFICATE, 0x1230, 0x2000)          # move.b  (a0,d2.w),d1
    w(0x41F9, DIGIT_LETTERS >> 16, DIGIT_LETTERS & 0xFFFF, 0x1030, 0x1000)
    w(0x4EB9, PRINT >> 16, PRINT & 0xFFFF)
    w(0x5202, 0xB42C, 0x0D8B)                       # addq.b #1,d2 / cmp.b $D8B(a4),d2
    s(0x6600, 'show')
    l(0x6100, 'place')                              # read it back
    c.label('same')
    w(0x1011, 0x5489, 0xB018)                       # move.b (a1),d0 / addq.l #2,a1 / cmp.b (a0)+,d0
    l(0x56CF, 'same')                               # dbne    d7,same
    w(0x41F9, places['saved'] >> 16, places['saved'] & 0xFFFF)
    s(0x6700, 'kept')
    w(0x41E8, len(SAVE_MESSAGES['saved']) - 1)      # it didn't keep: only the message's end, which waits
    c.label('kept')
    l(0x6100, 'say more')
    w(*back, 0x4E75)

    # Game Over: offer the level again. Not after winning: the game ends by way of Game Over,
    # with the wizard alive on the last level, and then it says what the original said.
    starts['game over'] = SAVES + len(c.data)
    w(0x0C2C, 0x0007, 0x0D70)                       # cmpi.b  #7,$D70(a4)       the last level?
    s(0x6600, 'lost')
    w(0x0C2C, 0x0010, WIZARD_HEALTH)                # cmpi.b  #$10,health(a4)   and alive?
    s(0x6500, 'lost')
    w(0x123C, 0x009C, 0x4EF9, SAY >> 16, SAY & 0xFFFF)  # "Game Over / Play again?"
    c.label('lost')
    w(0x48E7, 0x00C0)                               # movem.l a0-a1,-(sp)
    say('over', 'say')
    w(0x4CDF, 0x0300)
    w(0x4EB9, ANSWER >> 16, ANSWER & 0xFFFF)
    s(0x6500, 'ended')                              # NO: on to the prompts a game starts with
    w(0x4A2C, 0x0D70)                               # tst.b   $D70(a4)          which level?
    s(0x6600, 'fields')
    w(0x50F8, AGAIN, 0x4E75)                        # the first: a new game, without asking
    c.label('fields')
    w(0x50EC, 0x0D88)                               # any other: its certificate is still in the fields
    c.label('ended')
    w(0x4E75)

    # Starting a game.
    starts['loader'] = SAVES + len(c.data)
    w(0x422C, 0x0DD0)                               # clr.b   $DD0(a4)          as the original
    w(0x4A2C, 0x0D88)                               # tst.b   $D88(a4)          told to load from the fields?
    s(0x6700, 'ask')
    w(0x422C, 0x0D88)
    c.label('from fields')
    w(0x4EF9, LOADER_FROM_FIELDS >> 16, LOADER_FROM_FIELDS & 0xFFFF)
    c.label('ask')
    w(0x4A38, AGAIN)                                # tst.b   AGAIN.w
    s(0x6700, 'menu')
    w(0x4238, AGAIN)
    c.label('new')
    w(0x4EF9, LOADER_NEW >> 16, LOADER_NEW & 0xFFFF)
    c.label('menu')
    w(0x4A78, 0x962E)                               # tst.w   $962E.w           as the original
    s(0x6600, 'new')
    w(*all_mine)
    w(0x7C07)                                       # moveq   #7,d6            the furthest level saved
    c.label('find')
    l(0x6100, 'fetch')
    s(0x6700, 'have')
    w(0x5306)                                       # subq.b  #1,d6
    s(0x6600, 'find')
    c.label('old')                                  # nothing saved, or NO: the game's own prompt
    w(*back, 0x4EF9, LOADER_ASK >> 16, LOADER_ASK & 0xFFFF)
    c.label('have')
    say('continue', 'say')
    w(0x4EB9, ANSWER >> 16, ANSWER & 0xFFFF)
    s(0x6500, 'old')
    c.label('pick')
    w(0x7000, 0x1006, 0x5200)                       # d0 = the level's number, as players count
    w(0x50F8, 0x9642)                               # st.b    $9642.w           all at once, not typed
    say('pick', 'say')
    w(0x4278, 0x9642)                               # clr.w   $9642.w
    w(0x4EB9, SHOW >> 16, SHOW & 0xFFFF)            # and put it on the screen
    c.label('let go')
    w(0x4A38, PAD)                                  # tst.b   PAD.w
    s(0x6600, 'let go')
    c.label('press')
    w(0x1038, PAD)                                  # move.b  PAD.w,d0
    s(0x6700, 'press')
    w(0x7A01, 0x0800, 0x0000)                       # moveq #1,d5 / btst #0,d0      up
    s(0x6600, 'step')
    w(0x7AFF, 0x0800, 0x0001)                       # moveq #-1,d5 / btst #1,d0     down
    s(0x6600, 'step')
    w(0x0200, 0x00F0)                               # andi.b  #$F0,d0           a button?
    s(0x6700, 'let go')
    w(*back)
    l(0x6000, 'from fields')
    c.label('step')                                 # the next saved level that way, going round
    w(0xDC05)                                       # add.b   d5,d6
    s(0x6600, 'not under')
    w(0x7C07)
    c.label('not under')
    w(0x0C06, 0x0008)                               # cmpi.b  #8,d6
    s(0x6600, 'not over')
    w(0x7C01)
    c.label('not over')
    l(0x6100, 'fetch')
    s(0x6600, 'step')
    s(0x6000, 'pick')
    return c.finish(), starts, bytes(text)


def text_wait():
    """Message text with a button held: twice the typing speed, and pauses at full length.

    The game types a letter, then waits some units: 5 after a letter, more after punctuation,
    40 or 140 at the end of a page. Every fourth unit is a real wait of two frames. In the
    original that wait gave up at once if a button was down, and stopped letters being drawn
    one at a time until the next space, so with a button held whole words appeared as fast as
    they could be worked out and the pause at the end of a page was gone too.

    Now a held button shortens the waits while typing and makes no difference to a pause.
    After a letter the wait is one frame, every other time it comes around. After punctuation
    it's one frame every time. With the frame it takes to draw each letter, that comes to
    twice the usual typing speed. Every letter is drawn. A fresh press of A or C still ends a
    pause, as it always did: that's handled by the caller, and isn't changed. B and Start no
    longer do, since in the original they did it only by making every wait instant.
    """
    c = Code(TEXT_WAIT_NEW)
    w, s = c.words, c.short
    w(0x066C, 0x0001, 0x0FE4, 0x026C, 0x0003, 0x0FE4); s(0x6600, 'out')    # every fourth unit, as before
    w(0x48E7, 0xC000)
    w(0x1238, 0x962A, 0x0201, 0x00F0); s(0x6700, 'full')                   # no button held
    w(0x0C2C, TEXT_TYPING_UNITS, 0x094C); s(0x6200, 'full')                # a pause, not typing
    w(0x0C2C, TEXT_LETTER_UNITS, 0x094C); s(0x6200, 'frame')               # after punctuation
    w(0x0878, 0x0000, TEXT_TURN); s(0x6700, 'done')                        # after a letter: every other time
    c.label('frame')
    w(0x4EB9, 0x0001, 0x4E3A); s(0x6000, 'done')                           # one frame
    c.label('full')
    w(0x4281, 0x3200, 0xD2B8, 0x9624)                                      # the wait the game always made
    c.label('wait')
    w(0xB2B8, 0x9624); s(0x6A00, 'wait')
    c.label('done')
    w(0x4CDF, 0x0003)
    c.label('out')
    w(0x4E75)
    return c.finish()


def death_pause():
    """Show "Prepare to continue..." for 3 seconds, or until a button is pressed.

    The message used to end in three short pauses, about a second in all, which made the
    retry after a death feel abrupt. A press of A or C ended whichever pause it fell in, and
    B or Start did nothing. Now the message has no pauses of its own. This routine shows it,
    then waits up to DEATH_PAUSE_FRAMES frames for a fresh press of A, B, C or Start. A
    button already down when the message appears doesn't count until it has been let go.
    After a press it waits for the buttons to be let go, so a C still down as the game
    carries on doesn't open the inventory.
    """
    c = Code(DEATH_PAUSE)
    w = c.words
    w(0x123C, 0x009E)                                       # move.b  #$9E,d1      the message
    w(0x4EB9, SAY >> 16, SAY & 0xFFFF)                      # jsr     SAY          as the game did
    w(0x48E7, 0xE000)                                       # movem.l d0-d2,-(a7)
    w(0x1238, PAD)                                          # move.b  PAD.w,d1     buttons down now
    w(0x343C, DEATH_PAUSE_FRAMES - 1)                       # move.w  #frames-1,d2
    c.label('frame')
    w(0x4EB9, FRAME_WAIT >> 16, FRAME_WAIT & 0xFFFF)        # jsr     FRAME_WAIT
    w(0x1038, PAD, 0x0200, 0x00F0)                          # move.b PAD.w,d0 / andi.b #$F0,d0
    w(0x4601, 0xC200)                                       # not.b d1 / and.b d0,d1: pressed since
    c.short(0x6600, 'done')                                 # bne     done
    w(0x1200)                                               # move.b  d0,d1
    c.long(0x51CA, 'frame')                                 # dbra    d2,frame
    c.short(0x6000, 'out')                                  # bra     out
    c.label('done')                                         # a press: wait for it to be let go,
    w(0x4EB9, FRAME_WAIT >> 16, FRAME_WAIT & 0xFFFF)        #   or the game takes C as opening
    w(0x1038, PAD, 0x0200, 0x00F0)                          #   the inventory
    c.short(0x6600, 'done')
    c.label('out')
    w(0x4CDF, 0x0007, 0x4E75)                               # movem.l (a7)+,d0-d2 / rts
    return c.finish()


def mask_tables(rom, as_game=False):
    """Every mask shape at every horizontal shift.

    The game shifts the right-hand cell's shape by 31 minus the offset, which leaves it one
    bit out of line and miscolors stray pixels along mask edges. 32 lines it up. as_game
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
    exact = test_rom(patched)                       # the new routine with the game's own shift
    exact[MASK_TABLES:MASK_TABLES + 0x2000] = mask_tables(rom, as_game=True)
    for source in (test_rom(rom), exact):
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


def memory_check(count):
    """Ask the new routine for every tile, so that each is unpacked, found, pushed out and unpacked again.

    For each tile n the list is n, n, as many other tiles of n's set as it has places, and n.
    All must match the table at TILES. FF0000 counts longs that differ and calls that didn't
    fill a slot for each, FF0004 holds the next tile number, and FF000C becomes 600DF00D at the end.

    Before that, one test that tiles really are remembered: tile 1 is asked for, the copy
    kept of it is turned inside out, and it is asked for again. FF0010 becomes 1 if the
    second answer is the inside-out copy, and the set's turn has moved on.
    """
    step = MEMORY_SETS
    c = Code(0x1F0000)
    w, s, l = c.words, c.short, c.long
    w(0x4239, 0xFFFF, 0x0010)                       # clr.b   $FFFF0010
    s(0x6100, 'forget')                             # bsr.s   forget
    w(0x4278, 0x92F6, 0x31FC, 0x0100, 0x92FA, 0x31FC, 1, 0x931A)   # a list of tile 1 alone
    w(0x4EB9, ROUTINE >> 16, ROUTINE & 0xFFFF)      # jsr the routine
    w(0x0C78, 0x0100, MEMORY_TAGS + 16)             # set 1's first place holds tile 1?
    s(0x6600, 'not kept')
    w(0x0C38, 1, MEMORY_TURNS + 1)                  # and its second place is next?
    s(0x6600, 'not kept')
    w(0x41F8, MEMORY_TILES + 32, 0x7007)            # lea the tile kept,a0 / moveq #7,d0
    c.label('turn')
    w(0x4698)                                       # not.l   (a0)+
    l(0x51C8, 'turn')                               # dbra    d0,turn
    w(0x4EB9, ROUTINE >> 16, ROUTINE & 0xFFFF)      # ask again; the answer goes in the second slot
    w(0x43F9, 0xFFFF, 0x2020, 0x45F9, (TILES + 32) >> 16, (TILES + 32) & 0xFFFF, 0x7207)
    c.label('same')
    w(0x2019, 0x4680, 0xB09A)                       # move.l (a1)+,d0 / not.l d0 / cmp.l (a2)+,d0
    s(0x6600, 'not kept')
    l(0x51C9, 'same')                               # dbra    d1,same
    w(0x13FC, 0x0001, 0xFFFF, 0x0010)               # move.b  #1,$FFFF0010
    c.label('not kept')
    s(0x6100, 'forget')                             # bsr.s   forget
    s(0x6000, 'every tile')
    c.label('forget')                               # start with nothing remembered
    w(0x41F8, MEMORY_TAGS, 0x303C, (MEMORY_TILES - MEMORY_TAGS) // 2 - 1)
    c.label('clear')
    w(0x4258)                                       # clr.w   (a0)+
    l(0x51C8, 'clear')                              # dbra    d0,clear
    w(0x4E75)                                       # rts
    c.label('every tile')
    w(0x7C00, 0x383C, 0x0001)                       # moveq #0,d6 / move.w #1,d4
    c.label('tile')
    w(0x343C, step)                                 # move.w  #step,d2          the others lie above n,
    w(0x3004, 0x0640, step * MEMORY_WAYS, 0x0C40, count)
    s(0x6500, 'above')                              # bcs.s   above
    w(0x4442)                                       # neg.w   d2                or below it near the top
    c.label('above')
    w(0x4278, 0x92F6, 0x41F8, 0x92FA)               # clr.w $92F6.w / lea $92FA.w,a0
    w(0x3004, 0xE058, 0x30C0, 0x30C0)               # n twice, as the game stores it
    w(0x3A04, 0x7600 + MEMORY_WAYS - 1)             # move.w d4,d5 / moveq #places-1,d3
    c.label('others')
    w(0xDA42, 0x3005, 0xE058, 0x30C0)               # add.w d2,d5, and store it
    l(0x51CB, 'others')                             # dbra    d3,others
    w(0x3004, 0xE058, 0x30C0)                       # n again
    w(0x31FC, 3 + MEMORY_WAYS, 0x931A)              # how many are in the list
    w(0x4EB9, ROUTINE >> 16, ROUTINE & 0xFFFF)      # jsr the routine
    w(0x43F9, 0xFFFF, 0x2000)                       # lea     $FFFF2000,a1
    for _ in range(2):
        w(0x3004)                                   # move.w  d4,d0
        s(0x6100, 'compare')                        # bsr.s   compare
    w(0x3A04, 0x7600 + MEMORY_WAYS - 1)             # move.w d4,d5 / moveq #places-1,d3
    c.label('compare others')
    w(0xDA42, 0x3005)                               # add.w d2,d5 / move.w d5,d0
    s(0x6100, 'compare')                            # bsr.s   compare
    l(0x51CB, 'compare others')                     # dbra    d3
    w(0x3004)                                       # move.w  d4,d0
    s(0x6100, 'compare')                            # bsr.s   compare
    w(0x0C78, 3 + MEMORY_WAYS, 0x92F6, 0x6702, 0x5286)  # that many slots filled, or count it
    w(0x5244, 0x0C44, count)                        # addq.w #1,d4 / cmpi.w #count,d4
    l(0x6600, 'tile')                               # bne.w   tile
    w(0x23C6, 0xFFFF, 0x0000, 0x7000, 0x3004, 0x23C0, 0xFFFF, 0x0004)
    w(0x23FC, 0x600D, 0xF00D, 0xFFFF, 0x000C)       # move.l  #$600DF00D,$FFFF000C
    w(0x60FE)                                       # bra.s   *
    c.label('compare')                              # the next tile out against tile d0 of the table
    w(0x0280, 0x0000, 0xFFFF, 0xEB88, 0x0680, TILES >> 16, TILES & 0xFFFF, 0x2440, 0x7207)
    c.label('long')
    w(0xB38A, 0x6702, 0x5286)                       # cmpm.l (a2)+,(a1)+ / beq.s / addq.l #1,d6
    l(0x51C9, 'long')                               # dbra    d1,long
    w(0x4E75)
    return c.origin, c.finish()


def finish_rom(rom, path):
    rom = bytearray(rom)
    rom[0x1A4:0x1A8] = (len(rom) - 1).to_bytes(4, 'big')
    total = sum(word(rom, i) for i in range(0x200, len(rom), 2)) & 0xFFFF
    rom[0x18E:0x190] = total.to_bytes(2, 'big')
    with open(path + '.new', 'wb') as f:          # whole or not at all, for tools reading it meanwhile
        f.write(rom)
    os.replace(path + '.new', path)


def test_rom(rom, table=b''):
    """A ROM with a second megabyte for a test, holding this script's unpacked tiles if given."""
    out = bytearray(rom) + table
    return out + b'\xff' * (TEST_SIZE - len(out))


def routine_check(tile_list):
    """Call the new routine with known registers, saving them afterward at FF0100."""
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


def peek(path, addresses, frames=3000, timeout=120):
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
                         timeout=timeout, env={**os.environ, 'HOME': home, 'SDL_VIDEODRIVER': 'dummy',
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
    boot_into(test_rom(rom, table), origin, code, CHECK_ROM)
    got = peek(CHECK_ROM, [0xFF0000 + i for i in (0, 1, 2, 3, 8, 9, 10, 11, 12, 13, 14, 15)])
    bad, checked, done = (int.from_bytes(got[a:a + 4], 'big') for a in (0, 4, 8))
    print(f'game decoder against this script: {checked} tiles checked, {bad} different')
    if bad or checked != count - 1 or done != 0x600DF00D:
        sys.exit('tile check FAILED')


def check_memory(patched, count, table, fixed):
    origin, code = memory_check(count)
    boot_into(test_rom(patched, table), origin, code, MEMORY_CHECK_ROM)
    got = peek(MEMORY_CHECK_ROM, [0xFF0000 + i for i in (0, 1, 2, 3, 4, 5, 6, 7, 12, 13, 14, 15, 16)], 30000, 600)
    bad, reached, done = (int.from_bytes(got[a:a + 4], 'big') for a in (0, 4, 8))
    kept = got[12] == 1
    print(f'new routine against this script, which the original gets wrong at {fixed}: {reached - 1} tiles each unpacked, '
          f'found, pushed out and unpacked again, {bad} wrong; a remembered tile is copied, not unpacked: '
          f'{"yes" if kept else "NO"}')
    if bad or reached != count or done != 0x600DF00D or not kept:
        sys.exit('tile memory check FAILED')


def check_routine(patched, table):
    tile_list = [0x1234, 0, 25793, 1, 0x1234, 25793, 0, 129, 257, 385, 513, 641, 1, 29671, 2, 0]
    origin, code, pattern_at, pattern = routine_check(tile_list)
    test = test_rom(patched)
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
    for source, label in ((test_rom(rom), 'original'), (test_rom(patched), 'patched')):
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
    check = '--check' in sys.argv[1:]
    tiles = Tiles(rom)
    if check:
        count = tiles.count + 1             # the game's search also accepts the end marker
        as_game = [tiles.unpack(n, tiles.run_by_game(n)) for n in range(count)]
        table = list(as_game)
        fixed = []
        for n in range(tiles.count):
            right = tiles.unpack(n, tiles.run_correct(n))
            if right != as_game[n]:
                table[n] = right
                fixed.append(n)
        check_decoder(rom, count, b''.join(as_game))
    out = bytearray(rom)
    added = []

    def add(at, data):
        """Put something new in the unused space, which must be unused and not already taken."""
        assert FREE <= at and at + len(data) <= FREE_END and set(rom[at:at + len(data)]) == {0xFF}, hex(at)
        assert all(at + len(data) <= a or b <= at for a, b in added), hex(at)
        added.append((at, at + len(data)))
        out[at:at + len(data)] = data

    code, _ = tile_memory()
    add(TILE_MEMORY, code)
    assert rom[ROUTINE:ROUTINE + 4] == bytes.fromhex('48E7FFFE')
    out[ROUTINE:ROUTINE + 6] = b'\x4e\xf9' + TILE_MEMORY.to_bytes(4, 'big')     # jmp
    for done in (RAW_DONE, PACKED_DONE):            # the decoder's two ways out become returns
        assert rom[done:done + 4] == bytes.fromhex('527892F6')                  # addq.w #1,$92F6.w
        out[done:done + 4] = bytes.fromhex('4E754E71')                          # rts, nop
    assert rom[DECODE:DECODE + 6] == bytes.fromhex('203050003600')
    add(RUN_STARTS, run_starts(tiles))
    end = INDEX + 8 * (INDEX_LAST + 1) + 2              # the index's end marker, one past the last tile:
    out[end:end + 2] = b'\xff\xff'                      #   now past any number, to stop the new search
    for old, new, code in ((MAP_TILES, MAP_TILES_NEW, map_tiles()), (TILE_SYNC, TILE_SYNC_NEW, tile_sync()),
                           (TABLE_RESET_TAIL, TABLE_RESET_NEW, table_reset_tail())):
        add(new, code)
        out[old:old + 6] = b'\x4e\xf9' + new.to_bytes(4, 'big')    # jmp
    assert rom[TABLE_RESET_TAIL:TABLE_RESET_TAIL + 6] == bytes.fromhex('4CDF01034E75')
    add(CELL_DATA_COPY, rom[CELL_DATA:CELL_DATA + CELL_DATA_SIZE])
    code = cells()
    out[CELLS:CELLS + len(code)] = code
    tables = mask_tables(rom)
    add(MASK_TABLES, tables)
    code = sound_link(rom)
    add(SOUND_LINK_NEW, code)
    out[SOUND_LINK:SOUND_LINK + 6] = b'\x4e\xf9' + SOUND_LINK_NEW.to_bytes(4, 'big')   # jmp
    code = sprite_mask()
    out[MASK:MASK + len(code)] = code
    code, starts = music_keep()
    add(MUSIC_KEEP, code)
    for at, was, start in ((SONG_REQUEST, '23C0FFFF01E813FC0001FFFF02304E75', starts[0]),
                           (SONG_END, '13FC0001FFFF022F4E75', starts[1])):
        assert rom[at:at + len(was) // 2] == bytes.fromhex(was)
        out[at:at + 6] = b'\x4e\xf9' + start.to_bytes(4, 'big')     # jmp
    code = text_wait()
    add(TEXT_WAIT_NEW, code)
    assert rom[TEXT_WAIT:TEXT_WAIT + 22] == bytes.fromhex('066C00010FE4026C00030FE4660000064EBA1F764E75')
    out[TEXT_WAIT:TEXT_WAIT + 6] = b'\x4e\xf9' + TEXT_WAIT_NEW.to_bytes(4, 'big')        # jmp
    assert rom[TEXT_NO_WAIT - 4:TEXT_NO_WAIT + 4] == bytes.fromhex('B03C000367000016')
    out[TEXT_NO_WAIT:TEXT_NO_WAIT + 4] = b'\x4e\x71' * 2                                 # two buttons held: no shortcut
    code, starts = fight_pace()
    add(FIGHT_PACE, code)
    for at, was, start in ((FIGHT_PASS_DRAW, '4EBA40A24EBA4252', starts[0]), (FIGHT_STEP_DRAW, '4EBA3FF44EBA36C2', starts[1])):
        assert rom[at:at + 8] == bytes.fromhex(was)
        out[at:at + 8] = b'\x4e\xb9' + start.to_bytes(4, 'big') + b'\x4e\x71'      # jsr, nop
    out[BOOT_CHECK_BRANCH:BOOT_CHECK_BRANCH + 2] = b'\x4e\x71'      # nop
    code, starts, text = saves()
    add(SAVES, code)
    out[SAVE_TEXT:SAVE_TEXT + len(text)] = text     # in what's left of the old object routine, never run now
    for at, was, start, fill in ((LEVEL_END, '4EBA160E4EBA17B4', starts['level end'], b'\x4e\xb9'),
                                 (GAME_OVER_TEXT, '123C009C4EBAA70A4E75', starts['game over'], b'\x4e\xf9'),
                                 (LOADER, '422C0DD0102C0D886706', starts['loader'], b'\x4e\xf9')):
        assert rom[at:at + len(was) // 2] == bytes.fromhex(was)
        out[at:at + 6] = fill + start.to_bytes(4, 'big')        # jsr or jmp
    out[LEVEL_END + 6:LEVEL_END + 8] = b'\x4e\x71'               # nop
    code = death_pause()                            # in the old tile sync's body, after its jmp
    assert DEATH_PAUSE + len(code) <= DEATH_PAUSE_END and out[DEATH_PAUSE:DEATH_PAUSE_END] == rom[DEATH_PAUSE:DEATH_PAUSE_END]
    out[DEATH_PAUSE:DEATH_PAUSE + len(code)] = code
    assert rom[RETRY_MESSAGE:RETRY_MESSAGE + 8] == bytes.fromhex('123C009E4EBA4B5C')
    out[RETRY_MESSAGE:RETRY_MESSAGE + 8] = b'\x4e\xb9' + DEATH_PAUSE.to_bytes(4, 'big') + b'\x4e\x71'   # jsr, nop
    assert rom[PREPARE_TEXT:PREPARE_TEXT + 26] == b'Prepare to continue...]]]='
    out[PREPARE_TEXT + 22:PREPARE_TEXT + 26] = b'===='              # no pauses: the routine waits
    assert rom[SAVE_HEADER:SAVE_HEADER + 12] == b' ' * 12
    out[SAVE_HEADER:SAVE_HEADER + 12] = b'RA\xf8\x20' + (SAVE_RAM).to_bytes(4, 'big') + SAVE_RAM_END.to_bytes(4, 'big')
    os.makedirs(BUILD, exist_ok=True)
    finish_rom(out, OUTPUT)
    if check:
        check_memory(out, count, b''.join(table), fixed)
        check_routine(out, b''.join(table))
        check_background(rom, out)
        check_mask(rom, out)
        check_cells(rom, out)
        check_sound(rom, out)
    used = sum(b - a for a, b in added)
    print(f'{used} bytes added in the unused space at {FREE:06X}, {FREE_END - FREE - used} left')
    print(f'wrote {os.path.relpath(OUTPUT, ROOT)}')


if __name__ == '__main__':
    main()

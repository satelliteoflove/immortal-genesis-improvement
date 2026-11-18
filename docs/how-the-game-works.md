# How the game works

Notes from running and disassembling The Immortal (USA, Europe). Addresses are for that
ROM. Each section says what was seen happening in the running game and what has only been
read from the code so far. Timing comes from PicoDrive and was checked against BlastEm in two
builds, described below. None of it has been confirmed on real hardware.

`tools/harness/levels.py` reproduces the first timing table below and
`tools/harness/compare_cores.py` the second.

## Useful RAM

The game keeps most of its variables relative to a base of `FF0300`.

| Address | What it holds | Status |
|---|---|---|
| `FF1070` | Current level, 0 to 7 | Seen |
| `FF1051` | Current room | Seen |
| `FF109A` | Retries left on this level | Seen |
| `FF1073` | Set to restart the level | Seen |
| `FF1088` | Set to skip the "New game?" prompt and load from the fields below | Seen |
| `FF1091` | Level to load | Seen |
| `FF1090` to `FF1098` | The rest of what a certificate carries | Read from code |
| `FF9624` | Count of vertical blanks (long) | Seen |
| `FF12E6` | The count at which the next tick may begin (long) | Seen |
| `FF962A` | Pad 1, as read in the vertical blank | Read from code |

## The main loop

The loop is at `013470`. Each pass updates the game, draws if nothing has ended the level,
and then waits at `01349C` until the vertical blank count reaches a deadline. When the wait
ends, the deadline is set to the current count plus 5 (`0134A6`).

So the game runs at one tick every 5 video frames, 12 a second on a 60 Hz console, and
that's what sets the speed of the game. When a tick takes longer than 5 frames the next one
simply starts late, and the game has no way of catching up, so slowdown is lost time.

Raising the rate wouldn't make the game smoother by itself, because movement and timing are
counted in ticks and everything would run faster. A higher rate would need the game's
movement and timers changed to match.

## Death and retries

Seen in the running game:

- Each level starts with 2 retries, so the wizard has three lives per level. The count is
  set when a level starts (`012DFA`).
- After a fatal fall, the game holds on the scene for at least 3 seconds, unless a button
  is pressed, which skips the wait at once.
- With a retry left, it shows "Prepare to continue..." and puts the wizard back in the same
  room, at what looks like the room's entrance.
- With none left, it shows "Game Over", then "Play again?", then the "New game?" prompt.
  YES goes back to the very first room of the game. NO asks for a certificate.

The retry handling is at `0081D6`. It skips the retry altogether on the last level, level 8
(`0081DE`), which hasn't been tested in play. It also has special cases for levels 2, 4, 5,
7 and 8 that reset particular things on a retry, and those haven't been worked through.

## Certificates

These are the game's passwords. The code at `012876` gathers the values and `012804` works
out a four-digit check over them. Going by the code, a certificate holds the next level, a
three-digit number that is probably gold, one other value (`FF1071`), and flags for
particular carried items, some of them depending on the level. None of that has been
confirmed by entering one.

Between levels the game sets the flag at `FF1088` and loads straight from those fields, with
no typing. Setting the same flag by hand, with a level number, does load that level, which
is how the harness reaches all eight.

## Saving

Nothing has been built or tested here. This is what the ROM and the code read so far suggest.

The ROM is 1 MB and its header's save RAM field is blank, so battery RAM could sit at the
usual `200000`, well clear of the ROM. None of the code reached so far touches that area or
the cartridge's mapper port, though only part of the code has been reached. The header
checksum isn't read, but the game does check itself at boot: `0FFFB0` adds up the first
megabyte and halts on a solid screen if the total is wrong. Any patch has to get past that,
and ours turns off the branch at `0FFFD0`.

What a certificate holds is only a handful of small values, gathered when a level ends
(`012876`), so saving at the start of a level would take very little space. Saving in the
middle of a level would mean keeping the state of its rooms and objects, and how much that
comes to isn't known.

There's a run of about 10 KB of unused-looking `FF` bytes at `0FD65C`, and the ROM could also
be made larger, so new code should have room.

## Drawing

Only partly explored. The routine at `02E3E4` builds graphics for objects, 32 bytes per
tile, into RAM at `FF2000`. The code around `014802` queues the matching sprites, in blocks
of 4 by 4 tiles. `01428C` handles the queue afterwards. How the room itself reaches the
screen hasn't been traced yet.

Object tiles are numbered from 1 to 29,670, and tile 0 is blank. The index at `02DCEC` splits
them into runs, each with a fixed packed size per tile. Most are compressed with one fixed
code tree, and the rest are stored whole. The tree is written out as code from `02E6D6`, one
test and branch per bit, with each packed byte first spread into 8 bytes through the table at
`02D4EC`. That made an object tile cost about 5,000 cycles on level 6, every time it was
needed, with nothing kept between uses.

### The missing torch flame

The search through that index accepts a tile number equal to the first tile of the *next*
run. It's harmless nearly everywhere, because the two runs agree on where such a tile starts
and the tree stops by itself after 32 bytes. It goes wrong at one spot: tile 25793 begins the
final run of stored tiles, and the search lands on the run before it, so the stored bytes get
decoded as if compressed. On level 4 that tile is the top of the wall torch's flame, so the
original game draws the torch with the top of its flame missing. Comparing the original ROM's
picture with the corrected tile shows it. The walks also asked for this tile on levels 2, 3
and 5 to 8, and those uses haven't been looked at.

## Performance

The wizard was walked at random for 200 seconds on each level, the same way every run, with
levels reached by the jump described above. A tick is late when it takes more than 5 video
frames. Gaps of 12 frames or more were left out, since those are messages and transitions.

| Level | Ticks | Late | Worst gap (frames) | Object graphics, cycles per tick: on time / late |
|---|---|---|---|---|
| 1 | 909 | 1% | 8 | 206k / 146k |
| 2 | 1140 | 25% | 11 | 156k / 168k |
| 3 | 1997 | 9% | 9 | 123k / 147k |
| 4 | 1357 | 16% | 9 | 166k / 166k |
| 5 | 1210 | 42% | 11 | 142k / 338k |
| 6 | 1876 | 51% | 11 | 327k / 496k |
| 7 | 1599 | 14% | 8 | 195k / 238k |
| 8 | 1767 | 19% | 7 | 122k / 125k |

Across all levels, 23% of ticks were late. A tick has about 639k cycles to work with.

On levels 5 and 6, late ticks spend far more time building object graphics, so that routine
is the first thing to look at there. On levels 2, 4 and 8 it costs about the same whether
the tick is late or not, so something else is holding those back, and that isn't known yet.
A random walk also isn't how anyone plays, so these figures show where to look and don't
measure what a player would feel.

### PicoDrive against BlastEm

The same scripted opening, level jump and random walks were run on both emulators, using a
BlastEm libretro core built 2026-11-16 (version 1.0.1-pre). That build's emulation code was
last synced with BlastEm itself on 2026-07-27, so it lacks later upstream fixes, including
some to DMA. Ticks were read from the game's own deadline at
`FF12E6`. Across all levels 23.0% of ticks were late on both.

| Level | PicoDrive: ticks, late, worst gap | BlastEm: ticks, late, worst gap |
|---|---|---|
| 1 | 909, 1%, 8 | 906, 1%, 7 |
| 2 | 1136, 25%, 11 | 522, 20%, 9 |
| 3 | 1997, 9%, 9 | 1995, 9%, 9 |
| 4 | 1357, 16%, 9 | 1355, 16%, 9 |
| 5 | 1206, 43%, 11 | 1193, 44%, 11 |
| 6 | 1876, 51%, 11 | 1875, 52%, 11 |
| 7 | 1599, 14%, 8 | 1567, 14%, 8 |
| 8 | 1767, 19%, 7 | 1767, 19%, 6 |

Level 2 is the weak row. Its walks wander into deaths and prompts that stop the game, and
they do so at different moments on each emulator, so it has few ticks and they aren't
comparable. On BlastEm two of its four walks ended at Game Over.

PicoDrive shows a few ticks 4 frames apart (1.9%). BlastEm shows none, so those look like a
PicoDrive artifact, and the game's tick never runs early.

PicoDrive stays the tool for finding where time goes, since only its profiling build counts
cycles per instruction. BlastEm is the check on whether a change really helps.

### The BlastEm fork

Our reference is now a build of [ulalume/blastem](https://github.com/ulalume/blastem), which
can measure cycles between chosen addresses without changing the ROM. It's 10 changes behind
BlastEm itself. Two of those are DMA fixes for sources from `800000` to `DFFFFF`. The game
never used that range in these runs: on all eight levels, every DMA from the 68000 read from
work RAM (`FF0000` and up) or from ROM at `020000` to `03FFFF`. So those fixes weren't needed.
Two bugs in the fork had to be fixed first; see `docs/blastem-fork-fixes.md`.

`tools/harness/fork_timing.py` runs the same opening, jumps and walks. A second run of each
level gave identical video memory on all 6,499 frames, and so did a run with the profiler
turned off, on all eight levels.

| Level | Ticks | Late | Worst gap (frames) | Object graphics, cycles per tick: on time / late |
|---|---|---|---|---|
| 1 | 905 | 1% | 7 | 221k / 173k |
| 2 | 585 | 23% | 9 | 183k / 185k |
| 3 | 2082 | 10% | 9 | 129k / 161k |
| 4 | 1362 | 16% | 8 | 175k / 180k |
| 5 | 1199 | 41% | 11 | 141k / 360k |
| 6 | 1783 | 58% | 11 | 377k / 540k |
| 7 | 1528 | 15% | 8 | 207k / 255k |
| 8 | 1767 | 19% | 6 | 124k / 152k |

Across all levels 23.8% of ticks were late. Level 6 came out worse here, at 58% against about
51%, and object graphics cost roughly 10 to 15% more than PicoDrive's count on the busy
levels. The walks drift apart between emulators, so small differences between tables don't
mean much, but PicoDrive's cycle counts should be read as a little optimistic.

## The object graphics patch

`tools/build_rom.py` unpacks all the object tiles from your ROM into a new second megabyte
(`100000` onward, ending well short of `200000`), and replaces `02E3E4` with a routine that
copies them. The work per tile drops to a table lookup and a 32-byte copy.

`--check` tests this in the BlastEm fork. A test ROM runs the game's own decoder on every tile
number and compares the output with the unpacked table, and all 29,671 match, the torch tile
included as the game decodes it. A second test ROM confirms that the new routine writes the
right tiles and leaves every register as it found it. The old routine's work buffer at
`FF9656` is no longer written, and no other code we've reached refers to it. Clean-boot runs of
all eight levels never asked for a tile number outside the table.

Same opening, jumps and walks as the table above, on the same emulator:

| Level | Late before | Late now | Worst gap before | Worst gap now | Object graphics per tick, before / now (on-time ticks) |
|---|---|---|---|---|---|
| 1 | 1% | 1% | 7 | 7 | 221k / 16k |
| 2 | 23% | 22% | 9 | 10 | 183k / 21k |
| 3 | 10% | 11% | 9 | 7 | 129k / 15k |
| 4 | 16% | 17% | 8 | 7 | 175k / 18k |
| 5 | 41% | 24% | 11 | 7 | 141k / 18k |
| 6 | 58% | 20% | 11 | 7 | 377k / 21k |
| 7 | 15% | 14% | 8 | 7 | 207k / 13k |
| 8 | 19% | 19% | 6 | 6 | 124k / 11k |

Across all levels, late ticks went from 23.8% to 16.4%. Levels 5 and 6 are the ones that
changed. Late ticks elsewhere come from something else, which is the next thing to find. The
walks drift once timing changes, so small differences between the two columns don't mean much.

The game also runs closer to its intended speed on levels 5 and 6 now, which means less of the
slowdown players have been getting there, and enemies and traps there arrive sooner in real
time. None of this has been tried on real hardware.

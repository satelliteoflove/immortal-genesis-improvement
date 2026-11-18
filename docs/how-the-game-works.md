# How the game works

Notes from running and disassembling The Immortal (USA, Europe). Addresses are for that
ROM. Each section says what was seen happening in the running game and what has only been
read from the code so far. Timing comes from PicoDrive and was checked against BlastEm, a
much more exacting emulator. None of it has been confirmed on real hardware.

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
checksum doesn't appear to be read either, and it can be corrected anyway.

What a certificate holds is only a handful of small values, gathered when a level ends
(`012876`), so saving at the start of a level would take very little space. Saving in the
middle of a level would mean keeping the state of its rooms and objects, and how much that
comes to isn't known.

There's a run of about 10 KB of unused-looking `FF` bytes at `0FD65C`, and the ROM could also
be made larger, so new code should have room.

## Drawing

Only partly explored. The routine at `02E3E4` builds graphics for objects, 32 bytes per
tile, into RAM at `FF2000`, looking each one up with a binary search. The code around
`014802` queues the matching sprites, in blocks of 4 by 4 tiles. `01428C` handles the queue
afterwards. How the room itself reaches the screen hasn't been traced yet.

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
BlastEm libretro core built 2026-11-16. Ticks were read from the game's own deadline at
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

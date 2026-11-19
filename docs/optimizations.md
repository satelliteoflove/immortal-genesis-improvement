# Optimizing The Immortal

This is the record of the performance work on the Genesis version: what was slow, why, what
was changed, and how each change was checked. Addresses are for The Immortal (USA, Europe).
Everything here was measured in emulators with scripted random walks. None of it has been run
on real hardware or judged by someone playing it.

## Where it stands

The game runs one update, or tick, every 5 video frames. A tick that takes longer starts the next
one late, and the game never catches up, so a late tick is lost time.

| Level | Late: original | Late: object tiles | Late: background tiles | Late: now | Worst gap: original | Worst gap: now |
|---|---|---|---|---|---|---|
| 1 | 1% | 1% | 0% | 0% | 7 | 5 |
| 2 | 23% | 22% | 12% | 11% | 9 | 6 |
| 3 | 10% | 11% | 0% | 0% | 9 | 6 |
| 4 | 16% | 17% | 0% | 0% | 8 | 5 |
| 5 | 41% | 24% | 0% | 0% | 11 | 5 |
| 6 | 58% | 20% | 5% | 4% | 11 | 6 |
| 7 | 15% | 14% | 1% | 1% | 8 | 6 |
| 8 | 19% | 19% | 0% | 0% | 6 | 5 |
| **All** | **23.8%** | **16.4%** | **2.0%** | **1.7%** | | |

Each column adds one change to the one before it, and "now" has the sprite masking and camera
step changes as well. Late ticks stopped being the useful measure after the background tile
change, because nearly all that remain are deliberate waits. From there on the measure is
headroom: how much of a tick's time its work needs.

Gaps are in video frames, and 5 is on time. Gaps of 12 frames or more are left out, since those
are messages and transitions. Once the timing changes, the walks go different ways, so small
differences between columns don't mean much. Level 2's walks often end early at deaths and
prompts, which makes it the weakest row.

## How it was measured

A tick has about 639,000 68000 cycles, at about 127,800 per frame.

| Tool | What it's for |
|---|---|
| `tools/harness/fork_timing.py` | Late ticks per level on our build of the BlastEm fork. It also confirms that runs repeat exactly and that profiling doesn't change video memory |
| `tools/harness/tick_parts.py` | Splits ticks into parts between chosen addresses, comparing late ticks with on-time ones |
| `tools/harness/tick_parts.py --headroom` | How much work each tick does, leaving out its waits |
| `tools/harness/tick_parts.py --frames` | How many video frames each tick takes to get its picture ready. The best guide to whether a shorter tick would fit |
| `tools/harness/hotspots.py` | Cycles per routine on each level, using the PicoDrive profiling core |
| `tools/build_rom.py --check` | Builds the patch and runs its test ROMs |
| `tools/harness/sound_writes.py` | Logs every write two ROMs make to the sound chips over the same walks, and compares them |

Every walk boots the game, jumps to a level through the game's own reload flags, and plays
3,000 frames of random movement, four walks per level.

The useful habit was asking what late ticks do differently from on-time ones. Totals alone were
misleading: the routines that looked busiest in the first profile, `0153DA` and `014E06`, turned
out to be timed pauses and pad reads inside them.

## Object tiles

**What was slow.** `02E3E4` builds the graphics for objects. For each tile it did a binary search
through an index at `02DCEC`, spread the packed bytes through a table, then walked a decoding
tree written out as code, one test and one branch per bit. Nothing was kept, so a tile drawn on
every tick was unpacked on every tick. On level 6 that averaged about 5,000 cycles a tile, and it
was 54% of all the cycles in the run, waiting included.

| Share of the routine's time | Level 5 | Level 6 |
|---|---|---|
| Setup and search | 31% | 19% |
| Spreading the bytes | 20% | 23% |
| Decoding bits | 49% | 58% |

**The change.** There are 29,671 tile numbers, and they come to about 950 KB unpacked. That fits
in a second megabyte of ROM, from `100000` to `1E7CFF`, leaving `200000` free for save RAM. The
new routine looks a tile up by number and copies 32 bytes. It's 98 bytes long, against about
4 KB before, and it uses the same inputs and outputs. The tiles are generated from the player's
own ROM when the patch is built, so the project doesn't contain them.

**The result.** On-time ticks spent this much on object graphics:

| Level | Before | After |
|---|---|---|
| 1 | 221k | 16k |
| 2 | 183k | 20k |
| 3 | 129k | 16k |
| 4 | 175k | 17k |
| 5 | 141k | 19k |
| 6 | 377k | 23k |
| 7 | 207k | 16k |
| 8 | 124k | 14k |

The "after" column is from the current build.

**Also needed.** At boot, `0FFFB0` adds up the first megabyte and halts on a solid screen if the
total is wrong. The patch turns off the failure branch at `0FFFD0`, and it updates the ROM size
and checksum in the header.

## The torch flame

Unpacking every tile exposed a bug in the original. The index search accepts a tile number equal
to the first tile of the *next* run. That's usually harmless, because both runs agree on where
the tile starts. At tile 25793 it isn't: the tile begins a run of uncompressed tiles, the search
lands on the compressed run before it, and the bytes get decoded as if they were compressed. On
level 4 this tile is the top of the wall torch's flame, so the original draws the torch with the
top missing. The unpacked table holds the correct tile. The walks also asked for this tile on
levels 2, 3 and 5 to 8, and those uses haven't been looked at.

## Background tiles

**What was slow.** After the object tile change, nearly every late tick was one where the camera
crossed an 8-pixel step. Those ticks run three routines:

| Routine | Job | Cycles on a step, before | After |
|---|---|---|---|
| `013D34` | Works out the 612 cells on screen | about 95k | 96k |
| `013B16` | Gives each tile a slot in video memory | about 75k | 56k |
| `013B78` | Frees unused slots and sends tiles | about 250k to 300k | 69k |

The "before" figures are from late ticks on the levels where these routines dominated. The "after"
figures are the average over all camera-step ticks.

`013B16` marked every tile on screen to be sent, whether video memory already had it or not. Over
the walks, 346,317 tiles were sent when only 13,466 were new, so 96% of the sending changed
nothing. `013B78` then stepped through all 2,048 table entries, at about 70 cycles each by
instruction timings, even though most were empty.

It did this with interrupts masked, for around two frames at a time. Vertical blanks that arrived
in that window were lost, and the vertical blank handler is where the game counts frames and reads
the pad:

| Vertical blanks missed, first walk | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| Original | 0.1% | 2.2% | 2.5% | 2.5% | 6.1% | 2.5% | 1.6% | 3.9% |
| Now | 0.0% | 0.0% | 0.1% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |

**The change.** `013B16` now marks only newly allocated tiles. The new sync routine skips empty
entries in a tight loop, about 22 cycles each by instruction timings, and sends only marked tiles.
It visits entries in the original order, so slots are freed and handed out exactly as before. It's
144 bytes, so it sits at `02E480`, in space the old object code left free, with a jump at `013B78`.

## Sprite masking

**What was slow.** `01428C` hides the parts of sprites that are behind scenery. For every 8 by 8
sprite tile it looks up the four scenery cells under it, picks a mask shape for each by comparing
depths, and ANDs the result into the tile. It built the mask the long way: 16 rows for the left
pair of cells, shifted left a bit at a time, then 16 rows for the right pair shifted right, 32
variable shifts in all, and then used only 8 of the 16 rows. A masked tile cost about 2,900
cycles. The 75% of tiles with nothing in front of them still cost about 470 each, because the
depth comparison came before the test for empty cells.

**The change.** There are 16 shapes and 8 possible shifts, so every shifted shape fits in 8 KB of
tables, built from the player's ROM and placed at `1E8000`. The new routine reads the 8 rows it
needs straight from them. It also tests the four cells for "all empty" first, and works out
per-column values once per column. It's 536 bytes and replaces the old 636 in place.

Only 6 of the 16 shapes are real data. Numbers 6 to 15 run on into the old routine's own code. No
cell seems to use them, but the tables are built from the original bytes so that they'd still
behave as before.

**The result.** Cycles in `01428C` per on-time tick:

| Level | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| Before | 67k | 32k | 24k | 52k | 46k | 77k | 33k | 37k |
| After | 27k | 14k | 12k | 22k | 21k | 38k | 14k | 15k |

Over all the walks the routine went from 515 million cycles to 233 million.

**A bug this exposed, now fixed.** The game shifts the right-hand cells' mask by 31 minus the
offset, where 32 minus the offset would line it up. That leaves it one bit out, a quarter of a
pixel's colour number, so pixels along a mask edge come out in the wrong colour or show when they
should be hidden. In the walks it changed one to five pixels in about 13% of frames, such as a
yellow dot at the wizard's foot where he stands behind a floor edge. Because the shifted masks are
now tables, the fix is one number in `tools/build_rom.py`. The routine is still proven against the
original with the game's own shift, and the shipped tables use the corrected one.

## Camera steps

**What was slow.** After the changes above, the heaviest ticks were still the ones where the
camera crosses an 8-pixel step. The three routines from the background tile section took about
220k cycles between them on such a tick, a third of the tick.

`013D34` rebuilds all 612 cells from the level's maps, which are made of blocks 8 cells wide and
4 tall. For every row of every block it worked out the row's place in three buffers again with
multiplies done as shifts and adds, and for every cell it tested for the screen's right edge.

The sync routine at `02E480` still stepped through all 2,048 entries of the tile table. Measured
during play, 15 to 235 entries are in use, 278 at most, and they sit in about a third of the
table.

**The change.** The new `013D34` works out how many columns and rows of a block are on screen
before it copies, then copies each row through an unrolled run of moves with nothing else in the
loop. It's 450 bytes against 554. Its two small tables sit just before the routine, and a map byte
out of range would read past them into the old routine's code. So the new routine reads a copy of
those bytes as they were, at `1EA000`, and such a byte still gives what it always gave.

The tile table now has a count for each group of 32 entries, 64 bytes at `FF9660`, in RAM the old
object decoder used as a buffer. The slot routine adds one when it gives a tile a slot, the sync
takes one off when it frees a slot, and the room reset clears them. The sync skips any group whose
count is zero. It still visits the entries in use in the original order, so slots are freed and
handed out exactly as before. The slot routine moved to `02E540` to make room for the counting, and
its loop keeps two constants in registers.

**The result.** Cycles for each call, averaged over all camera steps in the walks:

| Routine | Before | After |
|---|---|---|
| `013D34`, the cells | 96k | 41k |
| The slot routine, `013B16` and now `02E540` | 56k | 58k |
| The sync, `02E480` | 71k | 34k |
| **Together** | **223k** | **133k** |

The share of ticks needing more than 3 frames of work fell from 11.6% to 3.7%.

**A quirk kept.** The original leaves part of the block's row number in the register it then uses
as the block's graphics number. It makes no difference until the row reaches 64, and from there on
it reads the cells from the wrong place. The test with random maps found this, because the first
version of the new routine didn't do it. The new routine now does the same thing, so that nothing
changes. Whether any level's map is tall enough to reach it hasn't been checked.

## The sound link

**What it costs.** Sound is the largest thing left. Every frame, from the vertical blank handler,
`01624E` stops the Z80, copies 48 bytes out of its memory, lets it go, runs the music and sound
effect sequencers on the 68000 (`015E9C` and `0165AE`), then stops the Z80 again and copies the 48
bytes back if anything changed. That's about 5,900 cycles a frame, or 29,500 a tick, which is
18% of the work in a typical tick. The sequencers take 3,200 of it and the two copies 1,150 each.

**The change.** The 68000 can only reach Z80 memory a byte at a time, so the copies can't use
longer moves. They were loops, though, and a loop spends nearly as long counting as copying. The
new link at `02E600` has the 48 moves written out for each copy. Everything else in it is the
original's instructions in the original order. It costs about 5,000 cycles a frame, so a tick has
about 4,600 more to spare.

**What it does to the sound.** Nothing changes in what's sent to the Z80. What changes is how long
the Z80 is stopped: about 0.08 ms for each copy, where it was about 0.15 ms. On levels 3, 4 and 7
the Z80 plays sampled sounds, which showed up in the sound chip logs as a steady stream of writes
to the YM2612's sample register. While it's stopped, the sample it's playing waits. In the logs
from level 4 the normal step between sample writes is 5 or 6 units of 1/44,100 s, and the stretched
steps went from 12 or 13 to 9 or 10. So the hitches in sampled sounds are shorter, and those sounds
run about 0.7% faster, around an eighth of a semitone. Music and effects made by the FM chip aren't
timed by the Z80 and shouldn't change at all. Nobody has listened to it, so this is the one change
here with a known effect on output that hasn't been judged by ear.

**Not done.** The sequencers are about 1,600 bytes of branching code that step through the song
data. They could be rewritten to be perhaps a third faster, which would gain about 5,000 cycles a
tick. That's a small return for rewriting the music player, so it's left alone.

**A dead end worth knowing.** The plan was to prove this change by showing that the game makes the
same sound chip writes before and after. `sound_writes.py` does that comparison, and a ROM against
itself matches write for write. But any change to timing sends the game a different way from the
title screen on, even a version of the new link padded to take the same number of cycles as the
old. The emulator models the 68000's memory refresh delays, so two different runs of instructions
can't be made to take exactly the same time. The tool is kept for the logs it makes.

## Fights, held to their old pace

Making the drawing faster made fights faster, and that was a mistake. Ordinary play has a clock:
an update can't start until 5 frames after the last one. A fight has none. It runs in its own two
loops, each of which draws a picture and goes straight round again, so its speed was simply how
long the drawing took.

| | Original | Patched, before this | Patched, now |
|---|---|---|---|
| Main loop, frames from one picture to the next | 6.08 | 1.05 | 6.00 |
| Animation loop | 8.49 | 3.17 | 8.00 |

The fix puts a wait before each loop's drawing call (`011694` and `011772`), which holds off until
the frame before the picture is due, counted from the last picture. The targets are the commonest
gaps in the original: 6 and 8 frames. The original wandered, between 5 and 7 in the main loop and
from 7 up to 14 in the animation, and the patched build doesn't, so the animation runs about 6%
quicker than the original's average. `tools/harness/fight_pace.py` makes the table.

Other things that run without the 5-frame clock: message text (3.17 frames a character in the
original, 2.99 now), and the death sequence, which hasn't been measured yet.

## How the changes were checked

A frame-by-frame comparison with the original doesn't work once the game runs faster, because the
same input lands on different ticks. So each change has its own proof.

| Check | What it shows |
|---|---|
| Tile test ROM | Runs the game's own decoder, under emulation, on all 29,671 tile numbers. Every result matches the table, including the torch tile as the game decodes it |
| Object routine test ROM | The new routine writes the right tiles, counts them correctly, and leaves all 15 registers as it found them |
| Background test ROM | Covers the slot routine and the sync, including the counts. Old and new routines run on 24 passes of random screens, with identical RAM and video memory after every pass, and all registers kept. Deliberately breaking the patch makes this fail |
| In-play check | A test build compared every skipped tile with video memory during play, across all levels and walks that press buttons. All 685,562 matched |
| Reading the code | Outside start-up code, one routine writes to the tile area: `0158EC` puts 7 status tiles in slots 0 to 6. Slots are handed out from 611 downward, so a screen would need over 600 different tiles to reach them, and the original had the same limit. A room reset (`015A7C`) empties the table |
| Tile numbers | Walks from a clean boot never asked for a tile outside the table |
| Masking test ROM | Old and new masking routines run on 400 passes of random sprites, depths and scenery, including sprites partly off the grid and the 10 shapes that aren't real data. The tiles and all registers come out the same. Six deliberate breaks, one in each path through the routine, all made it fail |
| Cell test ROM | Old and new `013D34` run on 300 passes of random block maps, rooms and camera positions, on and off the map. The cells, the mask shapes and all registers come out the same. Six deliberate breaks all made it fail, one of them being to leave out the quirk described above |
| Cells in play | A test build ran both routines on every camera step of 32 walks and compared their output. 3,941 steps agreed. A deliberately broken routine disagreed on all 3,941 |
| Tile counts in play | A test build recounted the tile table after every sync and compared it with the running counts. 3,943 syncs, none wrong. With the "take one off" left out, 29,744 groups were wrong |
| Sound test ROM | With the Z80 parked in a loop, old and new links play six songs for 256 frames each and then 256 frames of silence, with the Z80's 48 bytes set at random before every call. The 68000's sound memory, the Z80's memory and all registers come out the same. Six deliberate breaks, in both copies, the skip and the call to the music, all made it fail |
| Masking in play | A test build ran both routines on the game's own sprites, in alternating order, on every tick of 32 walks. 30,886 calls agreed. Masking a tile twice changes nothing, so a second routine that disagrees shows up as a changed tile. A deliberately broken routine gave 6,436 disagreements |

## What's left

**Late ticks.** Nearly all the remaining ones aren't a CPU problem. They spend about 490k cycles
waiting for vertical blank inside the game logic. On levels 2 and 6 the waits come from a drawing
loop at `0074A8`, which waits four frames per step. On level 7 most come from `011776`, which waits
two. They look like deliberate animations, though we haven't identified them.

**Frames to a finished picture.** This is the measure that matters for any change to the tick
rate: how many video frames pass from a tick's start until its picture is on screen. Deliberate
waits inside the game logic are left out.

| Level | 1 frame | 2 frames | 3 frames | 4 frames | 5 or more |
|---|---|---|---|---|---|
| 1 | 32.7% | 66.7% | 0.5% | 0.0% | 0.0% |
| 2 | 0.4% | 78.8% | 15.3% | 5.6% | 0.0% |
| 3 | 47.9% | 42.0% | 9.7% | 0.0% | 0.4% |
| 4 | 12.0% | 70.8% | 17.0% | 0.3% | 0.0% |
| 5 | 63.0% | 28.0% | 8.9% | 0.1% | 0.0% |
| 6 | 25.0% | 61.9% | 13.1% | 0.0% | 0.0% |
| 7 | 74.4% | 23.7% | 1.8% | 0.0% | 0.1% |
| 8 | 79.8% | 20.2% | 0.0% | 0.0% | 0.0% |
| **All, now** | **44.2%** | **46.8%** | **8.5%** | **0.4%** | **0.1%** |
| All, original | 2.1% | 22.5% | 26.3% | 20.8% | 28.3% |

The game's tick is 5 frames. As it stands, 99.5% of ticks would fit a tick of 3 frames and 91% a
tick of 2. In the original, three quarters of ticks needed 3 frames or more.

A test build that counted frames inside the game split this by kind of tick. Ticks without a
camera step are ready in 1 frame 51% of the time and in 2 frames 46%. Ticks with a camera step,
15% of all ticks, are never ready in 1: 44% take 2 frames, 51% take 3 and 3% take 4. So the camera
step is the whole of what's left above 2 frames, apart from the deliberate waits.

**Work in each tick.** This is the older measure: the work in each tick, in thousands of cycles,
without its waits. It overstates the cost, because it counts the sprite tile upload as work. See
"Sprite tile upload" below.

| Level | Median | 90% | 99% | Most | Over 4 frames | Over 3 frames | Over 2 frames |
|---|---|---|---|---|---|---|---|
| 1 | 164 | 226 | 279 | 330 | 0.0% | 0.0% | 1.1% |
| 2 | 262 | 415 | 464 | 532 | 0.1% | 13.3% | 66.2% |
| 3 | 145 | 293 | 386 | 654 | 0.4% | 1.1% | 16.5% |
| 4 | 236 | 343 | 417 | 452 | 0.0% | 4.1% | 39.1% |
| 5 | 140 | 302 | 422 | 504 | 0.0% | 7.0% | 35.8% |
| 6 | 234 | 352 | 395 | 659 | 0.0% | 5.2% | 23.3% |
| 7 | 140 | 282 | 305 | 598 | 0.1% | 0.1% | 12.8% |
| 8 | 138 | 273 | 290 | 299 | 0.0% | 0.0% | 19.9% |
| **All** | **155** | **294** | **420** | **659** | **0.1%** | **3.4%** | **24.9%** |

How the "All" row has moved:

| After | Median | 90% | 99% | Over 4 frames | Over 3 frames | Over 2 frames |
|---|---|---|---|---|---|---|
| Background tiles | 212 | 408 | 548 | 4.0% | 14.0% | 38.1% |
| Sprite masking | 162 | 395 | 526 | 1.3% | 11.6% | 26.6% |
| Camera steps | 161 | 295 | 423 | 0.1% | 3.7% | 25.8% |
| The sound link | 155 | 294 | 420 | 0.1% | 3.4% | 24.9% |

Changing the rate isn't only a question of fitting, because movement and timers are counted in
ticks.

**Remaining costs**, as shares of the CPU time not spent waiting, over all levels:

| Routine | Share | What it is |
|---|---|---|
| `02E3E4` | 9.7% | The new object tile copy |
| `01428C` | 8.7% | The new sprite masking. 17% on level 6 |
| `015E9C` | 7.4% | The music sequencer |
| `0150E6` | 7.4% | Starts the sprite tile DMA, and its time includes the CPU being held during DMA |
| `02E600` | 6.4% | The new sound link, mostly its two copies through Z80 memory |
| `02E540` | 3.5% | Assigns tile slots on a camera step |
| `0165AE` | 3.2% | The sound effect sequencer |
| `009930` | 2.7% | Game logic, not read yet |
| `013D34` | 2.6% | Works out the cells on a camera step |
| `005B78` | 2.5% | Game logic, not read yet |
| `01370A` | 2.3% | Not read yet |
| `01467C` | 2.2% | Part of preparing the sprites |

An earlier version of this table had `015466` and `00D2C6` near the top. They turned out to be the
YES/NO prompt polling the pad until the choice changes, which is waiting, and `hotspots.py` counts
it that way now. That's also why the other shares are higher than they were.

## What wasn't done, and why

**Sprite tile upload.** Each tick the game sends its sprite tiles to video memory by DMA, 48 to 64
tiles on most ticks and up to 160. It does this during active display, where DMA moves about 18
bytes a scan line against about 205 in vertical blank, and the 68000 is stopped while it runs.
That's 37k cycles on a median tick and 91k on a heavy one, which made it look like the best thing
left to fix. It isn't. The game's next step is to wait for vertical blank, so the upload fills time
that would otherwise be spent waiting. If vertical blank arrives part way through, the rest goes at
the fast rate and the tick carries on in the same blank. An estimate from the measured parts is
that if the upload cost nothing, the picture would be ready a frame sooner on somewhere between 1%
and 4% of ticks and in the same frame on the rest. That's not worth restructuring the end of the
tick for.

Looking into it turned up two things that aren't about speed. In the patched build, 16% of ticks
without a camera step and 52% of ticks with one finish their drawing after vertical blank has
ended. For camera steps that's mostly the last rows of the cell map, which are written well ahead
of where the screen is being drawn. For the rest it means the sprite table or the scroll position
changed a few lines into the picture. Whether that shows hasn't been checked, and it wasn't
measured on the original, though the code is the original's. The upload also stops the Z80 for as
long as it runs, which is another source of hitches in sampled sounds. Uploading in vertical blank
would help both, so it may come back as a fix.

**The music and sound effect sequencers.** See "The sound link" above.

**The object tile copy.** `02E3E4` is the largest single routine left, at about 190 cycles a tile,
160 of which are the eight moves that copy it. Going further would mean not copying tiles for
sprites that haven't changed, which also means not masking or uploading them, and that's a
redesign of how sprites are drawn.

**Game logic.** It's 28% of the work, spread over 281 routines, and the largest is under 3%. The
code reads as if it was translated mechanically from another processor's, with byte-sized
variables and flags juggled by hand. Nothing in it stands out, and rewriting game logic is the
riskiest kind of change for the least return.

**More from the camera step.** It's down from 223k cycles to 133k. The next step would be to
update only the row or column that scrolled into view, with a count of uses for each tile. That
changes which video memory slot each tile gets, so it couldn't be proven against the original the
way everything here has been, and it would only matter for a tick shorter than 3 frames.

## Mistakes worth remembering

- **A wrong register mask in the first build tool.** The new object routine saved one set of
  registers and restored another. The game still ran, and only a frame comparison gave it away.
  That's why the routine test exists, and it was confirmed to catch this exact mistake.
- **Old saved states don't suit a patched ROM.** A state saved while the CPU was inside a routine
  that's since been replaced resumes in the middle of the new code. On level 1 this looked like
  invalid tile numbers. Measurements now boot from power-on.
- **Test ROMs must set up the video chip.** Without Genesis mode, video memory reads and writes
  behaved differently and the old and new routines seemed to disagree.
- **Let the video queue drain before reading video memory back.** Queued writes may not have
  landed yet.
- **Counting stopped time as work.** The work-per-tick measure counted the sprite tile upload,
  which made the upload look like a third of a typical tick. Measuring frames to a finished
  picture showed that it costs almost nothing in practice.
- **The profiler reports once a frame.** A part of a tick that finishes in the frame the tick
  starts in is counted with the tick before. Averages are right, but a breakdown of single ticks
  isn't, which gave a confusing picture of camera steps until it was counted inside the game.
- **Faster isn't the same as better.** Fights, and anything else without a clock of its own, sped
  up along with the drawing, and nobody noticed until the game was played by hand. Random walks
  measure how long updates take. They don't say whether a fight looks right.
- **A failed emulator run can look like a game result.** BlastEm sometimes failed at startup, which
  once showed up as "level 8 not reached". The tools now stop on any short run, and the emulator
  bug is fixed. See `docs/blastem-fork-fixes.md`.

## Reproducing this

    tools/harness/build_blastem_fork.sh    # needs SDL2 and GLEW
    tools/harness/build_trace_core.sh      # for hotspots.py
    tools/disasm.py                        # for hotspots.py
    tools/build_rom.py --check             # builds build/immortal-patched.md and tests it

    ROM=build/immortal-patched.md tools/harness/fork_timing.py
    tools/harness/tick_parts.py
    tools/harness/tick_parts.py --headroom
    tools/harness/tick_parts.py --frames
    tools/harness/hotspots.py
    tools/harness/sound_writes.py rom/your-rom.md build/immortal-patched.md

`fork_timing.py` reads the original ROM unless `ROM` is set, and needs an absolute path if you run
it from elsewhere. The other tools default to the patched ROM.

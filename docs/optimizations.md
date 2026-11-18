# Optimizing The Immortal

This is the record of the performance work on the Genesis version: what was slow, why, what
was changed, and how each change was checked. Addresses are for The Immortal (USA, Europe).
Everything here was measured in emulators with scripted random walks. None of it has been run
on real hardware or judged by someone playing it.

## Where it stands

The game runs one update, or tick, every 5 video frames. A tick that takes longer starts the next
one late, and the game never catches up, so a late tick is lost time.

| Level | Late: original | Late: object tiles | Late: now | Worst gap: original | Worst gap: object tiles | Worst gap: now |
|---|---|---|---|---|---|---|
| 1 | 1% | 1% | 0% | 7 | 7 | 5 |
| 2 | 23% | 22% | 12% | 9 | 10 | 8 |
| 3 | 10% | 11% | 0% | 9 | 7 | 6 |
| 4 | 16% | 17% | 0% | 8 | 7 | 5 |
| 5 | 41% | 24% | 0% | 11 | 7 | 6 |
| 6 | 58% | 20% | 5% | 11 | 7 | 6 |
| 7 | 15% | 14% | 1% | 8 | 7 | 6 |
| 8 | 19% | 19% | 0% | 6 | 6 | 5 |
| **All** | **23.8%** | **16.4%** | **2.0%** | | | |

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
| `tools/harness/hotspots.py` | Cycles per routine on each level, using the PicoDrive profiling core |
| `tools/build_rom.py --check` | Builds the patch and runs its test ROMs |

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

## How the changes were checked

A frame-by-frame comparison with the original doesn't work once the game runs faster, because the
same input lands on different ticks. So each change has its own proof.

| Check | What it shows |
|---|---|
| Tile test ROM | Runs the game's own decoder, under emulation, on all 29,671 tile numbers. Every result matches the table, including the torch tile as the game decodes it |
| Object routine test ROM | The new routine writes the right tiles, counts them correctly, and leaves all 15 registers as it found them |
| Background test ROM | Old and new routines run on 24 passes of random screens, with identical RAM and video memory after every pass, and all registers kept. Deliberately breaking the patch makes this fail |
| In-play check | A test build compared every skipped tile with video memory during play, across all levels and walks that press buttons. All 685,562 matched |
| Reading the code | Outside start-up code, one routine writes to the tile area: `0158EC` puts 7 status tiles in slots 0 to 6. Slots are handed out from 611 downward, so a screen would need over 600 different tiles to reach them, and the original had the same limit. A room reset (`015A7C`) empties the table |
| Tile numbers | Walks from a clean boot never asked for a tile outside the table |

## What's left

**Late ticks.** Nearly all the remaining ones aren't a CPU problem. They spend about 490k cycles
waiting for vertical blank inside the game logic. On levels 2 and 6 the waits come from a drawing
loop at `0074A8`, which waits four frames per step. On level 7 most come from `011776`, which waits
two. They look like deliberate animations, though we haven't identified them.

**Headroom.** This is the work in each tick, in thousands of cycles, without those waits:

| Level | Median | 90% | 99% | Most | Over 4 frames | Over 3 frames | Over 2 frames |
|---|---|---|---|---|---|---|---|
| 1 | 221 | 267 | 395 | 449 | 0.0% | 1.1% | 25.0% |
| 2 | 270 | 537 | 566 | 650 | 13.2% | 13.9% | 85.3% |
| 3 | 186 | 405 | 527 | 779 | 1.6% | 11.1% | 21.8% |
| 4 | 262 | 457 | 560 | 635 | 4.0% | 19.1% | 57.7% |
| 5 | 191 | 421 | 559 | 650 | 7.3% | 22.7% | 36.6% |
| 6 | 261 | 471 | 532 | 781 | 7.8% | 14.5% | 55.6% |
| 7 | 156 | 402 | 431 | 672 | 0.1% | 11.6% | 15.1% |
| 8 | 168 | 394 | 417 | 431 | 0.0% | 14.9% | 20.1% |
| **All** | **212** | **408** | **548** | **781** | **4.0%** | **14.0%** | **38.1%** |

So 12 updates a second now has room, 15 would nearly fit, and 20 would need more work. This doesn't
settle the question of changing the rate, because movement and timers are counted in ticks.

**Remaining costs**, as shares of the CPU time not spent waiting, over all levels:

| Routine | Share | What it is |
|---|---|---|
| `01428C` | 14.4% | Masks sprites against the background, tile by tile. 28% on level 6. The next target |
| `02E3E4` | 7.2% | The new object tile copy |
| `01621E` block | 7.1% | Mostly `01624E`, which copies 48 bytes each way through Z80 memory, one byte at a time. It looks like the link to the sound driver |
| `015E9C` | 5.5% | Not read yet |
| `0150E6` | 5.5% | Starts the sprite tile DMA, and its time includes the CPU being held during DMA |
| `015466` | 5.3% | Turns the pad state into a direction. Called so often that it's probably polling at prompts, which isn't confirmed |
| `013D34` | 4.4% | Works out the cells on a camera step |
| `00D2C6` | 4.3% | Not read closely yet. Runs about as often as `015466` |
| `02E480` | 3.2% | The new background tile sync |
| `013B16` | 2.7% | Assigns tile slots on a camera step |

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
    tools/harness/hotspots.py

`fork_timing.py` reads the original ROM unless `ROM` is set, and needs an absolute path if you run
it from elsewhere. The other tools default to the patched ROM.

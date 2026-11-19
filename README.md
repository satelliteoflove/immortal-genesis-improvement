# The Immortal: a Genesis patch

A patch for the Genesis version of The Immortal. It's meant to make the game fairer, fix
its bugs, and smooth out its performance where that can be done, while leaving it the same
game. It started as an idea for a 32X port (hence the folder's name), but the problems
people raised with the game aren't ones the 32X would fix, so this is a straight patch for
the Genesis.

So far the patch speeds up object graphics and background scrolling, and restores the wall
torch's flame. `TODO.md` has
what we're looking into and `docs/progress/index.html` is the running record.

## The ROM

The patch is made for one dump, The Immortal (USA, Europe):

| | |
|---|---|
| Size | 1,048,576 bytes |
| SHA-256 | `b60aa52e46a199f755a1eb99daea543c468acf07d83624c85a84cdd14b786375` |
| CRC32 | `f653c508` |

Put your own copy in `rom/` and check it:

    tools/romcheck.py

## Building the patched ROM

    tools/build_rom.py            # writes build/immortal-patched.md, 2 MB
    tools/build_rom.py --check    # also tests the result (needs the BlastEm fork build)
    tools/build_rom.py --smooth   # also writes a trial ROM that draws in-between pictures

## What's kept in the repository

Everything we write is tracked: tools, patch source, notes, and the progress page's text.
The game isn't, and neither is anything made from it. `.gitignore` keeps these out:

- the ROM, patched ROMs and anything extracted from them
- disassembly listings, saves and emulator states
- screenshots, clips and sound recordings of the game

Addresses, hashes and our own descriptions of how the game works are fine to track.
Stretches of the game's code or data pasted into notes are not.

## The test harness

It runs the game headless in PicoDrive, using the core and source that 32xKarts fetches:

    make                                   # build/runner
    tools/harness/build_trace_core.sh      # PicoDrive with a profile of the 68000
    tools/harness/run.sh -n 600 -s 599:scratch/shot.png
    tools/harness/sheet.py scratch/sheet.png 840 90 12 -i tools/harness/input/new_game.txt
    tools/harness/levels.py                # reach every level, measure its timing
    tools/harness/get_blastem.sh           # BlastEm's libretro core, into build/cores/
    tools/harness/compare_cores.py         # the same timing run on PicoDrive and BlastEm
    tools/harness/build_blastem_fork.sh    # our patched build of the BlastEm fork (needs SDL2, GLEW)
    tools/harness/fork_timing.py           # timing and cycle counts on that build
    tools/harness/tick_parts.py            # which part of a tick is taking the time
    tools/harness/hotspots.py              # the busiest routines on each level
    tools/harness/fight_pace.py            # the pace of fights, original against patched
    tools/harness/text_pace.py             # typing speed of messages, with and without a button held
    tools/disasm.py                        # writes disasm/, which git ignores

`tools/harness/runner.c` lists its options. What's been learned is in
`docs/how-the-game-works.md`, the performance work is written up in `docs/optimizations.md`, and
fixes made to the emulator are in `docs/blastem-fork-fixes.md`.

## The progress page

    tools/progress.py "Title" "What changed, what to look at." shot.png clip.mp4
    tools/progress.py "Title" "Note." --ours chart.png

Pictures and clips go in `docs/progress/local/`, which git ignores, so they stay on this
machine. Anything of our own with none of the game in it, such as a chart, goes after
`--ours` and is tracked. Open `docs/progress/index.html` directly to read it.

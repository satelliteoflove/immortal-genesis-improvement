# The Immortal: a Genesis patch

A patch for the Genesis version of The Immortal. It's meant to make the game fairer, fix
its bugs, and smooth out its performance where that can be done, while leaving it the same
game. It started as an idea for a 32X port, but the problems people raised with the game
aren't ones the 32X would fix, so this is a straight patch for the Genesis.

So far the patch:

- draws objects, sprites and the scrolling background much faster, while keeping the
  game's own pace, fights included;
- saves each level reached to battery RAM, offers the saved levels at start, and offers
  the level again at Game Over;
- holds "Prepare to continue..." for 3 seconds after a death, unless a button is pressed;
- types messages faster while a button is held, without skipping their pauses;
- fixes the wall torch's flame, stray pixels behind scenery, the level's song starting
  over, and a soft-lock after a death in level 5's last room.

`TODO.md` has what we're looking into, `docs/release-checklist.md` what's left before a
release, and `docs/progress/index.html` is the running record. Its pictures and clips are
kept out of git, so they only show on the machine that made them.

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

    tools/build_rom.py            # writes build/immortal-patched.md, 1 MB like the original
    tools/build_rom.py --check    # also tests the result (needs the BlastEm fork build)

## Making the patch file

    tools/make_patch.py           # writes build/immortal-patch.bps

A BPS file checks that it's being applied to the right ROM. It's applied to the original as
it's made, and has to give back the patched ROM exactly. It isn't tracked here; it will go out
attached to a release. The patch changes about 11 KB of the ROM. None of that is the game's graphics.
What it holds of the game is a few small tables worked out from the game's own, and a few
hundred bytes of its code and data that the new routines carry with them.

## What's kept in the repository

Everything we write is tracked: tools, patch source, notes, and the progress page's text.
The game isn't, and neither is anything made from it. `.gitignore` keeps these out:

- the ROM, patched ROMs and anything extracted from them
- disassembly listings, saves and emulator states
- screenshots, clips and sound recordings of the game

Addresses, hashes and our own descriptions of how the game works are fine to track.
Stretches of the game's code or data pasted into notes are not.

## The test harness

It runs the game headless through libretro cores. Most of it uses BlastEm's core, or our
build of the BlastEm fork; the older tools use PicoDrive. Each core has a script that
fetches or builds it under `build/`, and nothing outside this repository is needed. Set
`CORE` or `PICODRIVE_SRC` to use your own instead.

    make                                   # build/runner
    tools/harness/get_picodrive.sh         # PicoDrive's source and its libretro core, into build/
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
    tools/harness/save_check.py            # battery saves, the level picker and Game Over's second try
                                           #   (--core picodrive or genesis_plus_gx for those emulators)
    tools/harness/get_genesis_plus_gx.sh   # Genesis Plus GX's libretro core, into build/cores/
    tools/harness/route/whole_game.py      # play the whole game by script (docs/playthrough.md)
    tools/harness/build_coverage_core.sh   # a BlastEm core that counts the instructions run (docs/dead-code.md)
    tools/disasm.py                        # writes disasm/, which git ignores

`tools/harness/runner.c` lists its options. What's been learned is in
`docs/how-the-game-works.md`, the performance work is written up in `docs/optimizations.md`, and
fixes made to the emulator are in `docs/blastem-fork-fixes.md`. Code the game never runs is listed
in `docs/dead-code.md`.

## The progress page

    tools/progress.py "Title" "What changed, what to look at." shot.png clip.mp4
    tools/progress.py "Title" "Note." --ours chart.png

Pictures and clips go in `docs/progress/local/`, which git ignores, so they stay on this
machine. Anything of our own with none of the game in it, such as a chart, goes after
`--ours` and is tracked. Open `docs/progress/index.html` directly to read it.

# The Immortal: a Genesis patch

A patch for the Genesis version of The Immortal. It's meant to make the game fairer, fix
its bugs, and smooth out its performance where that can be done, while leaving it the same
game. It started as an idea for a 32X port (hence the folder's name), but the problems
people raised with the game aren't ones the 32X would fix, so this is a straight patch for
the Genesis.

Nothing has been patched yet. `TODO.md` has what we're looking into and
`docs/progress/index.html` is the running record.

## The ROM

The patch is made for one dump, The Immortal (USA, Europe):

| | |
|---|---|
| Size | 1,048,576 bytes |
| SHA-256 | `b60aa52e46a199f755a1eb99daea543c468acf07d83624c85a84cdd14b786375` |
| CRC32 | `f653c508` |

Put your own copy in `rom/` and check it:

    tools/romcheck.py

## What's kept in the repository

Everything we write is tracked: tools, patch source, notes, and the progress page's text.
The game isn't, and neither is anything made from it. `.gitignore` keeps these out:

- the ROM, patched ROMs and anything extracted from them
- disassembly listings, saves and emulator states
- screenshots, clips and sound recordings of the game

Addresses, hashes and our own descriptions of how the game works are fine to track.
Stretches of the game's code or data pasted into notes are not.

## The progress page

    tools/progress.py "Title" "What changed, what to look at." shot.png clip.mp4
    tools/progress.py "Title" "Note." --ours chart.png

Pictures and clips go in `docs/progress/local/`, which git ignores, so they stay on this
machine. Anything of our own with none of the game in it, such as a chart, goes after
`--ours` and is tracked. Open `docs/progress/index.html` directly to read it.

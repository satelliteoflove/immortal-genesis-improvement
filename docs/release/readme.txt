The Immortal (Genesis) Improvement Patch
Version 1.0
by Christopher Childress (satelliteoflove)


ABOUT
-----

The Immortal is a hard game, and the Genesis version had a few rough spots on
top of that. It slows down badly in places, a death sends you straight back
in before you've caught your breath, and there's no way to save other than
writing down a long certificate at the end of each level. This patch is meant
to smooth those things out and fix some bugs, while leaving it the same game.

It doesn't make the game easier, and it doesn't make it faster. Traps, fights,
items and the three lives per level are all as they were. The game keeps its
original pace; it just doesn't bog down as often.


WHAT THE PATCH CHANGES
----------------------

Performance

  The game draws objects, sprites and the scrolling background much faster.
  In a scripted run through the whole game, about a third of the original's
  updates ran late, and on level 8 most of them did, so that level ran at
  about two-thirds speed. With the patch, 2% ran late in the same run, and
  about 4% in a full play-through by hand. Fights and other timed scenes
  still run at the original's speed.

Battery saves

  When you finish a level, the game saves the level you've reached to battery
  RAM and shows "Game saved." under the certificate. Each level has its own
  save, and reaching a level again replaces its save. There are no saves in
  the middle of a level.

  When you start the game with a save present, it asks "Continue a saved
  game?". Answer YES and it shows the furthest level saved. UP and DOWN step
  through the saved levels, and any button starts the one shown. Answer NO to
  go on to the usual "New game?" prompt.

  Certificates still work as they always did.

Game Over

  Game Over now asks "Try this level again?". YES starts the level over with
  three lives and whatever the wizard was carrying when he started it. NO goes
  on to the prompts the game starts with, as before.

After a death

  "Prepare to continue..." now stays up for 3 seconds instead of about 1.5,
  unless you press A, B, C or Start.

Messages

  Holding a button types messages at about 50 letters a second, around three
  times the usual speed, and every letter is drawn. That's slower than holding
  a button in the original, which put whole words up at about 106 letters a
  second and skipped every pause, so the pages flew by.

  With the patch, a held button doesn't skip the pauses. At the end of a page
  the game waits a little over a second, much as it does with nothing held,
  and then types the next page by itself. To go on sooner, let go and press
  A, B, C or Start again: a fresh press ends the pause, but a button that was
  already down when the pause began doesn't. The original's two-button
  shortcut, which skipped every wait, is gone too. With no button held,
  messages are as they were.

  This is meant for players who read quickly: the text comes out faster
  without blowing past something you wanted to read. If you've read the
  messages many times and just want them gone, holding a button is slower
  than it was in the original.

Bug fixes

  - The wall torch on level 4 is drawn with the top of its flame.
  - Where the wizard or a creature passes behind scenery, a few pixels along
    the edge used to come out in the wrong color or show through, such as a
    yellow dot at the wizard's foot. Those are gone.
  - The level's music no longer starts over every so often while you're just
    walking around.
  - Dying in the last room of level 5, the one with the straw bed and the
    ladder down, used to put the wizard back in the level's first room, where
    the level could no longer be finished. He now starts again at the foot of
    the ladder he came down.


WHAT IT DOESN'T CHANGE
----------------------

  - Traps, fights, creatures and items are untouched. Anything that killed you
    without warning before will still do it.
  - There are still three lives per level, and a death on the last level
    still goes straight to Game Over, as in the original.
  - The graphics, music and sound are the game's own.
  - The ROM is still 1 MB.


REQUIRED ROM
------------

  Immortal, The (USA, Europe).md
  Size:    1,048,576 bytes
  CRC32:   F653C508
  SHA-1:   71FC189FE2BA5687E9D45B68830BAED27194F627

  The patch won't apply to any other dump. A .bin with the same contents is
  the same ROM.

  After patching:
  CRC32:   4E217FBF
  SHA-1:   F80E77D5CAD820C9D9917D62FDDFC6C93D3D7D29


HOW TO APPLY
------------

  The patch is a BPS file, Immortal-Genesis-Improvement-v1.0.bps. Apply it
  with Flips, or in a browser with Rom Patcher JS
  (https://www.marcrobledo.com/RomPatcher.js/). Both check that you've given
  them the right ROM.

  Keep a copy of your original ROM. The patch is applied to the original, not
  to an already patched copy.


SAVES AND EMULATORS
-------------------

  Saves need an emulator or cartridge with battery RAM. The patch has been
  tested in BlastEm, PicoDrive and Genesis Plus GX. It hasn't been tried on
  a real console or a flash cartridge.

  Emulators keep battery RAM in different file formats, so a save file from
  one emulator usually won't load in another.

  The patch works on a 50 Hz (PAL) console or emulator setting too. There
  the game runs about a sixth slower than at 60 Hz, as the original always
  did.


CREDITS
-------

  Patch by Christopher Childress (satelliteoflove).

  The Immortal was designed by Will Harvey and published on the Genesis by
  Electronic Arts.

  Thanks to the authors of BlastEm, PicoDrive, Genesis Plus GX, Flips and
  Rom Patcher JS, all of which were a big help in making and testing this.

  The source and notes are at
  https://github.com/satelliteoflove/immortal-genesis-improvement


VERSION HISTORY
---------------

  1.0 (2026-11-27)  First release.

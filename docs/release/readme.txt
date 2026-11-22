The Immortal (Genesis) Improvement Patch
Version 1.0
by Christopher Childress (satelliteoflove)

[DRAFT. Items in square brackets are still to be decided or filled in.]


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
  Measured in emulators, about a quarter of the game's updates ran late in the
  original, and more than half on level 6. With the patch it's under 2%, and
  nearly all of those are the game's own deliberate waits. Fights and other
  timed scenes still run at the original's speed.

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

  Holding a button makes messages type out faster without skipping the pauses
  in them, so you don't blow past something you wanted to read. A fresh press
  of A, B, C or Start still ends a pause. With no button held, messages are as
  they were.

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
  CRC32:   [9BED8A95, to be confirmed against the release build]
  SHA-1:   [CE53765F6935AE25CB78BBCC1451CB1971CE5BF3, likewise]


HOW TO APPLY
------------

  The patch is a BPS file, [file name]. Apply it with Flips, or in a browser
  with Rom Patcher JS (https://www.marcrobledo.com/RomPatcher.js/). Both check
  that you've given them the right ROM.

  Keep a copy of your original ROM. The patch is applied to the original, not
  to an already patched copy.


SAVES AND EMULATORS
-------------------

  Saves need an emulator or cartridge with battery RAM. The patch has been
  tested in BlastEm, PicoDrive and Genesis Plus GX. [Kega Fusion still to
  try.] It hasn't been tried on a real console or a flash cartridge.

  Emulators keep battery RAM in different file formats, so a save file from
  one emulator usually won't load in another.

  [The patch has only been tested at 60 Hz so far.]


CREDITS
-------

  Patch by Christopher Childress (satelliteoflove).

  The Immortal was designed by Will Harvey and published on the Genesis by
  Electronic Arts.

  Thanks to the authors of BlastEm, PicoDrive, Genesis Plus GX, Flips and
  Rom Patcher JS, all of which were a big help in making and testing this.

  [Source and notes: link to the GitHub repository once it's public.]


VERSION HISTORY
---------------

  1.0 ([date])  First release.

# TODO

What's been found so far is in `docs/how-the-game-works.md`. Items below are leads from
reviews unless they say otherwise, and what to change is still to be decided.

## First: see how the game works

- [x] Get it running under a test harness: scripted input, screenshots, frame timing.
- [x] Find the main loop and its timing.
- [x] Find how deaths and lives work.
- [ ] Trace how a room reaches the screen.
- [ ] Enter a real certificate and confirm what it holds.

## Fairness

- [ ] Deaths with little or no warning: traps that kill within seconds of entering a room.
- [ ] Game Over gets a screen offering Continue (restart the current level) or End (back to
      the main menu). Decided, not built. Three lives per level stay as they are. Check what
      the player is carrying after a Continue.
- [ ] Items that can be used up in the wrong place, forcing a restart.
- [ ] Battery saves in place of typing certificates. Looks very doable at the start of each
      level; see "Saving" in `docs/how-the-game-works.md`. Not decided or built.
- [ ] Fights that start with little warning.
- [ ] Fights that all play alike.
- [ ] Ladders, which can kill when approached from the wrong angle.

## Bugs

- [ ] No list yet. Look for known ones, and note any found along the way.

## Performance

Optimizing the existing code comes first. The game's timing doesn't change until we know how
the optimized game really runs.

- [x] Check the timing on a more accurate emulator. The BlastEm fork is the reference now.
- [ ] Offer the fork fixes back when we're ready (`docs/blastem-fork-fixes.md`). Not yet.
- [ ] Record a realistic route through the levels to measure, in place of random walks.
- [x] Object graphics: tiles are unpacked ahead of time. Level 6 went from 58% of ticks late
      to 20%, and level 5 from 41% to 24%.
- [x] Back to a 1 MB ROM with the game's own packed graphics. The object routine remembers the
      last 640 tiles it unpacked in spare RAM. Late ticks are 1.7%, as with the 2 MB build.
- [x] Background tiles: only new ones are sent when the camera moves. Late ticks across all
      levels went from 16.4% to 2.0%, and the game no longer misses vertical blanks.
- [ ] Slowdown that's left: 2.0% of ticks, mostly deliberate waits in animations on levels 2, 6
      and 7. Find out what those animations are.
- [x] Sprite masking reads shifted masks from tables. It costs about half what it did.
- [x] Camera steps: the cell routine is rewritten and the tile sync skips empty parts of its
      table. A step costs about 133k cycles where it cost 223k, and ticks needing over 3 frames
      of work went from 11.6% to 3.7%.
- [x] The sound link's two copies through Z80 memory are written out in place of loops. About
      900 cycles a frame saved.
- [ ] Listen to sampled sounds on levels 3, 4 and 7 against the original. The Z80 is stopped for
      less time now, so they should have shorter hitches and run about 0.7% faster.
- [x] Measure frames to a finished picture (`tick_parts.py --frames`): 91% of ticks are ready in
      2 frames and 99.5% in 3. The optimizing pass stops here, and `docs/optimizations.md` lists
      what wasn't done and why.
- [ ] Find out whether drawing that finishes after vertical blank shows on screen (16% of plain
      ticks, 52% of camera steps). Sending sprite tiles in vertical blank would fix it, and would
      shorten the Z80's stops as well.
- [x] Patch files. The 1 MB build no longer carries unpacked tiles. It still holds a few small
      things made from the game: the masking tables, 448 bytes of cell data, the sound link's
      own instructions and a table made from the tile index. Chris decided on 2026-11-19 that
      those bits and pieces aren't a problem in a patch file. `tools/make_patch.py` writes BPS
      and IPS files.
- [ ] Try the patch files with a patcher other than our own, such as Flips.
- [ ] Release the patch: where it goes, what it's called and what the notes say.
- [ ] Try the patched ROM on real hardware.
- [ ] Controls said to feel less responsive than the NES version. Measure the delay from
      button to screen.

- [x] Fights ran nearly three times too fast after the drawing got faster. They're held to the
      original's pace now.
- [ ] The death sequence and restart were reported as too fast. A death in a fight is the fight's
      ending animation, which is now at the old pace, and the retry after it measures the same as
      the original (about 90 frames). Waiting to hear whether it still looks wrong.
- [x] Message text flew by with a button held. It now types at twice the usual speed with a
      button held, and the pause at the end of a page stays. Normal typing is unchanged.
- [x] Smoother movement at the same game speed: tried and dropped. A trial drew an in-between
      picture each update; see `docs/smoother-movement.md`. Chris chose the original drawing
      speed.

## Bugs fixed

- [x] The wall torch's flame loses its top, from a slip in the game's tile search.
- [x] Stray miscolored pixels where a sprite passes behind scenery, from a mask shifted one bit
      too little.

- [x] The level's song kept starting over while walking about. The game asked for an alert song
      and for the level's song back within one frame, at about twenty places, whenever nothing
      came of the alert. Those pairs of requests are now dropped. Not yet listened to.

## Things to keep

The danger is the game's character. The aim is for a death to feel earned, not to remove it.

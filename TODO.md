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
- [ ] Slowdown that's left: 16.4% of ticks still run late in random walks, mostly from
      something other than object graphics. Find it, starting with levels 2, 4 and 8.
- [ ] Decide how the patch is released. The unpacked tiles are the game's graphics, so an
      ordinary IPS or BPS file would contain them. `tools/build_rom.py` makes them from the
      player's own ROM instead.
- [ ] Try the patched ROM on real hardware.
- [ ] Controls said to feel less responsive than the NES version. Measure the delay from
      button to screen.

## Bugs fixed

- [x] The wall torch's flame loses its top, from a slip in the game's tile search.

## Things to keep

The danger is the game's character. The aim is for a death to feel earned, not to remove it.

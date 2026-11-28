# TODO

What's been found so far is in `docs/how-the-game-works.md`. Items below are leads from
reviews unless they say otherwise, and what to change is still to be decided.

## First: see how the game works

- [x] Get it running under a test harness: scripted input, screenshots, frame timing.
- [x] Find the main loop and its timing.
- [x] Find how deaths and lives work.
- [ ] Trace how a room reaches the screen.
- [x] Enter a real certificate and confirm what it holds. One has been typed in and matches
      what the game loads itself; the digits haven't been tried one by one.

## Fairness

Chris decided on 2026-11-19 not to redesign the game: traps, fights and items stay as they
are, since changing them goes beyond what this patch is for. Fairness work is limited to
saves, retries, and things that are really bugs.

- [-] Deaths with little or no warning: traps that kill within seconds of entering a room. Out of scope.
- [x] Game Over asks "Try this level again?". YES restarts the level with three lives and what
      the wizard carried into it; NO goes on to the prompts a game starts with. Three lives per
      level stay as they are.
- [-] Items that can be used up in the wrong place, forcing a restart. Out of scope.
- [x] Battery saves. Each level reached is saved when the level before it ends, and the game
      offers the saved levels when it starts. Certificates still work. See "Saving" in
      `docs/how-the-game-works.md`; `tools/harness/save_check.py` checks it.
- [x] Play through a level's end and a Game Over by hand, to see the new screens in use. Chris
      played the whole game through and tried each new feature on 2026-11-22.
- [-] Fights that start with little warning. Out of scope.
- [-] Fights that all play alike. Out of scope.
- [-] Ladders, which can kill when approached from the wrong angle. Not a bug: a ladder hole is
      drawn with the ladder in one half and the other half open, and the game follows the
      picture. Stepping onto the open half falls, and coming from the open side always meets
      it first. Chris decided on 2026-11-19 to leave them as they are.

## Bugs

- [ ] No list yet. A web search on 2026-11-19 found almost nothing for the Genesis version:
      one MobyGames review mentions a glitch that helps the player, without details. Note
      any found along the way.
- [ ] Look into the retry test's other failures (`tools/harness/route/retry_test.py`). The
      ones looked at so far were the test's own: walking back after flying, past traps, or
      through rooms where the route does something special.

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
- [x] Listen to the sampled sounds. They're the fights' sounds, on every level, not only 3, 4
      and 7 as first thought. The Z80 is stopped for less time now, so they should have
      shorter hitches and run about 0.7% faster. Chris heard nothing off in his play-through
      on 2026-11-22.
- [x] Measure frames to a finished picture (`tick_parts.py --frames`): 91% of ticks are ready in
      2 frames and 99.5% in 3. The optimizing pass stops here, and `docs/optimizations.md` lists
      what wasn't done and why.
- [ ] Find out whether drawing that finishes after vertical blank shows on screen (16% of plain
      ticks, 52% of camera steps). Sending sprite tiles in vertical blank would fix it, and would
      shorten the Z80's stops as well.
- [x] Patch files. The 1 MB build no longer carries unpacked tiles. It still holds a few small
      things made from the game: the masking tables, 448 bytes of cell data, the sound link's
      own instructions and a table made from the tile index. Chris decided on 2026-11-19 that
      those bits and pieces aren't a problem in a patch file. `tools/make_patch.py` writes a
      BPS file, the only format we'll release. It stays out of git and goes out attached to
      a release.
- [ ] Try the patch file with a patcher other than our own, such as Flips or Rom Patcher JS.
      Not done before v1.0; our own applier checks it.
- [x] Release the patch. v1.0 went up on RHDN and as a GitHub release on 2026-11-27, as
      `Immortal-Genesis-Improvement-v1.0.bps` with `docs/release/readme.txt`. The RHDN texts are
      in `docs/release/rhdn.md`.
- [ ] Try the patched ROM on real hardware.
- [ ] Controls said to feel less responsive than the NES version. Measure the delay from
      button to screen.

- [x] Fights ran nearly three times too fast after the drawing got faster. They're held to the
      original's pace now.
- [x] The death sequence and restart were reported as too fast. A death in a fight is the fight's
      ending animation, which is now at the old pace, and the retry after it measures the same as
      the original (about 90 frames). Chris agreed it was too quick. "Prepare to continue..."
      now stays up for 3 seconds, and a press of A, B, C or Start ends it sooner.
- [x] Pauses in other messages could only be cut short with A or C after the change above. A
      fresh press of A, B, C or Start ends them now, as any button did in the original.
- [x] Message text flew by with a button held. It now types at about three times the usual
      speed with a button held, every letter drawn, and the pause at the end of a page stays. Normal typing is unchanged.
- [x] Smoother movement at the same game speed: tried and dropped. A trial drew an in-between
      picture each update; see `docs/smoother-movement.md`. Chris chose the original drawing
      speed.

## Dead code

- [x] Look for code that's never run. About 540 bytes in some twenty small pieces can't be
      reached; 13 kind handlers and 2 creature actions are reachable but never ran in our
      play. See `docs/dead-code.md`.
- [ ] Find out whether the 13 kind handlers belong to things placed on some level.

## Bugs fixed

- [x] A death in level 5's last room (room 10) put the wizard back in room 0, past a hole he
      couldn't go through again, and the level couldn't be finished. The retry table has ten
      entries a level and level 5 has eleven rooms. He now comes back at the foot of the
      ladder into room 10.

- [x] The wall torch's flame loses its top, from a slip in the game's tile search.
- [x] Stray miscolored pixels where a sprite passes behind scenery, from a mask shifted one bit
      too little.

- [x] The level's song kept starting over while walking about. The game asked for an alert song
      and for the level's song back within one frame, at about twenty places, whenever nothing
      came of the alert. Those pairs of requests are now dropped. Not yet listened to.

## Things to keep

The danger is the game's character. The aim is for a death to feel earned, not to remove it.

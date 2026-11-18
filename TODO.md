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
- [ ] Three lives per level is confirmed. Game Over sends you back to the first room unless
      you have a certificate to type in. The game can already reload a level without one.
- [ ] Items that can be used up in the wrong place, forcing a restart.
- [ ] Passwords. The header declares no save RAM and the ROM is 1 MB, so there's room to
      add saving, though it would need a cartridge or emulator that provides the RAM.
- [ ] Fights that start with little warning.
- [ ] Fights that all play alike.
- [ ] Ladders, which can kill when approached from the wrong angle.

## Bugs

- [ ] No list yet. Look for known ones, and note any found along the way.

## Performance

- [ ] Slowdown: 23% of ticks ran late in random walks, and about half on level 6. Object
      graphics are the first suspect on levels 5 and 6. Levels 2, 4 and 8 need another answer.
- [ ] Controls said to feel less responsive than the NES version. Measure the delay from
      button to screen.

## Things to keep

The danger is the game's character. The aim is for a death to feel earned, not to remove it.

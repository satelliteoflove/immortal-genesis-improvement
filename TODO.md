# TODO

Everything under the three goals is a lead from reviews or from the ROM's header. None of
it has been checked in the game yet, and what to change is still to be decided.

## First: see how the game works

- [ ] Get it running under a test harness: scripted input, screenshots, frame timing.
- [ ] Find the main loop, how it draws, and what it does in the vertical blank.
- [ ] Find how deaths, lives per floor and passwords work.

## Fairness

- [ ] Deaths with little or no warning: traps that kill within seconds of entering a room.
- [ ] Three lives per floor, and what a failed floor costs.
- [ ] Items that can be used up in the wrong place, forcing a restart.
- [ ] Passwords. The header declares no save RAM and the ROM is 1 MB, so there's room to
      add saving, though it would need a cartridge or emulator that provides the RAM.
- [ ] Fights that start with little warning.
- [ ] Fights that all play alike.
- [ ] Ladders, which can kill when approached from the wrong angle.

## Bugs

- [ ] No list yet. Look for known ones, and note any found along the way.

## Performance

- [ ] Slowdown on busy screens.
- [ ] Controls said to feel less responsive than the NES version. Measure the delay from
      button to screen.

## Things to keep

The danger is the game's character. The aim is for a death to feel earned, not to remove it.

# Playing the game by script

The aim is a test that plays every level from start to finish, on the original ROM and on the
patched one, so that a change to the patch can be checked against the whole game and not just
random walks.

This file is the shared notebook for that work. Whoever is writing a level's route reads it
before starting and again before each new problem, and adds to "What we've learned" as soon as
something is worked out. That section is how one level's lessons reach the others.

## How a route is written

A route is a Python script that watches the game's memory and decides each press from it:
walk until the wizard is at this spot, wait until the trap has fired, strike when the enemy is
open. It never presses a button because a certain frame has come. The original runs late on
about a quarter of its updates and the patched game on under 2%, so anything keyed to frame
numbers falls out of step between the two within seconds.

`tools/harness/play.py` has the `Game` class. `step(frames, buttons)` runs the game and
brings back the whole of the 68000's RAM; `keep(slot)` and `back(slot)` remember and restore the
machine's state, which is what makes exploring quick; `shot(path)` writes a picture to look at.
Its docstring has the rest.

Each level stands on its own. It starts from a certificate, so a break in one level doesn't take
the later ones down with it. These seven are from a 1991 walkthrough of the computer version,
and the Genesis ROM accepts all of them:

| Level | Certificate |
|---|---|
| 2 | `cddff10006f70` |
| 3 | `f47ef21000e10` |
| 4 | `b5fff31001eb0` |
| 5 | `d630f43000eb0` |
| 6 | `563ff53010a41` |
| 7 | `c250f63010ac1` |
| 8 | `e011f730178c1` |

Level 1 starts from a new game.

## The files

    tools/harness/play.py             the Game class
    tools/harness/route/common.py     helpers every level uses: walking, messages, fights, things
    tools/harness/route/level1.py     one for each level, 1 to 8
    scratch/route/levelN/             pictures, saved states and notes while working; git ignores it
    scratch/walkthroughs/             the two walkthroughs; not ours, so not tracked

A level's file has:

    CERTIFICATE = 'cddff10006f70'       # None for level 1
    def play(g, log=print):             # g is a Game standing at the start of the level
        ...                             # plays to the "End of level!" screen and stops there
        return certificate              # the 13 letters the game made; None after level 8's ending

and runs by itself: `tools/harness/route/level2.py [--original] [--delay N]`, where `--delay`
waits N frames before the first press.

## Rules for a finished route

- It passes six times over: on the patched ROM and on the original, each with `--delay` 0, 3
  and 11. If the game's chances depend on timing, that is what catches a route that only works
  by luck.
- `play()` doesn't poke memory, and doesn't use `keep` or `back`. Those are for exploring.
- It reads RAM for every decision and every wait. A fixed wait is fine only for something the
  game itself times, and then it's counted in the game's updates, not frames.
- It finishes without a Game Over. Say in the log if a life was lost on the way.
- It checks itself as it goes: the room it expects, the thing it just picked up, health above
  zero. When something is wrong it stops with a message that says where and what, and writes a
  picture to `scratch/route/levelN/`.
- Anything another level could use goes in `common.py`, not the level's own file. Before writing
  a helper, look there first.

## What may be tracked

Our own scripts, addresses, coordinates, thing numbers and descriptions in our own words. Not
pictures, saved states, RAM dumps or stretches of the game's code or text. Nothing from the
walkthroughs is copied into tracked files.

## What's known about the game's memory

The game's variables are addressed from `FF0300` (a4). `docs/how-the-game-works.md` has more,
and `disasm/immortal.dis` is the whole disassembly (made by `tools/disasm.py`, not tracked).

| Address | What | How sure |
|---|---|---|
| `FF1070` | Level, 0 to 7 | Seen |
| `FF1051` | Room | Seen |
| `FF08BC` | The wizard's x. LEFT lowers it, RIGHT raises it | Seen once |
| `FF08D0` | The wizard's y. DOWN raises it | Seen once |
| `FF090C` | The wizard's health in the high four bits, 15 at most | Read from code |
| `FF109A` | Retries left on this level, 2 at its start | Seen |
| `FF0AEE` | 42 bytes, one for each thing on the level or carried, `FF` for none | Seen |
| `FF106F` | Set when the level is over | Seen |
| `FF1072` | Set when the retries have run out | Seen |
| `FF108C` | A certificate's 13 digits, a byte each | Seen |
| `FF9624` | Count of vertical blanks (long) | Seen |
| `FF12E6` | The count at which the next update may begin (long). An update is 5 frames | Seen |
| `FF962A` | Pad 1 as the game last read it | Read from code |

The x and y look like bytes in tables of 20, one entry for each moving thing, with the wizard
first: `FF08BC` + n and `FF08D0` + n. That's a guess from one look.

Messages: a box of text waits for a button at the end of each page. A question shows NO on the
left and YES on the right, and is answered by holding LEFT or RIGHT and pressing a button.

## What we've learned

Add to this as you go: the date, the level you're on, and what you found, in a few lines.
Put how to use it, not how you found it. If it's a helper, say its name in `common.py`.

- 2026-11-19, groundwork: the walkthrough's certificates are in capitals; the game's fields
  hold the digits' values, so `start_level` takes them in either case.
- 2026-11-19, groundwork: with a battery save present the patched game asks "Continue a saved
  game?" before "New game?". `Game()` is started without a battery file unless one is asked
  for, so routes never meet that prompt.

## Where each level stands

| Level | Route | Passes six runs |
|---|---|---|
| 1 | not started | |
| 2 | not started | |
| 3 | not started | |
| 4 | not started | |
| 5 | not started | |
| 6 | not started | |
| 7 | not started | |
| 8 | not started | |

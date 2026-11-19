# Code the game never runs

A survey on 2026-11-19 of the original ROM's code, to find routines that nothing reaches. It
took two passes. The first follows the code from the 68000's vectors. The second records
every instruction that runs while the eight level routes play.

## In short

About 540 bytes of the game's code can't be reached at all, and none of it ran in any play.
It comes in about twenty pieces, the largest 126 bytes. Most are small helpers that lost their
callers: a hex printer for debugging, a division routine, a sort, a Start-button reader, a
second way into the message routine, and some entries into the sound driver.

A further 13 of the 91 handlers for kinds of thing, and 2 of the 38 creature actions, are
reachable through the game's tables but never ran in our play. They may belong to things off
the routes' paths, so they aren't counted as dead.

## How code is reached

Most of the game's code isn't reached by plain calls, which is why the disassembly had large
gaps. These are the ways in that were found:

- **Calls through a6 and a3.** At start-up the game sets a4 to 0, a6 to `018000` and a3 to
  `008000`, and then a4 to `FF0300`. a6 and a3 keep those values for calls such as
  `jsr -$48F6(a6)`, which is a call to `01370A`.
- **Callbacks.** A caller puts a code address in `$304`/`$305(a4)` as two byte moves, low byte
  first, and calls `00D98E`, which keeps it in `$B66`/`$B67` and jumps to it through a3 for
  each thing it visits. Eight callbacks were found: `5D28`, `98F6`, `9C48`, `9C60`, `A728`,
  `ACEE`, `B36A`, `C520`.
- **Creature actions.** A table of 3-byte records from `005991`: the action's address, high
  byte first, then a parameter. Creatures step through lists of record offsets that start at
  `005A35`, and `005C34` pushes the address and returns into it. There are 38 distinct
  actions.
- **Handlers for each kind of thing.** For kind n, the handler's address is the byte at
  `005864`+n (low) and `0058C8`+n (high), and its parameter is at `00592C`+n. `012E9A`
  jumps to it. Kinds 1 to 91 have handlers, with 85 different addresses.
- **Sound commands.** The driver's command handler (`01646C`) jumps through a table of 73
  long offsets from `015D08`, at `01648A`.
- **The new routines.** Our patch's own code at `0FD65C` and up is reached through the jumps
  `tools/build_rom.py` writes, and isn't part of this survey.

## Code nothing reaches

None of these is reached by any of the ways above, and none ran in any play. Addresses are in
the original ROM, and the patched ROM has them at the same places.

| Where | Bytes | What it is |
|---|---|---|
| `005B76` | 2 | A branch to itself: an endless loop with no way in |
| `00CDC8`-`00CDF2` | 42 | A second way into the message routine, like `00CD56` but without starting a new box |
| `012650`-`01266C` | 28 | A lone `rts`, then a wait for a fresh press of A or C that returns 13 |
| `012A60`-`012A74` | 20 | Shows a message, then reads C and A. (`012A50`, just before it, is the certificate's letter table, which is used) |
| `012C9A`-`012CA0` | 6 | Sets the carry and returns |
| `0132CA`-`0132E0` | 22 | Puts a 16-bit address into `$304`/`$305` from two byte tables at `001684` and `00177E` |
| `013328`-`013362` | 58 | Prints a byte as two hex digits, with its own table of digits: a debugging aid |
| `0134DC`-`0134E8`, `01544E`-`015466` | 36 | A reader for the Start button, made like the game's readers for A, B and C |
| `013C50`-`013C6E` | 30 | Fills 612 words of RAM at `FF714A` with 0, 1, 2... and calls `013BF6` |
| `0154F4`-`015572` | 126 | A 64-by-32-bit unsigned division, then a sort of two lists of words side by side. The patch's text wait now sits here |
| `015CFA`-`015D08`, `015D14` | 18 | The fourth entry in the sound driver's jump table, and a wrapper that calls it. It leads to a routine that sets the flag at `FF022F`, which is also reached other ways |
| `015DFC`-`015E10`, `015E1A`-`015E24` | 30 | Two more small driver routines that set flags in its RAM |
| `016030`-`01603E` | 14 | A second way into a driver routine |
| `016342`-`016378` | 54 | Silences all six of the driver's channels and calls `01621E` |
| `016426`-`016432`, `016750`, `01678C`-`01679A` | 32 | Lookups into small tables in the driver |
| `016A2E`-`016A3C` | 14 | A sound command handler that isn't in the command table |

`013C80`-`013D34` and `016754`-`01678C` look like code at first but are tables that the
code reads.

Since nothing jumps into these pieces, they can be overwritten without changing anything else.
None is big enough for much: the death pause (58 bytes) went into the old tile sync's body for
the same reason. The masking tables for shapes 6 to 15 (about 5 KB, see `TODO.md`) are still
the one large reserve.

## Reachable but never run

These are reached through the tables, but none of their code ran while the routes played all
eight levels. The routes skip some optional things, such as level 3's ring and gold, and never
make wrong choices, so a handler here may simply belong to something off their paths. Finding
out would mean reading which kinds each level's data places, which hasn't been done.

- Kind handlers: kinds 2 (`9ABA`), 3 (`B38C`), 36 (`B2E0`), 41 (`9DDA`), 43 (`9DB8`), 46
  (`A2F0`), 47 (`A74C`), 57 (`A2FC`), 59 (`A780`), 70 (`A4A0`), 83 (`AD22`), 84 (`AC8E`) and
  85 (`A3CA`).
- Creature actions: `6B4C` and `6CC4`.

Inside routines that do run, many branches never ran too: deaths, wrong answers, Game Over and
the like. Those weren't listed, since our play doesn't try to reach them.

## How it was done

- Static: the vectors, then everything reachable through direct branches and the ways in
  above, with a third input, `scratch/entries.txt`, a list of addresses seen running in earlier
  profiling. Every stretch left over was decoded, and those that decode as code without a
  break were looked at by hand.
- Running: `tools/harness/build_coverage_core.sh` builds a libretro core from the BlastEm fork
  with the 68000 interpreter, counting each instruction it runs. `play.py` uses it when
  `PLAY_CORE` names it, and the runner's `prof FILE` command writes the counts. Each level's
  route was played on it: levels 1 and 2 on the original ROM and levels 3 to 8 on the patched
  one, since the interpreter's timing differs a little from the recompiler's and level 3's route
  doesn't get past its door troll on the original there. The game's own code is at the same
  addresses in both ROMs.
- The scripts are in `scratch/dead/`, which git ignores: `reach.py` for the static pass,
  `gaps.py`, `pairs.py` for the callbacks, `cov_level.py` and `cov_game.py` to play on the
  coverage core, and `compare.py`.

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
| 4 | `level4.py` gets past the troll, takes the carpet and flies the first flame room (room 4) to the door of the second | Those parts pass on both ROMs |
| 5 | `level5.py` plays rooms 8, 0, 1, 2, 4 and 5 (egg, potion, hole, trolls, chest, lizards, key, worm room) to the door of the last room | Those parts pass on both ROMs |
| 6 | `563ff53010a41` |
| 7 | `c250f63010ac1` |
| 8 | `level8.py` plays the whole level: chest, ladder, pit, the dragon, the teacher, the closing story | All six pass |

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
| `FF08BC` | The wizard's x in the room. LEFT lowers it by 3 an update, RIGHT raises it | Seen, level 1 |
| `FF08D0` | The wizard's y in the room. UP lowers it by 4 an update, DOWN raises it | Seen, level 1 |
| `FF090C` | The wizard's health in the high four bits, 15 at most | Seen through a fight, level 1 |
| `FF109A` | Retries left on this level, 2 at its start | Seen |
| `FF0AEE` | 42 bytes, one for each thing on the level or carried, `FF` for none | Seen |
| `FF106F` | Set when the level is over, and cleared again within an update | Seen |
| `FF1072` | Set when the retries have run out | Seen |
| `FF108C` | A certificate's 13 digits, a byte each | Seen |
| `FF9624` | Count of vertical blanks (long) | Seen |
| `FF12E6` | The count at which the next update may begin (long). An update is 5 frames | Seen |
| `FF962A` | Pad 1 as the game last read it: UP 01, DOWN 02, LEFT 04, RIGHT 08, B 10, C 20, A 40, START 80 | Seen |
| `FF0C4E` | Bit 1 set while the game has seen C down, bit 2 for A. It acts on a press only when the bit was clear | Seen |
| `FF0C52` | The last letter a text box drew. `40` or `00` when the text has ended and waits for a button, `3D` when it ended without waiting | Seen |
| `FF0C4C` | The length of the text box's wait in progress: 5 after a letter, `8C` or `28` for the pause at the end of a page | Seen |
| `FF0C4D` | A question's lit answer: 0 none, 1 NO, 2 YES. Only a question on screen changes it, and it's left as it was afterward | Seen |
| `FF0A70`, `FF0A9A` | Each thing's x and y, 42 bytes each, in step with the things table at `FF0AEE` | Seen |
| `FF0B42` | Each thing's place: `40` carried by the wizard, `40`+n by creature n, `80`+n on the floor of room n, lower numbers inside the thing of that number | Seen |
| `FF0DD4`+16, `FF0D54`+16, `FF0C54` | How many things the wizard carries, where his list starts, and the lists themselves (thing numbers, in inventory order) | Seen |
| `FF08F8` | 20 bytes, one for each creature (the wizard first): the number of the list that holds what it carries. The wizard's is 16 after a new game and 0 after a certificate | Seen, levels 1 and 6 |
| `FF0B6C` | 42 bytes in step with the things table: for a chest or body, the number of the list of what's inside it | Seen, level 6 |
| `FF1083` | The inventory's cursor: slot 0 to 5. `FF1086` is 1 if it was left with A | Seen |
| `FF1087` | The inventory page's first index into the carried list: 0, 5, 10 | Seen |
| `FF0A17` | The thing number of the fireball scroll once it has been used, `FF` before | Seen |
| `FF0A4C`, `FF0A4D` | The game's own copy of the wizard's x and y. It stops following `FF08BC`/`FF08D0` while he walks through a doorway by himself | Seen, level 1 |
| `FF090C` + n, `FF0920` + n | Creature n's health (high four bits) and pose (low seven bits); the wizard is n 0 | Seen, level 4 |
| `FF090C` + n, low four bits | The room creature n is in | Seen, level 3 |
| `FF0B6C` + a scroll's thing number | The fireballs left in it | Seen, level 3 |
| `FF0F62`, `FF0F68`, `FF0BCC` | Level 3's spike room: the x and y of the spike that is up, and its step in a round of 15 | Seen, level 3 |
| `FF0A1D` | 1 while the wizard is on the flying carpet | Seen, level 4 |
| `FF0A3E`, `FF0A3F` | The carpet's speed across and down, signed, -5 to 5 | Seen, level 4 |
| `FF1042` | The carpet's life left: 25 new, 1 less every 16 updates of flying | Seen, level 4 |
| `FF1043` | Steps on foot left before a worm comes (level 4's flame rooms): 16 on entering | Seen, level 4 |
| `FF0F80` + i, `FF0F88` + i, `FF0F90` + i | Fireball i of 8: x, y, and `FF` when the slot is empty | Seen, level 4 |
| `FF0984` | The barrel's speed on level 7's water: across in the low four bits, down in the high four, each signed, -5 to 5, half a step an update | Seen, level 7 |
| `FF1044`, `FF1045`, `FF1046` | Level 7's water monster: a count of updates 0 to 9, 1 once it is after the wizard, and the tens of updates since | Read from code, used |
| `FF10AE` | Not zero while a fight is on | Seen |
| `FF10A7`, `FF10A8` | In a fight, the enemy's health and the wizard's. A hit takes 1 | Seen |
| `FF10B0`, `FF10B2` | In a fight, the wizard's move and the enemy's (see "Fights" below) | Read from code, used |
| `FF10A6`, `FF10A5` | In a fight, the wizard's pose and the enemy's | Read from code, used |
| `FF0A1D`, `FF0A1C` | The wizard's size (3 while small from level 5's potion, 0 normal) and the updates of smallness left, about 126 falling by 1 an update (`FF` when unused) | Seen, level 5 |
| `FF0970` | 20 bytes of flags, one for each creature, the wizard first. Bit 6: poisoned, a point of health goes every 16 updates of the main loop | Read from code (`0076FE`), seen on level 5 |
| `FF09FC` + n | What creature n is having done to it, the wizard being n 0: 0 when free, else the number of a posted happening (a fall's landing, a spell on himself, a killing blow). `action(g)` | Read from code (`006452`, `0077C0`), seen on level 8 |
| `FF0AC4` + thing | The picture each thing is showing, 42 bytes in step with the things table. `thing_frame(g, n)` | Read from code (`00C976`), seen on level 8 |
| `FF0E68` + slot, `FF0E88` + slot | 32 slots of scripted animations: how far through each is (starts at 3, +1 an update, `FF` when the slot is free) and which animation it is. `animation(g, slot)` | Read from code (`00DA90` to `00DB64`), used on level 8 |
| `FF0600`, `FF0601` | While a text box is up, the ROM address its text began at, low byte first. `text_address(g)` | Read from code (`0132B4`), used on level 8 |
| `FF0C02` | The game's random numbers: 55 bytes, with its two indexes at `FF0C3A` and `FF0C3B` | Read from code (`00CCF4`) |
| `FF103E`, `FF103F` | Casts left in the blink book and the statue book, 6 each | Seen, level 8 |
| `FF0BC2`, `FF0BC3` | Level 8's dragon: how many of its 24 moves it has begun, and the slot of the animation running (`FF` between moves) | Read from code (`00BE7A`), used |
| `FF0BBD`, `FF0BBE`, `FF0BBC` | Level 8's teacher: moves begun, the move he is in, and its animation's slot | Read from code (`00BC1E`), used |
| `FF0BC4` | Level 8: 0 while the dragon attacks, 1 once the amulet is held up, 2 once the teacher has come | Read from code, used |

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

- 2026-11-19, level 1, **the buttons**. Walking: C opens the inventory, A fires the fireball
  once its scroll has been used, B and START do nothing. In a text box: a fresh press of C or
  A ends the wait in progress, and any button held hurries the typing. In a fight: LEFT or
  RIGHT alone slashes, A alone jabs, C or B with LEFT or RIGHT dodges.
- 2026-11-19, level 1, **presses**. The game looks at the pad once an update while walking
  (5 frames, up to 11 on the original) and every 4 or 5 frames in a text box or the inventory.
  A 4-frame press can be missed altogether. Hold a button until RAM shows it was seen
  (`FF0C4E`), which is what the helpers do. C and A only count when fresh, so a C still held
  when a text box closes does not open the inventory, but letting go and pressing again does.
- 2026-11-19, level 1, **trap in play.py**: in a new `Game()`, `g.load(file)` before any
  `g.step()` leaves the machine frozen (nothing errors, RAM just never changes). Do
  `g.step(1)` first. `keep`/`back` after a step are fine.
- 2026-11-19, level 1, **busy**. `busy(g)` is true when the main loop has stopped going
  round (vertical blank count more than 12 past the deadline at `FF12E6`): a text box, the
  inventory, a fight, a death. It shows about 12 frames after the thing begins, so after
  walking onto something call `wait_busy(g)` before `read(g)`. `tick(g, buttons)` runs one
  update and returns False if none came.
- 2026-11-19, level 1, **text boxes**: `read(g, answers='', quiet=24)` gets through whatever
  text is up and returns when the game is running again. `answers` has a letter for each
  question on the way, `'y'` or `'n'`: searching the first body is `read(g, 'yyy')` (search?
  take the first thing? take the second?). It raises if a question comes with no answer
  given, or if answers are left over after 600 frames of the game running. Text boxes are
  not part of the main loop; the routine at `00CF04` runs until the text is done. Pages in
  the middle pause and go on by themselves; the last page waits for C or A unless the text
  ends with its no-wait mark, as the candle's speech in the first room does. `read` holds B
  through the typing because B hurries text and does nothing anywhere else.
- 2026-11-19, level 1, **questions**: the lit answer follows the pad (RIGHT for YES, LEFT for
  NO) and C or A takes it. `FF0C4D` keeps its value after the question has gone, so `read`
  holds the other direction, then the wanted one, and presses C only after seeing the byte
  follow. Don't press C at a question by frame count.
- 2026-11-19, level 1, **walking**: the wizard's x and y are in the room's own coordinates,
  screen-wise, not along the tiles: LEFT is x-3 an update, UP is y-4, a diagonal is 2 and 2.
  The room's walls run diagonally, and walking into one slides the wizard along it, so he is
  seldom stuck dead. `walk_to(g, x, y)` walks a straight line and says how it ended
  (`'there'`, `'busy'`, `'room'`, `'stop'`), raising `Stuck` after 6 updates without moving.
  `go(g, (x, y), ...)` walks through points and raises unless each is reached. Take a
  position from RAM with `xy(g)` after stepping by hand, and look at `g.shot()` to see what
  is in the way: floor traps don't show in RAM before they fire.
- 2026-11-19, level 1, **doors**: nothing special in RAM. Walk into the doorway and the room
  number changes while the wizard keeps walking; his x and y jump to the new room's numbers.
  `through_door(g, buttons, room)` holds the buttons until the room changes and checks it.
- 2026-11-19, level 1, **things**: a thing is one index in seven 42-byte tables. Its kind is
  at `FF0AEE`, x and y at `FF0A70` and `FF0A9A`, its place at `FF0B42`. A body or chest is a
  thing on the floor (`80`+room) and what's in it has the container's number as its place.
  Walking to within about 9 across and 7 up or down of a container's x and y brings up its
  question by itself; no button. Taking something sets its place to `40`. `has(g, n)`,
  `place(g, n)`, `thing_xy(g, n)` and `carried(g)` read these. Print the tables at the start
  of your level to see where everything is.
- 2026-11-19, level 1, **inventory**: C opens it. It shows five things a page in slots 0 to
  4, and slot 5 is "more" when there are over five. Slot 0 is top middle, 1 top left, 2 top
  right, 3 bottom left, 4 bottom middle, 5 bottom right, and the things fill them in the
  order of `carried(g)`. There is no moving cursor: the slot is chosen by the direction held
  when A is pressed (none 0, LEFT 1, RIGHT 2, DOWN+LEFT 3, DOWN 4, DOWN+RIGHT 5). A uses the
  thing and closes the screen; choosing a thing with no use just closes it. `use(g, n)` does
  all of it for thing number n and checks the cursor at `FF1083` before pressing. Paging past
  five things is written but not yet tried.
- 2026-11-19, level 1, **fights**: an enemy that reaches the wizard starts one; `FF10AE`
  goes non-zero and the fight's own loop (`011590`) runs until one side's health is 0. The
  wizard's move is at `FF10B0` (0 free, 1 to 4 a slash begun with LEFT, 5 to 8 one begun with
  RIGHT, 9, 10 and 12 a jab, 11 reeling from a hit) and the enemy's at `FF10B2` (4 and 5 a
  swing that C+LEFT dodges, 8 and 9 one that C+RIGHT dodges, 2 and 3 its own dodges, 1
  reeling). The wizard can only dodge while his move is 0. Every hit takes 1 health.
  `fight(g)` dodges whenever the enemy is in a swing and slashes otherwise, changing sides so
  the next slash skips its wind-up. It returns the health left and raises `Died`. On the
  first goblin (3 health) it won 26 runs out of 26 without being hit, on both ROMs.
- 2026-11-19, level 1, **inventory pages**: tried with seven things. `use(g, n)` reached a
  thing on the second page on both ROMs. "Other" on the last page goes back to the first.
  The chest's gold went onto the wizard's own (20 became 40) without a slot of its own.
- 2026-11-19, level 1, **fireball**: using the scroll (thing 6 on level 1) only arms it; a
  text box says so, and `FF0A17` then holds the scroll's thing number (`FF` before). After
  that every fresh press of A while walking fires one of its three shots, which is why
  `read` and `use` never leave a stray A or C press behind.
- 2026-11-19, level 1, **containers**: `search(g, answers, *things)` waits for the box,
  answers, and checks each thing number is carried. A body or chest is solid, about 12 by
  12; the question comes when the wizard bumps it and doesn't come again once it's empty.
  A chest lists what's in it one question at a time, last thing in the table first. A key
  that has been used leaves the carried list.
- 2026-11-19, level 1, **people**: creatures' x and y are the other entries of the tables at
  `FF08BC` and `FF08D0` (entry n is creature n, the one a thing's place `40`+n names). An
  enemy starts the fight itself when the wizard is near, about 25 away on level 1, so walk
  with `walk_to(g, x, y, stop=fighting)` and then call `fight(g)`. A friend talks when
  walked into: `walk_to` returns `'busy'`, then `wait_busy(g); read(g)`. The second goblin
  of level 1 took about 1,800 frames to beat and never landed a hit in twelve runs.
- 2026-11-19, level 1, **dying**: health (`FF090C`, high bits) goes to 0, about 4 seconds
  later the retries at `FF109A` drop by one, a "prepare to continue" box comes and goes by
  itself, and the wizard stands at the room's entrance with full health. `dead(g)` is health
  0; `revive(g)` waits it out and returns the retries left, raising `Died` on the last life.
  `walk_to` raises `Died` if he dies on the way. The first room's marked floor tiles are a
  trap that kills about 5 seconds after its warning if the wizard stays on them.
- 2026-11-19, level 1, **end of the level**: `end_of_level(g)` waits for the "End of level!"
  screen and returns the certificate from `FF108C`; end `play()` with `return
  end_of_level(g)`. `FF106F` is set for less than an update, so it can't be waited on. The
  screen is found by the certificate's level digit (`FF1091`) being one more than the level
  being played, with the text box waiting. On the patched ROM the screen also says the game
  was saved, even with no battery file. Proven by poking `FF106F` in room 3: both ROMs gave
  `4cdcf10000220`. It is not for level 8, which has no certificate.
- 2026-11-19, level 1, **running a level's file**: `main(LEVEL, play, CERTIFICATE)` in
  `common.py` handles `--original`, `--delay` and `--quiet`, starts the level, gives `play`
  a `log` that stamps each line with the frame, room, position and health, and prints one
  line of result. `level1.py` shows the shape. `fail(g, LEVEL, message)` writes a picture
  and raises.
- 2026-11-19, level 1, **mapping a room**: `tools/harness/route/explore.py` has
  `room_map(g)`, which walks everywhere from where the wizard stands (using kept states, so
  never in `play()`) and returns a text map: where he can stand, where a step stops the game
  (a text box, a trap, a fight), and where a step leads to another room. About a minute a
  room. It only tries the four straight directions, so a door that is entered by sliding
  along a wall shows as a narrow neck at the room's edge, not as a room number: walk into
  the neck to find out. Enemies move while it runs, so make a map again after a fight.
- 2026-11-19, level 1, **what `walk_to` can't see**: `tick` gives up after 40 frames with no
  update and `walk_to` then returns `'busy'`. That's a text box nearly always, but check
  with `busy(g)` and a picture when it comes somewhere unexpected.
- 2026-11-19, level 1, **things that speak late**: the candle in the first room is solid and
  only speaks after about 16 updates of pushing against it, by which time `walk_to` has
  raised `Stuck`. `bump(g, buttons)` holds a direction until the game stops. Then `read(g)`:
  it got through the candle's four pages in 686 frames on the patched ROM and 265 on the
  original (a held button skips the original's page pauses), against 1,350 with no presses.
- 2026-11-19, level 6, **shared helper changed: `carried(g)`**. It read list 16, which is
  the wizard's only after a new game. Started from a certificate his list is number 0, and
  `carried` returned junk (so `use` and `search` failed). It now looks the list's number up
  at `FF08F8`. Lists are handed out as the level loads; a room has two (`FF0EC6` + room and
  `FF0ED6` + room, the second being the things on its floor) and a chest or body has one
  (`FF0B6C` + its thing number).
- 2026-11-19, level 1, **shared helper changed: `through_door`** now waits until the wizard
  can be steered again. After the room number changes he walks in by himself for about 4
  updates and ignores the pad; `through_door` used to return after 1. `walking_in(g)` is the
  test (`FF0A4C`/`FF0A4D`, the game's own note of his x and y, stand still meanwhile).
  Callers get the same positions as before, since their first presses were being ignored.
  `room_map` now tries diagonals where the straight moves find nothing, and marks `x` where
  a step costs health or kills. A door can need one particular direction: level 1's room 7
  to room 1 opens to LEFT (sliding down the wall) but not to UP+LEFT from below it.
- 2026-11-19, level 1, **loose things and the dead**: a thing lying on a room's floor (gold
  in level 1's room 7) is picked up by walking to its x and y: a box says what it was,
  `read(g)`, and its kind goes to `FF`. A beaten enemy that carried things asks its questions
  the moment the fight ends, so follow `fight(g)` with `search(g, 'yyy', 15, 16)` and the
  like, not `read(g)`, which will time out on the question.
- 2026-11-19, level 4, **a fight with no fight screen**. Level 4 opens with a troll swinging
  at the wizard where they stand in the room: `FF10AE` stays 0, `busy` is false, `fight()`
  doesn't apply, and the wizard can't walk until the troll is dead (a man across the room
  kills it; then about 8 updates more). Each creature has a health byte at `FF090C` + n
  (high four bits, the wizard is n 0) and a pose at `FF0920` + n (low seven bits). A blow
  costs 2. Holding LEFT or RIGHT as the blow lands turns it and hits the troll; the side
  wanted goes with the pose the troll has wound up in (`first_troll` in `level4.py`: pose
  `13` wants LEFT, `0D`/`0E` want RIGHT). UP hits the troll but doesn't turn the blow.
  `start_level` waits 120 frames after the level loads and blows land in that time: the
  wizard is at 13 of the certificate's 15 when a route's `play()` begins. The original gets
  two more swings in than the patched ROM before the troll dies.
- 2026-11-19, level 4, **people are things too**. The man who gives the carpet is thing 5
  in the things table, on the floor of his room, and what he gives is a thing inside him
  (place 5). Walk to within about 7 of his thing's x and y and he talks; `read(g)`, then
  `has(g, 6)`. The creature tables' x and y for him are something else; use the thing's.
- 2026-11-19, level 7, **giving a thing to a person**. No inventory press is needed. Walk
  into the person (the chained man on level 7 is thing 4, a thing on the floor like level
  4's man), his words come up, and the last box is a question: give him the ring? So
  `walk_to` returns `'busy'`, then `wait_busy(g); read(g, 'y')`. The thing given goes from
  the table (its kind at `FF0AEE` becomes `FF`, so `has` is false) and what he held (place
  = his thing number) is now carried. Check both.
- 2026-11-19, level 7, **a ladder down is a hole with a safe side**. Stepping onto the hole
  from the side the ladder leans on, the wizard snaps to the middle, climbs for about 38
  updates deaf to the pad, and the room changes: `through_door(g, 'LEFT', room)` covers it.
  Stepping onto the same hole from the other side drops him in and kills him (health 0 six
  updates later). On level 7's room 1 the safe side is the right and top right of the hole;
  the left, bottom and top left kill. Try each side from a kept state before choosing.
- 2026-11-19, level 7, **stale table entries**. The things tables aren't cleared between
  levels: after `start_level` the entries past the level's own things still hold level 1's
  x, y and place (their kind is `FF`). Count a level's things by the kinds at `FF0AEE`.
- 2026-11-19, level 1, **meeting creatures**: `walk_to(..., stop=fighting)` to a creature's
  spot is a race; in one run in six the wizard arrived before the goblin reacted and the
  route's next step failed. `meet(g, n)` walks at creature n (following it by
  `creature_xy(g, n)`) until it fights (`'fight'`) or a box comes (`'spoke'`), and
  `attack(g, n)` does that, reads any warning, and wins the fight. Also: a friend who is
  close when his attacker falls speaks at once, so the `read(g)` after the fight may already
  have taken what he gives. Check `has()` before walking over to him.
- 2026-11-19, level 1, **aiming at doors**: the side a door is come at from matters. Room 3's
  top door opens to UP from x 197 or less (sliding along the wall) and from x 200 the wizard
  sticks in the corner beside it. Try the approach from a few spots with keep/back before
  trusting it, and run all three delays early: they end walks a step apart. `walk_to` with
  `near=1` can step back and forth over a spot for ever; leave `near` at 2.
- 2026-11-19, level 5, **fights: `fight(g, counter=True)` for trolls**. Level 5's trolls
  (7 health) hit the wizard eight times running under the plain `fight`: it slashes while
  the enemy is free, a slash takes about 30 frames to land, the troll's first swing takes
  30 and its later ones 12, and a wizard in mid-slash can't dodge. With `counter=True` the
  wizard presses nothing while the enemy is free (move 0), dodges the swing when it comes,
  and slashes only while the enemy's move is 6, 7, 10 or 11 (recovering from a swing) or 1
  (reeling). Each dodge then gives one sure hit. Both trolls fell without landing a blow, on
  both ROMs, about 1,000 frames each. Try it wherever the plain policy loses health.
- 2026-11-19, level 5, **buying**. The merchant is a thing on the floor of his room (thing
  12) and what he sells is a thing inside him. Walk up to his x and y: `walk_to` returns
  `'busy'`, his words end in a question with the price, and `wait_busy(g); read(g, 'y')`
  buys. Check `has(g, thing)`. The gold comes off the purse by itself (110 became 50); there
  was no haggling on this level and no second question.
- 2026-11-19, level 5, **a thing that asks before it works**. Using the potion or the bottle
  brings a "Drink it?" question: `use(g, n); read(g, 'y')`. The thing leaves the carried
  list a few updates after the box closes, not at once, so wait on RAM for what it does
  (`g.until(lambda g: not has(g, n))`, or `shrunk`, or `not poisoned(g)`), don't test it
  straight after `read`.
- 2026-11-19, level 5, **a timed effect: the shrinking potion**. After the drink the wizard
  can't move for about 10 updates, then `shrunk(g)` is true and `shrink_left(g)` counts
  down from about 126 updates (`FF0A1D` and `FF0A1C`). Small, he steps 2 across, 2 up or
  down, or 1 and 1 on a diagonal, so `room_map` (which thinks in steps of 3 and 4) finds
  nothing: trace single `tick`s to explore. Growing back takes about 10 updates more. From
  then he is `poisoned(g)` (bit 6 of `FF0970`): a point of health every 16 updates of
  walking, none while a text box or a fight is up, until he drinks the bottle of water
  from the chest. So read text and fight freely but don't stand about. Level 5's small
  hole is not a door in the usual way: it takes a small wizard sliding up the wall under it
  with UP held (`through_door(g, 'UP', 2)` from below it), and other directions slide past.
- 2026-11-19, level 5, **creatures that stand by, then fight**. `creature_health(g, n)`
  reads a creature's health outside a fight (0 when dead), which tells which of two enemies
  is left. After the first troll fell the second walked a long loop before coming back
  (about 80 updates on some runs, 20 on others); `meet(g, n)` cut that to 20 updates.
- 2026-11-19, level 5, **`read` with too few answers** doesn't fail fast: with one answer
  for a chest that asks five questions it sits on the second question for 6,000 frames and
  then raises. Count the questions (a chest: one to open, one for each thing in it; gold in
  a chest is not a thing and has no question) and give them all.
- 2026-11-19, level 5, **a thing lying on the floor** (the egg) asks its question only when
  the wizard is within about 2 of its x and y: walking past 4 away does nothing.
  `walk_to(g, x, y, near=1)` got there; `room_map` shows the spot as `!`.
- 2026-11-19, level 3, **ladders: `ladder(g, buttons, room)`**. A ladder hole has two
  halves: one is the ladder and the other is a drop that kills, and which one the wizard
  touches first decides. Either way he snaps to the hole's middle, so his x and y don't
  tell them apart; health goes to 0 six updates after a drop. Level 3's room 4: the hole
  spans x 57 to 72, walking DOWN onto it is the ladder from x 64 to 72 and death from 58
  to 62, and RIGHT onto it from its left is death. Room 0's: LEFT onto it is the ladder
  with y 28 to 36 and death at y 40. Find the halves by standing the wizard on a grid of
  spots with pokes and walking each way (`scratch/route/level3/scan.py` is one way to do
  it), then aim for the middle of the ladder half. `ladder()` holds the direction until
  the room changes and then waits for him to climb off: going UP a ladder he stands on
  the rungs for about 38 updates more in the new room before stepping off, and
  `through_door` gives up waiting before that. The new room's loading can also take more
  than 40 frames with no update, which `tick` and `through_door` report as the game going
  busy; `ladder()` steps by frames. Don't steer back toward the hole on arriving: he
  stands right beside it.
- 2026-11-19, level 3, **which room a creature is in**: the low four bits of `FF090C` + n
  (the high four are its health). `creature_xy` alone can't tell a creature in this room
  from one with the same numbers three rooms away.
- 2026-11-19, level 3, **flamethrowers** (rooms 6 and 5). The nozzles are in the floor's
  picture, small pale marks. One thing of kind `16` on the room's floor is the flame, and
  its x and y jump to whichever nozzle fired last, so watching `thing_xy` for a few
  hundred frames lists the nozzles. A flame kills outright, but only a wizard standing on
  the nozzle (6 away to any side was safe through 1,500 frames). So nothing needs timing:
  keep the walk 8 clear of each nozzle.
- 2026-11-19, level 3, **floor that kills (the spike room, room 0)**. Most of that floor
  kills the moment it is stepped on, with nothing to see first. `room_map` does not mark
  it `x`: the health goes a few updates after the step, so the first deadly patch shows
  as `.` and the patches beyond it as blank, like a wall. Where a map has blank floor
  that the picture shows as open, treat the map's outer ring of `.` as deadly and keep 4
  inside it. The one spike that pops up around the room is only a show: its x and y are
  `FF0F62` and `FF0F68`, its place in a 15-step round is `FF0BCC`, 16 updates a step, and
  the spots it visits are all on deadly floor. No timing is needed, only the path.
- 2026-11-19, level 3, **fireballs: `fire(g, buttons)` and `shots(g)`**. `fire` turns the
  wizard with one update of walking, presses A, and checks that the scroll's count (its
  byte at `FF0B6C`) went down. The ball flies straight and kills the first creature it
  meets, a full-health troll included, within about 40 frames. Two creatures fighting
  each other stand about 10 apart, so stand in line with them on the target's side.
- 2026-11-19, level 3, **creatures fighting each other** (the troll and goblin of room 6)
  trade blows on a fixed timetable that starts when the wizard enters the room: each
  blow takes 2 from `creature_health`, and the goblin was dead about 3,600 frames in on
  every run. If one of them has to live, that is the time there is. When the troll died
  the goblin walked to the locked door and it was open after that; nothing to press.
- 2026-11-19, level 3, **someone who speaks before a ladder**: the goblin king is thing 23
  beside the ladder up in room 7. Pushing at the ladder first brings his words
  (`bump(g, 'RIGHT'); read(g)`), and the same push afterward climbs.
- 2026-11-19, level 4, **flying** (the carpet, thing 6). `mount(g, 6)` gets on by using it
  from the inventory and `mount(g, 6, on=False)` gets off; no text box either way.
  `flying(g)` is `FF0A1D`. The carpet has a speed on each axis (`FF0A3E` across, `FF0A3F`
  down, signed, 5 at most): a direction held changes that axis by 1 an update and letting
  go does not slow it, so it has to be braked. `fly_to(g, x, y)` steers to a point and
  stops dead on it; `fly(g, (x, y), ...)` does several. Walls turn the carpet aside. Getting
  off stops it where it is. Its life is `FF1042` (`fly_time(g)`): 25 when first used, 1 less
  every 16 updates in the air, not counting while he walks, and not topped up by getting
  on again. At 0 he is set down where he is. Doors don't open to the carpet: get off beside
  the door and walk in.
- 2026-11-19, level 4, **worms under the floor**. In level 4's two flame rooms `FF1043`
  (`worm_steps(g)`) is 16 on coming in and drops by 1 for every update the wizard walks.
  At 0 a worm takes him, wherever he is. Standing still and flying don't count, so the
  doorway is safe to stand in, and about 12 steps are left after the 3 or 4 that walking
  in costs. It is not a matter of where he stands, so `room_map` shows such a room as a
  small diamond round the door: that's the count running out, not walls.
- 2026-11-19, level 4, **flamethrowers and fireballs**. A nozzle on the floor burns the
  wizard at once if he is within its square, 12 by 12 in his coordinates, flying or not
  (on foot it is simply solid). Nothing in the things table says where they are; thing 16
  hops from nozzle to nozzle every 20 updates and seems only to be the one that is
  spitting. Fireballs are another table: 8 slots, x at `FF0F80` + i, y at `FF0F88` + i,
  `FF0F90` + i is `FF` when the slot is empty. They fly along the tiles' diagonals (2 or 4
  on both axes an update), always down the same few lanes, and one that comes within about
  4 of the wizard costs 1 or 2 health and is gone. Hovering in a lane gets him hit over
  and over; crossing one is mostly luck.
- 2026-11-19, level 4, **x is in half pixels**: one of the wizard's x is 2 pixels on the
  320-wide screen and one y is 1, which is why a step is 3 across and 4 down. Remember it
  when reading a position off a picture.
- 2026-11-19, level 4, **mapping a room that kills** (exploring only, it pokes). Writing
  the wizard's x and y to `FF08BC`/`FF08D0` and their copies at `FF0A3A`/`3C`/`4C` (x) and
  `FF0A3B`/`3D`/`4D` (y) puts him there, on foot or on the carpet, and the game carries on
  from it. Doing that for every 4th x and y from a kept state, then one or two ticks, shows
  what each spot does (pose at `FF0920` leaves `18` when the carpet burns; a short push
  each way finds walls) without flying there. The same on foot along the edges, holding
  each direction for 7 updates, finds the doors a flyer can't use. A room's coordinates run
  0 to 255 both ways and other rooms' floors show up in the corners; only the part joined
  to the doorway matters.
- 2026-11-19, level 5, **fireballs at moving targets: `hunt(g, creatures)`**. What a
  fireball does: it starts about 12 ahead of the wizard the way he faces and flies 6 an
  update across, 8 up or down, or 4 and 4 on a diagonal, for about 22 updates; at a wall it
  turns and runs along it. Its x and y are `FF0F80` and `FF0F88`. It kills what it comes
  within about 5 of. Level 5's flying lizards (creatures; health 1) sit still for 15 to 60
  updates, fly about, and sometimes swoop back and forth through the wizard, a point of
  health each pass, about one pass in 10 updates. A swoop runs along one of the wizard's
  eight lines and stays regular while he stands still, so `hunt` shoots a sitting lizard
  from up to 110 away when it is on a line (`ray(dx, dy)` gives the buttons), and a flying
  one when it is on a line, 10 to 34 away and turning or coming at him. Both lizards fell
  in 3 or 4 shots and 2 or 3 health on both ROMs. Give `inside=` a test of where he may
  step if there is a door or trap near. A creature's heading is at `FF0948` + n (0 to 7)
  and the spot it is making for at `FF09D4` + n and `FF09E8` + n.
- 2026-11-19, level 5, **a spell on a clock**. Level 5's fireball book is not a count of
  shots: its byte at `FF0B6C` + thing starts at 250 when the book is armed and drops 1
  every 4 updates whether or not anything is fired (so `shots(g)` reads time there, and
  `fire`'s check that the count fell still passes). 1,000 updates, then the book leaves
  the carried list. Arm such a thing in the room where it's wanted.
- 2026-11-19, level 5, **a dead creature that carried something** (the lizard with the
  key: the key's place is `40` + the creature's number) asks to be searched by itself a
  few updates after it dies if the wizard is close. If he shot it from far off, walk to
  `creature_xy(g, n)`, where it fell, and the question comes: `search(g, 'yy', KEY)`.
- 2026-11-19, level 8, **timing an action by an enemy's animation**. An enemy with set-piece
  moves (level 8's dragon and teacher; look for the same on other levels) plays each move as
  a scripted animation in one of 32 slots. Its routine keeps the slot's number in a byte of
  its own, `FF` between moves. `animation(g, slot)` returns `(which, position)`: `which` is
  the animation's number, so it tells one move from another, and `position` starts at 3 and
  goes up by exactly one an update on either ROM. Find the enemy's slot byte by watching
  `FF0E68` to `FF0E87` for the slot that leaves `FF` when the move starts, then looking for
  a byte nearby that holds that slot number. To find the window, keep a state at the start
  of the move, and for each k go back, run k updates, act, and see whether the wizard lives.
  Then act in the middle of the window: `if now[1] >= 9: press`. The animations' pictures
  are bytes in the ROM (a table of addresses at `0011B4`, low byte first, indexed by the
  animation's number; three bytes of header, then a picture number an update, `FF` at the
  end), so a move's length can be read off before trying it.
- 2026-11-19, level 8, **the wizard's action byte**. `action(g)` (`FF09FC`) is 0 when the
  wizard is free. The game posts a number there for anything that happens to him (landing
  from a fall is 1, level 8's blink `14`, fire protection `15`, statue `16`, the dragon's
  fire `1D`) and his routine clears it when that's over. While it isn't 0 he can't walk and
  **C doesn't open the inventory, and the press is used up**, so `use()` fails with "the
  inventory did not open". After a fall, a ladder or a spell, wait with
  `g.until(lambda g: action(g) == 0)` before `use()`. A harmful number can overwrite a
  spell's while the spell still protects him, so wait for 0, not for the spell's number to
  go.
- 2026-11-19, level 8, **spell books**. A book (blink, statue) is armed from the inventory
  like the fireball scroll: a box says so, `armed(g)` then gives its thing number, and each
  fresh press of A casts it once. `press_a(g)` holds A until the game has seen it. The cast
  begins on the next update and holds the wizard for 11. The casts left are at `FF103E`
  (blink) and `FF103F` (statue); check the count went down. When a book's casts run out it
  leaves the carried list, though `armed(g)` still gives its number. A scroll (fire
  protection, sonic, magnetic hands) works the moment it is used, with no box, and is gone.
- 2026-11-19, level 8, **a box that opens inside an update**. `tick()` returns True for the
  update in which an enemy's routine opened a text box, because the box only shows as
  `busy` 12 frames later. A `use()` straight after such a tick presses C into the box. When
  RAM says a speech has just begun (the enemy's move changed to the one that speaks), call
  `wait_busy(g)` and `read(g)` before anything else.
- 2026-11-19, level 8, **which message is up**: `text_address(g)` is the ROM address of the
  text in the box, the same on both ROMs for the game's own messages (the patch's own are
  at `97B0`). Message n's address is in two tables, low bytes at `001684` + n and high bytes
  at `00177E` + n.
- 2026-11-19, level 8, **`has()` can be wrong about a thing that was taken away**. When the
  teacher takes the amulet its place byte stays `40`; only the carried list loses it. Test
  `thing in carried(g)` for something a creature takes from the wizard.
- 2026-11-19, level 8, **a death on level 8, and how the game ends**. The last level has no
  retries, whatever `FF109A` says: health 0, then about 50 updates later the Game Over flag
  (`FF1072`), with no "prepare to continue". `revive()` raises `Died` there, rightly. And
  winning ends the same way. The Genesis game never sets its level-over flag on level 8, so
  the "Congratulations!" message in the main loop (`011256`) is never shown: the closing
  story's pages turn by themselves, then the wizard's routine runs into the last level's
  death code and the Game Over flag goes up. The original shows "Game Over" and asks to
  play again; the patched ROM shows its "Try this level again?" there, after a win.
  `ending(g)` is true while the story is in the box, and `end_of_game(g)` is level 8's
  `end_of_level()`: it waits for the story, lets it play, and returns None when the flag
  goes up. Which of the story's two tellings comes depends on bit 1 of `FF1071`, which the
  certificate carries.
- 2026-11-19, level 8, **random choices**. The game's random numbers are a table of 55
  bytes at `FF0C02`. To see every branch of something random while exploring (the teacher
  throws either of two bolts of different lengths), go back to a kept state, poke random
  bytes over the table and play on. Never in `play()`.
- 2026-11-19, level 5, **a path with unseen deadly sides (the worm room, room 5)**. The
  walkthroughs' "only safe path" is a maze drawn in the wizard's own x and y: its walls
  are straight lines about 3 wide, up and down or across, that kill at a touch (he sinks
  where he stands, `action(g)` 4, health unchanged for a while), and the corridors between
  are 20 or more wide. Nothing shows on the floor, and the Genesis room is brown, not red.
  `room_map` draws it exactly: the lines come out as `x`, with `.` on both sides where the
  far side was reached another way. So make the map, read the corridors off it, and
  `go()` down their middles; `near=2` is plenty and no step counting is needed. The
  sensor only beeps and the route doesn't use it. Also in `room_map`: an edge of floor
  with no wall (he falls) is `x` too, and so is the spot inside a door he was walking in
  from, since he is carried through.
- 2026-11-19, level 5, **a locked door**. Without the key, walking into it brings a box
  and nothing else. With the key the box says so, and when it closes the wizard walks
  through by himself: `wait_busy(g); read(g, quiet=0)`, then wait for the room number.
  The key leaves the carried list. `room_map` shows such a door as `!`.
- 2026-11-19, level 7, **a harder one-on-one fight**: the man at the foot of level 7's
  first ladder has 9 health (the troll above him 3). The plain `fight(g)` beat both without
  a hit on both ROMs, about 1,000 and 770 frames; nothing needed changing. He speaks first,
  the moment the ladder ends: `wait_busy(g); read(g)` returns when the fight has begun.
  `ladder()` can't be used for a ladder that ends in a text box like that (it waits for the
  wizard to step off, which he doesn't while the box is up, and raises); `through_door`
  got down both of level 7's ladders on both ROMs.
- 2026-11-19, level 7, **steering a vehicle: the barrel, `sail_to(g, x, y)` and
  `sail(g, (x, y), ...)`**. In level 7's water the wizard steps off the ladder onto a
  barrel. Its speed is one byte, `FF0984` (`sail_speed(g)`): across in the low four bits,
  down in the high four, each signed, -5 to 5, and 1 of speed is half a step of his
  coordinates an update (2.5 at most on each axis). A direction held changes that axis by 1
  an update; letting go changes nothing, there is no drag, and the water's current is
  slight (about 1 of speed downward every 4 updates in the one channel that has it). A wall
  throws the barrel back like a ball at the speed it came, which turns it round at once but
  not where you'd choose. The carpet's bytes (`FF0A3E`/`3F`) hold only the last step here,
  so `fly_to` won't do. `sail_to` passes through a point flat out on the axis with farther
  to go and holds the other axis on the point's line; `rest=True` brakes to a stop on it;
  `stop=` ends it on a test, as in `walk_to`. `room_map` is no use with a thing that keeps
  its speed: `scratch/route/level7/bmap.py` did the same search holding each direction for
  3 updates, in about 5 minutes.
- 2026-11-19, level 7, **being chased: it was a timetable**. The water monster doesn't
  follow the wizard. Its routine (`009FF0`, once an update) wakes it when he comes inside
  a box by its gate, then counts updates (`FF1044` 0 to 9, `FF1046` the tens, `FF1045` the
  awake flag) and kills him if he is still inside a fixed part of the room when the count
  passes fixed marks. `level7.py`'s docstring has the boxes and marks. So the route is a
  race against a count that RAM shows, the same on both ROMs since it is in updates, and
  the log says how many updates were to spare at each mark. If something on your level
  "chases", search the ROM for the bytes of its state's address (a level's retry code,
  near `0081D6`, clears them, which is how these were found) and read its routine with
  `dasm.py` before trying to outrun it by feel. Also: wake such a thing on the move. Coming
  to a stop inside its box and turning round cost 9 of the 90 updates.
- 2026-11-19, level 7, **the end through the whirlpool** needs nothing new. The whirlpool
  drowns a wizard the monster isn't after, and ends the level if it is: about 1,100 frames
  of him going under with the game not busy, then the usual "End of level!" screen.
  `end_of_level(g)` as it stands returned the certificate on both ROMs, the same one the
  1991 walkthrough gives for level 8.

## Where each level stands

| Level | Route | Passes six runs |
|---|---|---|
| 1 | `level1.py` plays rooms 6, 3 and 7 (body, three goblins, key, chest) to the door of room 1 | Those parts pass all six; the last four rooms aren't written |
| 2 | not started | |
| 3 | `level3.py` takes the scroll, kills the troll for the knife, passes the king, takes the gem and climbs down to room 8 | Those parts pass all six |
| 4 | `level4.py` gets past the troll at the start and takes the carpet | Those parts pass all six |
| 5 | `level5.py` takes the egg, buys the potion, goes through the hole, beats both trolls, empties the chest and drinks the water | Those parts pass on both ROMs |
| 6 | not started | |
| 7 | `level7.py` plays the whole level: troll, ring, the fight below the ladder, the barrel, the water monster, the whirlpool | Patched and original pass with no delay; the six runs are next |
| 8 | not started | |

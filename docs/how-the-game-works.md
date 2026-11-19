# How the game works

Notes from running and disassembling The Immortal (USA, Europe). Addresses are for that
ROM. Each section says what was seen happening in the running game and what has only been
read from the code so far. Timing comes from PicoDrive and was checked against BlastEm in two
builds, described below. None of it has been confirmed on real hardware.

`tools/harness/levels.py` reproduces the first timing table below and
`tools/harness/compare_cores.py` the second.

## Useful RAM

The game keeps most of its variables relative to a base of `FF0300`.

| Address | What it holds | Status |
|---|---|---|
| `FF1070` | Current level, 0 to 7 | Seen |
| `FF1051` | Current room | Seen |
| `FF109A` | Retries left on this level | Seen |
| `FF1073` | Set to restart the level | Seen |
| `FF1088` | Set to skip the "New game?" prompt and load from the fields below | Seen |
| `FF1091` | Level to load | Seen |
| `FF108C` to `FF1098` | A certificate's 13 digits, a byte each: 4 of check, then 9 | Seen |
| `FF106F` | Set when the level is over. Setting it by hand ends the level | Seen |
| `FF1072` | Set when the retries have run out. Setting it by hand brings Game Over | Seen |
| `FF0AEE` to `FF0B17` | The level's 42 things, a byte each, `FF` for none | Seen |
| `FF9624` | Count of vertical blanks (long) | Seen |
| `FF12E6` | The count at which the next tick may begin (long) | Seen |
| `FF962A` | Pad 1, as read in the vertical blank | Read from code |
| `FF9656` to `FF9755` | The object decoder's working space: a packed tile's bits, one to a byte | Seen |
| `FF9642` | Set, text is drawn without the frame's wait after each letter, and isn't shown until `015738` is called with it clear | Seen |
| `FF9760` to `FFBFFF` | No fixed address here is named anywhere in the code. The patch keeps its own variables from `FF9760`, a message being shown at `FF97B0`, and the tile memory from `FF9800` | Read from code |
| `FFC000` to `FFF7FF` | Used by the Sega logo, then cleared and left alone | Seen on 32 walks |

## The main loop

The loop is at `013470`. Each pass updates the game, draws if nothing has ended the level,
and then waits at `01349C` until the vertical blank count reaches a deadline. When the wait
ends, the deadline is set to the current count plus 5 (`0134A6`).

So the game runs at one tick every 5 video frames, 12 a second on a 60 Hz console, and
that's what sets the speed of the game. When a tick takes longer than 5 frames the next one
simply starts late, and the game has no way of catching up, so slowdown is lost time.

Raising the rate wouldn't make the game smoother by itself, because movement and timing are
counted in ticks and everything would run faster. A higher rate would need the game's
movement and timers changed to match.

## Death and retries

Seen in the running game:

- Each level starts with 2 retries, so the wizard has three lives per level. The count is
  set when a level starts (`012DFA`).
- After a fatal fall, the game holds on the empty scene for about 4 seconds (246 frames on
  both ROMs, measured on level 3), and after a lost fight for 6 to 8 seconds. A button
  doesn't shorten either.
- With a retry left, it shows "Prepare to continue..." on a black screen and puts the
  wizard back at a spot the game keeps for the room he died in (see below), with full
  health. Everything else stays as it was: what he carries, what he has used up, the
  creatures he has killed. The scroll or book he had armed is no longer armed. The message ended
  in three short pauses, about a second in all, so the black screen lasted about 1.5
  seconds. A fresh press of A or C ended whichever pause it fell in; in the original, any
  button held made the pauses' waits instant.
- With none left, it shows "Game Over", then "Play again?", then the "New game?" prompt.
  YES goes back to the very first room of the game. NO asks for a certificate.

**The changes.** "Prepare to continue..." now stays up for 3 seconds, or until a fresh
press of A, B, C or Start; a button already down when it appears doesn't count until it's
let go. The message's own pauses are gone, and the waiting is done by a routine at `013B7E`,
in the body of the old tile sync routine, which never runs now. It's called from `0081F4`,
and after a press it waits for the buttons to be let go, since a C still down when play
carries on would open the inventory. From the black screen to walking again takes about 3.5
seconds without a press.

Game Over now asks "Try this level again?". YES starts the level over with
three lives and what the wizard carried into it. NO goes on to the prompts a game starts
with. See "Saving" below.

The retry handling is at `0081D6`. It skips the retry altogether on the last level, level 8
(`0081DE`): a death there brings Game Over about 50 updates later, with the retries left
untouched. Winning the game ends the same way. After the closing story the wizard's routine
runs into the last level's death code and the Game Over flag goes up, so the original
follows its ending with "Game Over / Play again?". There's no congratulations screen.

**Where a retry puts him.** `008318` works out an index, ten times the level (counting from
0) plus the room, and `01119A` reads three tables of 80 bytes with it: the room at `0110AA`,
then x at `0110FA` and y at `01114A`. Most rooms send him to where he came into the room
before it; some, such as level 2's room 7, send him back to the room he died in. A spot of
(0, 0) is a doorway he walks in by himself, as at the start of level 6's corridor.

Ten entries a level is one too few for level 5, which has eleven rooms, 0 to 10. A death in
room 10, the last one, reads level 6's first entry and puts him in level 5's room 0, at (97,
64). By then the shrinking potion is gone, the hole from room 0 to room 2 only takes a
shrunken wizard, and the merchant has nothing more to sell, so the level can't be finished.
The retry test found it, and `scratch/retry/l5room10.py` shows the same on both ROMs. Room
10 holds the straw bed and the ladder down, which kills from the wrong side.

A death in level 5's first room, room 8, sends him into room 7, the slime's room near the
end of the level. Nothing is known to kill him in room 8.

The special cases, after the spot is chosen, by level:

- Level 2: if `$71C(a4)` isn't FF, `00646C` is called with 50. Not worked out.
- Level 4: a death in room 0 or 4, the two rooms flown over on the carpet, sets the
  carpet's time back to 25 (`$D42(a4)`) and `$D43(a4)` to 16.
- Level 5: rooms 4 and 5 call `00832E`, which does something to thing 47 and sets
  `$8B2(a4)` to C3. Rooms 0, 1 and 7 clear `$D40(a4)`.
- Level 7: `00834A` clears `$D44(a4)` to `$D46(a4)` and does something to thing 2C.
- Level 8: `00820C` would set a few variables, but the retry has already been skipped for
  level 8 by then, so it never runs.

Nothing on level 6 is reset. Its levitation spell keeps running down. After a death in room 4,
the route crossed the corridor again with 7 of the spell's units left, and arrived with 3.

## Fights

A fight is one routine, entered at `0113E6` when an opponent has been set in `$DAE(a4)`. It
switches to the fight song (`0114B0`), runs a main loop from `011590` until one side's strength
(`$DA7(a4)`, `$DA8(a4)`) reaches zero, plays an ending animation in a second loop from `01170E`,
and puts the level's song back (`0117BC`), which starts it from the beginning.

The two fighters are drawn at fixed places and only change pose. The loops draw with their own
routines (`015738`, `015768`), not the main loop's, and they have no clock: each goes around as
soon as its picture is up.

## Song changes

Three routines choose the song, and the game logic reaches them through its jump table as well
as directly:

- `015CAA` sets the level's song, from a table of song by level and room at `010F44`, and
  remembers it in `$964E`.
- `015CC6` plays some other song for the time being: the fight song, a speech, an alert.
- `015CDE` puts the level's song back.

All three end in a request at `015D44`, which only leaves a note for the sound driver. The driver
acts on it at the next frame, and a song always starts from its beginning.

About twenty places in the game logic do the same thing: play another song, do something, put the
level's song back. `008D66` is the commonest on level 1. When the something is over at once, both
requests land in the same frame, the other song is never heard, and the level's song starts over.
That's the restart heard again and again while walking about, and the original does it too.

**The fix.** The request routine now notices a request made while another is still waiting to be
picked up. If the new one asks for the song that's playing anyway, both are dropped and the music
carries on. A change that lasts even one frame goes through as before, so a real fight still
switches to the fight song and starts the level's song over afterward. A song that has run out
is noted (`015E10`), so that asking for it again still starts it. On four scripted walks around
level 1, the original started a song 18 times and the patched build 8.

## Message text

Messages are run by a small interpreter at `00CF04`. Most bytes are letters. Others are
commands: end the page, wait, clear, ask a question and so on.

After each letter it waits a number of units (`00CE6E`): 5 after a letter, 13 more after a comma,
26 after a period, 39 after a question mark or colon, and 40 or 140 at the end of a page. Only
every fourth unit is a real wait (`013452`), of two frames. Drawing a letter takes about a frame
more. That comes to about 15 letters a second.

Buttons in the original:

- A fresh press of either of two buttons ends the wait in progress. That's how a page is
  dismissed early.
- Any button held makes each real wait give up at once, and also stops letters being drawn one
  at a time until the next space. Whole words appear as fast as they can be worked out, about 106
  letters a second, and the pause at the end of a page is gone as well.
- Two particular buttons held together skip the waits altogether (`00CEC0`).

**The change.** A held button now shortens the waits while typing and leaves pauses alone. The
wait after a letter is one frame, every other time; after punctuation, one frame every time. Every
letter is drawn. The two-button shortcut is taken out. With nothing held, nothing is different.

A fresh press of A, B, C or Start ends a pause, and the rest of a run of pauses (many messages
end in eight in a row), until typing starts again. In the original any button did that, by
making the waits instant while it was down, and a tap of any button ended level 1's
eight-pause message `001AD7` in 12 frames. The first version of the change only let A and C
through, since those are the two the game itself looks for; B and Start did nothing. Now all
four take 12 frames there again, and a button held since before the pause still doesn't count.
The routine keeps the buttons down at the start of each pause in `FF97AC` and its "skip" flag in
`FF97AD`, and it lives at `0154F4`, over a division and a sort nothing called (see
`docs/dead-code.md`).

| Opening message, first page | Nothing held | A button held |
|---|---|---|
| Original | 16 letters a second, then a 93-frame pause | 106 a second, no pause |
| Patched | 17 a second, then 93 frames | 34 a second, then 81 frames |

The pause with a button held is a little shorter than without because the wait after the page's
last period counts as typing. `tools/harness/text_pace.py` makes the table.

## Certificates

These are the game's passwords. The code at `012876` gathers the values and `012804` works
out a four-digit check over them. Going by the code, a certificate holds the next level, a
three-digit number that is probably gold, one other value (`FF1071`), and flags for
particular carried items, some of them depending on the level.

A certificate is 13 letters from `0` to `f`. The game keeps them a digit to a byte at
`FF108C`: four digits of check, one more value, the level (1 for the second level), then
the rest. The entry screen (`01266C`) takes a letter with RIGHT, changes it with UP and
DOWN, erases with LEFT and finishes with Start or A. It accepts anything whose check
digits agree (`012782`).

Confirmed with one certificate: ending the first level at once gives `2b9cf10000020`, the
same on the original and the patched ROM. Typed into the original it starts level 2, and
the level's 42 things at `FF0AEE` come out the same as when the game loads from the fields
itself. What each of the other digits changes hasn't been tried one by one.

When a level starts (`012DF4`) everything carried is cleared (`00C7C0`) before the loader
gives back what the certificate names. So a level started from a certificate never carries
more than the certificate holds, whatever was picked up before.

Between levels the game sets the flag at `FF1088` and loads straight from those fields, with
no typing. Setting the same flag by hand, with a level number, does load that level, which
is how the harness reaches all eight.

## Saving

The patch adds battery saves. `tools/harness/save_check.py` checks all of what follows.

**What a save is.** A level's certificate, which the game makes when the level before it
ends (`012876`). There's a place in battery RAM for each of levels 2 to 8, so reaching a
level again replaces its save, and nothing else ever erases one. Mid-level saves were
ruled out: they'd need the state of every room and object, and would change how hard the
game is.

**Battery RAM.** The header's field at `0001B0` now declares battery RAM on the odd bytes
of `200001` to `2001FF`, and the code writes 1 to the mapper port `A130F1` before using it.
A level's save is 13 bytes starting 16 bytes times the level's digit into that RAM, so an
emulator's save file has level 2 at offset 16 and level 8 at 112. A save is believed only if
all 13 bytes are digits, its level digit matches its place and the game's check (`012804`)
gives its first four digits. Empty RAM, whether zeros or `FF`, fails that.

**When a level ends** (`011266`), the new routine makes the certificate, writes it, shows
the game's "End of level! Here is your certificate:" and the letters, reads the save back,
and adds "Game saved." under the letters if it reads back right. If it doesn't, as on a
cartridge with no battery RAM, the screen is the original's.

**When a game starts** (`012A74`), the new loader looks for saves from level 8 down. With
none, everything is as it was. With one or more it asks "Continue a saved game?". NO goes
on to "New game?" as before. YES shows "Level" and a number, starting with the furthest
level saved. UP and DOWN step through the saved levels and go round at the ends, and any
button takes the one shown. The save goes into the certificate's fields and the game loads
from them (`012AB0`), which is what it does itself between levels.

**Game Over** (`012646`) asks "Try this level again?". On YES the routine sets `FF1088`,
since the fields still hold the certificate the level was started from, however it was
started. On the first level there's no certificate, so it sets a flag of its own
(`FF97AA`) that makes the loader start a new game without asking. NO changes nothing, and
the game goes on to the loader's prompts as the original did.

Winning the game also comes through Game Over (see "Death and retries"), so on the last level
with the wizard still alive the routine leaves the original's "Game Over / Play again?"
alone. It was offering to try level 8 again after the ending until the level 8 route found
it. The room for that check came from shorter forms of four of the routine's own
instructions.

**Messages.** The game finds a message's text by a 16-bit address, so it can't point at new
text high in the ROM. The new routine copies its message to `FF97B0` and enters the game's
message routine past the point where it looks the text up (`00CF2A`), with the address
`97B0`, which the game reads as RAM. The four new messages are kept at `02E3EA`, in the
part of the old object routine that no longer runs. The level list is drawn with `FF9642`
set, so it appears at once when UP or DOWN is pressed.

**Space.** The routines are 510 bytes at `0FFCCA` and the messages 147 bytes. The ROM is
still 1 MB.

**Tested** on BlastEm's libretro core and on our build of the fork, both of which keep the
battery RAM in a file. Not tried on a console or a flash cartridge.

The harness's timing tools clear the fork's saved battery RAM before they run
(`fork_timing.forget_saves`), so a save left by an earlier run can't put a new prompt in
front of their scripted openings.

## Drawing

Only partly explored. The routine at `02E3E4` builds graphics for objects, 32 bytes per
tile, into RAM at `FF2000`. The code around `014802` queues the matching sprites, in blocks
of 4 by 4 tiles. `01428C` handles the queue afterward. How the room itself reaches the
screen hasn't been traced yet.

Object tiles are numbered from 1 to 29,670, and tile 0 is blank. The index at `02DCEC` splits
them into runs, each with a fixed packed size per tile. Most are compressed with one fixed
code tree, and the rest are stored whole. The tree is written out as code from `02E6D6`, one
test and branch per bit, with each packed byte first spread into 8 bytes through the table at
`02D4EC`. That made an object tile cost about 5,000 cycles on level 6, every time it was
needed, with nothing kept between uses.

### The missing torch flame

The search through that index accepts a tile number equal to the first tile of the *next*
run. It's harmless nearly everywhere, because the two runs agree on where such a tile starts
and the tree stops by itself after 32 bytes. It goes wrong at one spot: tile 25793 begins the
final run of stored tiles, and the search lands on the run before it, so the stored bytes get
decoded as if compressed. On level 4 that tile is the top of the wall torch's flame, so the
original game draws the torch with the top of its flame missing. Comparing the original ROM's
picture with the corrected tile shows it. The walks also asked for this tile on levels 2, 3
and 5 to 8, and those uses haven't been looked at.

## Performance

The full story of the optimization work is in `docs/optimizations.md`. This section and the ones
below keep the measurements as they were taken.

The wizard was walked at random for 200 seconds on each level, the same way every run, with
levels reached by the jump described above. A tick is late when it takes more than 5 video
frames. Gaps of 12 frames or more were left out, since those are messages and transitions.

| Level | Ticks | Late | Worst gap (frames) | Object graphics, cycles per tick: on time / late |
|---|---|---|---|---|
| 1 | 909 | 1% | 8 | 206k / 146k |
| 2 | 1140 | 25% | 11 | 156k / 168k |
| 3 | 1997 | 9% | 9 | 123k / 147k |
| 4 | 1357 | 16% | 9 | 166k / 166k |
| 5 | 1210 | 42% | 11 | 142k / 338k |
| 6 | 1876 | 51% | 11 | 327k / 496k |
| 7 | 1599 | 14% | 8 | 195k / 238k |
| 8 | 1767 | 19% | 7 | 122k / 125k |

Across all levels, 23% of ticks were late. A tick has about 639k cycles to work with.

On levels 5 and 6, late ticks spend far more time building object graphics, so that routine
is the first thing to look at there. On levels 2, 4 and 8 it costs about the same whether
the tick is late or not, so something else is holding those back, and that isn't known yet.
A random walk also isn't how anyone plays, so these figures show where to look and don't
measure what a player would feel.

### PicoDrive against BlastEm

The same scripted opening, level jump and random walks were run on both emulators, using a
BlastEm libretro core built 2026-11-16 (version 1.0.1-pre). That build's emulation code was
last synced with BlastEm itself on 2026-07-27, so it lacks later upstream fixes, including
some to DMA. Ticks were read from the game's own deadline at
`FF12E6`. Across all levels 23.0% of ticks were late on both.

| Level | PicoDrive: ticks, late, worst gap | BlastEm: ticks, late, worst gap |
|---|---|---|
| 1 | 909, 1%, 8 | 906, 1%, 7 |
| 2 | 1136, 25%, 11 | 522, 20%, 9 |
| 3 | 1997, 9%, 9 | 1995, 9%, 9 |
| 4 | 1357, 16%, 9 | 1355, 16%, 9 |
| 5 | 1206, 43%, 11 | 1193, 44%, 11 |
| 6 | 1876, 51%, 11 | 1875, 52%, 11 |
| 7 | 1599, 14%, 8 | 1567, 14%, 8 |
| 8 | 1767, 19%, 7 | 1767, 19%, 6 |

Level 2 is the weak row. Its walks wander into deaths and prompts that stop the game, and
they do so at different moments on each emulator, so it has few ticks and they aren't
comparable. On BlastEm two of its four walks ended at Game Over.

PicoDrive shows a few ticks 4 frames apart (1.9%). BlastEm shows none, so those look like a
PicoDrive artifact, and the game's tick never runs early.

PicoDrive stays the tool for finding where time goes, since only its profiling build counts
cycles per instruction. BlastEm is the check on whether a change really helps.

### The BlastEm fork

Our reference is now a build of [ulalume/blastem](https://github.com/ulalume/blastem), which
can measure cycles between chosen addresses without changing the ROM. It's 10 changes behind
BlastEm itself. Two of those are DMA fixes for sources from `800000` to `DFFFFF`. The game
never used that range in these runs: on all eight levels, every DMA from the 68000 read from
work RAM (`FF0000` and up) or from ROM at `020000` to `03FFFF`. So those fixes weren't needed.
Two bugs in the fork had to be fixed first; see `docs/blastem-fork-fixes.md`.

`tools/harness/fork_timing.py` runs the same opening, jumps and walks. A second run of each
level gave identical video memory on all 6,499 frames, and so did a run with the profiler
turned off, on all eight levels.

| Level | Ticks | Late | Worst gap (frames) | Object graphics, cycles per tick: on time / late |
|---|---|---|---|---|
| 1 | 905 | 1% | 7 | 221k / 173k |
| 2 | 585 | 23% | 9 | 183k / 185k |
| 3 | 2082 | 10% | 9 | 129k / 161k |
| 4 | 1362 | 16% | 8 | 175k / 180k |
| 5 | 1199 | 41% | 11 | 141k / 360k |
| 6 | 1783 | 58% | 11 | 377k / 540k |
| 7 | 1528 | 15% | 8 | 207k / 255k |
| 8 | 1767 | 19% | 6 | 124k / 152k |

Across all levels 23.8% of ticks were late. Level 6 came out worse here, at 58% against about
51%, and object graphics cost roughly 10 to 15% more than PicoDrive's count on the busy
levels. The walks drift apart between emulators, so small differences between tables don't
mean much, but PicoDrive's cycle counts should be read as a little optimistic.

### Sprite masking

`01428C` hides the parts of sprites behind scenery. `8ADE` holds one byte per cell of a 34 by 18
grid over the play window, two 4-bit shape numbers each. For every sprite tile the routine takes
the four cells under it and compares the sprite's depth (its word in the list at `9254`, plus the
camera's y) with each cell row's to choose which half of the byte applies. Shape 0 hides nothing
and shape 5 hides everything. The shapes are 32 bytes each at `0141CC`, and only the first six are
data. A list word with its top bit set means the sprite isn't masked at all.

The original shifts the right-hand cells' shape one bit too little, which miscolors stray pixels
along mask edges. `docs/optimizations.md` has the details and the fix.

## The object graphics patch

The first version of the patch unpacked all the object tiles from your ROM into a new second
megabyte and replaced `02E3E4` with a routine that copied them. The rest of this section
describes that 2 MB build.

The patch is 1 MB now. `02E3E4` jumps to a routine that keeps the last 640 tiles it unpacked in
RAM from `FF9800` to `FFF07F`, which the game only touches while starting up, and calls the game's
decoder for the rest. `docs/optimizations.md` has the details under "One megabyte".

`--check` tests this in the BlastEm fork. A test ROM runs the game's own decoder on every tile
number and compares the output with the unpacked table, and all 29,671 match, the torch tile
included as the game decodes it. A second test ROM confirms that the new routine writes the
right tiles and leaves every register as it found it. The old routine's work buffer at
`FF9656` is no longer written, and no other code we've reached refers to it. Clean-boot runs of
all eight levels never asked for a tile number outside the table.

Same opening, jumps and walks as the table above, on the same emulator:

| Level | Late before | Late now | Worst gap before | Worst gap now | Object graphics per tick, before / now (on-time ticks) |
|---|---|---|---|---|---|
| 1 | 1% | 1% | 7 | 7 | 221k / 16k |
| 2 | 23% | 22% | 9 | 10 | 183k / 21k |
| 3 | 10% | 11% | 9 | 7 | 129k / 15k |
| 4 | 16% | 17% | 8 | 7 | 175k / 18k |
| 5 | 41% | 24% | 11 | 7 | 141k / 18k |
| 6 | 58% | 20% | 11 | 7 | 377k / 21k |
| 7 | 15% | 14% | 8 | 7 | 207k / 13k |
| 8 | 19% | 19% | 6 | 6 | 124k / 11k |

Across all levels, late ticks went from 23.8% to 16.4%. Levels 5 and 6 are the ones that
changed. Late ticks elsewhere come from something else, which is the next thing to find. The
walks drift once timing changes, so small differences between the two columns don't mean much.

The game also runs closer to its intended speed on levels 5 and 6 now, which means less of the
slowdown players have been getting there, and enemies and traps there arrive sooner in real
time. None of this has been tried on real hardware.

## The background tile patch

With object graphics out of the way, `tools/harness/tick_parts.py` showed where late ticks went.
Almost all of them were ticks where the camera crossed an 8-pixel step. Those run three
routines from `015600`: `013D34` works out the 612 cells on screen, `013B16` gives each tile a
slot in video memory, and `013B78` frees unused slots and sends tiles. Together they took about
500k of the 639k cycles a tick has.

`013B16` marked every tile on screen as needing to be sent, not just new ones. In the walks that
meant 346,317 tiles sent for only 13,466 new ones, so 96% of the sending was repeating what
video memory already held. `013B78` also stepped through all 2,048 table entries at about 70
cycles each, and it did all this with interrupts masked for around two frames. That made the
game miss vertical blanks, up to 6% of them on level 5, which is when it reads the pad.

The patch sends only newly allocated tiles and scans the table about three times faster, keeping
the original's order so slots are handed out exactly as before. The new `013B78` lives in space
the old object code left free.

Three things back this up:

- `--check` runs the old and new routines on 24 passes of random screens. RAM and video memory
  come out identical, and all registers are kept. Breaking the patch on purpose makes it fail.
- A test build compared each skipped tile against video memory during play, across eight levels
  with walks that also press buttons. All 685,562 matched.
- Reading the code, only one other routine in normal play writes to the tile area: `0158EC`,
  which puts 7 status tiles in slots 0 to 6. Slots are handed out from 611 downward, so a screen
  would need over 600 different tiles to reach them, and the game behaved the same way before.
  The rest are start-up code, and a room reset (`015A7C`) empties the table.

| Level | Late, graphics patch only | Late now | Worst gap then | Worst gap now |
|---|---|---|---|---|
| 1 | 1% | 0% | 7 | 5 |
| 2 | 22% | 12% | 10 | 8 |
| 3 | 11% | 0% | 7 | 6 |
| 4 | 17% | 0% | 7 | 5 |
| 5 | 24% | 0% | 7 | 6 |
| 6 | 20% | 5% | 7 | 6 |
| 7 | 14% | 1% | 7 | 6 |
| 8 | 19% | 0% | 6 | 5 |

Across all levels, 2.0% of ticks are late, down from 23.8% in the original. Vertical blanks are no
longer missed.

### What's still late

Nearly all the late ticks left aren't the CPU running out of time. They're on levels 2, 6 and 7,
and they spend about 490k cycles inside the wait for vertical blank (`014E3A`). On levels 2 and 6
the waits come from a drawing loop at `0074A8`, which waits four frames per step. On level 7 most
come from `011776`, which waits two. These look like deliberate animations, though what's being
animated hasn't been identified. Making them faster would change how they look, so they're left
alone.

### Room to spare

`tools/harness/tick_parts.py --headroom` measures the work in each tick without those waits. The
median tick needs about 155k cycles, 90% need under 294k and 99% under 420k, against 639k
available. Counted in frames, 44% of ticks have their picture ready in 1 frame, 47% in 2 and 8.5%
in 3, where the original had three quarters at 3 or more. The heaviest are still camera-step ticks, which spend about 133k in the three map
routines where they spent 223k. Only 0.1% of ticks wouldn't fit in 4 frames and 3.7% wouldn't fit
in 3, but 26% wouldn't fit in 2. These are random walks, so a real route may differ.

The largest remaining costs, as shares of work outside waits, are the object tile copy at
`02E3E4` (9%), what looks like the link to the sound driver at `01624E` (9%), the sprite masking
at `01428C` (9%), `015E9C`, which hasn't been read (7%), and sprite tile uploads through `0150E6`
(7%).

### The end of a tick

`01564E` draws a tick's picture. It masks the sprites (`01428C`), then sends all their tiles to
video memory (`014A34`), 16 DMA transfers into whichever of two areas isn't on screen, at `4C80`
and `8980`. Then it waits for vertical blank unless it's already in it (`014E4E`), builds the
sprite table pointing at the new area (`0149B8`), sends it (`014A12`), sets the scroll position,
and on a camera step writes the 612 cells of the map (`013BF6`). The DMA routine `0150E6` stops
the Z80 for as long as each transfer runs.

The vertical blank handler at `014D2A` counts the frame, reads the pad, steps a color cycle every
12 frames when one is running, and runs the sound link, which takes about 10 of vertical blank's 38 scan lines. The
main loop then waits until 5 frames after the tick started.

### How sound works

The music and sound effects are sequenced on the 68000, not the Z80. Once a frame, from the
vertical blank handler, `01624E` stops the Z80, copies 48 bytes from its memory at `A00229` to
`FF01F0`, and lets it go. Then `015E9C` steps the music's channels and `0165AE` the six sound
effect channels, changing those bytes: 8 for each of 6 channels. If anything changed, the link
stops the Z80 again and copies them back, and it always writes a flag at `A00259` to say whether
it did. The Z80's part is to turn those bytes into YM2612 writes. It also plays sampled sounds on
levels 3, 4 and 7, timing them itself, so a sample waits whenever the 68000 has the Z80 stopped.
The 68000's sound state is `FF0000` to `FF0240`, with 80 bytes for each channel from `FF0008`.
Songs start through `015D10` with a number in d0, and there are at least eight.

### How the screen's cells are built

`013D34` fills two buffers on a camera step: 612 words at `FF6C82`, one for each 8 by 8 cell on a
34 by 18 screen, and 612 mask-shape bytes at `FF8ADE` for the sprite masking. A level is a grid of
blocks 20 across and up to 128 down, each 8 cells wide and 4 tall. Three maps give each block its
graphics number, the room it belongs to and its kind of mask. A block shows only if it belongs to
the room the wizard is in, or to every room. Doorway blocks belong to two rooms, and six of them
are swapped for a different block depending on which side the wizard is on. The graphics are 64
bytes a block at `03ABF2`.

The tile table at `FF7612` now has a companion at `FF9660`: 64 bytes counting the entries in use
in each group of 32, which lets the sync skip empty groups.

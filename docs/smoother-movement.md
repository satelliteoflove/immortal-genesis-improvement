# Smoother movement without a faster game

> **Dropped on 2026-11-19.** Chris played the trial and chose to go back to the original
> drawing speed. Blending the poses in between couldn't be done on the console, and poses
> made by RIFE and by Qwen Image Edit didn't look good enough and couldn't be rebuilt by
> someone else making the patch. `tools/build_rom.py --smooth` is gone; the routine is in
> the history at commit c66628f, with its last fix (depth isn't blended). What follows is
> kept as a record.

The game updates 12 times a second and draws one picture for each update. The idea here is to
keep that rate and draw a second picture between updates, with everything part of the way from
its old position to its new one. That gives 24 pictures a second of movement and scrolling at
the same game speed. This is a study of whether it can be done. Nothing has been built.

## What was checked

**How far things move in one update.** Far enough to be worth splitting. A scripted walk on levels
1, 3 and 5 gave these steps, in pixels:

| What moves | Step per update |
|---|---|
| The wizard, straight across | 6 or 12 |
| The wizard, straight up or down | 4 or 8 |
| The wizard, along the diagonals | 4 across and 2 down, or 8 and 4 |
| The camera | 2 to 6, most often 4 |

The wizard has two walking speeds, with a two-pose walk at the faster one and a four-pose walk at
the slower one. When the camera follows him he stays put on screen and the room moves instead.

**Where positions come from.** They can be read cleanly. The game logic doesn't draw anything
itself. During each update it fills in a list of up to 32 things to draw, and all of it goes
through one routine, `01359E`, called from one place. Each entry has a screen position, two
numbers choosing the pose, a depth for sorting and a pointer to its set of sprites. The list is
at `FF10E2` to `FF12E1`, with its count at `FF12E2`. The camera is two words at `FF1460`.

Entries stay in the same order from one update to the next, so entry 2 in one update is entry 2
in the next. In about 100 updates of each walk the list changed size on 2 to 5 of them, when
something appeared or went away, and once it kept its size with a different sprite in it. Room
changes show up as one large jump of the camera.

**Whether the drawing can run twice.** It looks safe. `013682` sorts the list and turns each entry
into sprite pieces (`01467C`), and `01564E` masks them, sends them and updates the screen. Reading
them, they keep no state that the game logic depends on. One thing would need guarding: in room
`$64`, `01564E` steps a color cycle each time it runs, so a second run would double its speed.

**What a second picture costs.** About 50k to 75k cycles: 33k to build the sprite pieces, 12k to
38k to mask them and 5k for the screen update. That's about half a frame. The sprite tiles are
sent a second time too, but that fits in time spent waiting. If the in-between camera position
crosses an 8-pixel step, the camera step work (133k) lands on that picture.

## How it would work

Keep the previous update's list and camera. After the game logic has filled in the new list:

1. Check the two lists match: same size, same sprite sets in the same places, no large jumps.
   If they don't, skip the in-between picture for this update.
2. Move every position, and the camera, part of the way back toward the previous update's, and
   draw. Screen positions and the camera can each be blended on their own, and scenery and
   sprites stay lined up.
3. Put the new values back and draw again, as now.

**Timing.** An update lasts 5 frames, which can't be split evenly. Showing the in-between picture
at frame 2 and the finished one at frame 4 leaves gaps of 2 and 3 frames. If the in-between picture
sits 60% of the way along, movement is still at an even speed.

## What it costs

- **Delay.** At present the finished picture is on screen 1 or 2 frames after the update starts.
  It would be 4, so a completed step shows 33 to 50 ms later, though 60% of the step shows as early
  as it does now.
- **Poses.** The wizard still has only the poses that were drawn. He'd move in smaller steps, but
  his legs would change no more often. That may look like sliding, most of all at the faster walk,
  which has two poses and 12-pixel steps.
- **Heavy updates.** On a camera step the two pictures won't always make frames 2 and 4, so
  scrolling would be a little less even than walking in a still room.
- **Sampled sound.** Sending sprite tiles twice an update doubles the time the Z80 is stopped for
  it, unless the upload moves into vertical blank first.

## The trial build

`tools/build_rom.py --smooth` writes `build/immortal-smooth.md` beside the normal build, which it
leaves alone. The trial replaces the main loop's two drawing calls at `01348C` with a call to one
new routine at `02E800`. Fights, menus and the title screen don't go through those calls, so
they're as they were.

**What it does each update.** If the conditions below hold, it saves the list's positions, moves
each one and the camera 3/8 of the way back toward the last update's, draws that at frame 2, puts
the real values back and draws again at frame 4. If the in-between picture was late, the real one
follows 2 frames after it, and never later than the update's end. Otherwise it draws once, as the
game did, at frame 4.

**Pairing.** The list has no names for things. The first attempt paired each entry with the one in
the same place in last update's list, and it went wrong at once: entries come and go, several share
a sprite set, and on level 4 the wizard and a ladder were drawn pulled toward each other for one
picture. Each entry is now paired with the nearest entry of last update's list that has the same
sprite set and is within 16 pixels of where this one would have been if it hadn't moved in the
room. An entry with no pair is drawn where it really is. A wrong pair can still happen when two
things of one set are within 16 pixels of each other, and then it puts something at most 6 pixels
out for one picture.

Over steady walks on all eight levels, 3,732 entries in 696 updates: 78% hadn't moved in the room,
21% had moved and were paired, 1.2% had no pair, and in 2.8% of cases two entries took the same
partner (mostly identical things drawn on top of each other). 11% were paired with a different
place in the list, which is what the first attempt got wrong.

**No in-between picture when:**

- sprites are already waiting when drawing starts. Message text is drawn that way, outside the list.
- the list is empty.
- the game logic took 2 frames or more, so frame 2 has gone.
- the last update drawn was more than 8 frames ago, as after a fight or a pause.
- the camera moved more than 16 pixels, as on a change of room.

**How often it happens.** On random walks in the BlastEm fork, 96 to 100% of updates got an
in-between picture on six of the levels. Level 2 got 82 to 90% and level 6 got 89 to 100%, and what
stopped it there was nearly always the game logic taking too long. Late updates went from 1.5% to
1.9% on the same walks. Object graphics are unpacked twice an update now, 33k cycles where it was
16k, which a later version could avoid by keeping the first picture's tiles.

**What the screen does.** Measured from clips of the same scripted walk on both builds, a walk
with the camera following on level 4 changed the picture 136 times in 680 frames on the normal
build, at gaps of 5 frames, and 262 times on the trial, at gaps of 2 and 3.

**Fights.** A fight runs in its own loop from `011590`, with its own drawing at `015738` and
`015768`. The two fighters stand at fixed places and only change pose. There's nothing to blend,
so this method can't smooth a fight, and the trial doesn't touch one. Fights were run on the trial
on levels 3 and 7 and the game carried on afterward.

**Memory.** RAM from `FF969F` to `FFFEA8` was zero in 30 snapshots taken across five levels, so
it's taken to be unused. The trial uses `FFA000` to `FFA225`.

**The cost that's certain.** The real picture now waits for frame 4. On the normal build it's
usually up by frame 1 or 2, so what the player does shows 2 to 3 frames later, though most of the
movement shows at frame 2 in the in-between picture.

## What isn't known

- How it looks and feels in play. The clips say the pictures are there and nothing is out of
  place in the stretches that were looked at. They don't say whether it's better.
- Whether the wizard seems to slide. He moves in smaller steps but his legs change no more often.
- What happens with spells, deaths, traps and message text. None of those were looked at.
- Whether any wrong pairs show. They were counted, not watched.
- Sampled sound on levels 3, 4 and 7. Sprite tiles are sent twice an update now, so the Z80 is
  stopped twice as long for them. Nobody has listened.
- Real hardware. All of this was run in BlastEm.

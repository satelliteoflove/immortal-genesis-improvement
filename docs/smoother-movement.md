# Smoother movement without a faster game

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
`$64`, `01564E` steps a colour cycle each time it runs, so a second run would double its speed.

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

## What isn't known

- Whether anything draws to the screen outside the list. The walks didn't show any, but they didn't
  cover fights, spells, deaths or messages.
- Whether the routines with their own waits, such as the animations at `0074A8`, go through the
  same drawing and would need the in-between picture turned off.
- How it looks. That's the real test, and it needs a build to watch.

## Memory

The patch has 190 spare bytes of RAM at `FF96A0`, left over from the old object decoder. Positions
are a byte each as the game hands them over, so the previous list fits in about 100 bytes. Whether
there's other free RAM hasn't been looked into.

# RHDN texts: drafts

Three texts for the release: the hack page's description, the news post, and the Personal
Projects forum post. The screenshots for each are listed at the end.

## Hack page description

The Immortal is a hard game, both due to the trial-and-error nature of the game and also
because it is generally unforgiving of mistakes. The Genesis version had a few rough spots on
top of that. It slows down badly in busy rooms, a death sends you straight back into the room
almost immediately, and the only way to keep your progress is to write down the 13-character
"certificate" (the game's password) that it shows at the end of each level. This patch smooths
some of the more frustrating design choices out and fixes a few bugs in the original, while
leaving it the same game. It doesn't make the game easier: traps, fights, creatures, items and
getting three lives per level stay as they were, and nothing runs faster than it was meant to.

The patch was made with Claude, Anthropic's AI model, which wrote most of the code and the
testing tools under the author's direction. The author played the game through on the finished
patch and tested each new feature.

What it changes:

- Much less slowdown. The game is meant to move everything along 12 times a second (5 vblanks
  for each game update), but in busy rooms it often couldn't draw everything in time, and the
  whole game slowed down. The patch makes it draw creatures, objects and the scrolling
  background much faster. It was measured with test scripts that play the whole game through,
  the same way every time. In that run, about a third of the original's updates took too long,
  and on levels 7 (the barrel ride on the water) and 8 (the dragon), even more of them did, so
  the slowdowns were very noticeable. With the patch, only 2% of the updates took too long
  (according to the automated testing), and about 4% of the updates came late in a full
  play-through by hand.
- Fights are kept at their original pace. The sword fights, which the game shows on a screen of
  their own, have no clock: they simply run as fast as the game can draw them. Faster drawing
  made them faster too, so the patch holds them to the pace they had in the original (the
  animation is about 6% quicker).
- Battery saves. Finishing a level now saves your place at the start of the next one, along
  with everything you're carrying, and "Game saved." appears under the certificate. When you
  turn the game on, it asks "Continue a saved game?". YES shows a level number: UP and DOWN
  step through the levels you've saved, and any button starts the one shown. NO goes on to "New
  game?" as before, so you can still start over or type in a certificate. Your emulator keeps
  the saves in its save file. Each emulator stores that file its own way, so a save made in one
  won't load in another.
- A second try at Game Over. In the original, losing your last life went to "Game Over" and
  "Play again?" and then back to the prompts the game starts with, so picking up where you'd
  been meant typing in a certificate again. Game Over now asks "Try this level again?". YES
  starts the level you were on over from its beginning, with three lives and whatever you were
  carrying when you started it. NO goes on to the usual prompts.
- More time after a death. When you die with a life left, the game shows "Prepare to
  continue..." on a black screen and then puts you back in the level. In the original that
  lasted about a second and a half, and less if you were holding a button. It now stays up for
  3 seconds, or until you press A, B, C or Start.
- Message acceleration now goes fast, but not too fast to be read. Messages type out one letter
  at a time. Holding a button while one types now makes it go about three times as fast, with
  every letter drawn. That's slower than holding a button was in the original, which put whole
  words up at once and skipped every pause, so pages could go by before you'd read them. With
  the patch, a held button doesn't skip the pause at the end of a page: the page stays up for a
  little over a second, and then the next one starts. To go on sooner, let go of the button and
  press A, B, C or Start again. The original also had a hidden shortcut, two particular buttons
  held together, that skipped every wait, and that's gone too. If you've read the messages many
  times and just want them gone, this is slower than the original was. With no button held,
  messages are as they always were.

Bug fixes from the original game:

- In level 4's first room, the torch on the wall was drawn with the top of its flame missing.
  The game had a small mistake in the way it looked up that one piece of graphics. The torch
  now has its whole flame.
- When the wizard or a creature walks behind part of the scenery, such as a wall or the edge of
  a floor, the game hides the parts of him that should be out of sight. The original got this
  slightly wrong along the edge, so a few pixels there came out in the wrong color, or showed
  when they should have been hidden. One you might have noticed is a yellow dot at the wizard's
  foot when he stands behind the edge of a floor. In the test runs it happened in about one
  frame in eight. Those pixels now come out right.
- While you walk around a level, the music would often start over from the beginning for no
  reason you could see. In many places the game asks for a different piece of music for a
  moment and then for the level's music back, and when nothing came of it, both requests came
  so close together that the other piece never played and the level's music just restarted. The
  patch ignores those pairs of requests, so the music keeps playing. Real changes of music,
  such as going into a fight, happen as before.
- In level 5, dying in the last room (the one with the straw bed) sent the wizard back to the
  level's first room. There was no way out of there anymore: the hole out of that room only
  lets a shrunken wizard through, the shrinking potion was used up by then, and the merchant
  had nothing left to sell. There was nothing there that could kill him either, so you couldn't
  even reach Game Over, and the only way out was to reset the game. Now a death in that room
  puts him back at the foot of the ladder he climbed down into it, beside the straw bed.

Tested in the emulators BlastEm, PicoDrive and Genesis Plus GX, at 60 Hz (North American and
Japanese consoles) and 50 Hz (European consoles). It hasn't been tried on a real Genesis or
Mega Drive. The source and notes are at
https://github.com/satelliteoflove/immortal-genesis-improvement

## News post

The Immortal is a hard game, and it's meant to be. On the Genesis, though, it also fights you
in ways that are just plain frustrating. It slows down badly in busy rooms, a death throws you
straight back into the room before you can think, and the only way to keep your place is to
write down the 13-character "certificate" (the game's password) that it shows at the end of
every level, and then type it back in each time you play. The Immortal (Genesis) Improvement
Patch attempts to mitigate those problems and leaves the rest of the game alone.

The biggest change is speed. The game is meant to move everything along 12 times a second (5
vblanks are provided for each game loop update), but in busy rooms it often still couldn't
process logic and draw everything in time, and the whole game slowed down. It rebuilt the
graphics for every creature and object on screen from scratch on every update, and it sent
background graphics to the video chip that were already there. With that fixed, it mostly runs
the way it was meant to. It was measured with test scripts that play the whole game through,
the same way every time. In that run, about a third of the original's updates took too long,
the Norlac barrel race would slow down very badly, and the last level played at about
two-thirds of its proper speed. With the patch, only about 2% of the updates took too long, and
about 4% of the updates were late in a full play-through by hand. Nothing runs faster than it
was meant to, though. The sword fights, which the game shows on a screen of their own, have no
clock and simply run as fast as the game can draw them, so the patch holds them to the pace
they had in the original (the animation is about 6% quicker).

Keeping your progress is easier too. Finishing a level now saves your place at the start of the
next one to battery RAM, along with everything you're carrying. When you turn the game on, it
asks "Continue a saved game?" and lets you pick any level you've saved. Certificates still work
for anyone who wants them. When you run out of lives, Game Over now asks "Try this level
again?" and starts the level over from its beginning, with three fresh lives and whatever you
carried into it. In the original, it sent you back to the prompts the game starts with, and you
had to type in a certificate to get back to where you'd been.

There are smaller touches as well. After a death, "Prepare to continue..." stays up for 3
seconds, unless you press a button, so the retry doesn't come at you out of nowhere. In the
original it was gone in about a second and a half. Holding a button now types messages about
three times faster than normal, with every letter drawn, and it no longer skips the pause at
the end of a page. That's meant for players who read quickly. The original's held button was
faster still, putting up whole words at once and skipping every pause, so if you just want the
text gone, this is slower than you're used to.

A few bugs from the original are fixed, too:

- The torch on the wall in level 4's first room is drawn with its whole flame, where the
  original cut off the top of it.
- When the wizard or a creature walks behind scenery, a few pixels along the edge came out in
  the wrong color or showed through, such as a yellow dot at the wizard's foot. They're drawn
  right now.
- The level's music no longer starts over from the beginning while you're just walking around.
- In level 5, a death in the last room, the one with the straw bed, sent the wizard back to the
  level's first room, where the level could no longer be finished and nothing could even kill
  him. Only a reset got you out. He now starts again at the foot of the ladder into that room.

What hasn't changed are the things that make the game what it is. Traps, fights, creatures and
items are just as they were, and so are the three lives per level. It's still the same
(sometimes brutally) difficult game; it just doesn't get in its own way anymore.

The patch was made with Claude, Anthropic's AI model, which wrote most of the code and the
testing tools under the author's direction, and the author played the game through on the
finished patch and tested each new feature. It's been tested in the emulators BlastEm,
PicoDrive and Genesis Plus GX, but not yet on a real console. The source, the testing tools and
a lot of notes on how the game works are on GitHub:
https://github.com/satelliteoflove/immortal-genesis-improvement

## Personal Projects forum post

**The Immortal (Genesis) Improvement Patch**

I've just released a patch for the Genesis version of "The Immortal", and I wanted to say a bit
about how it came about.

This started out as an idea for a 32X port. The more I read about what people actually disliked
about the game, though, the less it looked like something the 32X would fix. Most of it is
about how unfair the game can feel: traps that kill you seconds after you walk into a room,
losing all your lives and starting over, and having to write down a 13-character "certificate"
(the game's password) after every level to keep your place. None of that needs more hardware,
so it turned into a straight patch for the Genesis. The Genesis version also slows down a lot
in busy rooms, and that I could do something about.

I want to be up front that I built this with Claude, Anthropic's AI model. It wrote most of the
code and the testing tools, working under my direction, and I made the calls on what should
change and what shouldn't. I also played the whole game through on the finished patch to make
sure it holds together as a game, not just as a set of test results.

The game is meant to move everything along 12 times a second (5 vblanks for each game update),
and the slowdown comes from updates that take longer than that to process and draw. It turned
out to have a couple of big causes. The graphics for the creatures and objects are stored
packed, to save space, and the game unpacked every one on screen from scratch on every update,
through a routine that worked through the packed data one bit at a time. On level 6 that was
over half of all the work the console did. It also sent background graphics to the video chip
that were already there. We measured it with scripts that play the whole game through the same
way every time. In that run, about a third of the original's updates took too long, the Norlac
barrel race on level 7 slowed down very badly, and level 8 played at about two-thirds of its
proper speed. With those fixed, and a few smaller things, only about 2% of the updates took too
long in the same run, and about 4% were late when I played it through by hand.

One thing I didn't expect: making the drawing faster made the fights faster too. The sword
fights happen on a screen of their own, and they have no clock. They just run as fast as the
game can draw them. So the patch holds them to the pace they had in the original. The animation
ends up about 6% quicker than the original's average, since the original's pace wandered a
little and the patch's doesn't.

The messages took some thought. In the original, holding a button made whole words pop up and
skipped every pause, so pages went by faster than most people can read. I wanted something in
between for people who read quickly: holding a button now types about three times as fast as
normal, every letter drawn, and it doesn't skip the pause at the end of a page. Let go and
press again and the next page comes right away. If you've read the messages many times and just
want them gone, this is slower than the original was for that. That's not who I had in mind
with it.

The rule I held to throughout was that this is still The Immortal. It's still brutal. Traps
still kill you without warning and the fights work the way they always did; there's no easy
mode in here. What's different is that you can save, you get a second try at a level when you
run out of lives, and the game doesn't bog down while you're trying to dodge something. After a
death, "Prepare to continue..." also stays up for 3 seconds now, so you get a moment to take in
what just happened before you're back in the room.

Along the way we built a set of scripts that play the whole game start to finish, level by
level, so every change could be checked against the original. That's also how we found a
soft-lock in the original. Dying in level 5's last room, the one with the straw bed, put the
wizard back in the level's first room. The hole out of that room only lets a shrunken wizard
through, and by then the shrinking potion is used up and the merchant has nothing left to sell,
so the level can't be finished. Nothing in there can kill him either, so you can't even get to
Game Over; only a reset gets you out. Now a death in that room puts him back at the foot of the
ladder he came down into it.

A few smaller bugs in the original are fixed as well. The torch on the wall in level 4's first
room was drawn with the top of its flame cut off, from a slip in how the game looked up that
one piece of graphics. Where the wizard or a creature passes behind scenery, a few pixels along
the edge came out in the wrong color or showed through, like a yellow dot at the wizard's foot.
And the level's music kept starting over from the beginning while you were just walking around,
because the game would ask for a different piece of music and then for the level's music back,
so close together that the other one never played.

It's been tested in BlastEm, PicoDrive and Genesis Plus GX. I haven't been able to try it on
real hardware, so if anyone runs it on a console or a flash cart, I'd really like to hear how
it goes. The source, the testing tools and a lot of notes on how the game works are on GitHub:
https://github.com/satelliteoflove/immortal-genesis-improvement

If you run into anything odd, feel free to post here or open an issue there.

## Screenshots

Taken from the patched ROM at the game's own 320 by 224, in `scratch/rhdn/final/` (kept out of
git, since they're the game's graphics):

1. `1-title.png`: the title screen.
2. `2-continue-a-saved-game.png`: the prompt at start when a save is present.
3. `3-level-picker.png`: the level picker, showing level 5.
4. `4-try-this-level-again.png`: Game Over's new question.
5. `5-level-7-water.png`: level 7's room 4, the wizard in the barrel with a water creature
   attacking. In the scripted run this room had 62% of its updates late on the original,
   running at 71% speed, and 4% late with the patch.
6. `6-level-8-dragon.png`: level 8's room 2, the dragon breathing fire. The original had nearly
   every update late here (62% speed); the patch has 11% late (96% speed). It's the final
   battle, so it gives away the last fight.

Suggested use:

- **Hack page:** 1, then 2, 3, 4 and 5.
- **News post:** 2 and 5.
- **Forum post:** all six.

Uploaded to the RHDN scratchpad:

| Screenshot | Scratchpad page |
|---|---|
| 1, title | https://www.romhacking.net/scratchpad/101862/ |
| 2, continue a saved game | https://www.romhacking.net/scratchpad/101863/ |
| 3, level picker | https://www.romhacking.net/scratchpad/101864/ |
| 4, try this level again | https://www.romhacking.net/scratchpad/101865/ |
| 5, level 7 barrel race | https://www.romhacking.net/scratchpad/101866/ |
| 6, level 8 dragon | https://www.romhacking.net/scratchpad/101867/ |

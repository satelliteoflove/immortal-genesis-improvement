# RHDN texts: drafts

Three texts for the release: the hack page's description, the news post, and the Personal
Projects forum post. The screenshots for each are listed at the end.

## Hack page description

The Immortal is a hard game, and the Genesis version had a few rough spots on top of that. It
slows down badly in places, a death sends you straight back in before you've caught your
breath, and the only way to keep your progress is to write down a long certificate at the end
of each level. This patch smooths those things out and fixes a few bugs, while leaving it the
same game. It doesn't make the game easier or faster: traps, fights, items and the three lives
per level are as they were, and the game keeps its original pace.

I made this patch with Claude, Anthropic's AI model, which wrote most of the code and the
testing tools under my direction. I played the game through on the finished patch myself.

What it changes:

- Much less slowdown. The game draws objects, sprites and the scrolling background much
  faster. In a scripted run through the whole game, about a third of the original's updates
  ran late, and level 8 ran at about two-thirds speed. With the patch, 2% ran late in the same
  run, and about 4% in a full play-through by hand. Fights still run at the original's speed.
- Battery saves. Finishing a level saves it, and the game offers your saved levels when it
  starts. Certificates still work.
- Game Over asks "Try this level again?", and starts the level over with three lives and what
  you carried into it.
- "Prepare to continue..." stays up for 3 seconds after a death, unless you press a button.
- Holding a button types messages out faster without skipping their pauses.
- Bug fixes: the level 4 wall torch's flame, stray pixels where characters pass behind
  scenery, the level's music starting over for no reason, and a soft-lock after a death in
  level 5's last room.

Tested in BlastEm, PicoDrive and Genesis Plus GX, at 60 Hz and 50 Hz. It hasn't been tried on
real hardware. The source and notes are at
https://github.com/satelliteoflove/immortal-genesis-improvement

## News post

The Immortal (Genesis) Improvement Patch fixes the Genesis version's worst slowdown, adds
battery saves and a second try at Game Over, and fixes a few bugs, while leaving the game as
hard as it always was. Traps, fights and items are untouched, and the game keeps its original
pace; it just doesn't bog down the way it did, most of all on the later levels.

The patch was made with Claude, Anthropic's AI model, which wrote most of the code and the
testing tools under my direction.

## Personal Projects forum post

**The Immortal (Genesis) Improvement Patch**

I've just released a patch for the Genesis version of The Immortal, and I wanted to say a bit
about how it came about.

This started out as an idea for a 32X port. The more I read about what people actually
disliked about the game, though, the less it looked like something the 32X would fix. Most of
it is about how unfair the game can feel: traps that kill you seconds after you walk into a
room, losing all your lives and starting over, and having to write down a 13-character
certificate after every level to keep your place. None of that needs more hardware, so it
turned into a straight patch for the Genesis. The Genesis version also slows down a lot in
busy rooms, and that I could do something about.

I want to be up front that I built this with Claude, Anthropic's AI model. It wrote most of the
code and the testing tools, working under my direction, and I made the calls on what should
change and what shouldn't. I also played the whole game through on the finished patch to make
sure it holds together as a game, not just as a set of test results.

The slowdown turned out to have a couple of big causes. The game unpacked the graphics for
every object on screen from scratch on every update, through a decoder that tested one bit at
a time, and on level 6 that was over half of everything the CPU did. It also re-sent
background tiles to video memory that were already there. In a scripted run through the
whole game, about a third of the original's updates ran late, and level 8 ran at about
two-thirds speed. With those fixed, and a few smaller things, it's 2% in the same run, and
about 4% when I played it through by hand.

One thing I didn't expect: making the drawing faster made the fights faster too, because
fights in this game have no clock of their own. They just run as fast as they can draw. So
the patch holds them to the pace they had in the original, and a fight plays the way it
always did.

The rule I held to throughout was that this is still The Immortal. It's still brutal. Traps
still kill you without warning and the fights are unchanged; there's no easy mode in here.
What's different is that you can save, you get a second try at a level when you run out of
lives, and the game doesn't bog down while you're trying to dodge something.

Along the way we built a set of scripts that play the whole game start to finish, level by
level, so every change could be checked against the original. That's also how we found a
soft-lock in the original: dying in level 5's last room put the wizard back in the level's
first room, where the level could no longer be finished. That one's fixed now.

It's been tested in BlastEm, PicoDrive and Genesis Plus GX. I haven't been able to try it on
real hardware, so if anyone runs it on a console or a flash cart, I'd really like to hear how
it goes. The source, the testing tools and a lot of notes on how the game works are on GitHub:
https://github.com/satelliteoflove/immortal-genesis-improvement

If you run into anything odd, feel free to post here or open an issue there.

## Screenshots

Taken from the patched ROM at the game's own 320 by 224.

- **Hack page:** the title screen and up to four in-game shots, from: "Continue a saved
  game?", the level picker, "Try this level again?", and the two busy rooms.
- **News post:** two of them.
- **Forum post:** all of them.

[The busy rooms are still being chosen: the two that slowed down worst in the original and
only a little now.]

#!/usr/bin/env python3
"""Level 8, the last: from its certificate to the game's ending. See docs/playthrough.md.

    tools/harness/route/level8.py [--original] [--delay N] [--quiet]

There is no "End of level!" screen and no certificate here, so play() returns None once the
ending's message is up. A death on this level is a Game Over at once: the game skips the
retry on its last level, whatever the count at FF109A says.

Thing numbers on this level (indexes into the tables at FF0AEE): 0 the gold, 1 the amulet,
2 the statue book, 3 the magnetic hands scroll, 4 the sonic scroll, all carried in from the
certificate; 7 the chest in room 0, holding 9 (the fire protection scroll) and 8 (the blink book)
and some gold.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

CERTIFICATE = 'e011f730178c1'
LEVEL = 8

GOLD, AMULET, STATUE, MAGNETIC, SONIC = 0, 1, 2, 3, 4
CHEST, BLINK, FIRE = 7, 8, 9
MORDAMIR, DRAGON, REAPER = 10, 11, 12           # they are things, in room 2

# The dragon's routine (00BE7A) and the wizard's teacher's (00BC1E) each work through a
# list of animations, one after another.
DRAGON_STEP, DRAGON_SLOT = 0x0BC2, 0x0BC3       # how many begun; the slot of the one running
MORDAMIR_STEP, MORDAMIR_MOVE, MORDAMIR_SLOT = 0x0BBD, 0x0BBE, 0x0BBC
STAGE = 0x0BC4                  # 0 the dragon attacks, 1 the amulet is up, 2 the teacher has come
REAPER_COMING = 0x0BA8          # not zero once the reaper has been sent
BLINKS, STATUES = 0x103E, 0x103F                # casts left of each

BREATH, LONG_BREATH = 0x08, 0x0A                # the dragon's animations that end in fire
BOLTS = {0x14: 20, 0x16: 26}                    # the teacher's two bolts, and how long each is
STOOP, GLOAT, BURNING = 0x1A, 0x20, 0x22        # his other moves that matter

# What the wizard's action byte holds while each thing is happening to him.
BLINKING, PROTECTED, STATUE_NOW = 0x14, 0x15, 0x16

def cast(g, level, counter, what):
    """Press A to cast the armed spell and check that one of its casts was spent."""
    before = g.byte(counter)
    press_a(g)
    for _ in range(12):
        if g.byte(counter) != before:
            return
        g.step(1)
    fail(g, level, f'{what}: A cast nothing')


def play(g, log=print):
    if g.level != 7 or g.room != 0:
        fail(g, LEVEL, f'expected the first room of level 8, found level {g.level} room {g.room}')
    for thing in (AMULET, STATUE, MAGNETIC, SONIC):
        if not has(g, thing):
            fail(g, LEVEL, f'thing {thing} is not carried at the start; carrying {carried(g)}')

    # Room 0. The chest is unlocked: yes to opening it and to both things in it.
    walk_to(g, 104, 64)
    search(g, 'yyy', BLINK, FIRE)
    log('opened the chest, carrying', carried(g))

    # The ladder is in the hole below the chest. Stepping into the hole from above or from
    # the right climbs down it; from the left or from below the wizard falls and dies.
    go(g, (110, 80))
    through_door(g, 'DOWN', 1)
    log('down the ladder')

    # Room 1 is empty. The pit in the middle can't be seen; walking onto it drops the wizard
    # onto the rock in front of the dragon.
    go(g, (112, 70))
    through_door(g, 'LEFT', 2)
    log('fell down the pit')

    # Room 2. Nothing can be done until he has landed. The dragon takes about 107 updates
    # to rise, which is time enough to make the blink book the spell that A casts.
    g.until(lambda g: action(g) == 0, limit=600)
    use(g, BLINK)
    read(g)
    if armed(g) != BLINK:
        fail(g, LEVEL, 'the blink book is not the armed spell')
    log('blink is armed')
    dragon(g, log)
    teacher(g, log)
    log('the closing story is up, the one beginning at %04X' % text_address(g))
    return end_of_game(g)


def dragon(g, log):
    """Live through the dragon's seven breaths and hold the amulet up.

    Fire reaches the wizard while the dragon's picture is 7: positions 14 to 20 of a short
    breath, 22 to 33 of the long one. A blink lasts 11 updates and has to be under way
    before the fire comes and not be over until it has gone, so A is pressed at position 9
    (7 to 11 work). The seventh breath is too long for a blink; the fire protection scroll
    lasts 16 updates and is used at position 16 (15 to 19 work)."""
    blinked = None
    while True:
        if not tick(g):
            fail(g, LEVEL, 'the game stopped during the dragon\'s breaths')
        if dead(g):
            fail(g, LEVEL, f'burned at the dragon\'s step {g.byte(DRAGON_STEP)}')
        now = animation(g, g.byte(DRAGON_SLOT))
        if not now:
            continue
        step = g.byte(DRAGON_STEP)
        if now[0] == BREATH and now[1] >= 9 and step != blinked:
            if now[1] > 12:
                fail(g, LEVEL, f'too late to blink: the breath is at {now[1]}')
            cast(g, LEVEL, BLINKS, 'blink')
            blinked = step
            log(f'blinked at breath position {now[1]}, {g.byte(BLINKS)} left')
        if now[0] == LONG_BREATH and now[1] >= 16:
            break
    if g.byte(BLINKS) != 0:
        fail(g, LEVEL, f'the long breath came with {g.byte(BLINKS)} blinks unused')
    if now[1] > 19:
        fail(g, LEVEL, f'too late for fire protection: the breath is at {now[1]}')
    use(g, FIRE)
    g.until(lambda g: action(g) == PROTECTED, limit=120)
    log(f'fire protection used at breath position {now[1]}')
    # The fire writes its own number over the scroll's in the action byte while it plays on
    # him. Both are gone, and he can open the inventory again, when the byte is back to 0.
    while action(g) != 0:
        tick(g)
        if dead(g):
            fail(g, LEVEL, 'burned by the long breath')

    # The dragon wheezes until its animation ends at position 65. The amulet has to be up
    # by then, or it breathes again. Yes to holding it up, no to reading the runes.
    use(g, AMULET)
    read(g, 'yn')
    if g.byte(STAGE) != 1:
        fail(g, LEVEL, 'the amulet is not up')
    log('holding the amulet up')


def teacher(g, log):
    """From the teacher's arrival to the game's last message."""
    # He appears and speaks, and takes the amulet.
    while tick(g):
        if dead(g):
            fail(g, LEVEL, 'died waiting for the teacher')
    read(g)
    if g.byte(STAGE) != 2 or AMULET in carried(g):      # its place byte doesn't change
        fail(g, LEVEL, 'the teacher has not taken the amulet')
    use(g, STATUE)
    read(g)
    if armed(g) != STATUE:
        fail(g, LEVEL, 'the statue book is not the armed spell')
    log('the teacher has the amulet; statue is armed')
    duel(g, log)


def duel(g, log):
    """Outlast the teacher's spells, then take the amulet from him."""
    # A bolt lands when its animation ends, and strikes for the 6 updates after. A statue
    # lasts 11, so A is pressed 4 positions before the end (6 to 1 before work).
    done = None
    used_sonic = used_magnetic = dodged_reaper = False
    while True:
        if not tick(g):
            g.until(busy, limit=60)
            if ending(g):
                return
            read(g)
            continue
        if dead(g):
            fail(g, LEVEL, f'killed at the teacher\'s step {g.byte(MORDAMIR_STEP)}, '
                           f'move {g.byte(MORDAMIR_MOVE):02x}')
        step, move = g.byte(MORDAMIR_STEP), g.byte(MORDAMIR_MOVE)
        now = animation(g, g.byte(MORDAMIR_SLOT))
        if now and move in BOLTS and step != done and now[1] >= BOLTS[move] - 2:
            cast(g, LEVEL, STATUES, 'statue')
            done = step
            log(f'statue for bolt {move:02x} at step {step}, position {now[1]}; '
                f'{g.byte(STATUES)} left')
        elif now and move == STOOP and not used_sonic:
            # He stoops to cast something that kills when the animation ends (12 updates)
            # unless the sonic scroll is used while it runs. Used sooner, it's wasted.
            use(g, SONIC)
            used_sonic = True
            log('used the sonic scroll')
        elif g.byte(REAPER_COMING) and not dodged_reaper and thing_frame(g, REAPER) >= 0x0B:
            # The reaper strikes when its picture reaches 10h. The last statue covers it.
            cast(g, LEVEL, STATUES, 'statue')
            dodged_reaper = True
            log(f'statue for the reaper, {g.byte(STATUES)} left')
        elif now and move == GLOAT and not used_magnetic:
            # He speaks as this move begins (the box is up before busy() can show it), then
            # holds the amulet up for 40 updates. The scroll works for 60 from its use, and
            # has to be working when he finishes.
            wait_busy(g, limit=120)
            read(g)
            use(g, MAGNETIC)
            used_magnetic = True
            log('used magnetic hands')


if __name__ == '__main__':
    main(LEVEL, play, CERTIFICATE)

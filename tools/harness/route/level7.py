#!/usr/bin/env python3
"""Level 7, from its certificate to the "End of level!" screen. See docs/playthrough.md.

    tools/harness/route/level7.py [--original] [--delay N] [--quiet]

The level has five rooms, 0 to 4, and the route uses three: room 1 where it starts, room 2
below the first ladder, and room 4, the water, below the second.

Thing numbers on this level (indexes into the tables at FF0AEE): 0 the wizard's gold, 1 the
ring, 2 the amulet, 4 the man chained to the wall in room 1, who holds 5 (a book of statue
spells), 6 (a magnetic scroll) and 7 (a sonic scroll); 3 is the straw in room 2; 8 is the
water monster at its gate in room 4 and 9 the whirlpool.
Creature 2 is the troll in room 1 and creature 1 is the man in room 2.

The water monster (the game's routine at 009FF0, once an update):

    FF1045  0 until the wizard comes within reach of the gate (x 192 or more, y 128 to
            191), then 1: it is after him
    FF1044  counts updates, 0 to 9
    FF1046  counts tens of updates since it woke, up to 22

It doesn't follow him. It keeps a timetable, and he dies if he is still in a part of the
water it has reached: from 20 updates after it wakes, x 192 or more with y 128 or more;
from 90, x 96 or more with y 80 or more; from 140, x 104 or more; from 190, y under 96;
and from 220, anywhere. The whirlpool at (31, 176) drowns him if the monster is asleep and
ends the level if it is awake.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

CERTIFICATE = 'c250f63010ac1'
LEVEL = 7

RING, STATUE, MAGNETIC, SONIC = 1, 5, 6, 7
AWAKE, CLOCK, TENS = 0x1045, 0x1044, 0x1046     # the water monster; see above
POOL = (31, 176)


def chased(g):
    return g.byte(AWAKE) != 0


def since_woken(g):
    """Updates since the water monster woke."""
    return g.byte(TENS) * 10 + g.byte(CLOCK)


def water(g, log):
    """Room 4, on the barrel from the foot of the ladder: wake the monster and get to the
    whirlpool ahead of its timetable. If the wizard dies on the way this raises Died or
    some other RouteError, and play() tells a death from a fault by the retries."""
    # Up the left channel, right along the top water, down the long diagonal channel and
    # into the bottom water. The gate is up a short channel at the bottom water's right.
    sail(g, (30, 66), (44, 46), (196, 46), (208, 76), (126, 158), (116, 200), (150, 212))
    sail(g, (224, 201), near=1, rest=True)
    log('below the gate')

    # Wake it on the move: run left under the mouth of the gate's channel and dip up into
    # it just far enough (y 191), so no time goes on turning round.
    if sail_to(g, 190, 190, stop=chased) != 'stop':
        fail(g, LEVEL, 'the water monster did not wake')
    log('the water monster is awake')

    # Back the way he came. The tight part is the first: left along the bottom water,
    # round the corner at (128, 190) and up the diagonal channel to y under 80 inside 90
    # updates. Flat out all the way it takes about 80.
    sail(g, (130, 199), (118, 186))
    sail_to(g, 204, 76, stop=lambda g: xy(g)[1] < 80)
    log(f'out of the diagonal channel {since_woken(g)} updates after it woke (90 allowed)')
    sail(g, (196, 50))
    sail_to(g, 40, 48, stop=lambda g: xy(g)[0] < 104)
    log(f'x under 104 after {since_woken(g)} (140 allowed)')
    sail(g, (40, 48), (28, 70))
    sail_to(g, 30, 110, stop=lambda g: xy(g)[1] >= 96)
    log(f'y 96 after {since_woken(g)} (190 allowed)')
    sail(g, (30, 110))

    # The whirlpool pulls the barrel in from a little way off.
    if not chased(g):
        fail(g, LEVEL, 'the water monster is not awake; the whirlpool would drown him')
    sail_to(g, POOL[0], 150)
    for _ in range(60):
        if xy(g) == POOL:
            break
        if dead(g):
            raise Died(f'the wizard died at the whirlpool, at {xy(g)}, frame {g.frame}')
        tick(g)
    else:
        fail(g, LEVEL, 'the whirlpool did not take the barrel')
    log(f'in the whirlpool {since_woken(g)} updates after it woke (220 allowed)')


def play(g, log=print, until=None):
    """until names a place to stop early, for exploring: 'troll', 'ring', 'room2', 'man',
    'room4'."""
    if g.level != 6 or g.room != 1:
        fail(g, LEVEL, f'expected the first room of level 7, found level {g.level} room {g.room}')
    if not has(g, RING):
        fail(g, LEVEL, f'the wizard has no ring to give; carrying {carried(g)}')

    # Room 1. The troll by the chained man comes over by itself and starts the fight.
    g.until(fighting, limit=900)
    log('the troll: won with health', fight(g))
    read(g)
    if until == 'troll':
        return

    # The chained man is thing 4, in the left corner. Walking into him brings his words and
    # then a question: give him the ring? Yes, and he hands over what he holds.
    go(g, (28, 48))
    if walk_to(g, 20, 48) != 'busy':
        fail(g, LEVEL, 'the chained man did not speak')
    wait_busy(g)
    read(g, 'y')
    if has(g, RING) or not (has(g, STATUE) and has(g, MAGNETIC) and has(g, SONIC)):
        fail(g, LEVEL, f'the ring was not exchanged; carrying {carried(g)}')
    log('gave the ring, carrying', carried(g))
    if until == 'ring':
        return

    # The ladder down is a hole in the floor near the bottom corner. Stepped onto from its
    # right, the wizard climbs down. Stepped onto from its left, he falls in and dies.
    go(g, (60, 80), (84, 106))
    through_door(g, 'LEFT', 2)      # not ladder(): a text box comes before he steps off
    log('down the first ladder')
    if until == 'room2':
        return

    # Room 2. A man is waiting at the foot of the ladder. He talks and then fights, and has
    # 9 health to the troll's 3.
    wait_busy(g)
    read(g)
    log('the man at the foot of the ladder: won with health', fight(g))
    read(g)
    if until == 'man':
        return

    # The straw (thing 3) isn't needed. The next ladder is a hole on the left, safe from its
    # right and top like the first one, and it goes straight to room 4, the water, where the
    # wizard steps off onto a barrel. A death in the water puts him back in room 2.
    while True:
        lives = retries(g)
        go(g, (90, 80), (67, 102))
        through_door(g, 'LEFT', 4)
        log('down the second ladder')
        if until == 'room4':
            return
        try:
            water(g, log)
            return end_of_level(g)
        except RouteError as error:
            # Drowning takes his health to 0. Being caught by the monster doesn't: he is
            # pulled under at full health and only the retries show it, about 50 updates
            # after he is caught.
            if not isinstance(error, Died):
                for _ in range(600):
                    if retries(g) < lives or game_over(g):
                        break
                    g.step(1)
                else:
                    raise
            revive(g)
            g.until(lambda g: game_over(g) or (g.room == 2 and not busy(g)), limit=3000)
            if game_over(g):
                raise Died(f'the retries ran out in the water (frame {g.frame})')
            log(f'lost a life in the water ({error}); {retries(g)} retries left')


if __name__ == '__main__':
    main(LEVEL, play, CERTIFICATE)

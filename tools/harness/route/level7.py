#!/usr/bin/env python3
"""Level 7, from its certificate to the "End of level!" screen. See docs/playthrough.md.

    tools/harness/route/level7.py [--original] [--delay N] [--quiet]

Not finished: it gets as far as the barrel in the water of room 4.

The level has five rooms, 0 to 4, and starts in room 1.

Thing numbers on this level (indexes into the tables at FF0AEE): 0 the wizard's gold, 1 the
ring, 2 the amulet, 4 the man chained to the wall in room 1, who holds 5 (a book of statue
spells), 6 (a magnetic scroll) and 7 (a sonic scroll); 3 is in room 2, 8 and 9 in room 4.
Creature 2 is the troll in room 1 and creature 1 is the man in room 2.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

CERTIFICATE = 'c250f63010ac1'
LEVEL = 7

RING, STATUE, MAGNETIC, SONIC = 1, 5, 6, 7


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
    through_door(g, 'LEFT', 2)
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
    # right and top like the first one, and it goes straight to room 4.
    go(g, (90, 80), (67, 102))
    through_door(g, 'LEFT', 4)
    log('down the second ladder')
    if until == 'room4':
        return

    fail(g, LEVEL, 'the route is not written past the second ladder')
    return end_of_level(g)


if __name__ == '__main__':
    main(LEVEL, play, CERTIFICATE)

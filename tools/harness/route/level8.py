#!/usr/bin/env python3
"""Level 8, the last: from its certificate to the game's ending. See docs/playthrough.md.

    tools/harness/route/level8.py [--original] [--delay N] [--quiet]

There is no "End of level!" screen and no certificate here, so play() returns None once the
ending's message is up. A death on this level is a Game Over at once: the game skips the
retry on its last level, whatever the count at FF109A says.

Thing numbers on this level (indexes into the tables at FF0AEE): 0 the gold, 1 the amulet,
2 the statue book, 3 the magnetic hands scroll, 4 the sonic scroll, all carried in from the
certificate; 7 the chest in room 0, holding 9 and 8 (the blink book and the fire scroll)
and some gold.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

CERTIFICATE = 'e011f730178c1'
LEVEL = 8

GOLD, AMULET, STATUE, MAGNETIC, SONIC = 0, 1, 2, 3, 4
CHEST, FIRE, BLINK = 7, 8, 9


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

    fail(g, LEVEL, 'the route is not written past the fall')


if __name__ == '__main__':
    main(LEVEL, play, CERTIFICATE)

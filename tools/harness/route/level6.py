#!/usr/bin/env python3
"""Level 6 (the spiders), from its certificate to the "End of level!" screen.
See docs/playthrough.md.

    tools/harness/route/level6.py [--original] [--delay N] [--quiet]

Not finished: it gets as far as killing the big spider in room 1.

Thing numbers on this level (indexes into the tables at FF0AEE): 13 and 14 the two spider
holes of room 0; 3 and 4 the egg sacks of room 1.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

CERTIFICATE = '563ff53010a41'
LEVEL = 6

LEGS = 0x0BAE               # the thing number of the hole with legs showing, FF for neither
THING_FRAME = 0x0AC4        # 42 bytes in step with the things table: each thing's animation
SPIDER = 1                  # the big spider of room 1 is creature 1
CREATURE_ACT = 0x0948       # 20 bytes, one a creature: what it is doing, in the low four bits
CREATURE_STATE = 0x0934     # 20 bytes: 33 for a wizard wrapped in web or covered in spiders
REARING = 9


def rearing(g):
    """True from the update the big spider rears up until its web has landed, 8 updates."""
    return g.byte(CREATURE_ACT + SPIDER) & 15 == REARING


def caught(g):
    """True when the wizard is held fast by a web or a swarm; he dies about 30 updates on,
    and his health doesn't show it until then (or at all, for the swarm)."""
    return g.byte(CREATURE_STATE) == 0x33


def big_spider(g, log):
    """Room 1, from where the hole lets the wizard out, to the big spider dead.

    The spider looks for the wizard once every 6 updates. If he is anywhere in front of it
    (above y 88, right of x 70 or so) it rears, and 6 updates later its web wraps him
    wherever in that part of the room he then stands. After a shot it waits 20 updates or
    more before it will rear again. So: step over the line, step back when it rears, let
    the web miss, and run in while it waits. Reaching the spider starts a fight like any
    other. The run is 8 updates, up the column x 94 to keep left of the egg sack at
    (112, 80) and right of the one at (80, 47)."""
    go(g, (94, 92))
    for _ in range(40):                         # over the line until it rears
        if rearing(g):
            break
        if xy(g)[1] > 84:
            tick(g, 'UP')
        else:
            tick(g)
        if caught(g):
            fail(g, LEVEL, 'the web caught the wizard while he was drawing the shot')
    else:
        fail(g, LEVEL, 'the spider never reared')
    while xy(g)[1] < 88:                        # and back behind it
        tick(g, 'DOWN')
    for _ in range(40):
        if not rearing(g):
            break
        tick(g)
        if caught(g):
            fail(g, LEVEL, 'the web caught the wizard behind the line')
    else:
        fail(g, LEVEL, 'the spider stayed reared')
    log('the web missed; running at the spider')
    walk_to(g, 94, 66, stop=lambda g: fighting(g) or caught(g))
    if not caught(g) and meet(g, SPIDER) != 'fight':
        fail(g, LEVEL, 'the spider did not fight')
    if caught(g):
        fail(g, LEVEL, 'the web caught the wizard on his way in')
    left = fight(g)
    log('big spider: won with health', left)


def play(g, log=print):
    if g.level != 5 or g.room != 0:
        fail(g, LEVEL, f'expected the first room of level 6, found level {g.level} room {g.room}')

    # Room 0. Two holes in the back wall, things 13 and 14. A spider's legs show in one or
    # the other for 16 updates at a time. Going into a hole is only safe while the legs are
    # in the other one; with legs in neither, or in this one, the spider is inside and kills.
    # The near hole (13) is entered by walking UP from just below it.
    go(g, (32, 64), (75, 64), (81, 62))
    g.until(lambda g: g.byte(LEGS) == 14 and g.byte(THING_FRAME + 14) <= 0x14, limit=3000)
    through_door(g, 'UP', 1, limit=80)
    log('through the spider hole')

    big_spider(g, log)

    fail(g, LEVEL, 'the route is not written past the big spider')
    return end_of_level(g)


if __name__ == '__main__':
    main(LEVEL, play, CERTIFICATE)

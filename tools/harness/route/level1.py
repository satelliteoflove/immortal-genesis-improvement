#!/usr/bin/env python3
"""Level 1, from a new game to the "End of level!" screen. See docs/playthrough.md.

    tools/harness/route/level1.py [--original] [--delay N] [--quiet]

Not finished: it gets as far as the first big room's chest.

Thing numbers on this level (indexes into the tables at FF0AEE): 2 the wizard's gold,
5 the dead fighter in room 3 holding 7 (a ring) and 6 (the fireball scroll), 13 the key the
man in room 3 gives, 8 the chest in room 3 holding 9 (a map), 10 (a bottle), 11 (spores),
12 (bait) and some gold.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

CERTIFICATE = None
LEVEL = 1


def play(g, log=print):
    if g.level != 0 or g.room != 6:
        fail(g, LEVEL, f'expected the first room of level 1, found level {g.level} room {g.room}')

    # Room 6. The square of marked tiles in the middle is a trap; go round it by the left
    # wall. The door is in the top left wall, and walking UP slides along the wall into it.
    go(g, (43, 112), (37, 104), (37, 68))
    through_door(g, 'UP', 3)
    log('out of the first room')

    # Room 3. The dead fighter is thing 5; walking up to him brings his question.
    go(g, (160, 100))
    walk_to(g, 134, 92)
    search(g, 'yyy', 7, 6)
    log('searched the body, carrying', carried(g))

    # A goblin comes over by itself.
    g.until(fighting, limit=900)
    log('first goblin: won with health', fight(g))
    read(g)

    # A second goblin is fighting a man in the bottom left. Getting close starts the fight.
    go(g, (151, 130), (70, 130))
    if walk_to(g, 36, 144, stop=fighting) != 'stop':
        fail(g, LEVEL, 'the second goblin did not come to fight')
    log('second goblin: won with health', fight(g))
    read(g)

    # The man gives a key (thing 13), which opens the chest (thing 8) below him.
    walk_to(g, 36, 142)
    wait_busy(g)
    read(g)
    if not has(g, 13):
        fail(g, LEVEL, 'the man gave no key')
    log('have the key')
    walk_to(g, 34, 190)
    search(g, 'yyyyy', 9, 10, 11, 12)
    log('opened the chest, carrying', carried(g))

    fail(g, LEVEL, 'the route is not written past the chest in room 3')
    return end_of_level(g)


if __name__ == '__main__':
    main(LEVEL, play, CERTIFICATE)

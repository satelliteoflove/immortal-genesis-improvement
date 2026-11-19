#!/usr/bin/env python3
"""Level 2, from its certificate to the "End of level!" screen. See docs/playthrough.md.

    tools/harness/route/level2.py [--original] [--delay N] [--quiet]

Not finished: see the fail() at the end of play().

The rooms: 4 is the first (two slimes, a gem, a pile of bones), with doors to 1 (top left)
and 3 (bottom). 1 is the big room of the will-o'-the-wisps, the merchant and the stone, with
two doors to 0 (two goblins) at its top, one to 2 (a troll) at its bottom left and one to 4
at its bottom. 0 leads to 5 (the goblin king and two guards). 3 is the dwarf's passage, with
doors to 4, 2 and 6 (two slimes), and 6 leads on to the last room.

Thing numbers on this level (indexes into the tables at FF0AEE): 0 to 6 what the
certificate gives the wizard (0 gold, 1 the bottle of water, 5 the spores, 6 the charm
scroll); 14 the gem in room 4 and 15 the bones there; 7 the merchant in room 1, who holds 8
(the slime oil), and 9 the stone on its floor; 10 the dust one of room 0's goblins carries;
16 the goblin king in room 5, who holds 17 (a key); 12 the dwarf in room 3, who holds 13
(a gem). Creatures: 1 to 4 the wisps, 5 and 6 the goblins of room 0, 7 the troll, 8 and 9
the slimes of room 6, 10 and 11 the slimes of room 4, 12 and 13 the king's guards.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

CERTIFICATE = 'cddff10006f70'
LEVEL = 2

WATER, SPORES, CHARM = 1, 5, 6
MERCHANT, OIL, STONE, DUST = 7, 8, 9, 10
DWARF, DWARF_GEM, GEM, BONES, KING, KEY = 12, 13, 14, 15, 16, 17
TROLL = 7
SLIMES_4, SLIMES_6 = (10, 11), (8, 9)
SWORD = 0x0A1A                          # 1 once the sword has been taken from the bones

ANIMATION = 0x0984                      # + n: creature n's animation step; see slime_resting


def slime_resting(g, n):
    """True while slime n sits still for its 16 updates of rest: its animation step at
    FF0984 + n runs 0F to 1F then, and stays 1F while it moves."""
    return 0x0F <= g.byte(ANIMATION + n) < 0x1F


def first_room(g, log):
    """Room 4. Two slimes come for the wizard from the start and their touch kills. The gem
    and the bones are left for later, when the oil is on his boots: now it is only to the
    door in the top left wall, which opens to UP, and one slime starts beside it.

    The slimes' moves are fixed by the game's state, with no chance in them, so the route
    first waits for slime 10 to begin its first rest. From that update on the room plays
    the same on both ROMs whatever the delay was. Then a walk along the top wall reaches
    the door with the slimes behind. Waiting anywhere from 16 to 36 updates after that
    first rest got through; the route waits 26, the middle."""
    for _ in range(100):
        if slime_resting(g, 10):
            break
        tick(g)
    else:
        fail(g, LEVEL, 'slime 10 never rested')
    ticks(g, 26)
    go(g, (100, 30), (80, 40), (61, 54))
    through_door(g, 'UP', 1)
    log('out of the first room')


STEPS = [first_room]


def play(g, log=print):
    if g.level != 1 or g.room != 4:
        fail(g, LEVEL, f'expected the first room of level 2, found level {g.level} room {g.room}')
    for step in STEPS:
        step(g, log)
    fail(g, LEVEL, 'the route is not written past here')
    return end_of_level(g)


if __name__ == '__main__':
    main(LEVEL, play, CERTIFICATE)

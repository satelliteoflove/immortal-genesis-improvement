#!/usr/bin/env python3
"""Level 3, from its certificate to the "End of level!" screen. See docs/playthrough.md.

    tools/harness/route/level3.py [--original] [--delay N] [--quiet]

Not finished: see the fail() at the end of play().

The rooms, in the order the route meets them: 4 the start, cut in two by a chasm, with two
ladder holes; 6 below the right-hand hole, with the flamethrowers, a chest and a troll and
goblin fighting; 7 through 6's door, with the goblin king and a ladder up; 0 the room of
spikes with the gem; 8 below its far ladder, where the trolls begin.

Thing numbers on this level: 0 to 3 what the wizard arrives with (gold, a ring, bait, an
amulet), 16 the chest in room 6 holding 17 (the fireball scroll, two shots), 9 the knife the
troll in room 6 carries, 13 the gem in room 0, 15 and 19 the flames of rooms 6 and 5,
23 the goblin king, 5 the chest in room 3 holding 6, 7 and 8.

Creatures: 2 the goblin and 3 the troll fighting in room 6, 5 and 6 the pair in room 2,
1 the guard in room 3, 7 and 8 trolls in room 5, 9 and 10 trolls in room 8, 4 in room 1.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

CERTIFICATE = 'f47ef21000e10'
LEVEL = 3

GOLD, SCROLL, KNIFE, GEM = 0, 17, 9, 13
GOBLIN, TROLL = 2, 3                    # the two fighting in room 6


def start_room(g, log):
    """Room 4. Two ladder holes; the right-hand one leads down to room 6. Its left half is a
    drop that kills and its right half is the ladder, so walk onto it downward from above
    its right half."""
    go(g, (56, 126), (68, 126))
    ladder(g, 'DOWN', 6)
    log('down the ladder to room 6')


def flame_room(g, log):
    """Room 6. The chest (thing 16) is in the left corner with a flamethrower on either
    side of it, at (60, 68) and (40, 88): standing on one when it fires kills, and nothing
    else about them hurts, so the walk in passes above the first."""
    go(g, (116, 60), (50, 61))
    walk_to(g, 44, 66)
    search(g, 'yy', SCROLL)
    use(g, SCROLL)
    wait_busy(g)
    read(g)
    if armed(g) != SCROLL:
        fail(g, LEVEL, 'the fireball scroll did not arm')
    log('took the scroll and armed it,', shots(g), 'shots')

    # The troll and the goblin trade blows by the far wall, the troll on the left. The
    # goblin has to live: he opens the door once the troll is dead. Left alone he lasts
    # about 3,600 frames from the wizard's coming into the room. A fireball thrown from the
    # troll's left, along his row, meets the troll first.
    go(g, (48, 52), (110, 52))
    if creature_health(g, GOBLIN) == 0:
        fail(g, LEVEL, 'the goblin is already dead')
    fire(g, 'RIGHT')
    for _ in range(400):
        if creature_health(g, TROLL) == 0:
            break
        g.step(1)
    else:
        fail(g, LEVEL, 'the fireball did not kill the troll')
    if creature_health(g, GOBLIN) == 0:
        fail(g, LEVEL, 'the fireball killed the goblin')
    log('the troll is dead; goblin health', creature_health(g, GOBLIN))

    walk_to(g, *creature_xy(g, TROLL))
    search(g, 'yy', KNIFE)
    log('took the knife, carrying', carried(g))

    # The goblin walks to the door in the bottom right wall and opens it.
    go(g, (140, 84))
    if walk_to(g, 172, 104) != 'room' or g.room != 7:
        fail(g, LEVEL, 'the door to room 7 did not let the wizard through')
    while walking_in(g):
        tick(g)
    log('through the door to room 7')


def king_room(g, log):
    """Room 7. The king (thing 23) sits by the ladder up in the top right. He speaks when
    the wizard pushes toward the ladder, and after that the same push climbs it."""
    go(g, (44, 104), (100, 104), (130, 60), (130, 30))
    try:
        walk_to(g, 150, 24)
    except Stuck:
        pass
    bump(g, 'RIGHT')
    read(g)
    ladder(g, 'RIGHT', 0)
    log('heard the king out and climbed to room 0')


def spike_room(g, log):
    """Room 0. Most of the floor kills the moment it is stepped on. The safe part is a wide
    band across the middle (y 60 to 88), a way up from it between x 84 and 100, and the top
    of the room right of x 60. The gem (thing 13) lies in the band. The ladder down is in
    the top left, and is safe walked onto leftward with y between 28 and 36."""
    go(g, (125, 84), (59, 84))
    walk_to(g, 59, 76)
    wait_busy(g)
    read(g, 'y')
    if not has(g, GEM):
        fail(g, LEVEL, 'the gem was not taken')
    log('took the gem')
    go(g, (92, 84), (92, 40), (66, 40), (66, 32))
    ladder(g, 'LEFT', 8)
    log('down the ladder to room 8')


def play(g, log=print):
    if g.level != LEVEL - 1 or g.room != 4:
        fail(g, LEVEL, f'expected the first room of level 3, found level {g.level + 1} '
                       f'room {g.room}')
    start_room(g, log)
    flame_room(g, log)
    king_room(g, log)
    spike_room(g, log)
    fail(g, LEVEL, 'the route is not written past the ladder into room 8')
    return end_of_level(g)


if __name__ == '__main__':
    main(LEVEL, play, CERTIFICATE)

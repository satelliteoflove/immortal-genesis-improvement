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


def shades(g, points, log):
    """Walk through points in the dark room, fighting any shade that gets in the way.

    A shade swings faster than the wizard slashes, so it is fought by counter-attack."""
    for x, y in points:
        for _ in range(8):
            result = walk_to(g, x, y, stop=fighting)
            if result == 'there':
                break
            if fighting(g):
                log('a shade attacks')
                log('shade: won with health', fight(g, counter=True))
                read(g)
            elif result == 'busy' and (x, y) == points[-1]:
                return                          # the thing being walked to has spoken
            elif result == 'busy':
                read(g)
            else:
                fail(g, LEVEL, f'walking to ({x}, {y}) ended with {result}')
        else:
            fail(g, LEVEL, f'never reached ({x}, {y})')


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

    # A second goblin (creature 3) is fighting a man (creature 2) in the bottom left.
    go(g, (151, 130), (70, 130))
    log('second goblin: won with health', attack(g, 3))
    read(g)

    # The man gives a key (thing 13), which opens the chest (thing 8) below him.
    # If the wizard is close he speaks as soon as the goblin is down, and read() above has
    # already been through it.
    if not has(g, 13):
        if meet(g, 2) != 'spoke':
            fail(g, LEVEL, 'the man started a fight')
        read(g)
    if not has(g, 13):
        fail(g, LEVEL, 'the man gave no key')
    log('have the key')
    walk_to(g, 34, 190)
    search(g, 'yyyyy', 9, 10, 11, 12)
    log('opened the chest, carrying', carried(g))

    # The far door is at the top of the room. Come at it from the left: UP from x 197 or
    # less slides along the wall into it, and from x 200 it sticks in the corner.
    go(g, (60, 130), (151, 130), (151, 94), (189, 20))
    through_door(g, 'UP', 7)

    # Room 7. A goblin (creature 4) warns, then fights. It carries things 15 and 16 and
    # offers them the moment it is beaten.
    log('third goblin: won with health', attack(g, 4))
    search(g, 'yyy', 15, 16)
    walk_to(g, *thing_xy(g, 14))                # gold on the floor
    wait_busy(g)
    read(g)
    log('room 7 cleared, carrying', carried(g))

    # The way on is a door low in the left wall. Walking LEFT slides down the wall into it.
    go(g, (120, 100), (100, 100), (70, 132))
    through_door(g, 'LEFT', 1)
    log('in the arrow room')

    # Room 1. Floor plates loose arrows that take 7 health each. This line keeps a step
    # clear of every spot where room_map saw one land: along the bottom, then up the left
    # wall of this half of the room to the corner at about (134, 64). From there LEFT
    # slides down the wall into the door of room 2.
    before = health(g)
    go(g, (199, 94), (199, 102), (187, 102), (187, 90), (157, 90), (133, 64))
    through_door(g, 'LEFT', 2)
    if health(g) != before:
        log('hit by arrows: health', before, 'to', health(g))
    log('in the pit room')

    # Room 2. Three pits lie across the middle (x 57 to 96, y 48 to 60). Keep to the left
    # wall; the door is in the lower left wall and the walk along it runs into it.
    go(g, (60, 16), (12, 62), (40, 88))
    if walk_to(g, 66, 112) != 'room' or g.room != 0:
        fail(g, LEVEL, 'did not find the door from the pit room to the dark room')
    while walking_in(g):
        tick(g)
    log('in the dark room')

    # Room 0. Five more pits, and shades that can't be seen. A scroll (thing 20) lies by the
    # upper left wall and the amulet (thing 19) by the lower left; each asks before it's taken.
    for thing, way in ((20, [(140, 30), (100, 70), (50, 70)]), (19, [(20, 100), (22, 122)])):
        shades(g, way + [thing_xy(g, thing)], log)
        search(g, 'y', thing)
    log('have the scroll and the amulet, carrying', carried(g))

    # The door in the lower right wall is locked, and the third goblin's key opens it.
    shades(g, [(50, 122), (94, 124), (106, 124), (106, 125)], log)
    bump(g, 'DOWN')
    log('at the locked door: busy', busy(g), 'fighting', fighting(g))
    read(g)
    if g.room == 0:
        through_door(g, 'DOWN', 4)
    while walking_in(g):
        tick(g)
    if g.room != 4:
        fail(g, LEVEL, f'expected room 4 behind the locked door, in room {g.room}')
    log('in the last room')

    fail(g, LEVEL, 'the route is not written past the door into room 4')
    return end_of_level(g)


if __name__ == '__main__':
    main(LEVEL, play, CERTIFICATE)

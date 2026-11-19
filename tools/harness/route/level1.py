#!/usr/bin/env python3
"""Level 1, from a new game to the "End of level!" screen. See docs/playthrough.md.

    tools/harness/route/level1.py [--original] [--delay N] [--quiet]

Rooms in order: 6, 3, 7, 1 (arrows), 2 (pits), 0 (dark, shades), 4 (crater, beam, ladder).

Thing numbers on this level (indexes into the tables at FF0AEE): 2 the wizard's gold,
5 the dead fighter in room 3 holding 7 (a ring) and 6 (the fireball scroll), 13 the key the
man in room 3 gives, 8 the chest in room 3 holding 9 (a map), 10 (a bottle), 11 (spores),
12 (bait) and some gold, 15 and 16 what room 7's goblin carries (15 is the key to room 4),
17 room 1's arrow trap, 19 the amulet and 20 a scroll in room 0, 3 the straw bed and 4 the
beam of light in room 4.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

CERTIFICATE = None
LEVEL = 1
THING_FLAGS = 0x0B18                    # 42 bytes: a thing's state bits
ARROW_TRAP = 17                         # the thing that runs room 1's plates and arrows
AMULET = 19
WIZARD_STATE, ON_HIS_FEET = 0x0934, 0x22


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

    # Room 1. Fifteen floor plates: a long row bent like a '>' just left of the door in,
    # and a short row further left. The wizard at (x, y) sets plate (px, py) off when x is
    # px-10 to px+2 and y is py-12 to py (bit 1 of the trap's flags, thing 17), and arrows
    # then fly at random for 64 updates. This line keeps 6 or more clear of every plate:
    # up the right wall, across the top above the long row, down the gap between the rows,
    # and left below the short row. DOWN+LEFT from the top left corner then slides into the
    # door of room 2 from anywhere along that wall; LEFT from below only works from one x
    # in three.
    before = health(g)
    for point in ((238, 84), (238, 56), (230, 44), (220, 32), (212, 22), (178, 22),
                  (178, 40), (185, 48), (192, 58), (192, 70), (150, 74), (140, 62),
                  (128, 54)):
        go(g, point)
        if g.byte(THING_FLAGS + ARROW_TRAP) & 2:
            fail(g, LEVEL, f'set off an arrow plate on the way to {point}')
    through_door(g, 'DOWN+LEFT', 2)
    if health(g) != before:
        fail(g, LEVEL, f'hit by arrows: health {before} to {health(g)}')
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

    # Room 4: the crater, the beam of light and the straw bed. The amulet can be held up
    # anywhere, but the ladder only shows if the wizard is within 16 of (151, 104) on both
    # axes; the game then puts him on that spot, plays the reflection, and the ladder is
    # in the floor beside the crater. Hold it up, yes; read the runes, no (that kills).
    go(g, (130, 92), (150, 102))
    use(g, AMULET)
    read(g, 'yn', quiet=0)
    if xy(g) != (151, 104):
        fail(g, LEVEL, 'the amulet showed no ladder')
    g.until(lambda g: g.byte(WIZARD_STATE) == ON_HIS_FEET and not busy(g), limit=900)
    log('the ladder is showing')

    # The ladder's hole is about x 90 to 111, y 56 to 76. DOWN onto it from above with x
    # 100 to 108 climbs down and ends the level; most other ways onto it are a fall.
    go(g, (140, 90), (122, 76), (118, 56), (104, 44))
    for _ in range(200):
        if busy(g):
            break
        if dead(g):
            fail(g, LEVEL, 'fell into the ladder hole')
        tick(g, 'DOWN')
    else:
        fail(g, LEVEL, 'the ladder did not take the wizard down')
    return end_of_level(g)


if __name__ == '__main__':
    main(LEVEL, play, CERTIFICATE)

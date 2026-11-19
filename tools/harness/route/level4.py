#!/usr/bin/env python3
"""Level 4, from its certificate to the "End of level!" screen. See docs/playthrough.md.

    tools/harness/route/level4.py [--original] [--delay N] [--quiet]

Not finished: see the fail() at the end of play().

Thing numbers on this level (indexes into the tables at FF0AEE): 0 to 4 what the certificate
gives the wizard, 5 the man in the first room (room 6), who holds 6, the flying carpet.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

CERTIFICATE = 'b5fff31001eb0'
LEVEL = 4

MAN, CARPET = 5, 6
TROLL = 1                               # the creature beside the wizard as the level starts
CREATURE_HEALTH = 0x090C                # 20 bytes, the wizard first; health in the high bits
CREATURE_POSE = 0x0920                  # 20 bytes; the low seven bits are the pose


def first_troll(g, log):
    """The level opens with a troll swinging at the wizard where they stand. There is no
    fight screen and FF10AE stays 0; the wizard can't walk until the man across the room has
    killed the troll. A blow that is coming is turned, and the troll hit, by holding LEFT
    or RIGHT: which one depends on the side the troll has wound up on, read from its pose."""
    before = health(g)
    while g.byte(CREATURE_HEALTH + TROLL) >> 4:
        pose = g.byte(CREATURE_POSE + TROLL) & 0x7F
        g.step(1, 'LEFT' if pose == 0x13 else 'RIGHT' if pose in (0x0D, 0x0E) else '')
    log(f'the troll is dead; it cost {before - health(g)} health')
    for _ in range(40):                 # he stays rooted for a few updates more
        was = xy(g)
        tick(g, 'LEFT')
        if xy(g) != was:
            return
    fail(g, LEVEL, 'the wizard cannot walk after the troll died')


def get_carpet(g, log):
    """The man gives the carpet when walked into."""
    go(g, (68, 120))
    walk_to(g, 62, 112)
    wait_busy(g)
    read(g)
    if not has(g, CARPET):
        fail(g, LEVEL, 'the man gave no carpet')
    log('have the carpet, carrying', carried(g))


def first_flame_room(g, log):
    """Out by the door at the top right of room 6 into room 4, the first of two rooms where
    the floor is death: 16 steps on foot (the count at FF1043, see worm_steps) bring a worm.
    So the carpet from the doorway, and off it only at the wooden door on the far side.

    The way across is the lane along y 83. The flamethrowers' nozzles burn anything within
    their 12 by 12 squares, flying or not; the lane runs between two rows of them, 8 high."""
    go(g, (90, 110), (158, 32), (161, 8))
    through_door(g, 'UP', 4)
    mount(g, CARPET)
    log('on the carpet, life', fly_time(g))
    fly(g, (184, 150), (184, 83), (66, 83), (64, 78))
    mount(g, CARPET, on=False)
    through_door(g, 'LEFT', 0)
    log(f'through the first flame room; carpet life {fly_time(g)}, steps left {worm_steps(g)}')


STAGES = [first_troll, get_carpet, first_flame_room]


def play(g, log=print, stages=None):
    """stages, for exploring only, stops after that many of STAGES."""
    if g.level != 3 or g.room != 6:
        fail(g, LEVEL, f'expected the first room of level 4, found level {g.level} room {g.room}')
    for stage in STAGES[:stages]:
        stage(g, log)
    if stages is not None:
        return None
    fail(g, LEVEL, 'the route is not written past the first flame room')
    return end_of_level(g)


if __name__ == '__main__':
    main(LEVEL, play, CERTIFICATE)

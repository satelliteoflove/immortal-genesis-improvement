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

MAN, CARPET, BED = 5, 6, 7
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


def second_flame_room(g, log):
    """Room 0 is the same again, with the door out (to room 1) in the far wall at the top
    right. The lane here is y 147, then up through the gap between two nozzles at x 142."""
    mount(g, CARPET)
    fly(g, (76, 176), (76, 147), (142, 147), (142, 108), (166, 80), (196, 78))
    mount(g, CARPET, on=False)
    through_door(g, 'RIGHT', 1)
    log(f'through the second flame room; carpet life {fly_time(g)}')


def bed_and_ladder(g, log):
    """Room 1 has the straw bed (thing 7) and a ladder down to room 5. The hole is at x 57 to
    78, y 60 to 80: walking DOWN onto it with x 66 to 70 is the ladder, with x 62 or less a
    drop that kills, and from the left is the drop too."""
    walk_to(g, *thing_xy(g, BED), near=1)
    log(f'slept on the straw, {rest(g)} health better')
    go(g, (68, 50))
    ladder(g, 'DOWN', 5)
    log('down the first ladder')


def two_trolls(g, log):
    """Room 5: two trolls (creatures 2 and 3, 8 health each) wait at the foot of the ladder
    and come one after the other. They swing faster than the wizard slashes, so each is
    fought by dodging and then striking (fight's counter=True)."""
    for _ in range(2):
        try:
            g.until(fighting, limit=1500)
        except TimeoutError:
            fail(g, LEVEL, 'a troll did not come to fight')
        log('beat a troll, health', fight(g, counter=True))
    if creature_health(g, 2) or creature_health(g, 3):
        fail(g, LEVEL, 'a troll is still alive')
    read(g)
    # The hole at x 36 to 52, y 80 to 100: DOWN onto it with x 45 to 49 is the ladder.
    go(g, (47, 70))
    ladder(g, 'DOWN', 2)
    log('down the second ladder')


def past_the_girl(g, log):
    """Room 2: a girl (thing 18) stands in the top corner and asks after a ring when walked
    up to. The route doesn't go for the ring and leaves her be. The hole at x 24 to 45, y 40
    to 60 is the ladder when walked LEFT onto with y 46 to 50; lower down it is a drop."""
    go(g, (56, 48))
    ladder(g, 'LEFT', 3)
    log('down the third ladder')


TURNS = 0x0612                          # quarter turns made round the triangle, 0 to 11
SIGN = 8                                # the thing at the middle of the triangle's circle


def triangle(g, log):
    """Room 3: a triangle in a circle on the floor, its middle at thing 8. Three times round
    it clockwise opens a trapdoor. The game counts quarter turns at FF0612 (a walk through
    the points above, right of, below and left of the middle adds 1 at each) and at the
    twelfth the count goes back to 0 and the hole is there.

    The ladder back up is just right of where the wizard lands, so the first steps go left
    of it. The hole opens at x 24 to 42, y 36 to 56; LEFT onto it with y 42 to 46 is the
    ladder, and that ends the level."""
    cx, cy = thing_xy(g, SIGN)
    go(g, (62, 24))
    round_it = [(cx, cy - 24), (cx + 20, cy), (cx, cy + 24), (cx - 20, cy)]
    turns = None
    for step in range(20):
        go(g, round_it[step % 4])
        was, turns = turns, g.byte(TURNS)
        if was and turns < was:
            break
    else:
        fail(g, LEVEL, f'the trapdoor did not open; the count of turns is {turns}')
    log(f'the trapdoor is open after {step} quarter turns')
    go(g, (54, 44))
    bump(g, 'LEFT', limit=1200)


STAGES = [first_troll, get_carpet, first_flame_room, second_flame_room, bed_and_ladder,
          two_trolls, past_the_girl, triangle]


def play(g, log=print, stages=None):
    """stages, for exploring only, stops after that many of STAGES."""
    if g.level != 3 or g.room != 6:
        fail(g, LEVEL, f'expected the first room of level 4, found level {g.level} room {g.room}')
    for stage in STAGES[:stages]:
        stage(g, log)
    if stages is not None:
        return None
    return end_of_level(g)


if __name__ == '__main__':
    main(LEVEL, play, CERTIFICATE)

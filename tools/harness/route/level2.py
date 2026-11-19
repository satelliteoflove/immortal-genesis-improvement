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


CHARMED = 0x0BB6                        # 1 once the charm scroll has been read


def merchant(g, log):
    """Room 1, the big room. Take the stone from its far left corner, read the charm (the
    wisps follow the wizard about after that and leave him alone), and buy the slime oil
    from the merchant on the ledge to the right. He asks 80 gold first, which is refused;
    walked into again he asks 60, which is taken."""
    go(g, (160, 175), (100, 175), (40, 165))
    walk_to(g, 25, 140, near=1)
    search(g, 'y', STONE)
    log('took the stone')
    use(g, CHARM)
    read(g)
    if g.byte(CHARMED) != 1:
        fail(g, LEVEL, 'the charm was read but the wisps are not charmed')
    log('read the charm')
    go(g, (60, 170), (150, 170))
    walk_to(g, 150, 140)
    wait_busy(g)
    read(g, 'n')
    go(g, (150, 158))
    walk_to(g, 150, 140)
    wait_busy(g)
    read(g, 'y')
    if not has(g, OIL):
        fail(g, LEVEL, 'the merchant did not sell the oil')
    log('bought the oil')


def to_the_goblins(g, log):
    """Room 1 to room 0 by the metal door in the upper floor's top right wall."""
    go(g, (100, 165), (60, 150), (60, 110), (110, 50), (116, 44))
    through_door(g, 'RIGHT', 0)
    log("in the goblins' room")


GOBLINS = (5, 6)


def goblins(g, log):
    """Room 0. Two goblins guard the door to the king's room, the one nearer that door
    carrying the dust. Each has 10 health and fight(counter=True) beats them without a
    blow taken (the plain fight lost to the second). The first is searched as he falls;
    the second has nothing, and a box comes and goes. Then the door at the top right."""
    for n in GOBLINS:
        health_left = attack(g, n, counter=True)
        log(f'beat goblin {n}, health {health_left}')
        if n == GOBLINS[0]:
            search(g, 'yy', DUST)
            log('took the dust')
        else:
            read(g)
    go(g, (186, 136))
    through_door(g, 'RIGHT', 5)
    log("in the king's room")


GUARDS = (13, 12)


def king(g, log):
    """Room 5. Two goblin guards with 15 health each stand still until walked up to;
    fight(patient=True) beats both without a blow taken (counter=True lost 2). A box with
    no question follows each. Then the spores go down on the patch of dirt left of the
    door, which the inventory does with no box (they become a thing on the floor). Their
    cloud kills a wizard who stays about 29 updates, so out by the door at once, a few
    updates in room 0, and back: the king is lying down then, and walking up to him he
    asks for water; yes, and he gives the key."""
    go(g, (66, 86))
    for n in GUARDS:
        health_left = attack(g, n, patient=True)
        log(f'beat guard {n}, health {health_left}')
        read(g)
    go(g, (44, 52))
    use(g, SPORES)
    g.until(lambda g: not busy(g) and not has(g, SPORES), limit=300)
    log('planted the spores')
    go(g, (66, 86), (66, 104))
    through_door(g, 'LEFT', 0)
    ticks(g, 10)
    through_door(g, 'RIGHT', 5)
    go(g, (66, 86), (72, 40))
    if walk_to(g, 76, 18) != 'busy':
        fail(g, LEVEL, 'the king did not speak')
    wait_busy(g)
    read(g, 'y')
    if not has(g, KEY) or has(g, WATER):
        fail(g, LEVEL, f'the king did not take the water and give the key: {carried(g)}')
    log('gave the king water and took the key')


OIL_LEFT = 0x0A1C                       # the oil's budget; see oil_left()


def oil_left(g):
    """What is left of the slime oil: 80 when it is rubbed on, 1 less for each update a
    slime touches the wizard. FF before."""
    return g.byte(OIL_LEFT)


def back_to_the_first_room(g, log):
    """Rooms 5, 0 and 1 back to room 4, rubbing the oil on the wizard's boots by the door."""
    go(g, (72, 40), (66, 86), (66, 104))
    through_door(g, 'LEFT', 0)
    go(g, (170, 180), (160, 200))
    through_door(g, 'LEFT', 1)
    go(g, (110, 50), (60, 110), (60, 150), (100, 165), (160, 175))
    use(g, OIL)
    read(g)
    g.until(lambda g: not busy(g) and oil_left(g) == 80, limit=300)
    log('oiled the boots')
    go(g, (166, 218))
    through_door(g, 'DOWN', 4)
    log('back in the first room')


GEM_KIND = 0x39


def gems_and_sword(g, log):
    """Room 4 again, oiled: the slimes still come and sit on the wizard, but each update
    they do only takes 1 off the oil. The stone is dropped from the inventory (no
    question) a little in from the door, and the first slime to cross it turns it into a
    gem, there on the floor: its kind goes from 3A to 39, about 35 updates later. Then the
    gem that was always here, the one the stone became, and the bones (search them? the
    sword, take it? search further? no: further down is a slime). The sword isn't
    carried; FF0A1A goes to 1. Out by the bottom door to room 3."""
    go(g, (80, 50))
    use(g, STONE)
    g.until(lambda g: not busy(g) and place(g, STONE) == 0x84, limit=300)
    for _ in range(200):
        if g.byte(THING_KIND + STONE) == GEM_KIND:
            break
        if not tick(g):
            fail(g, LEVEL, 'the game stopped while waiting for a slime to take the stone')
    else:
        fail(g, LEVEL, 'no slime turned the stone into a gem')
    log(f'a slime turned the stone into a gem; oil left {oil_left(g)}')
    walk_to(g, *thing_xy(g, GEM), near=1)
    search(g, 'y', GEM)
    walk_to(g, *thing_xy(g, STONE), near=1)
    search(g, 'y', STONE)
    log(f'took both gems; oil left {oil_left(g)}')
    try:
        walk_to(g, *thing_xy(g, BONES), near=1)
    except Stuck:
        pass                            # the bones are solid; the box comes all the same
    search(g, 'yyn')
    if g.byte(SWORD) != 1:
        fail(g, LEVEL, 'the bones did not give the sword')
    log(f'took the sword; oil left {oil_left(g)}')
    go(g, (66, 110), (68, 126))
    through_door(g, 'DOWN', 3)
    log(f'in the dwarf\'s passage; oil left {oil_left(g)}')


def dwarf(g, log):
    """Room 3, the long passage. The dwarf is in its top left corner. The dust is used a
    little way short of him (do that here? yes), and walking up to him then he talks and
    gives his gem, with no question. The door to room 6 is in the right hand wall of the
    passage's lower end; walking at (175, 200) goes through it."""
    go(g, (70, 110), (48, 92))
    use(g, DUST)
    read(g, 'y')
    if has(g, DUST):
        fail(g, LEVEL, 'the dust was not thrown')
    if walk_to(g, 44, 80) == 'busy':
        read(g)
    if not has(g, DWARF_GEM):
        wait_busy(g)
        read(g)
    if not has(g, DWARF_GEM):
        fail(g, LEVEL, 'the dwarf did not give his gem')
    log('the dwarf gave his gem')
    go(g, (80, 140), (120, 200))
    if walk_to(g, 175, 200) != 'room' or g.room != 6:
        fail(g, LEVEL, 'did not come to room 6')
    tick(g)
    for _ in range(12):                 # he walks in by himself, as in through_door
        if not walking_in(g):
            break
        tick(g)
    log(f"in the slimes' passage; oil left {oil_left(g)}")


STEPS = [first_room, merchant, to_the_goblins, goblins, king, back_to_the_first_room,
         gems_and_sword, dwarf]


def play(g, log=print):
    if g.level != 1 or g.room != 4:
        fail(g, LEVEL, f'expected the first room of level 2, found level {g.level} room {g.room}')
    for step in STEPS:
        step(g, log)
    fail(g, LEVEL, 'the route is not written past here')
    return end_of_level(g)


if __name__ == '__main__':
    main(LEVEL, play, CERTIFICATE)

#!/usr/bin/env python3
"""Level 2, from its certificate to the "End of level!" screen. See docs/playthrough.md.

    tools/harness/route/level2.py [--original] [--delay N] [--quiet]

The route: room 4's gem and the sword, past its slimes; in room 1 the charm, the stone and
the oil; room 0's goblins and the dust; room 5's guards, the spores and the king's key;
back through room 1 to room 2's troll; room 3's dwarf and his gem; room 6 with the oil on,
where a slime turns the stone into a gem, and its locked door; room 7's holes and the
ladder. Room 4 is not gone back to: its slimes would use up the oil that room 6 needs.

The rooms: 4 is the first (two slimes, a gem, a pile of bones), with doors to 1 (top left)
and 3 (bottom). 1 is the big room of the will-o'-the-wisps, the merchant and the stone, with
two doors to 0 (two goblins) at its top, one to 2 (a troll) at its bottom left and one to 4
at its bottom. 0 leads to 5 (the goblin king and two guards). 3 is the dwarf's passage, with
doors to 4, 2 and 6 (two slimes), and 6 leads on to 7, the last room, through a locked door.

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
from common import _toward

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
    lying in the room is taken, then the sword from the bones (search them? the sword,
    take it? search further? no: further down is a slime), and it is out by the door in the
    top left wall, which opens to UP. The sword isn't carried; FF0A1A goes to 1.

    The slimes' moves are fixed by the game's state, with no chance in them while the
    random numbers agree, so the route first waits for slime 10 to begin its first rest.
    From that update on the room plays the same on both ROMs whatever the delay was. Then
    the walk below was found by trying waits from a state kept there: 5 to 9 updates got
    through (and a dozen others between 1 and 36), so the route waits 7."""
    for _ in range(100):
        if slime_resting(g, 10):
            break
        tick(g)
    else:
        fail(g, LEVEL, 'slime 10 never rested')
    ticks(g, 7)
    go(g, (100, 40))
    if walk_to(g, *thing_xy(g, GEM), near=1) != 'busy':
        wait_busy(g, limit=60)
    search(g, 'y', GEM)
    log('took the gem')
    go(g, (100, 60), (70, 92))
    try:
        walk_to(g, *thing_xy(g, BONES), near=1)
    except Stuck:
        pass                            # the bones are solid; the box comes all the same
    search(g, 'yyn')
    if g.byte(SWORD) != 1:
        fail(g, LEVEL, 'the bones did not give the sword')
    log('took the sword')
    go(g, (52, 70), (61, 54))
    through_door(g, 'UP', 1)
    log('out of the first room')


CHARMED = 0x0BB6                        # 1 once the charm scroll has been read


def merchant(g, log):
    """Room 1, the big room. Read the charm at once (the wisps follow the wizard about
    after that and leave him alone; before it they hit him), take the stone from the far
    left corner, and buy the slime oil from the merchant on the ledge to the right. He
    asks 80 gold first, which is refused; walked into again he asks 60, which is taken."""
    use(g, CHARM)
    read(g)
    if g.byte(CHARMED) != 1:
        fail(g, LEVEL, 'the charm was read but the wisps are not charmed')
    log('read the charm')
    go(g, (160, 175), (100, 175), (40, 165))
    walk_to(g, 25, 140, near=1)
    search(g, 'y', STONE)
    log('took the stone')
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


def back_to_room_1(g, log):
    """Rooms 5 and 0 back to room 1, by the doors they were come in by."""
    go(g, (72, 40), (66, 86), (66, 104))
    through_door(g, 'LEFT', 0)
    go(g, (170, 180), (160, 200))
    through_door(g, 'LEFT', 1)
    log('back in room 1')


GEM_KIND = 0x39


def troll(g, log):
    """Rooms 1 and 2 to room 3, which keeps away from room 4's slimes. Room 1's door to
    room 2 is in the bottom left wall of its lower floor. Room 2 is a long corridor with a
    troll (5 health) part way down; fight(patient=True) beat him without a blow taken. Its
    door to room 3 is in the right hand wall at the far end."""
    go(g, (110, 50), (60, 110), (60, 150), (40, 175))
    through_door(g, 'DOWN', 2)
    go(g, (24, 40))
    health_left = attack(g, TROLL, patient=True)
    log(f'beat the troll, health {health_left}')
    read(g)
    # the fight can end anywhere down the corridor, as far as its bend
    if xy(g)[1] < 130:
        go(g, (20, 130))
    if xy(g)[1] < 185:
        go(g, (30, 180))
    go(g, (60, 200))
    through_door(g, 'RIGHT', 3)
    log("in the dwarf's passage")


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
    use(g, OIL)
    read(g)
    g.until(lambda g: not busy(g) and oil_left(g) == 80, limit=300)
    log('oiled the boots')
    if walk_to(g, 175, 200) != 'room' or g.room != 6:
        fail(g, LEVEL, 'did not come to room 6')
    tick(g)
    for _ in range(12):                 # he walks in by himself, as in through_door
        if not walking_in(g):
            break
        tick(g)
    log(f"in the slimes' passage; oil left {oil_left(g)}")


def locked_door(g, log):
    """Room 6, a long passage with two slimes, oiled, to the locked door at its far right
    end. The door is walked into from the left (RIGHT); the king's key opens it and the
    wizard walks through by himself.

    First the stone, for a slime to turn into a gem (see stone_for_a_slime). Then the walk
    to the door, which a slime can block for a while (walk_to raises Stuck); it is tried
    again after a few updates. With the oil on, each update a slime spends touching the
    wizard (posting action 2 to him) takes 1 off the oil and nothing else."""
    go(g, (44, 52))
    for attempt in range(5):
        if stone_for_a_slime(g, fetch=attempt > 0):
            break
        log(f'no slime came to the stone; oil left {oil_left(g)}')
    else:
        fail(g, LEVEL, 'no slime turned the stone into a gem')
    log(f'a slime turned the stone into a gem; oil left {oil_left(g)}')
    take_from_the_floor(g, STONE)
    log(f'took it; oil left {oil_left(g)}')
    for x, y in ((60, 64), (120, 86), (190, 86), (196, 76)):
        for _ in range(10):
            try:
                result = walk_to(g, x, y)
                break
            except Stuck:
                ticks(g, 4)             # a slime in the way; it moves on
        else:
            fail(g, LEVEL, f'could not get to ({x}, {y}) past the slimes')
        if result != 'there':
            fail(g, LEVEL, f'walking to ({x}, {y}) in room 6 ended {result}')
    log(f'at the locked door; oil left {oil_left(g)}')
    bump(g, 'RIGHT')
    read(g, quiet=0)
    g.until(lambda g: g.room == 7, limit=600)
    tick(g)
    for _ in range(30):
        if not walking_in(g):
            break
        tick(g)
    if has(g, KEY):
        fail(g, LEVEL, 'the key was not used')
    log('through the locked door')


SLIMES_6 = (8, 9)


def nearest_slime(g):
    """The x and y of the nearest live slime in the wizard's room, or None."""
    here = [creature_xy(g, n) for n in SLIMES_6
            if g.byte(HEALTH + n) & 15 == g.room and creature_health(g, n)]
    if not here:
        return None
    wx, wy = xy(g)
    return min(here, key=lambda c: max(abs(c[0] - wx), abs(c[1] - wy)))


def take_from_the_floor(g, thing):
    """Pick up a thing lying on the floor: it asks only when walked onto, not while the
    wizard stands on it, so step off it first if need be."""
    tx, ty = thing_xy(g, thing)
    wx, wy = xy(g)
    if abs(tx - wx) <= 6 and abs(ty - wy) <= 6:
        go(g, (tx + 8, ty + 8))
    if walk_to(g, tx, ty, near=1) != 'busy':
        wait_busy(g, limit=60)
    search(g, 'y', thing)


def stone_for_a_slime(g, fetch=False, wait=150):
    """Drop the stone at the wizard's feet and wait up to `wait` updates for a slime to
    cross it, which turns it into a gem (kind 3A to 39). True if it did.

    The slimes mostly come for the wizard, but on one timing in thirty neither came near
    in 400 updates. With fetch, the stone is picked up again first and carried toward the
    nearest slime, and dropped when it is within 16; it comes on over the stone to him."""
    if fetch:
        take_from_the_floor(g, STONE)
        for _ in range(100):
            slime = nearest_slime(g)
            if slime is None:
                fail(g, LEVEL, 'no slime left in the room')
            wx, wy = xy(g)
            if max(abs(slime[0] - wx), abs(slime[1] - wy)) <= 16:
                break
            # not left of x 46: the door back to room 3 is there
            if not tick(g, _toward(max(slime[0], 46) - wx, slime[1] - wy, 2)):
                fail(g, LEVEL, 'the game stopped while carrying the stone to a slime')
    use(g, STONE)
    g.until(lambda g: not busy(g) and place(g, STONE) == 0x80 + g.room, limit=300)
    for _ in range(wait):
        if g.byte(THING_KIND + STONE) == GEM_KIND:
            return True
        if not tick(g):
            fail(g, LEVEL, 'the game stopped while waiting for a slime to take the stone')
    return g.byte(THING_KIND + STONE) == GEM_KIND


# Room 7's three symbols have four holes each, a corner at the top, the left and the right
# and one in the middle. A table of their x and y is at 001EAD in the ROM, twelve pairs,
# and its first three are the ones that open the floor: the first symbol's right hole, the
# second's top one and the third's middle. A gem dropped within about 6 of a hole goes in.
HOLES = [(91, 17), (109, 36), (144, 79)]


def holes(g, log):
    """Room 7. A gem is put in a hole by standing beside it and using the gem from the
    inventory, which drops it with no question; within about 6 it settles in the hole. When
    the third is in, a ladder hole opens in the floor left of the middle symbol, at (92,
    64). It is safe from the right and from above, and kills from below. Climbing down it
    ends the level."""
    for gem, (x, y) in zip((GEM, STONE, DWARF_GEM), HOLES):
        go(g, (x, y + 3))
        use(g, gem)
        g.until(lambda g: not busy(g) and not has(g, gem), limit=600)
        if thing_xy(g, gem) != (x, y):
            fail(g, LEVEL, f'gem {gem} lay at {thing_xy(g, gem)}, not in the hole at {(x, y)}')
    log('put the three gems in the holes')
    ticks(g, 4)
    go(g, (110, 63))
    for _ in range(300):
        if g.byte(0x0934) == CLIMBING or busy(g):
            break
        if dead(g):
            fail(g, LEVEL, 'fell down the ladder hole')
        g.step(1, 'LEFT')
    else:
        fail(g, LEVEL, 'no ladder opened at (92, 64)')
    log('climbing down')


CLIMBING = 0x2B                         # the wizard's state at FF0934 on a ladder


STEPS = [first_room, merchant, to_the_goblins, goblins, king, back_to_room_1, troll,
         dwarf, locked_door, holes]


def play(g, log=print):
    if g.level != 1 or g.room != 4:
        fail(g, LEVEL, f'expected the first room of level 2, found level {g.level} room {g.room}')
    for step in STEPS:
        step(g, log)
    return end_of_level(g)


if __name__ == '__main__':
    main(LEVEL, play, CERTIFICATE)

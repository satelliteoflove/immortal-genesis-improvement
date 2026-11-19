#!/usr/bin/env python3
"""Level 5, from its certificate to the "End of level!" screen. See docs/playthrough.md.

    tools/harness/route/level5.py [--original] [--delay N] [--quiet]

Not finished: see the fail() at the end of play().

Thing numbers on this level (indexes into the tables at FF0AEE): 0 the wizard's gold, 1 a
ring, 2 the bait, 3 an amulet, 4 the egg on the floor of room 8, 12 the merchant in room 1,
who sells 13 (the shrinking potion), 7 the chest in room 2 holding 11 (a bottle of water),
10 (the fireball book), 9 (a note) and 8 (the worm sensor), plus gold.
Creatures 2 and 3 are the trolls in room 2.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

CERTIFICATE = 'd630f43000eb0'
LEVEL = 5

BAIT, EGG, POTION, CHEST, SENSOR, NOTE, FIREBALLS, WATER = 2, 4, 13, 7, 8, 9, 10, 11
TROLLS = 2, 3
LIZARDS = 4, 5
KEY = 14


def play(g, log=print, until=None):
    """until names a place to stop early, for exploring: 'egg', 'room0', 'bought', 'hole',
    'room2', 'trolls', 'chest', 'lizards'."""
    if g.level != 4 or g.room != 8:
        fail(g, LEVEL, f'expected the first room of level 5, found level {g.level} room {g.room}')

    # Room 8. A goblin speaks as the level begins. The egg lies on the floor to the left;
    # walking onto its spot brings the question.
    read(g)
    walk_to(g, 32, 48, near=1)
    search(g, 'y', EGG)
    log('took the egg, carrying', carried(g))
    if until == 'egg':
        return

    # The way out is in the bottom right wall: RIGHT from the bottom corner slides into it.
    go(g, (60, 100), (62, 120))
    through_door(g, 'RIGHT', 0)
    if until == 'room0':
        return

    # Room 0. The goblins in the middle speak when the wizard comes near, and don't fight.
    if walk_to(g, 100, 72) != 'busy':
        fail(g, LEVEL, 'the goblins did not speak')
    wait_busy(g)
    read(g)
    log('heard the goblins out')

    # Round them to the door at the bottom, which opens to DOWN.
    go(g, (89, 90), (118, 110), (120, 118))
    through_door(g, 'DOWN', 1)

    # Room 1. The merchant (thing 12) asks his price when walked up to; yes buys the potion.
    go(g, (99, 40), (80, 44))
    if walk_to(g, 46, 40) != 'busy':
        fail(g, LEVEL, 'the merchant did not speak')
    wait_busy(g)
    read(g, 'y')
    if not has(g, POTION):
        fail(g, LEVEL, f'the merchant sold no potion; carrying {carried(g)}')
    log('bought the potion, carrying', carried(g))
    go(g, (80, 44), (99, 40), (99, 12))
    through_door(g, 'LEFT', 0)
    if until == 'bought':
        return

    # Room 0 again. The hole is in the top left wall, above the floor at about (119, 13),
    # and only a shrunken wizard holding UP as he slides up the wall past it goes in. Stand
    # below it, drink, and hold UP.
    go(g, (89, 90), (89, 44), (112, 40), (112, 26))
    if until == 'hole':
        return
    use(g, POTION)
    read(g, 'y', quiet=0)
    g.until(shrunk, limit=600)
    log('shrunk, with', shrink_left(g), 'updates of it left')
    through_door(g, 'UP', 2)
    if until == 'room2':
        return

    # Room 2. Two trolls walk over and stand by the wizard while he is small, and tread on
    # him if he moves. So he stands still. They fight him one after the other once he has
    # grown, and from then the potion takes a point of health every 16 updates of walking.
    g.until(lambda g: not shrunk(g), limit=4000)
    g.until(fighting, limit=900)
    log('the first troll: won with health', fight(g, counter=True))
    read(g, quiet=0)
    # The other troll wanders off for a while before it comes back, and the potion is
    # costing health all that time, so go to it.
    alive = [troll for troll in TROLLS if creature_health(g, troll)]
    if len(alive) != 1:
        fail(g, LEVEL, f'expected one troll left, found {alive}')
    if meet(g, alive[0]) != 'fight':
        fail(g, LEVEL, 'the second troll spoke')
    log('the second troll: won with health', fight(g, counter=True))
    read(g, quiet=0)
    if until == 'trolls':
        return

    # The chest (thing 7) is unlocked. The water cures the potion's harm.
    go(g, (111, 60))
    walk_to(g, 111, 47)
    search(g, 'yyyyy', WATER, FIREBALLS, NOTE, SENSOR)
    use(g, WATER)
    read(g, 'y')
    g.until(lambda g: not has(g, WATER), limit=600)
    if poisoned(g):
        fail(g, LEVEL, 'the water did not cure the potion')
    log('emptied the chest and drank the water, carrying', carried(g))
    if until == 'chest':
        return

    # The door is in the top left wall near the left corner, and opens to UP.
    go(g, (60, 90), (24, 92))
    through_door(g, 'UP', 4)

    # Room 4. Two flying lizards (creatures 4 and 5); one of them carries the key (thing 14)
    # to the door at the bottom left. The fireball book runs down by the clock from the
    # moment it is armed, about 1,000 updates, so it is armed here and not at the chest.
    use(g, FIREBALLS)
    read(g)
    if armed(g) != FIREBALLS:
        fail(g, LEVEL, 'the fireballs are not armed')
    carrier = place(g, KEY) - CARRIED
    if carrier not in LIZARDS:
        fail(g, LEVEL, f'the key is not with a lizard: its place is {place(g, KEY):02x}')
    # Out of the doorway first: DOWN from where he comes in leads back to room 2.
    go(g, (205, 40))
    shots_fired = hunt(g, LIZARDS, log=log, inside=lambda x, y: x < 214 and y > 20)
    log('both lizards dead after', shots_fired, 'shots')
    # A lizard that dies close by is searched at once; otherwise walk to where it fell.
    for _ in range(20):
        if busy(g):
            break
        tick(g)
    if not busy(g):
        where = creature_xy(g, carrier)
        if walk_to(g, *where) != 'busy':
            fail(g, LEVEL, f'no question at the dead lizard at {where}')
    search(g, 'yy', KEY)
    log('took the key, carrying', carried(g))
    if until == 'lizards':
        return

    fail(g, LEVEL, 'the route is not written past the chest in room 2')
    return end_of_level(g)


if __name__ == '__main__':
    main(LEVEL, play, CERTIFICATE)

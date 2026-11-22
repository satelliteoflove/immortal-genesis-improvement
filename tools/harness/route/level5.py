#!/usr/bin/env python3
"""Level 5, from its certificate to the "End of level!" screen. See docs/playthrough.md.

    tools/harness/route/level5.py [--original] [--delay N] [--quiet]

Thing numbers on this level (indexes into the tables at FF0AEE): 0 the wizard's gold, 1 a
ring, 2 the bait, 3 an amulet, 4 the egg on the floor of room 8, 12 the merchant in room 1,
who sells 13 (the shrinking potion), 7 the chest in room 2 holding 11 (a bottle of water),
10 (the fireball book), 9 (a note) and 8 (the worm sensor), plus gold.
Creatures 2 and 3 are the trolls in room 2, 4 and 5 the lizards in room 4, 6 the
hatchling and 7 the slime in room 7. Thing 16 is room 7's floor design and 17 room 10's
straw bed.
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
SLIME, HATCHLING = 7, 6
DESIGN, BED = 16, 17
ON_DESIGN = 0x0A15          # 1 while the wizard stands on the middle of the floor design
DESIGN_WEIGHT = 0x0B97      # how many things weigh on its middle: wizard, hatchling


def play(g, log=print, until=None):
    """until names a place to stop early, for exploring: 'egg', 'room0', 'bought', 'hole',
    'room2', 'trolls', 'chest', 'lizards', 'room5', 'room7'."""
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
        # Come at it from the open floor below: along the back wall, a corner of the wall
        # stops him short of a lizard that fell there, at (181, 29) in one 50 Hz run.
        where = creature_xy(g, carrier)
        if walk_to(g, where[0], max(where[1], 40)) != 'busy' and walk_to(g, *where) != 'busy':
            fail(g, LEVEL, f'no question at the dead lizard at {where}')
    search(g, 'yy', KEY)
    log('took the key, carrying', carried(g))
    if until == 'lizards':
        return

    # The door at the bottom left is locked. Walking into it with the key brings a box, and
    # after it the wizard goes through by himself.
    go(g, (160, 78), (110, 84), (96, 100))
    if walk_to(g, 80, 100) != 'busy':
        fail(g, LEVEL, 'the locked door said nothing')
    wait_busy(g)
    read(g, quiet=0)
    g.until(lambda g: g.room == 5, limit=300)
    for _ in range(12):
        if not walking_in(g):
            break
        tick(g)
    log('through the locked door')
    if until == 'room5':
        return

    # Room 5, the worm room (brown here, not red). The floor is an unseen maze: its walls
    # are lines about 3 wide that kill at a touch (the wizard sinks where he stands), and
    # the corridors between them are 20 or more wide. The sensor only tells how near a
    # line is and isn't needed. Down the middle of each corridor: left along the top wall
    # (keeping above the ladder's hole), down the left side, right, down, left, down,
    # right, up, right, and down into the door.
    go(g, (24, 32), (24, 70), (81, 72), (81, 146), (57, 146), (57, 186), (105, 186),
       (105, 138), (137, 146))
    # Room 7's slime moves by the game's random numbers from the moment the room is
    # entered, and shoot_down() loses to it in about one game in eight. The route's
    # arrival here is the same game whatever the delay, so the room is pinned to it and
    # the wait before the door chooses the game: with 18 to 25 updates the slime died on
    # both ROMs (the patched lost at 17 and 26, the original at 14, 15 and 26).
    ticks(g, 22)
    through_door(g, 'DOWN', 7)
    log('across the worm room')
    if until == 'room7':
        return

    # Room 7. A slime (creature 7) comes after the wizard as fast as he walks and kills at
    # a touch. Kill it in the top part of the room, above the line at y 60 where the egg
    # hatches, so that no ball can hit the hatchling.
    shots_fired = shoot_down(g, SLIME, inside=top_of_room7)
    log('the slime dead after', shots_fired, 'shots')

    # The egg hatches (a box) as the wizard steps over the line, and the hatchling
    # (creature 6) follows him if it is near.
    go(g, (67, 50))
    bump(g, 'DOWN')
    read(g)
    if not creature_health(g, HATCHLING):
        fail(g, LEVEL, 'the egg did not hatch')
    go(g, (67, 100), (80, 128), (95, 150))
    fetch_hatchling(g, log)

    # The floor design (thing 16) holds the way down open while something weighs on its
    # middle. Drop the bait there; the hatchling settles on it.
    walk_to(g, *thing_xy(g, DESIGN), near=1, stop=lambda g: g.byte(ON_DESIGN))
    if not g.byte(ON_DESIGN):
        fail(g, LEVEL, 'not on the middle of the floor design')
    use(g, BAIT)
    read(g, 'y')
    go(g, (91, 178))
    try:
        g.until(lambda g: g.byte(DESIGN_WEIGHT), limit=2000)
    except TimeoutError:
        fail(g, LEVEL, f'nothing settled on the bait; the hatchling is at '
                       f'{creature_xy(g, HATCHLING)}')
    log('the hatchling is on the bait at', creature_xy(g, HATCHLING))

    # The ladder down opens at the bottom left: LEFT along y 190 runs onto it.
    go(g, (79, 190), (60, 190))
    ladder(g, 'LEFT', 10)

    # Room 10: a straw bed (thing 17) beside the foot of the ladder, and the ladder down
    # in the middle that ends the level.
    walk_to(g, *thing_xy(g, BED), near=1)
    log('slept on the straw bed, gaining', rest(g))
    go(g, (130, 60), (120, 74))
    for _ in range(100):
        if not tick(g, 'LEFT'):
            break
    return end_of_level(g)


# Room 7's top part, above the line where the egg hatches: the left edge of the floor at
# each y from 0 to 56 in fours. The right edge runs 93 + 3y/4, 123 at most. The doorway
# is at the top left.
ROOM7_LEFT = {0: 66, 4: 63, 8: 66, 12: 63, 16: 60, 20: 45, 24: 42, 28: 39, 32: 33, 36: 30,
              40: 27, 44: 21, 48: 18, 52: 15, 56: 9}


def top_of_room7(x, y, margin=6):
    """Where shoot_down() may step in room 7: in from the walls, out of the doorway, and
    above the line where the egg hatches."""
    if not 8 <= y <= 54:
        return False
    row = min(56, y // 4 * 4)
    if y < 20:
        left = 67
    else:
        left = max(ROOM7_LEFT[row], ROOM7_LEFT[min(56, row + 4)]) + margin
    return left <= x <= min(123, 93 + 0.75 * y) - margin


def fetch_hatchling(g, log):
    """Make sure the hatchling is with the wizard below room 7's narrow middle (y 96 to
    124). It flies straight at what it wants and can't get round a wall, so one left
    behind sits against the narrow part's side. Then go back up for it, wait until it is
    close, and come down again."""
    for _ in range(4):
        for _ in range(60):
            (wx, wy), (cx, cy) = xy(g), creature_xy(g, HATCHLING)
            if max(abs(cx - wx), abs(cy - wy)) <= 24 and cy > 128:
                return
            tick(g)
        log('going back for the hatchling, at', creature_xy(g, HATCHLING))
        go(g, (80, 128), (70, 104))
        for _ in range(100):
            (wx, wy), (cx, cy) = xy(g), creature_xy(g, HATCHLING)
            if max(abs(cx - wx), abs(cy - wy)) <= 24:
                break
            tick(g)
        go(g, (80, 128), (95, 150))
    fail(g, LEVEL, f'the hatchling would not follow; it is at {creature_xy(g, HATCHLING)}')


if __name__ == '__main__':
    main(LEVEL, play, CERTIFICATE)

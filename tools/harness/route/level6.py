#!/usr/bin/env python3
"""Level 6 (the spiders), from its certificate to the "End of level!" screen.
See docs/playthrough.md.

    tools/harness/route/level6.py [--original] [--delay N] [--quiet]

Thing numbers on this level (indexes into the tables at FF0AEE): 13 and 14 the two spider
holes of room 0; 3 and 4 the egg sacks of room 1; 5 the bottle of alcohol on the floor of
room 2, 6 the chest there holding 7 (the levitation spell), 16 and 17 its egg sacks; 8 to 12
the egg sacks of the corridor, room 3; 15 the straw bed of room 4.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

CERTIFICATE = '563ff53010a41'
LEVEL = 6

HOLE, FAR_HOLE = 13, 14
BOTTLE, CHEST, SPELL = 5, 6, 7

LEGS = 0x0BAE               # the thing number of the hole with legs showing, FF for neither
SPIDER = 1                  # the big spider of room 1 is creature 1
CREATURE_ACT = 0x0948       # 20 bytes, one a creature: what it is doing, in the low four bits
CREATURE_STATE = 0x0934     # 20 bytes: 33 for a wizard wrapped in web or covered in spiders
REARING = 9
SACK = 0x29                 # the kind of the corridor's egg sacks
STRETCHES = 0x1089          # stretches of the corridor still to come, 21 at its start
GROUND_TIME = 0x108A        # updates the wizard may still stand on the corridor's floor


def rearing(g):
    """True from the update the big spider rears up until its web has landed, 8 updates."""
    return g.byte(CREATURE_ACT + SPIDER) & 15 == REARING


def caught(g):
    """True when the wizard is held fast by a web or a swarm of small spiders. He dies about
    30 updates on, and his health doesn't show it until then (for the swarm, not at all)."""
    return g.byte(CREATURE_STATE) == 0x33


def spider_hole(g):
    """Room 0. A spider's legs show in one hole or the other for 16 updates at a time.
    Going into a hole is only safe while the legs are in the other one: with legs in
    neither, or in this one, the spider is inside and kills. The game looks once, as the
    wizard steps in. The near hole is entered by walking UP from just below it."""
    go(g, (32, 64), (75, 64), (81, 62))
    # legs in the far hole, and no more than 5 of their 16 updates gone
    g.until(lambda g: g.byte(LEGS) == FAR_HOLE and thing_frame(g, FAR_HOLE) <= 0x14,
            limit=3000)
    through_door(g, 'UP', 1, limit=80)


def big_spider(g, log):
    """Room 1, from where the hole lets the wizard out, to the big spider dead.

    The spider looks for the wizard once every 6 updates. If he is anywhere in front of it
    (above y 88, right of x 70 or so) it rears, and 6 updates later its web wraps him
    wherever in that part of the room he then stands. After a shot it waits 20 updates or
    more before it will rear again. So: step over the line, step back when it rears, let
    the web miss, and run in while it waits. Reaching the spider starts a fight like any
    other. The run is 8 updates, up the column x 94: with the spider alive, x 100 and
    beyond below y 90 is a swarm of small spiders, and the egg sack at (80, 47) is to the
    left."""
    go(g, (94, 92))
    for _ in range(40):                         # over the line until it rears
        if rearing(g):
            break
        tick(g, 'UP' if xy(g)[1] > 84 else '')
        if caught(g):
            fail(g, LEVEL, 'the web caught the wizard while he was drawing the shot')
    else:
        fail(g, LEVEL, 'the spider never reared')
    while xy(g)[1] < 88:                        # and back behind it
        tick(g, 'DOWN')
    for _ in range(40):
        if not rearing(g):
            break
        tick(g)
        if caught(g):
            fail(g, LEVEL, 'the web caught the wizard behind the line')
    else:
        fail(g, LEVEL, 'the spider stayed reared')
    log('the web missed; running at the spider')
    walk_to(g, 94, 66, stop=lambda g: fighting(g) or caught(g))
    if not caught(g) and meet(g, SPIDER) != 'fight':
        fail(g, LEVEL, 'the spider did not fight')
    if caught(g):
        fail(g, LEVEL, 'the web caught the wizard on his way in')
    log('big spider: won with health', fight(g))


def chest(g, log):
    """Room 2. The chest has something under its latch that kills whoever opens it. The
    bottle on the floor is alcohol: used beside the chest and not drunk, it is poured on
    the latch, and then the chest opens safely. Two egg sacks, at (45, 44) and (110, 79),
    are walked round."""
    go(g, (60, 58), (24, 56))
    walk_to(g, *thing_xy(g, BOTTLE), near=1)
    search(g, 'y', BOTTLE)
    log('have the bottle')
    go(g, (24, 56), (66, 56), (66, 36))
    if walk_to(g, 66, 20) != 'busy':            # the chest stops him and asks
        fail(g, LEVEL, 'the chest asked nothing')
    read(g, 'n')                                # not yet
    use(g, BOTTLE)
    read(g, 'ny')                               # drink it? no. pour it on the chest? yes
    if has(g, BOTTLE):
        fail(g, LEVEL, 'the bottle was not poured out')
    ticks(g, 2, 'DOWN')
    walk_to(g, 66, 20)
    search(g, 'yy', SPELL)
    log('opened the chest, carrying', carried(g))


def sacks(g):
    """Where the egg sacks of the room are."""
    here = 0x80 + g.room
    return [thing_xy(g, n) for n in range(42)
            if g.byte(THING_KIND + n) == SACK and place(g, n) == here]


def corridor_push(x, y, vx, vy, blocks, cruise=3, horizon=16, wall=21, margin=6):
    """Which way to push this update while flying down the corridor: (across, down), each
    -1, 0 or 1, or None if every choice ends on a sack.

    The corridor runs down and right at 45 degrees with its walls 27 either side of the
    line y = x. Speed across is brought to `cruise` and held. Speed down is chosen by
    looking `horizon` updates ahead at every way of pushing up or down, keeping those that
    stay `wall` or less from the middle line and never come within `margin` of a sack on
    both axes at once (a sack catches at 3), and taking the one that keeps nearest the
    middle. Flying is exact: a push changes the speed by 1, then the speed is added."""
    xs, speed, at, pushes = [], vx, x, []
    for _ in range(horizon):
        push = 1 if speed < cruise else -1 if speed > cruise else 0
        speed += push
        at += speed
        xs.append(at)
        pushes.append(push)
    before_x = [x] + xs

    def bad(t, to, came):
        off = to - xs[t]
        if abs(off) > wall and abs(off) > abs(came - before_x[t]):
            return True                         # past the edge and still going out
        return any(abs(xs[t] - sx) <= margin and abs(to - sy) <= margin for sx, sy in blocks)

    worst = 10 ** 9
    memo = {}

    def cost(t, at, speed):
        """The least total distance from the middle line from update t on, or `worst`."""
        if t == horizon:
            return 0
        key = (t, at, speed)
        if key not in memo:
            best = worst
            for push in (0, 1, -1):
                fast = speed + push
                if abs(fast) > FLY_TOP or bad(t, at + fast, at):
                    continue
                rest = cost(t + 1, at + fast, fast)
                if rest < worst:
                    best = min(best, rest + abs(at + fast - xs[t]) + abs(push))
            memo[key] = best
        return memo[key]

    best, pick = worst, None
    for push in (0, 1, -1):
        fast = vy + push
        if abs(fast) > FLY_TOP or bad(0, y + fast, y):
            continue
        rest = cost(1, y + fast, fast)
        if rest < worst and rest + abs(y + fast - xs[0]) + abs(push) < best:
            best, pick = rest + abs(y + fast - xs[0]) + abs(push), push
    return None if pick is None else (pushes[0], pick)


def corridor(g, log):
    """Room 3, a long corridor full of webs. Small spiders take anyone who stands on its
    floor for more than about 35 updates all told, so the levitation spell is used at once
    and switched off beside the ladder at the far end. The spell lasts 400 updates.

    The corridor is far longer than a room can be. Each time the wizard reaches x 183 the
    game moves him and the five egg sacks back by 32 and puts the sack that fell behind
    ahead again at a new height, 21 times over, before the real end comes. So the sacks
    can't be learned: each update this reads where they are and steers between them."""
    left = g.byte(GROUND_TIME)
    mount(g, SPELL)
    log('levitating, with', left, 'updates of standing left and', g.byte(STRETCHES),
        'stretches to fly')
    for _ in range(600):
        (x, y), (vx, vy) = xy(g), fly_speed(g)
        if g.byte(STRETCHES) == 0 and x >= 200:
            break                               # past the last sack
        if caught(g):
            fail(g, LEVEL, 'an egg sack caught the wizard in the corridor')
        if not flying(g):
            fail(g, LEVEL, 'the levitation spell ran out in the corridor')
        for margin in (6, 5, 4):
            push = corridor_push(x, y, vx, vy, sacks(g), margin=margin)
            if push:
                break
        else:
            fail(g, LEVEL, f'no way between the egg sacks {sacks(g)} at speed {(vx, vy)}')
        buttons = [('UP', '', 'DOWN')[push[1] + 1], ('LEFT', '', 'RIGHT')[push[0] + 1]]
        if not tick(g, '+'.join(b for b in buttons if b)):
            fail(g, LEVEL, 'the game stopped in the corridor')
    else:
        fail(g, LEVEL, 'the corridor never ended')
    log('at the end of the corridor with', fly_time(g), 'of the spell left')
    # The ladder up is at (232, 200), and it takes a wizard on foot coming from its left.
    fly(g, (224, 203), top=2)
    mount(g, SPELL, on=False)
    left = g.byte(GROUND_TIME)
    ladder(g, 'RIGHT', 4)
    log('up the ladder; there were', left, 'updates of standing left on landing')


def play(g, log=print):
    if g.level != 5 or g.room != 0:
        fail(g, LEVEL, f'expected the first room of level 6, found level {g.level} room {g.room}')

    spider_hole(g)
    log('through the spider hole')

    big_spider(g, log)

    # The ladder down is the hole at (124, 16), safe from its right and its top.
    go(g, (108, 40), (122, 32), (140, 30), (140, 20))
    ladder(g, 'LEFT', 2)
    log('down the ladder')

    chest(g, log)

    # The next ladder down is the hole at (87, 74), safe from its top and its right.
    go(g, (66, 36), (66, 56), (87, 60))
    through_door(g, 'DOWN', 3)
    corridor(g, log)

    # Room 4. The straw bed (thing 15) isn't needed. The way out is the hole at (40, 84),
    # safe from its right and its top.
    go(g, (105, 44), (60, 72), (56, 84))
    for _ in range(80):
        if not tick(g, 'LEFT'):
            break
        if dead(g):
            fail(g, LEVEL, 'the last ladder killed the wizard')
    return end_of_level(g)


if __name__ == '__main__':
    main(LEVEL, play, CERTIFICATE)

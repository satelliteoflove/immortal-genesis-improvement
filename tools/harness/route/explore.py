"""Map the room the wizard is in by walking everywhere from where he stands.

    from explore import room_map
    print(room_map(g))                  # g is left as it was found

It tries each of the four directions from every spot it reaches (and the diagonals where
none of the four leads anywhere new, as in a doorway), going back to a kept state each time, so it is for exploring only, never for play(). The map is a grid with a
letter for each patch 3 wide and 4 high of the wizard's coordinates:

    .   he can stand here               @   where he started
    !   stepping here stopped the game: a text box, a trap, a fight
    x   stepping here cost health or killed the wizard, or he couldn't move off it (a pit)
    0-9, a-z   stepping here led into that room (a door)

Enemies keep moving while it walks, so a '!' near one is probably the fight starting, and
a second map made a little later may differ there. Kept slots 60 to 63 are used.
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common import busy, dead, tick, xy

WIDE, HIGH = 3, 4                        # a step across is 3 and a step up or down is 4
DIGITS = '0123456789abcdefghijklmnopqrstuvwxyz'


def room_map(g, limit=4000, moves=('UP', 'DOWN', 'LEFT', 'RIGHT')):
    """Returns the map as text, with the x and y of its top left corner and of each door
    and stop found."""
    room = g.room
    start = xy(g)
    marks = {}
    notes = {}
    g.keep(63)
    with tempfile.TemporaryDirectory() as folder:
        def remember(spot):
            path = os.path.join(folder, '%d_%d' % spot)
            g.save(path)
            return path

        def patch(spot):
            return spot[0] // WIDE, spot[1] // HIGH

        seen = {patch(start)}                   # one visit to each patch is enough
        queue = [(start, remember(start))]
        while queue and len(seen) < limit:
            spot, path = queue.pop(0)
            g.load(path)
            os.remove(path)
            g.keep(62)
            health = g.byte(0x090C) >> 4
            marks.setdefault(patch(spot), '.')
            found = len(queue)
            held = True                         # no move goes anywhere: a pit, most likely
            for move in list(moves) + ['UP+LEFT', 'UP+RIGHT', 'DOWN+LEFT', 'DOWN+RIGHT']:
                if '+' in move and len(queue) > found:
                    break                       # diagonals only where the straight moves fail
                g.back(62)
                moved = tick(g, move)
                if xy(g) != spot or g.room != room:
                    held = False
                cell = None
                if dead(g) or g.byte(0x090C) >> 4 < health:
                    mark = 'x'
                elif not moved or busy(g):
                    mark = '!'
                elif g.room != room:
                    mark = DIGITS[g.room % 36]
                else:
                    mark = None
                    there = xy(g)
                    across, down = abs(there[0] - spot[0]), abs(there[1] - spot[1])
                    if across > 3 or down > 4 or ('+' not in move and (
                            down > 2 if move in ('LEFT', 'RIGHT') else across > 2)):
                        # dragged somewhere no step goes: a pit pulling him in
                        marks[patch(spot)] = marks[patch(there)] = 'x'
                        notes.setdefault('x', (spot, move))
                    elif patch(there) not in seen:
                        seen.add(patch(there))
                        queue.append((there, remember(there)))
                if mark:
                    dx = -3 if 'LEFT' in move else 3 if 'RIGHT' in move else 0
                    dy = -4 if 'UP' in move else 4 if 'DOWN' in move else 0
                    cell = ((spot[0] + dx) // WIDE, (spot[1] + dy) // HIGH)
                    if marks.get(cell, '.') == '.':
                        marks[cell] = mark
                    notes.setdefault(mark, (spot, move))
            if held:
                marks[patch(spot)] = 'x'
                notes.setdefault('x', (spot, 'standing'))
    g.back(63)
    marks[(start[0] // WIDE, start[1] // HIGH)] = '@'
    xs = [c[0] for c in marks]
    ys = [c[1] for c in marks]
    lines = [f'room {room}: the left column is x {min(xs) * WIDE}, each letter is {WIDE} wide '
             f'and {HIGH} high, y is at the left; {len(seen)} spots']
    for row in range(min(ys), max(ys) + 1):
        lines.append(f'{row * HIGH:3d} ' + ''.join(marks.get((col, row), ' ')
                                                   for col in range(min(xs), max(xs) + 1)))
    for mark, (spot, move) in sorted(notes.items()):
        what = ('stopped the game' if mark == '!' else 'hurt or held the wizard' if mark == 'x'
                else f'led to room {DIGITS.index(mark)}')
        lines.append(f'{mark}: {move} from {spot} {what}')
    return '\n'.join(lines)

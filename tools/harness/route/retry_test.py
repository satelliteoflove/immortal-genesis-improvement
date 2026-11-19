#!/usr/bin/env python3
"""Die on purpose in each room of each level, and see whether the level can still be finished.

    tools/harness/route/retry_test.py [--original] [--levels 1,2,...] [--jobs 3]
    tools/harness/route/retry_test.py --one LEVEL ENTRY [--original]

A level's route is played as usual, but on its ENTRY-th first entry into a room (0 is the
room the level starts in) the wizard is killed once he has walked a little way in (16 from
where he could first be steered, or after 15 seconds): his health is set to 0, and the game's own death and retry follow. A retry puts him back at the start of
the level (or of part of it) with everything else as he left it, so the test walks him back
along the route's own path: the turns it took and the doors it went through, fighting what
attacks and answering NO to any question. Back where he died, the route carries on as if
nothing had happened, except that his health is set back to what it was when he died
(routes check it). The test notes where he came back, his health, retries and what he
carries, and whether the level could be finished.

A route is written for an unbroken run, and the walk back only knows how to walk, so a
failure is a lead to look at, not a bug in itself. It's a bug when the level can't be
finished at all from where the retry leaves it.

The whole run tries every room of every level; --one runs one case and prints its result as
JSON. Pictures of failures go in scratch/route/retry/. See docs/playthrough.md.
"""
import argparse
import importlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import common
import play

OUT = os.path.join(common.ROOT, 'scratch', 'route', 'retry')


def state(g):
    return {'frame': g.frame, 'room': g.room, 'xy': list(common.xy(g)), 'health': common.health(g),
            'retries': common.retries(g), 'carried': sorted(common.carried(g))}


def steerable(g):
    return not (common.busy(g) or common.dead(g) or common.walking_in(g) or common.fighting(g)
                or common.action(g))


class WalkBack(Exception):
    pass


def path(track):
    """The route's path as [(room, [(x, y) at each turn], buttons that took it out of the room)].

    track is (room, x, y, buttons) after each step. The last room's buttons are None."""
    rooms = []
    for room, x, y, buttons in track:
        if not rooms or rooms[-1][0] != room:
            if rooms:
                rooms[-1][2] = last_buttons
            rooms.append([room, [], None])
        points = rooms[-1][1]
        if not points or points[-1] != (x, y):
            points.append((x, y))
        last_buttons = buttons
    for entry in rooms:                 # keep the turns: where the direction of walking changes
        points, turns, heading = entry[1], [], None
        for a, b in zip(points, points[1:]):
            way = ((b[0] > a[0]) - (b[0] < a[0]), (b[1] > a[1]) - (b[1] < a[1]))
            if heading is not None and way != heading:
                turns.append(a)
            heading = way
        entry[1] = turns + points[-1:]
    return rooms


def clear(g):
    """Fight or read whatever has stopped the game."""
    for _ in range(20):
        if common.dead(g):
            raise WalkBack(f'died again on the way back, in room {g.room} at {common.xy(g)}')
        if common.fighting(g):
            common.fight(g)
        elif common.busy(g):
            try:
                common.read(g)
            except common.RouteError as error:
                if 'question' not in str(error):
                    raise
                common.read(g, 'n')
        else:
            return
    raise WalkBack(f'kept stopping on the way back, in room {g.room}')


def walk(g, x, y, beyond=None):
    """Walk to (x, y), dealing with fights and text. True if it went on into room `beyond`,
    as walking to the last spot before a doorway can."""
    for _ in range(20):
        result = common.walk_to(g, x, y)
        if result == 'there':
            return False
        if result == 'room' and g.room == beyond:
            return True
        if result == 'room':
            raise WalkBack(f'walking to ({x}, {y}) went into room {g.room}')
        clear(g)
    raise WalkBack(f'never reached ({x}, {y}) in room {g.room}')


def settle(g, limit=400):
    for _ in range(limit):
        if steerable(g):
            return
        if common.busy(g) or common.fighting(g):
            clear(g)
        else:
            g.step(1)
    raise WalkBack(f'the wizard never came to rest in room {g.room}')


def walk_back(g, track, to):
    """Retrace the route's path from wherever the retry left the wizard to `to` (room, x, y).

    It starts from the route's last time in the room he came back in, at the turn nearest
    to him: a retry puts him where he last went through a door, or at the level's start."""
    rooms = path(track)
    starts = [i for i, (room, _, _) in enumerate(rooms) if room == g.room]
    if not starts:
        raise WalkBack(f'came back in room {g.room}, which the route never went through')
    here = common.xy(g)
    first = rooms[starts[-1]][1]
    nearest = min(range(len(first)), key=lambda i: abs(first[i][0] - here[0]) + abs(first[i][1] - here[1]))
    rest = rooms[starts[-1]:]
    for n, (room, points, buttons) in enumerate(rest):
        if g.room != room:
            raise WalkBack(f'expected room {room}, in room {g.room}')
        beyond = rest[n + 1][0] if n + 1 < len(rest) else None
        through = False
        for x, y in points[nearest if n == 0 else 0:]:
            if walk(g, x, y, beyond):
                through = True
                break
        if through:
            settle(g)
        elif buttons is not None:
            try:
                common.through_door(g, buttons, limit=200)
            except common.RouteError as error:
                raise WalkBack(f'leaving room {room}: {error}')
            settle(g)
    if g.room != to[0]:
        raise WalkBack(f'ended in room {g.room}, not {to[0]}')
    walk(g, to[1], to[2])
    settle(g)


class DyingGame(play.Game):
    """A Game that kills the wizard once, on the entry-th first entry into a room, and then
    walks him back to where he died."""

    def __init__(self, rom, entry):
        super().__init__(rom)
        self.entry, self.seen, self.armed, self.inside, self.pending = entry, [], False, False, False
        self.entered = None             # where he could first be steered in the room
        self.before = self.after = self.back = None
        self.track = []

    def step(self, frames=1, buttons=''):
        super().step(frames, buttons)
        if not self.armed or self.inside or self.after is not None:
            return self
        self.track.append((self.room, *common.xy(self), buttons))
        if self.room not in self.seen:
            self.seen.append(self.room)
            if len(self.seen) - 1 == self.entry:
                self.pending, self.entered = self.frame, None
        if self.pending is not False and self.entered is None and steerable(self):
            self.entered = common.xy(self)
        if self.pending is not False and self.entered and steerable(self) and (
                abs(common.xy(self)[0] - self.entered[0]) + abs(common.xy(self)[1] - self.entered[1]) >= 16
                or self.frame - self.pending > 900):
            self.inside = True
            try:
                self.die()
            finally:
                self.inside = False
        return self

    def die(self):
        self.before = state(self)
        self.poke(common.HEALTH, self.byte(common.HEALTH) & 0x0F)
        for _ in range(120):
            if common.dead(self):
                break
            self.step(1)
        common.revive(self)
        self.after = state(self)
        self.after['steerable'] = steerable(self)
        start = self.frame
        walk_back(self, self.track, (self.before['room'], *self.before['xy']))
        self.back = {'frames': self.frame - start, 'health': common.health(self),
                     'retries': common.retries(self)}
        # The retry refills his health, and routes check it (a straw bed does nothing at
        # full health, a trap room is crossed without losing any), so give back what he had.
        self.poke(common.HEALTH, self.byte(common.HEALTH) & 0x0F | min(self.before['health'], self.back['health']) << 4)


def one(level, entry, original):
    route = importlib.import_module(f'level{level}')
    rom = play.original() if original else play.PATCHED
    result = {'level': level, 'entry': entry, 'rom': 'original' if original else 'patched'}
    with DyingGame(rom, entry) as g:
        if route.CERTIFICATE:
            g.start_level(route.CERTIFICATE)
        else:
            g.new_game()
        g.armed = True
        try:
            result['certificate'] = route.play(g, lambda *words: None)
            result['outcome'] = 'finished' if g.after else 'no such room'
        except Exception as error:
            result['outcome'] = 'failed'
            result['error'] = f'{type(error).__name__}: {error}'
            path = os.path.join(OUT, f'level{level}-entry{entry}-{result["rom"]}.png')
            try:
                g.shot(path)
                result['picture'] = os.path.relpath(path, common.ROOT)
            except Exception:
                pass
        result['rooms'] = g.seen
        result['before'], result['after'], result['back'] = g.before, g.after, g.back
        result['frames'] = g.frame
    return result


def run_level(level, original):
    """Every entry of one level, in order, until the route never reaches the next."""
    results = []
    for entry in range(40):
        command = [sys.executable, os.path.abspath(__file__), '--one', str(level), str(entry)]
        if original:
            command.append('--original')
        done = subprocess.run(command, capture_output=True, text=True)
        try:
            result = json.loads(done.stdout.strip().splitlines()[-1])
        except (IndexError, ValueError):
            result = {'level': level, 'entry': entry, 'outcome': 'crashed', 'error': done.stderr[-300:]}
        results.append(result)
        print(line(result), flush=True)
        if result['outcome'] == 'no such room':
            break
    return results


def line(r):
    if r['outcome'] == 'no such room':
        return f"level {r['level']}: {r['entry']} rooms tried"
    a, b = r.get('before') or {}, r.get('after') or {}
    where = (f"died in room {a.get('room')} at {tuple(a.get('xy', ()))}, back in room {b.get('room')} "
             f"at {tuple(b.get('xy', ()))}, health {b.get('health')}, retries {b.get('retries')}"
             + ('' if b.get('steerable', True) else ', not steerable')
             + ('' if a.get('carried') == b.get('carried') else
                f", carried {a.get('carried')} became {b.get('carried')}")) if b else 'never died'
    tail = f"finished, certificate {r.get('certificate')}" if r['outcome'] == 'finished' else \
        f"FAILED: {r.get('error', '')[:160]}"
    return f"level {r['level']} entry {r['entry']:2d}: {where}; {tail}"


def main():
    parser = argparse.ArgumentParser(description='Die in each room and see whether the level can still be finished.')
    parser.add_argument('--original', action='store_true')
    parser.add_argument('--levels', default='1,2,3,4,5,6,7,8')
    parser.add_argument('--jobs', type=int, default=3)
    parser.add_argument('--one', nargs=2, type=int, metavar=('LEVEL', 'ENTRY'))
    args = parser.parse_args()
    if args.one:
        print(json.dumps(one(args.one[0], args.one[1], args.original)))
        return
    began = time.time()
    levels = [int(n) for n in args.levels.split(',')]
    with ThreadPoolExecutor(args.jobs) as pool:
        everything = [r for rs in pool.map(lambda n: run_level(n, args.original), levels) for r in rs]
    os.makedirs(OUT, exist_ok=True)
    name = 'original' if args.original else 'patched'
    with open(os.path.join(OUT, f'results-{name}.json'), 'w') as f:
        json.dump(everything, f, indent=1)
    tried = [r for r in everything if r['outcome'] != 'no such room']
    failed = [r for r in tried if r['outcome'] != 'finished']
    print(f'\n{name}: {len(tried)} deaths tried, {len(tried) - len(failed)} levels finished afterward, '
          f'{len(failed)} not, {time.time() - began:.0f} s')
    for r in failed:
        print('  ' + line(r))
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()

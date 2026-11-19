#!/usr/bin/env python3
"""Die on purpose in each room of each level, and see whether the level can still be finished.

    tools/harness/route/retry_test.py [--original] [--levels 1,2,...] [--jobs 3]
    tools/harness/route/retry_test.py --plan LEVEL [--original]
    tools/harness/route/retry_test.py --one LEVEL ENTRY FRAME [--original]

Each level's route is played once without dying, to choose a moment in each room it goes
through: the moment he is farthest from the doors he came in and went out by, among those
when he is steered and no button but a direction is held. Then the route is played again for
each room, and at that moment his health is set to 0. The game's own death and retry follow.
A retry puts him at a spot the game keeps for the room he died in, most often where he came
into the room before it, and leaves everything else as it was. The test walks him back along
the route's own path (the turns it took and the doors it went through, fighting what attacks
and answering NO to any question), sets his health back to what it was and arms again the
spell he had armed, since the routes count on those. Then the route carries on as if nothing
had happened, with the time all that took hidden from it.

A route is written for an unbroken run, and the walk back only knows how to walk, so a
failure is a lead to look at, not a bug in itself. It's a bug when the level can't be
finished at all from where the retry leaves it.

--plan prints a level's moments as JSON, and --one runs one of them and prints its result.
The results go in scratch/route/retry/, with a picture of each failure. See
docs/playthrough.md.
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
PREPARE = 0x42F9                        # the text of "Prepare to continue..."
DIRECTIONS = ('UP', 'DOWN', 'LEFT', 'RIGHT')


def state(g):
    return {'frame': g.frame, 'room': g.room, 'xy': list(common.xy(g)), 'health': common.health(g),
            'retries': common.retries(g), 'carried': sorted(common.carried(g)), 'armed': common.armed(g)}


def steerable(g):
    return not (common.busy(g) or common.dead(g) or common.walking_in(g) or common.fighting(g)
                or common.action(g))


class WalkBack(Exception):
    pass


def path(track):
    """The route's path as [(room, [(x, y) at each turn], buttons that took it out of the room)].

    track is (room, x, y, buttons, ...) after each update. The last room's buttons are None."""
    rooms = []
    for room, x, y, buttons, *_ in track:
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
    to him: a retry puts him at a spot set for the room he died in, most often where he came
    into the room before it."""
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


def quiet(buttons):
    """True if buttons holds nothing but directions: a kill then can't leave a C or an A to
    be taken once he is back."""
    return all(w in DIRECTIONS for w in (buttons or '').split('+') if w)


class DyingGame(play.Game):
    """A Game that notes the route's path and, if `at` is a frame, kills the wizard once at the
    first update from then on when he can be steered, and walks him back to where he died."""

    def __init__(self, rom, at=None):
        super().__init__(rom)
        self.at, self.inside = at, False
        self.not_before = 0             # a kill that ran into a text box is tried again later
        self.before = self.after = self.walked = None
        self.track = []                 # (room, x, y, buttons, steered, frame, could die) per update
        self.spent = 0                  # frames the death and walk back took

    def step(self, frames=1, buttons=''):
        if self.inside or self.after is not None:
            return super().step(frames, buttons)
        can = steerable(self)
        deadline = self.long(common.DEADLINE)
        super().step(frames, buttons)
        if self.long(common.DEADLINE) == deadline:          # not an update of the game
            return self
        could = can and quiet(buttons) and steerable(self)
        self.track.append((self.room, *common.xy(self), buttons, bool(buttons) and can, self.frame, could))
        if self.at is not None and could and self.frame >= max(self.at, self.not_before):
            self.inside = True
            try:
                self.die()
            finally:
                self.inside = False
        return self

    def die(self):
        """Set his health to 0. If a text box comes up first (he has walked onto a thing,
        and a question is coming), go back and try again 30 frames later."""
        self.keep(9)
        before = state(self)
        self.poke(common.HEALTH, self.byte(common.HEALTH) & 0x0F)
        for _ in range(600):            # he falls for about 370 frames before the message
            if common.busy(self):
                break
            self.step(1)
        if common.text_address(self) != PREPARE:
            self.back(9)
            self.not_before = self.frame + 30
            return
        self.before = before
        common.revive(self)
        self.after = state(self)
        self.after['steerable'] = steerable(self)
        start = self.frame
        walk_back(self, self.track, (self.before['room'], *self.before['xy']))
        self.walked = {'frames': self.frame - start, 'health': common.health(self),
                     'retries': common.retries(self)}
        # The route was in the middle of a step, and may be counting frames toward a limit
        # (the wait for a straw bed's dream, say): hide the time the death and the walk back
        # took, so it goes on as if this step had been an ordinary one.
        self.spent = self.frame - self.before['frame']
        self.frame = self.before['frame']
        # The retry refills his health, and routes check it (a straw bed does nothing at
        # full health, a trap room is crossed without losing any), so give back what he had.
        self.poke(common.HEALTH, self.byte(common.HEALTH) & 0x0F | self.before['health'] << 4)
        # A retry leaves nothing armed (docs/playthrough.md); arm again what was.
        if self.before['armed'] is not None and common.armed(self) is None:
            common.use(self, self.before['armed'])
            common.read(self)
            self.walked['armed again'] = self.before['armed']


def start(level, original, at=None):
    route = importlib.import_module(f'level{level}')
    g = DyingGame(play.original() if original else play.PATCHED, at)
    if route.CERTIFICATE:
        g.start_level(route.CERTIFICATE)
    else:
        g.new_game()
    g.track.clear()
    return route, g


def plan(level, original):
    """Play the level without dying, and choose a moment in each room to die: the update,
    among those when he could be killed, farthest from where he came in and where he left
    (the smaller of the two distances)."""
    route, g = start(level, original)
    with g:
        route.play(g, lambda *words: None)
        track = g.track
    visits, seen = [], set()
    for i, (room, *_rest) in enumerate(track):
        if room in seen and visits and visits[-1]['room'] == room:
            visits[-1]['last'] = i
        elif room not in seen:
            seen.add(room)
            visits.append({'room': room, 'first': i, 'last': i})
    moments = []
    for v in visits:
        steps = track[v['first']:v['last'] + 1]
        steered = [s for s in steps if s[4]] or steps
        come, go = steered[0][1:3], steps[-1][1:3]
        could = [s for s in steps if s[6]]
        if not could:
            moments.append({'room': v['room'], 'frame': None})
            continue
        far = max(could, key=lambda s: min(abs(s[1] - come[0]) + abs(s[2] - come[1]),
                                           abs(s[1] - go[0]) + abs(s[2] - go[1])))
        moments.append({'room': v['room'], 'frame': far[5], 'xy': far[1:3]})
    return moments


def one(level, entry, at, original):
    result = {'level': level, 'entry': entry, 'rom': 'original' if original else 'patched', 'at': at}
    route, g = start(level, original, at)
    with g:
        try:
            result['certificate'] = route.play(g, lambda *words: None)
            result['outcome'] = 'finished' if g.after else 'never died'
        except common.Died as error:
            if level == 8 and 'retries ran out' in str(error):
                result['outcome'] = 'game over'     # level 8 gives no retries
            else:
                result['outcome'], result['error'] = 'failed', f'Died: {error}'
        except Exception as error:
            result['outcome'] = 'failed'
            result['error'] = f'{type(error).__name__}: {error}'
            path = os.path.join(OUT, f'level{level}-entry{entry}-{result["rom"]}.png')
            try:
                g.shot(path)
                result['picture'] = os.path.relpath(path, common.ROOT)
            except Exception:
                pass
        result['before'], result['after'], result['back'] = g.before, g.after, g.walked
        result['frames'] = g.frame + g.spent
    return result


def run_level(level, original):
    """Plan the level's deaths, then try each in its own process."""
    flag = ['--original'] if original else []
    me = [sys.executable, os.path.abspath(__file__)]
    done = subprocess.run(me + ['--plan', str(level)] + flag, capture_output=True, text=True)
    try:
        moments = json.loads(done.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        result = {'level': level, 'entry': -1, 'outcome': 'failed', 'error': 'plan: ' + done.stderr[-300:]}
        print(line(result), flush=True)
        return [result]
    results = []
    for entry, moment in enumerate(moments):
        if moment['frame'] is None:
            result = {'level': level, 'entry': entry, 'outcome': 'skipped',
                      'error': f"room {moment['room']}: never a moment to die in"}
        else:
            done = subprocess.run(me + ['--one', str(level), str(entry), str(moment['frame'])] + flag,
                                  capture_output=True, text=True)
            try:
                result = json.loads(done.stdout.strip().splitlines()[-1])
            except (IndexError, ValueError):
                result = {'level': level, 'entry': entry, 'outcome': 'crashed', 'error': done.stderr[-300:]}
        results.append(result)
        print(line(result), flush=True)
    return results


def line(r):
    a, b = r.get('before') or {}, r.get('after') or {}
    where = (f"died in room {a.get('room')} at {tuple(a.get('xy', ()))}, back in room {b.get('room')} "
             f"at {tuple(b.get('xy', ()))}, health {b.get('health')}, retries {b.get('retries')}"
             + ('' if b.get('steerable', True) else ', not steerable')
             + ('' if a.get('carried') == b.get('carried') else
                f", carried {a.get('carried')} became {b.get('carried')}")) if b else 'never died'
    tail = f"finished, certificate {r.get('certificate')}" if r['outcome'] == 'finished' else \
        'game over, as level 8 has no retries' if r['outcome'] == 'game over' else \
        f"skipped: {r.get('error')}" if r['outcome'] == 'skipped' else \
        f"FAILED: {r.get('error', '')[:160]}"
    return f"level {r['level']} entry {r['entry']:2d}: {where}; {tail}"


def main():
    parser = argparse.ArgumentParser(description='Die in each room and see whether the level can still be finished.')
    parser.add_argument('--original', action='store_true')
    parser.add_argument('--levels', default='1,2,3,4,5,6,7,8')
    parser.add_argument('--jobs', type=int, default=3)
    parser.add_argument('--one', nargs=3, type=int, metavar=('LEVEL', 'ENTRY', 'FRAME'))
    parser.add_argument('--plan', type=int, metavar='LEVEL')
    args = parser.parse_args()
    if args.one:
        print(json.dumps(one(*args.one, args.original)))
        return
    if args.plan:
        print(json.dumps(plan(args.plan, args.original)))
        return
    began = time.time()
    levels = [int(n) for n in args.levels.split(',')]
    with ThreadPoolExecutor(args.jobs) as pool:
        everything = [r for rs in pool.map(lambda n: run_level(n, args.original), levels) for r in rs]
    os.makedirs(OUT, exist_ok=True)
    name = 'original' if args.original else 'patched'
    with open(os.path.join(OUT, f'results-{name}.json'), 'w') as f:
        json.dump(everything, f, indent=1)
    tried = [r for r in everything if r['outcome'] != 'skipped']
    failed = [r for r in tried if r['outcome'] not in ('finished', 'game over')]
    print(f'\n{name}: {len(tried)} deaths tried, {len(tried) - len(failed)} levels finished afterward, '
          f'{len(failed)} not, {time.time() - began:.0f} s')
    for r in failed:
        print('  ' + line(r))
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()

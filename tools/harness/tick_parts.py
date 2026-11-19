#!/usr/bin/env python3
"""Split each game tick into parts, on the BlastEm fork, and compare late ticks with on-time ones.

    tools/harness/tick_parts.py [rom] [name:start:end ...]
    tools/harness/tick_parts.py --headroom [rom]
    tools/harness/tick_parts.py --frames [rom]

Uses the walks from fork_timing.py, on the patched ROM by default. Each part is a pair of
addresses; the default parts follow the main loop at 013470 and the drawing at 01564E. The
fork allows seven parts alongside the tick itself. Figures are thousands of cycles per
tick, and a tick has about 639k before it runs late.

--headroom shows how much work each tick does, leaving out its waits for vertical blank
and its timed pauses, and how many ticks wouldn't fit a shorter tick.

--frames shows how many video frames each tick takes to get its picture ready, counting
from the tick's start to the end of the drawing that follows its wait for vertical blank.
Waits inside the game logic and timed pauses are left out. This is the figure that says
whether a shorter tick would fit.

The profiler reports once a video frame, so a part that finishes in the same frame its
tick starts in is counted with the tick before. Averages over many ticks come out right,
and so do --headroom and --frames, which rest on parts that finish at a tick's end. Don't
rely on the parts of any one tick.
"""
import collections
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import compare_cores as cc
import fork_timing as ft

DEFAULT = ['logic:1347c:13480', 'check:13484:13488', 'prep:1348c:13490', 'sprites:15652:15656',
           'upload:15656:1565a', 'vwait:1565a:1565e', 'after:1565e:15732']
HEADROOM = ['work:1347c:13494', 'vblank:14e3a:14e4c', 'vblank2:14e4e:14e6c', 'pause:153da:15404']
FRAME = 127.8                   # thousands of 68000 cycles in a video frame
FIELD = re.compile(r'(\w+)=(\d+):(\d+)')


def run(rom, parts, level, walk):
    base = f'{ft.OUT}/parts_{level}_{walk}'
    with open(base + '.script', 'w') as f:
        f.write(ft.fork_script(level, walk))
    init = [f'script {base}.script', f'prof lap tick {ft.TICK}', 'prof log on']
    init += [f'prof bracket {n} {a} {b}' for n, a, b in parts]
    with open(base + '.init', 'w') as f:
        f.write('\n'.join(init) + '\n')
    env = {**os.environ, 'HOME': ft.HOME, 'SDL_VIDEODRIVER': 'dummy', 'SDL_AUDIODRIVER': 'dummy',
           'BLASTEM_NO_GUI': '1', 'BLASTEM_KIT_INIT': base + '.init'}
    out = subprocess.run([ft.BLASTEM, '-b', str(cc.START + cc.FRAMES), rom], env=env, capture_output=True,
                         text=True, errors='replace', timeout=300).stdout
    ticks, last, spent = [], None, collections.Counter()
    for line in out.splitlines():
        if not line.startswith('KIT PROF'):
            continue
        frame = int(line.split('frame=')[1].split()[0])
        if frame <= cc.START:
            continue
        hit = False
        for name, cycles, hits in FIELD.findall(line):
            if name == 'tick':
                hit = int(hits) > 0
            else:
                spent[name] += int(cycles)
        if hit:
            if last is not None:
                ticks.append((frame - last, spent))
            last, spent = frame, collections.Counter()
    return level, ticks


def percentile(values, share):
    return sorted(values)[min(len(values) - 1, int(len(values) * share))]


def headroom(rom):
    parts = [p.split(':') for p in HEADROOM]
    jobs = [(l, w) for l in range(8) for w in range(cc.WALKS)]
    with ThreadPoolExecutor(os.cpu_count()) as pool:
        done = list(pool.map(lambda j: run(rom, parts, *j), jobs))
    every = []
    print('level  ticks  median    90%    99%    max   over 4, 3 and 2 frames of work')
    for level in [*range(8), None]:
        if level is None:
            work = every
        else:
            work = [(t[1]['work'] - t[1]['vblank'] - t[1]['vblank2'] - t[1]['pause']) / 1000
                    for l, found in done if l == level for t in found if t[0] < cc.PAUSE]
            every += work
        over = '  '.join(f'{100 * sum(w > n * FRAME for w in work) / len(work):4.1f}%' for n in (4, 3, 2))
        print(f'{"all" if level is None else level + 1:>5} {len(work):6} ' +
              ''.join(f'{percentile(work, p):7.0f}' for p in (.5, .9, .99)) + f'{max(work):7.0f}   {over}')


def frames(rom):
    parts = [p.split(':') for p in HEADROOM]
    jobs = [(l, w) for l in range(8) for w in range(cc.WALKS)]
    with ThreadPoolExecutor(os.cpu_count()) as pool:
        done = list(pool.map(lambda j: run(rom, parts, *j), jobs))
    print('level  ticks   picture ready in 1, 2, 3, 4 and 5 or more frames')
    every = []
    for level in [*range(8), None]:
        if level is None:
            ready = every
        else:
            ready = [max(1, round((t[1]['work'] - t[1]['vblank'] - t[1]['pause']) / 1000 / FRAME))
                     for l, found in done if l == level for t in found if t[0] < cc.PAUSE]
            every += ready
        shares = [100 * sum(r == n for r in ready) / len(ready) for n in (1, 2, 3, 4)]
        shares.append(100 * sum(r >= 5 for r in ready) / len(ready))
        print(f'{"all" if level is None else level + 1:>5} {len(ready):6}   ' + ''.join(f'{x:7.1f}%' for x in shares))


def main():
    args = sys.argv[1:]
    if args and args[0] in ('--headroom', '--frames'):
        rom = args[1] if len(args) > 1 else os.path.join(ft.ROOT, 'build', 'immortal-patched.md')
        return headroom(rom) if args[0] == '--headroom' else frames(rom)
    rom = args.pop(0) if args and ':' not in args[0] else os.path.join(ft.ROOT, 'build', 'immortal-patched.md')
    parts = [p.split(':') for p in (args or DEFAULT)]
    names = [p[0] for p in parts]
    os.makedirs(ft.OUT, exist_ok=True)
    os.makedirs(ft.HOME, exist_ok=True)
    jobs = [(l, w) for l in range(8) for w in range(cc.WALKS)]
    with ThreadPoolExecutor(os.cpu_count()) as pool:
        done = list(pool.map(lambda j: run(rom, parts, *j), jobs))
    print('level kind      ticks ' + ''.join(f'{n[:8]:>9}' for n in names) + '      sum')
    for level in range(8):
        ticks = [t for l, found in done if l == level for t in found if t[0] < cc.PAUSE]
        for kind, chosen in (('on time', [t for t in ticks if t[0] <= 5]), ('late', [t for t in ticks if t[0] > 5])):
            if chosen:
                means = [sum(t[1][n] for t in chosen) / len(chosen) / 1000 for n in names]
                print(f'{level + 1:5} {kind:8} {len(chosen):6} ' + ''.join(f'{m:9.0f}' for m in means) + f'{sum(means):9.0f}')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Jump to each of the eight levels and measure how steadily the game runs.

    tools/harness/levels.py

Needs the profiling core (build_trace_core.sh) and the runner (make). The wizard
is walked about at random, the same way every run, and for each level this prints
how many of the game's ticks came late. Saved states and a picture of each level
go in scratch/levels/, which git ignores.

A level is reached the way the game reloads one between levels: the "reload"
flag, the level number and the "restart" flag are set in RAM.
"""
import collections
import os
import random
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, 'scratch', 'levels')
CORE = os.path.join(ROOT, 'build', 'picodrive_trace_libretro.so')
RUN = os.path.join(HERE, 'run.sh')

TICK = '134a8'                  # runs once per game tick, as the wait ends
WAIT = '1349c,134a4'            # the wait loop itself
BUILDER = '2e3e4,2f4e0'         # builds object graphics into RAM
FRAMES = 3000
WALKS = 4
CYCLES_PER_FRAME = 127841       # NTSC: 262 lines of 488 cycles, near enough
PAUSE = 12                      # gaps this long are messages and such, not slowdown
DIRECTIONS = ['UP', 'DOWN', 'LEFT', 'RIGHT', 'UP+LEFT', 'UP+RIGHT', 'DOWN+LEFT', 'DOWN+RIGHT']


def run(*args):
    subprocess.run([RUN, '-q', *map(str, args)], check=True, stderr=subprocess.DEVNULL,
                   env={**os.environ, 'CORE': CORE})


def make_state(level):
    run('-n', 1000, '-x', 1, '-l', f'{OUT}/room1.state',
        '-p', '10:ff1088=1', '-p', f'10:ff1091={level:x}', '-p', '10:ff1073=1',
        '-S', f'900:{OUT}/level{level}.state', '-s', f'900:{OUT}/level{level}.png')


def ticks(path):
    rows = [tuple(map(int, line.split())) for line in open(path)]
    return rows


def walk(job):
    level, i = job
    rnd = random.Random(level * 100 + i)
    frame, lines = 0, []
    while frame < FRAMES:
        lines.append(f'{frame} 0 {rnd.choice(DIRECTIONS)}')
        frame += rnd.choice([20, 40, 60, 90])
    base = f'{OUT}/walk{level}_{i}'
    with open(base + '.txt', 'w') as f:
        f.write('\n'.join(lines) + '\n')
    common = ('-n', FRAMES, '-l', f'{OUT}/level{level}.state', '-i', base + '.txt')
    run(*common, '-T', f'{TICK},{WAIT}:{base}.idle')
    run(*common, '-T', f'{TICK},{BUILDER}:{base}.build')
    idle = sum(r[2] for r in ticks(base + '.idle'))
    spans, last, spent = [], None, 0
    for f, n, cycles in ticks(base + '.build'):
        spent += cycles
        if n:
            if last is not None:
                spans.append((f - last, spent))
            last, spent = f, 0
    return level, spans, idle


def mean(values):
    return sum(values) / len(values) if values else 0


def main():
    if not os.path.exists(CORE):
        sys.exit('build the profiling core first: tools/harness/build_trace_core.sh')
    os.makedirs(OUT, exist_ok=True)
    run('-n', 2601, '-i', os.path.join(HERE, 'input', 'first_room.txt'), '-S', f'2600:{OUT}/room1.state')
    with ThreadPoolExecutor(os.cpu_count()) as pool:
        list(pool.map(make_state, range(8)))
        results = list(pool.map(walk, [(l, i) for l in range(8) for i in range(WALKS)]))

    sheet = Image.new('RGB', (1280, 448))
    for n in range(8):
        sheet.paste(Image.open(f'{OUT}/level{n}.png'), ((n % 4) * 320, (n // 4) * 224))
    sheet.save(f'{OUT}/levels.png')

    print('level  ticks  late  worst gap  idle  object-graphics cycles a tick (on time / late)')
    every = collections.Counter()
    for level in range(8):
        spans = [s for r in results if r[0] == level for s in r[1] if s[0] < PAUSE]
        every.update(g for g, _ in spans)
        on = [c for g, c in spans if g <= 5]
        late = [c for g, c in spans if g > 5]
        idle = mean([r[2] for r in results if r[0] == level]) / (CYCLES_PER_FRAME * FRAMES)
        print(f'{level + 1:5}  {len(spans):5}  {100 * len(late) / len(spans):3.0f}%  {max(g for g, _ in spans):9}'
              f'  {100 * idle:3.0f}%  {mean(on) / 1000:6.0f}k / {mean(late) / 1000:.0f}k')
    total = sum(every.values())
    print('\nvideo frames per tick, all levels:',
          ', '.join(f'{g}: {100 * n / total:.1f}%' for g, n in sorted(every.items())))


if __name__ == '__main__':
    main()

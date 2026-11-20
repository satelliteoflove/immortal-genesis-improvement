#!/usr/bin/env python3
"""Compare the game's tick timing on PicoDrive and on BlastEm.

    tools/harness/compare_cores.py [--check]

Each run starts from power-on: the same scripted opening, a jump to a level, then
a random walk that is the same on both emulators. A tick is seen as a change in
the game's own deadline variable, so no profiling core is needed. The walks can
drift apart between emulators, so compare the totals, not single ticks.

--check only reaches each level and saves a picture of it in scratch/cores/.
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
OUT = os.path.join(ROOT, 'scratch', 'cores')
CORES = {
    'picodrive': (os.path.join(ROOT, 'build', 'cores', 'picodrive', 'picodrive_libretro.so'), []),
    'blastem': (os.path.join(ROOT, 'build', 'cores', 'blastem', 'blastem_libretro.so'), ['-b', '0,8,11']),
}
DEADLINE = 'ff12e6'
JUMP = 2610                     # the frame the level is set
START = 3500                    # the frame the walk begins
FRAMES = 3000
WALKS = 4
PAUSE = 12
DIRECTIONS = ['UP', 'DOWN', 'LEFT', 'RIGHT', 'UP+LEFT', 'UP+RIGHT', 'DOWN+LEFT', 'DOWN+RIGHT']


def run(core, *args):
    path, extra = CORES[core]
    subprocess.run([os.path.join(HERE, 'run.sh'), '-q', *extra, *map(str, args)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env={**os.environ, 'CORE': path})


def jump(level):
    return ['-p', f'{JUMP}:ff1088=1', '-p', f'{JUMP}:ff1091={level:x}', '-p', f'{JUMP}:ff1073=1']


def script(level, walk, walking=True):
    with open(os.path.join(HERE, 'input', 'first_room.txt')) as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith('#')]
    if walking:
        rnd = random.Random(level * 100 + walk)
        frame = 0
        while frame < FRAMES:
            lines.append(f'{START + frame} 0 {rnd.choice(DIRECTIONS)}')
            frame += rnd.choice([20, 40, 60, 90])
    return '\n'.join(lines) + '\n'


def check(job):
    core, level = job
    base = f'{OUT}/{core}_check{level}'
    with open(base + '.txt', 'w') as f:
        f.write(script(level, 0, False))
    run(core, '-n', START, '-x', 1, '-i', base + '.txt', *jump(level), '-s', f'{START - 1}:{base}.png',
        '-m', base + '.ram')
    ram = open(base + '.ram', 'rb').read()
    return core, level, ram[0x1070], ram[0x1051]


def walk(job):
    core, level, i = job
    base = f'{OUT}/{core}_{level}_{i}'
    with open(base + '.txt', 'w') as f:
        f.write(script(level, i))
    run(core, '-n', START + FRAMES, '-i', base + '.txt', *jump(level), '-W', f'{DEADLINE}:{base}.w')
    values = [int(x) for x in open(base + '.w')]
    ticks = [f for f in range(START + 1, len(values)) if values[f] != values[f - 1]]
    return core, level, [b - a for a, b in zip(ticks, ticks[1:])]


def main():
    os.makedirs(OUT, exist_ok=True)
    with ThreadPoolExecutor(os.cpu_count()) as pool:
        if '--check' in sys.argv:
            jobs = [(c, l) for c in CORES for l in range(8)]
            for r in pool.map(check, jobs):
                print(*r)
            sheet = Image.new('RGB', (1280, 896))
            for row, c in enumerate(CORES):
                for n in range(8):
                    im = Image.open(f'{OUT}/{c}_check{n}.png').convert('RGB').resize((320, 224))
                    sheet.paste(im, ((n % 4) * 320, (row * 2 + n // 4) * 224))
            sheet.save(f'{OUT}/check.png')
            return
        jobs = [(c, l, i) for c in CORES for l in range(8) for i in range(WALKS)]
        results = list(pool.map(walk, jobs))
    print('level  ' + '  '.join(f'{c:>22}' for c in CORES))
    print('       ' + '  '.join(f'{"ticks  late  worst":>22}' for _ in CORES))
    totals = {c: collections.Counter() for c in CORES}
    for level in range(8):
        cells = []
        for c in CORES:
            gaps = [g for r in results if r[0] == c and r[1] == level for g in r[2] if g < PAUSE]
            totals[c].update(gaps)
            late = sum(g > 5 for g in gaps)
            cells.append(f'{len(gaps):5}  {100 * late / max(1, len(gaps)):3.0f}%  {max(gaps, default=0):5}')
        print(f'{level + 1:5}  ' + '  '.join(f'{x:>22}' for x in cells))
    for c, t in totals.items():
        n = sum(t.values())
        print(f'{c}: {100 * sum(v for g, v in t.items() if g > 5) / n:.1f}% late of {n};',
              ', '.join(f'{g}: {100 * v / n:.1f}%' for g, v in sorted(t.items())))


if __name__ == '__main__':
    main()

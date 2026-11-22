#!/usr/bin/env python3
"""Compare the original and the patched ROM on a 60 Hz console and a 50 Hz (PAL) one.
    tools/harness/pal_check.py [--core blastem|genesis_plus_gx|picodrive] [--check]

The game never asks which kind of console it's on: it runs one tick every 5 vertical blanks,
so 12 ticks a second at 60 Hz and 10 at 50 Hz. The ROM's header names only the US, so an
emulator left to choose runs it at 60 Hz, and each core here is forced into PAL with its own
options. The runner reports the frame rate the core settled on, and the run stops if it isn't
the one asked for.

For each ROM and rate it plays the same opening, level jumps and random walks as
compare_cores.py, and counts a tick as late when it starts more than 5 frames after the last.
--check only reaches each level at 50 Hz on both ROMs and saves a sheet of pictures, to show
the scripted opening still gets there. Output goes in scratch/pal/, which git ignores.
"""
import collections
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from PIL import Image

import compare_cores as cc

HERE = cc.HERE
ROOT = cc.ROOT
OUT = os.path.join(ROOT, 'scratch', 'pal')
RUNNER = os.path.join(ROOT, 'build', 'runner')
PATCHED = os.path.join(ROOT, 'build', 'immortal-patched.md')
CORES = {   # path, runner options, options for 60 Hz, options for 50 Hz
    'blastem': ('blastem/blastem_libretro.so', ['-b', '0,8,11'],
                ['blastem_region=U', 'blastem_force_region=on'],
                ['blastem_region=E', 'blastem_force_region=on']),
    'genesis_plus_gx': ('genesis_plus_gx/genesis_plus_gx_libretro.so', [],
                        ['genesis_plus_gx_region_detect=ntsc-u'], ['genesis_plus_gx_region_detect=pal']),
    'picodrive': ('picodrive/picodrive_libretro.so', [], ['picodrive_region=US'], ['picodrive_region=Europe']),
}
RATES = (60, 50)
CORE = 'blastem'


def original():
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    import romcheck
    return romcheck.find_rom()


def run(rom, rate, *args):
    path, extra, ntsc, pal = CORES[CORE]
    opts = [x for o in (ntsc if rate == 60 else pal) for x in ('-o', o)]
    out = subprocess.run([RUNNER, os.path.join(ROOT, 'build', 'cores', path), rom, *extra, *opts,
                          *map(str, args)], check=True, stdout=subprocess.DEVNULL,
                         stderr=subprocess.PIPE, text=True, errors='replace').stderr
    fps = [float(l.split()[1]) for l in out.splitlines() if l.startswith('fps ')]
    if not fps or round(fps[0] / 10) * 10 != rate:
        raise SystemExit(f'{CORE} ran at {fps} fps, not {rate} Hz')


def name(rom):
    return 'patched' if rom == PATCHED else 'original'


def check(job):
    rom, level = job
    base = f'{OUT}/{CORE}_{name(rom)}_check{level}'
    with open(base + '.txt', 'w') as f:
        f.write(cc.script(level, 0, False))
    run(rom, 50, '-n', cc.START, '-x', 1, '-i', base + '.txt', *cc.jump(level),
        '-s', f'{cc.START - 1}:{base}.png', '-m', base + '.ram')
    ram = open(base + '.ram', 'rb').read()
    return name(rom), level, ram[0x1070], ram[0x1051]


def walk(job):
    rom, rate, level, i = job
    base = f'{OUT}/{CORE}_{name(rom)}_{rate}_{level}_{i}'
    with open(base + '.txt', 'w') as f:
        f.write(cc.script(level, i))
    run(rom, rate, '-q', '-n', cc.START + cc.FRAMES, '-i', base + '.txt', *cc.jump(level),
        '-W', f'{cc.DEADLINE}:{base}.w')
    values = [int(x) for x in open(base + '.w')]
    ticks = [f for f in range(cc.START + 1, len(values)) if values[f] != values[f - 1]]
    return rom, rate, level, [b - a for a, b in zip(ticks, ticks[1:])]


def main():
    global CORE
    if '--core' in sys.argv:
        CORE = sys.argv[sys.argv.index('--core') + 1]
    roms = [original(), PATCHED]
    os.makedirs(OUT, exist_ok=True)
    with ThreadPoolExecutor(os.cpu_count()) as pool:
        if '--check' in sys.argv:
            for r in pool.map(check, [(r, l) for r in roms for l in range(8)]):
                print(*r)
            sheet = Image.new('RGB', (1280, 896))
            for row, rom in enumerate(roms):
                for n in range(8):
                    im = Image.open(f'{OUT}/{CORE}_{name(rom)}_check{n}.png').convert('RGB').resize((320, 224))
                    sheet.paste(im, ((n % 4) * 320, (row * 2 + n // 4) * 224))
            sheet.save(f'{OUT}/{CORE}_check.png')
            return
        jobs = [(r, rate, l, i) for r in roms for rate in RATES for l in range(8) for i in range(cc.WALKS)]
        results = list(pool.map(walk, jobs))
    columns = [(r, rate) for r in roms for rate in RATES]
    print(f'{CORE}: ticks, the share late, and the longest gap in frames')
    print('level  ' + '  '.join(f'{name(r) + " " + str(rate) + " Hz":>20}' for r, rate in columns))
    totals = {c: collections.Counter() for c in columns}
    for level in range(8):
        cells = []
        for r, rate in columns:
            gaps = [g for x in results if x[:3] == (r, rate, level) for g in x[3] if g < cc.PAUSE]
            totals[r, rate].update(gaps)
            late = sum(g > 5 for g in gaps)
            cells.append(f'{len(gaps):5} {100 * late / max(1, len(gaps)):5.1f}% {max(gaps, default=0):4}')
        print(f'{level + 1:5}  ' + '  '.join(f'{x:>20}' for x in cells))
    cells = []
    for c in columns:
        n = sum(totals[c].values())
        cells.append(f'{n:5} {100 * sum(v for g, v in totals[c].items() if g > 5) / max(1, n):5.1f}%     ')
    print('  all  ' + '  '.join(f'{x:>20}' for x in cells))


if __name__ == '__main__':
    main()

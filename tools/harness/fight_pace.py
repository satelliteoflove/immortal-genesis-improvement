#!/usr/bin/env python3
"""Compare the pace of fights on the original ROM and the patched one.

    tools/harness/fight_pace.py [ROM ...]

A fight has two loops, each drawing one picture a time round. This counts the frames from
one picture to the next in each loop, on level 7, which opens with a fight, over the same
four scripted runs for each ROM. With no ROMs named it compares the original with
build/immortal-patched.md. Runs on our build of the BlastEm fork.
"""
import collections
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import compare_cores as cc
import fork_timing as ft

LEVEL = 6
LOOPS = (('main loop', '1169c'), ('animation', '1177a'))     # the instruction after each loop's drawing
OUT = os.path.join(ft.ROOT, 'scratch', 'fight-pace')


def run(job):
    rom, walk = job
    base = f'{OUT}/{abs(hash(rom)) % 9999}_{walk}'
    with open(base + '.script', 'w') as f:
        f.write(ft.fork_script(LEVEL, walk))
    with open(base + '.init', 'w') as f:
        f.write(f'script {base}.script\n' + ''.join(f'prof lap l{i} {a}\n' for i, (_, a) in enumerate(LOOPS))
                + 'prof log on\n')
    env = {**os.environ, 'HOME': ft.HOME, 'SDL_VIDEODRIVER': 'dummy', 'SDL_AUDIODRIVER': 'dummy',
           'BLASTEM_NO_GUI': '1', 'BLASTEM_KIT_INIT': base + '.init'}
    out = subprocess.run([ft.BLASTEM, '-b', str(cc.START + cc.FRAMES), rom], env=env, capture_output=True,
                         text=True, errors='replace', timeout=300).stdout
    frames = collections.defaultdict(list)
    for line in out.splitlines():
        if 'KIT PROF' in line:
            frame = int(re.search(r'frame=(\d+)', line).group(1))
            for name, hits in re.findall(r'l(\d)=\d+:(\d+)', line):
                if int(hits) and frame >= cc.START:
                    frames[int(name)].append(frame)
    return rom, frames


def main():
    roms = [os.path.abspath(r) for r in sys.argv[1:]] or [ft.ROM, os.path.join(ft.ROOT, 'build', 'immortal-patched.md')]
    os.makedirs(OUT, exist_ok=True)
    gaps = {r: collections.defaultdict(collections.Counter) for r in roms}
    with ThreadPoolExecutor(os.cpu_count()) as pool:
        for rom, frames in pool.map(run, [(r, w) for r in roms for w in range(cc.WALKS)]):
            for loop, at in frames.items():
                gaps[rom][loop].update(b - a for a, b in zip(at, at[1:]) if b - a <= 30)
    for i, (name, _) in enumerate(LOOPS):
        for rom in roms:
            count = gaps[rom][i]
            total = sum(count.values())
            if not total:
                print(f'{name:10} {os.path.basename(rom)[:28]:28} no fight seen')
                continue
            mean = sum(g * n for g, n in count.items()) / total
            most = ', '.join(f'{g} frames {100 * n // total}%' for g, n in count.most_common(4))
            print(f'{name:10} {os.path.basename(rom)[:28]:28} {total:4} pictures, {mean:5.2f} frames apart ({most})')


if __name__ == '__main__':
    main()

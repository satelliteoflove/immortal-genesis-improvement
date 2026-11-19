#!/usr/bin/env python3
"""Show where the 68000's time goes on each level, grouped by routine.

    tools/harness/hotspots.py [rom]

Boots ROM (the patched one by default) in the profiling core, jumps to each level as
compare_cores.py does, walks at random and adds up cycles. Routines are the sub_ labels
in disasm/immortal.dis, so run tools/disasm.py first, plus the patch's relocated routine.
Time spent waiting (for the next tick, for vertical blank, in timed pauses) is shown apart.
Output goes in scratch/hotspots/, which git ignores.
"""
import bisect
import collections
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import compare_cores as cc

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, 'scratch', 'hotspots')
CORE = os.path.join(ROOT, 'build', 'picodrive_trace_libretro.so')
WAITS = ((0x1349C, 0x134A7),     # the main loop, until the next tick is due
         (0x14E06, 0x14E0B),     # reading the pad variable, nearly always from a pause
         (0x14E3A, 0x14E6D),     # the two waits for vertical blank
         (0x153DA, 0x15405),     # timed pauses
         (0xD2DE, 0xD317),       # the YES/NO prompt, polling until the choice changes
         (0x134BE, 0x134C3),     # which reads the pad through these two
         (0x15466, 0x15481))
PATCH_ROUTINES = [0x2E480, 0x2E540, 0x2E5C0]   # the patch's routines inside the old 02E3E4's space
TOP = 12


def routines():
    starts = []
    pending = False
    for line in open(os.path.join(ROOT, 'disasm', 'immortal.dis'), errors='replace'):
        if line.startswith(('sub_', 'vector_')):
            pending = True
        elif pending and re.match(r'[0-9a-f]{6}  ', line):
            starts.append(int(line[:6], 16))
            pending = False
    return sorted({*starts, *PATCH_ROUTINES})


def run(rom, level, walk):
    base = f'{OUT}/{level}_{walk}'
    with open(base + '.in', 'w') as f:
        f.write(cc.script(level, walk))
    args = ['-q', '-n', str(cc.START + cc.FRAMES), '-i', base + '.in',
            '-p', f'{cc.JUMP}:ff1088=1', '-p', f'{cc.JUMP}:ff1091={level:x}', '-p', f'{cc.JUMP}:ff1073=1',
            '-P', f'{cc.START}:{cc.START + cc.FRAMES - 1}:{base}.prof']
    subprocess.run([os.path.join(HERE, 'run.sh'), *args], check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, timeout=280, env={**os.environ, 'ROM': rom, 'CORE': CORE})
    return level, base + '.prof'


def main():
    rom = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'build', 'immortal-patched.md')
    os.makedirs(OUT, exist_ok=True)
    starts = routines()
    jobs = [(rom, l, w) for l in range(8) for w in range(cc.WALKS)]
    with ThreadPoolExecutor(os.cpu_count()) as pool:
        done = list(pool.map(lambda j: run(*j), jobs))
    per_level = collections.defaultdict(collections.Counter)
    for level, path in done:
        for line in open(path):
            address, _hits, cycles = line.split()
            address = int(address, 16)
            waiting = any(low <= address <= high for low, high in WAITS)
            name = 'waiting' if waiting else starts[max(bisect.bisect_right(starts, address) - 1, 0)]
            per_level[level][name] += int(cycles)
    every = collections.Counter()
    for level in range(8):
        every.update(per_level[level])
        total = sum(per_level[level].values())
        busy = total - per_level[level]['waiting']
        parts = [f'{k:06x} {100 * v / busy:.0f}%' for k, v in per_level[level].most_common(TOP + 1) if k != 'waiting'][:7]
        print(f'level {level + 1}: waiting {100 * per_level[level]["waiting"] / total:.0f}%  busy: ' + '  '.join(parts))
    busy = sum(every.values()) - every['waiting']
    print('\nall levels, share of busy time:')
    for k, v in [x for x in every.most_common(TOP + 1) if x[0] != 'waiting'][:TOP]:
        print(f'  {k:06x}  {100 * v / busy:5.1f}%')


if __name__ == '__main__':
    main()

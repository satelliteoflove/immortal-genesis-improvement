#!/usr/bin/env python3
"""Time the game on our build of the BlastEm fork, and check the profiler is harmless.

    tools/harness/fork_timing.py

Uses the same opening, level jumps and random walks as compare_cores.py. Before
trusting the timing it checks two things from the fork's per-frame hash of video
memory: the same run twice gives the same hashes, and turning the profiler on
doesn't change them. Output goes in scratch/fork-timing/, which git ignores.
"""
import glob
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import compare_cores as cc

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, 'scratch', 'fork-timing')
BLASTEM = os.environ.get('BLASTEM', os.path.join(ROOT, 'build', 'blastem-fork', 'blastem'))
HOME = os.path.join(ROOT, 'build', 'blastem-home')
ROM = os.environ.get('ROM', sorted(glob.glob(os.path.join(ROOT, 'rom', '*')))[0])
TICK = '134a8'
OBJECT_GRAPHICS = ('2e3e4', '2f4e0')
PROF = re.compile(r'KIT PROF frame=(\d+) total=(\d+) tick=(\d+):(\d+) objgfx=(\d+):(\d+)')
HASH = re.compile(r'KIT VHASH frame=(\d+) hash=(\w+)')
PEEK = re.compile(r'peek ff1070 (\w+)')


def fork_script(level, walk):
    """The harness's input script, as the fork's press and release events."""
    events, held = [], set()
    rows = []
    for line in cc.script(level, walk).splitlines():
        frame, _port, buttons = line.split(None, 2)
        rows.append((int(frame), set() if buttons == '-' else {b.lower() for b in buttons.split('+')}))
    for frame, now in sorted(rows, key=lambda r: r[0]):
        events += [(frame, f'{frame} up 1 {b}') for b in sorted(held - now)]
        events += [(frame, f'{frame} down 1 {b}') for b in sorted(now - held)]
        held = now
    events += [(cc.JUMP, f'{cc.JUMP} poke ff1088 1'), (cc.JUMP, f'{cc.JUMP} poke ff1091 {level:x}'),
               (cc.JUMP, f'{cc.JUMP} poke ff1073 1'), (cc.START - 1, f'{cc.START - 1} peek ff1070')]
    return '\n'.join(text for _, text in sorted(events, key=lambda e: e[0])) + '\n'


def run(level, walk, tag, profile=True):
    base = f'{OUT}/{tag}_{level}_{walk}'
    with open(base + '.script', 'w') as f:
        f.write(fork_script(level, walk))
    init = [f'script {base}.script', 'vramhash on']
    if profile:
        init += [f'prof lap tick {TICK}', f'prof bracket objgfx {OBJECT_GRAPHICS[0]} {OBJECT_GRAPHICS[1]}', 'prof log on']
    with open(base + '.init', 'w') as f:
        f.write('\n'.join(init) + '\n')
    env = {**os.environ, 'HOME': HOME, 'SDL_VIDEODRIVER': 'dummy', 'SDL_AUDIODRIVER': 'dummy',
           'BLASTEM_NO_GUI': '1', 'BLASTEM_KIT_INIT': base + '.init'}
    done = subprocess.run([BLASTEM, '-b', str(cc.START + cc.FRAMES), ROM], env=env, capture_output=True,
                          text=True, errors='replace', timeout=300)
    out = done.stdout
    hashes = HASH.findall(out)
    reached = PEEK.search(out)
    if done.returncode or len(hashes) < cc.START + cc.FRAMES - 1 or not reached:
        with open(base + '.failed', 'w') as f:
            f.write(f'exit {done.returncode}, {len(hashes)} frames, reached {reached}\n--- stderr\n{done.stderr}'
                    f'\n--- end of stdout\n{out[-1500:]}')
        raise RuntimeError(f'{tag} level {level + 1} walk {walk} failed; see {base}.failed')
    spans, last, spent = [], None, 0
    for frame, _total, _cycles, hits, obj, _objhits in PROF.findall(out):
        frame = int(frame)
        if frame <= cc.START:
            continue
        spent += int(obj)
        if int(hits):
            if last is not None:
                spans.append((frame - last, spent))
            last, spent = frame, 0
    return {'level': level, 'walk': walk, 'hashes': hashes, 'spans': spans,
            'reached': int(reached.group(1), 16) if reached else None}


def mean(values):
    return sum(values) / len(values) if values else 0


def main():
    if not os.path.exists(BLASTEM):
        sys.exit('build it first: tools/harness/build_blastem_fork.sh')
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(HOME, exist_ok=True)
    jobs = [(l, w) for l in range(8) for w in range(cc.WALKS)]
    with ThreadPoolExecutor(os.cpu_count()) as pool:
        main_runs = list(pool.map(lambda j: run(j[0], j[1], 'a'), jobs))
        again = list(pool.map(lambda l: run(l, 0, 'b'), range(8)))
        bare = list(pool.map(lambda l: run(l, 0, 'c', profile=False), range(8)))
    first = {r['level']: r for r in main_runs if r['walk'] == 0}
    repeat = sum(r['hashes'] == first[r['level']]['hashes'] for r in again)
    unprofiled = sum(r['hashes'] == first[r['level']]['hashes'] for r in bare)
    frames = len(first[0]['hashes'])
    print(f'{frames} hashed frames a run. Same on a second run: {repeat}/8 levels. '
          f'Same with the profiler off: {unprofiled}/8 levels.')
    wrong = [r['level'] for r in main_runs if r['reached'] != r['level']]
    print('levels reached as asked:', 'all' if not wrong else f'NOT {sorted(set(wrong))}')
    print('\nlevel  ticks  late  worst  object-graphics cycles a tick (on time / late)')
    every = []
    for level in range(8):
        spans = [s for r in main_runs if r['level'] == level for s in r['spans'] if s[0] < cc.PAUSE]
        every += spans
        on = [c for g, c in spans if g <= 5]
        late = [c for g, c in spans if g > 5]
        print(f'{level + 1:5}  {len(spans):5}  {100 * len(late) / max(1, len(spans)):3.0f}%  '
              f'{max((g for g, _ in spans), default=0):5}  {mean(on) / 1000:6.0f}k / {mean(late) / 1000:.0f}k')
    late = sum(g > 5 for g, _ in every)
    print(f'\nall levels: {100 * late / len(every):.1f}% late of {len(every)} ticks')


if __name__ == '__main__':
    main()

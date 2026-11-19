#!/usr/bin/env python3
"""Time the game's opening message with nothing held, one button held and two held.

    tools/harness/text_pace.py [ROM ...]

The opening message is typed out a page at a time, starting around frame 1,170. Each run
plays the same opening, then holds the named buttons from frame 1,150 on. For each page it
prints how many letters were typed, over how many frames, and the pause before the next
page. With no ROMs named it compares the original with build/immortal-patched.md. Runs on
our build of the BlastEm fork.
"""
import collections
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import fork_timing as ft

LETTER = '13414'            # where a letter's sprite is added
HOLD_FROM, END = 1150, 2600
HOLDS = (('nothing held', ()), ('C held', ('c',)), ('A held', ('a',)), ('A and B held', ('a', 'b')))
OUT = os.path.join(ft.ROOT, 'scratch', 'text-pace')


def opening():
    """The harness's opening inputs up to the first message, as the fork's press and release events."""
    events, held = [], set()
    with open(os.path.join(ft.HERE, 'input', 'first_room.txt')) as f:
        rows = [line.split(None, 2) for line in f if line.strip() and not line.startswith('#')]
    for frame, _port, buttons in rows:
        if int(frame) >= HOLD_FROM:
            break
        now = set() if buttons.strip() == '-' else {b.lower() for b in buttons.strip().split('+')}
        events += [f'{frame} up 1 {b}' for b in sorted(held - now)] + [f'{frame} down 1 {b}' for b in sorted(now - held)]
        held = now
    return events


def run(job):
    rom, (name, buttons) = job
    base = f'{OUT}/{abs(hash(rom)) % 9999}_{"".join(buttons) or "none"}'
    with open(base + '.script', 'w') as f:
        f.write('\n'.join(opening() + [f'{HOLD_FROM} down 1 {b}' for b in buttons]) + '\n')
    with open(base + '.init', 'w') as f:
        f.write(f'script {base}.script\nprof lap letter {LETTER}\nprof log on\n')
    env = {**os.environ, 'HOME': ft.HOME, 'SDL_VIDEODRIVER': 'dummy', 'SDL_AUDIODRIVER': 'dummy',
           'BLASTEM_NO_GUI': '1', 'BLASTEM_KIT_INIT': base + '.init'}
    out = subprocess.run([ft.BLASTEM, '-b', str(END), rom], env=env, capture_output=True, text=True,
                         errors='replace', timeout=300).stdout
    letters = collections.Counter()
    for line in out.splitlines():
        found = re.search(r'KIT PROF frame=(\d+).* letter=\d+:(\d+)', line)
        if found and int(found.group(2)) and int(found.group(1)) >= HOLD_FROM:
            letters[int(found.group(1))] += int(found.group(2))
    pages, frames = [], sorted(letters)
    for frame in frames:
        if not pages or frame - pages[-1][-1] > 30:
            pages.append([])
        pages[-1].append(frame)
    return rom, name, [(p[0], p[-1], sum(letters[f] for f in p)) for p in pages]


def main():
    roms = [os.path.abspath(r) for r in sys.argv[1:]] or [ft.ROM, os.path.join(ft.ROOT, 'build', 'immortal-patched.md')]
    os.makedirs(OUT, exist_ok=True)
    with ThreadPoolExecutor(os.cpu_count()) as pool:
        results = list(pool.map(run, [(r, h) for r in roms for h in HOLDS]))
    for name, _ in HOLDS:
        print(name)
        for rom, held, pages in results:
            if held != name:
                continue
            parts = []
            for i, (first, last, count) in enumerate(pages[:4]):
                pause = f', then {pages[i + 1][0] - last} frames' if i + 1 < len(pages) else ''
                parts.append(f'{count} letters in {last - first + 1} frames ({60 * count / (last - first + 1):.0f} a second){pause}')
            print(f'  {os.path.basename(rom)[:22]:22} ' + ' | '.join(parts))


if __name__ == '__main__':
    main()

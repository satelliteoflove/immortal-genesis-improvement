#!/usr/bin/env python3
"""Compare the sound chip writes two ROMs make over the same scripted walks.

    tools/harness/sound_writes.py ROM_A ROM_B

Each walk is run on both ROMs in our build of the BlastEm fork, which logs every write
to the YM2612 and the PSG as a VGM file. Video memory is compared frame by frame as
well, since the sound can only match if the game itself went the same way.

A ROM against itself matches write for write. Two ROMs whose timing differs at all
don't, because the game goes a different way from the title screen on, so this can't
prove that a change which saves time leaves the sound alone. What it's good for is the
logs: scratch/sound/ (which git ignores) ends up with a VGM file for every walk, which
can be read for what the game sends, or played.
"""
import os
import struct
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import compare_cores as cc
import fork_timing as ft

OUT = os.path.join(ft.ROOT, 'scratch', 'sound')


def run(rom, level, walk, tag):
    base = f'{OUT}/{tag}_{level}_{walk}'
    with open(base + '.script', 'w') as f:
        f.write(ft.fork_script(level, walk))
    with open(base + '.init', 'w') as f:
        f.write(f'script {base}.script\nvramhash on\nvgm {base}.vgm\n')
    if os.path.exists(base + '.vgm'):
        os.remove(base + '.vgm')
    env = {**os.environ, 'HOME': ft.HOME, 'SDL_VIDEODRIVER': 'dummy', 'SDL_AUDIODRIVER': 'dummy',
           'BLASTEM_NO_GUI': '1', 'BLASTEM_KIT_INIT': base + '.init'}
    done = subprocess.run([ft.BLASTEM, '-b', str(cc.START + cc.FRAMES), rom], env=env, capture_output=True,
                          text=True, errors='replace', timeout=300)
    hashes = ft.HASH.findall(done.stdout)
    if done.returncode or len(hashes) < cc.START + cc.FRAMES - 1 or not os.path.exists(base + '.vgm'):
        raise RuntimeError(f'{tag} level {level + 1} walk {walk} failed')
    return writes(base + '.vgm'), hashes


def writes(path):
    """The log as (time in 44,100ths of a second, chip, register, value)."""
    with open(path, 'rb') as f:
        d = f.read()
    version, offset = struct.unpack_from('<I', d, 8)[0], struct.unpack_from('<I', d, 0x34)[0]
    at = 0x34 + offset if version >= 0x150 and offset else 0x40
    time, out = 0, []
    while at < len(d):
        c = d[at]
        if c in (0x52, 0x53):
            out.append((time, c, d[at + 1], d[at + 2]))
            at += 3
        elif c == 0x50:
            out.append((time, c, 0, d[at + 1]))
            at += 2
        elif c == 0x61:
            time += d[at + 1] | d[at + 2] << 8
            at += 3
        elif c in (0x62, 0x63):
            time += 735 if c == 0x62 else 882
            at += 1
        elif 0x70 <= c <= 0x7F:
            time += (c & 15) + 1
            at += 1
        elif 0x80 <= c <= 0x8F:
            out.append((time, c, 0, 0))
            time += c & 15
            at += 1
        elif c == 0x67:
            at += 7 + struct.unpack_from('<I', d, at + 3)[0]
        elif c == 0xE0:
            at += 5
        elif c == 0x66:
            break
        else:
            sys.exit(f'{path}: VGM command {c:02x} not handled')
    return out


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    roms = [os.path.abspath(p) for p in sys.argv[1:]]
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(ft.HOME, exist_ok=True)
    jobs = [(l, w) for l in range(8) for w in range(cc.WALKS)]
    with ThreadPoolExecutor(os.cpu_count()) as pool:
        a = list(pool.map(lambda j: run(roms[0], j[0], j[1], 'a'), jobs))
        b = list(pool.map(lambda j: run(roms[1], j[0], j[1], 'b'), jobs))
    total = same_sound = same_video = 0
    furthest = 0
    for (level, walk), (wa, ha), (wb, hb) in zip(jobs, a, b):
        total += len(wa)
        video = ha == hb
        sound = [w[1:] for w in wa] == [w[1:] for w in wb]
        same_video += video
        same_sound += sound
        if sound:
            furthest = max([furthest] + [abs(x[0] - y[0]) for x, y in zip(wa, wb)])
        else:
            first = next((i for i, (x, y) in enumerate(zip(wa, wb)) if x[1:] != y[1:]), min(len(wa), len(wb)))
            print(f'level {level + 1} walk {walk}: writes differ from number {first} of {len(wa)} and {len(wb)}'
                  f'{"" if video else " (video differs too)"}')
    print(f'{len(jobs)} walks, {total} sound chip writes in the first ROM')
    print(f'same writes in the same order: {same_sound}/{len(jobs)} walks')
    print(f'same video memory on every frame: {same_video}/{len(jobs)} walks')
    print(f'largest move in time: {furthest} samples at 44,100 a second ({furthest / 44.1:.2f} ms)')
    sys.exit(0 if same_sound == len(jobs) else 1)


if __name__ == '__main__':
    main()

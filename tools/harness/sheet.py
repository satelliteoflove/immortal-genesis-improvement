#!/usr/bin/env python3
"""Run the game and lay evenly spaced frames out on one contact sheet.

    tools/harness/sheet.py OUT.png FIRST STEP COUNT [runner options]

The sheet shows the game, so it belongs in scratch/, which git ignores.
"""
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
COLUMNS = 4


def main():
    if len(sys.argv) < 5:
        sys.exit(__doc__)
    out, first, step, count = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    frames = [first + step * i for i in range(count)]
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [os.path.join(HERE, 'run.sh'), '-q', '-x', '1', '-n', str(frames[-1] + 1)] + sys.argv[5:]
        for f in frames:
            cmd += ['-s', f'{f}:{tmp}/{f}.png']
        subprocess.run(cmd, check=True, stderr=subprocess.DEVNULL)
        shots = [Image.open(f'{tmp}/{f}.png').convert('RGB') for f in frames]
    w, h = shots[0].size
    rows = (count + COLUMNS - 1) // COLUMNS
    sheet = Image.new('RGB', (w * COLUMNS, h * rows))
    draw = ImageDraw.Draw(sheet)
    for i, (f, shot) in enumerate(zip(frames, shots)):
        x, y = (i % COLUMNS) * w, (i // COLUMNS) * h
        sheet.paste(shot, (x, y))
        draw.rectangle((x, y, x + 34, y + 11), fill=(0, 0, 0))
        draw.text((x + 2, y), str(f), fill=(255, 255, 0))
    sheet.save(out)


if __name__ == '__main__':
    main()

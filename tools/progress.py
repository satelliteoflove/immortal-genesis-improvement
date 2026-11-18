#!/usr/bin/env python3
"""Add an entry to the progress page and rebuild it.

    tools/progress.py "Title" "What changed, what to look at." shot.png clip.mp4 ...
    tools/progress.py "Title" "Note." --ours chart.png -- shot.png
    tools/progress.py                 (rebuilds the page only)

Files go to docs/progress/local/, which git ignores, because screenshots, clips
and recordings of the game are the game's. Files after --ours are things we made
ourselves, such as charts with nothing of the game in them; those go to
docs/progress/ours/ and are tracked. A bare -- goes back to local files.

The page and its entries are tracked, so a fresh clone has the whole written
record, and simply doesn't show the local files it hasn't got.

Open docs/progress/index.html directly, or serve it over the LAN with
    python3 -m http.server 8080 --bind 0.0.0.0 --directory docs/progress
"""
import html
import json
import os
import shutil
import subprocess
import sys
import time
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'docs', 'progress')
LOG = os.path.join(OUT, 'entries.json')
TITLE = 'The Immortal (Genesis patch): progress'

CSS = """
body { font: 16px/1.5 system-ui, sans-serif; background: #14161a; color: #dde1e6; margin: 0 auto; max-width: 72rem; padding: 1.5rem; }
h1 { font-size: 1.5rem; margin: 0 0 .25rem; }
.sub { color: #8b93a1; margin-bottom: 2rem; }
article { border-top: 1px solid #2a2e36; padding: 1.25rem 0 1.75rem; }
h2 { font-size: 1.15rem; margin: 0 0 .25rem; }
time { color: #8b93a1; font-size: .85rem; font-variant-numeric: tabular-nums; }
p { margin: .5rem 0 1rem; max-width: 60rem; white-space: pre-line; }
.media { display: flex; flex-wrap: wrap; gap: .75rem; }
figure { margin: 0; }
figcaption { color: #8b93a1; font-size: .8rem; margin-top: .2rem; }
img, video { image-rendering: pixelated; max-width: 100%; border: 1px solid #2a2e36; background: #000; display: block; }
"""

# A clone has no local/ files, so a figure whose file is missing removes itself.
GONE = 'onerror="this.closest(\'figure\').remove()"'


def has_sound(path):
    """Whether a video has a soundtrack (ffprobe finds an audio stream in it)."""
    try:
        r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=index',
                            '-of', 'csv=p=0', path], capture_output=True, text=True, timeout=20)
        return bool(r.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return False


def add_entry(entries, title, note, args):
    stamp = time.strftime('%Y%m%d_%H%M%S')
    folder = 'local'
    files = []
    for arg in args:
        if arg == '--ours':
            folder = 'ours'
        elif arg == '--':
            folder = 'local'
        else:
            if not os.path.isfile(arg):
                sys.exit(f'no such file: {arg}')
            os.makedirs(os.path.join(OUT, folder), exist_ok=True)
            name = f'{folder}/{stamp}_{os.path.basename(arg)}'
            shutil.copy(arg, os.path.join(OUT, name))
            files.append(name)
    entries.append(dict(time=time.strftime('%Y-%m-%d %H:%M'), title=title, note=note, files=files))
    with open(LOG, 'w') as f:
        json.dump(entries, f, indent=1)
        f.write('\n')


def figure(name):
    src = html.escape(quote(name), quote=True)
    cap = html.escape(os.path.basename(name).split('_', 2)[2])
    if name.endswith(('.mp4', '.webm')):
        if has_sound(os.path.join(OUT, name)):
            # browsers won't start a video with sound by itself: this one waits for play
            return (f'<figure><video src="{src}" {GONE} controls loop playsinline preload="metadata" width="640">'
                    f'</video><figcaption>{cap} (with sound)</figcaption></figure>')
        return (f'<figure><video src="{src}" {GONE} controls loop muted autoplay playsinline width="640">'
                f'</video><figcaption>{cap}</figcaption></figure>')
    if name.endswith(('.mp3', '.ogg', '.wav')):
        return (f'<figure><audio src="{src}" {GONE} controls loop preload="none"></audio>'
                f'<figcaption>{cap}</figcaption></figure>')
    return f'<figure><img src="{src}" {GONE} alt=""><figcaption>{cap}</figcaption></figure>'


def build(entries):
    parts = []
    for e in reversed(entries):
        media = ''.join(figure(f) for f in e['files'])
        parts.append(f'<article><time>{html.escape(e["time"])}</time><h2>{html.escape(e["title"])}</h2>'
                     f'<p>{html.escape(e["note"])}</p><div class="media">{media}</div></article>')
    updated = entries[-1]['time'] if entries else 'never'
    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(TITLE)}</title><style>{CSS}</style></head>
<body><h1>{html.escape(TITLE)}</h1>
<div class="sub">Newest first. Last entry {html.escape(updated)}. Reload to see new entries.</div>
{''.join(parts) or '<p>Nothing yet.</p>'}
</body></html>
"""
    with open(os.path.join(OUT, 'index.html'), 'w') as f:
        f.write(page)


def main():
    os.makedirs(OUT, exist_ok=True)
    entries = []
    if os.path.exists(LOG):
        with open(LOG) as f:
            entries = json.load(f)
    if len(sys.argv) == 2:
        sys.exit(__doc__)
    if len(sys.argv) >= 3:
        add_entry(entries, sys.argv[1], sys.argv[2], sys.argv[3:])
    build(entries)


if __name__ == '__main__':
    main()

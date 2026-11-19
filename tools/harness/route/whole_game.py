#!/usr/bin/env python3
"""Play the whole game, from a new game to the closing story, with the eight levels' routes.

    tools/harness/route/whole_game.py [--original] [--delay N] [--quiet]

Each level is played by its own route, as when it's run by itself, but here a level starts
the way the game starts it: after the last level's "End of level!" screen is dismissed, with
whatever the wizard carried out of it. The certificates each level is tested from on its own
are the 1991 walkthrough's, and a level here may begin from a different one (level 3's route
makes `573ff31000e60`, where level 4 by itself starts from `b5fff31001eb0`). So this is the
test that the routes join up, as well as that each one plays.

Exits 1, with a picture in scratch/route/whole/, if any level fails. See docs/playthrough.md.
"""
import argparse
import importlib
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import common
import play

LEVELS = 8


def next_level(g, level, limit=3000):
    """From the "End of level!" screen to the start of the next level, standing where a
    route expects to begin: as play.Game.start_level leaves it."""
    common.read(g)
    start = g.frame
    while not (g.level == level - 1 and not g.var(0xD73)):
        if g.frame - start > limit:
            raise common.RouteError(f'level {level} did not begin within {limit} frames')
        g.step(1)
    g.step(120)


def main():
    parser = argparse.ArgumentParser(description='Play the whole game with the levels\' routes.')
    parser.add_argument('--original', action='store_true', help='the original ROM, not the patched')
    parser.add_argument('--delay', type=int, default=0, help='frames to wait before the first press')
    parser.add_argument('--quiet', action='store_true', help="don't print the routes' logs")
    args = parser.parse_args()
    name = 'original' if args.original else 'patched'
    began = time.time()
    with play.Game(play.original() if args.original else play.PATCHED) as g:
        g.new_game()
        g.step(args.delay)
        first = g.frame
        level = 1
        try:
            for level in range(1, LEVELS + 1):
                route = importlib.import_module(f'level{level}')
                if level > 1:
                    next_level(g, level)
                at = g.frame

                def log(*words):
                    if not args.quiet:
                        print(f'  [{g.frame - at:6d}] room {g.room:2d} {common.xy(g)} '
                              f'health {common.health(g):2d}:', *words, flush=True)
                carried = ' '.join(f'{n:02x}' for n in g.things)
                result = route.play(g, log)
                print(f'level {level}: done in {g.frame - at} frames, health {common.health(g)}, '
                      f'retries left {common.retries(g)}, certificate {result}', flush=True)
                if not args.quiet:
                    print(f'  it began carrying {carried}', flush=True)
        except Exception as error:
            path = os.path.join(common.ROOT, 'scratch', 'route', 'whole', f'fail-{name}-delay{args.delay}.png')
            try:
                g.shot(path)
            except Exception:
                path = 'no picture'
            print(f'whole game {name} delay {args.delay}: FAILED on level {level}, {g.frame - first} frames in, '
                  f'room {g.room}, {common.xy(g)}: {type(error).__name__}: {error} (picture: {path})')
            sys.exit(1)
        print(f'whole game {name} delay {args.delay}: passed, {g.frame - first} frames '
              f'({(g.frame - first) / 60 / 60:.1f} minutes of play), {time.time() - began:.0f} s')


if __name__ == '__main__':
    main()

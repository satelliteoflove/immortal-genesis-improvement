#!/bin/bash
# run.sh [runner options]: run the game (or ROM=path) in the headless harness.
root=$(cd "$(dirname "$0")/../.." && pwd)
core=${CORE:-$root/../32xKarts/tools/core/picodrive_libretro.so}
rom=${ROM:-$(ls "$root"/rom/* | head -1)}
exec "$root/build/runner" "$core" "$rom" "$@"

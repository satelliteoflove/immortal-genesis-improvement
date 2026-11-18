#!/bin/bash
# Fetches BlastEm's libretro core into build/cores/blastem/, which git ignores.
set -e
root=$(cd "$(dirname "$0")/../.." && pwd)
dir=$root/build/cores/blastem
mkdir -p "$dir"
[ -f "$dir/blastem_libretro.so" ] && { echo "already have $dir/blastem_libretro.so"; exit 0; }
curl -fsSL -o "$dir/blastem.zip" \
    https://buildbot.libretro.com/nightly/linux/x86_64/latest/blastem_libretro.so.zip
unzip -q -o "$dir/blastem.zip" blastem_libretro.so -d "$dir"
rm -f "$dir/blastem.zip"
echo "fetched $dir/blastem_libretro.so"

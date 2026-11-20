#!/bin/bash
# Fetches Genesis Plus GX's libretro core into build/cores/genesis_plus_gx/, which git ignores.
set -e
root=$(cd "$(dirname "$0")/../.." && pwd)
dir=$root/build/cores/genesis_plus_gx
mkdir -p "$dir"
[ -f "$dir/genesis_plus_gx_libretro.so" ] && { echo "already have $dir/genesis_plus_gx_libretro.so"; exit 0; }
curl -fsSL -o "$dir/genesis_plus_gx.zip" \
    https://buildbot.libretro.com/nightly/linux/x86_64/latest/genesis_plus_gx_libretro.so.zip
unzip -q -o "$dir/genesis_plus_gx.zip" genesis_plus_gx_libretro.so -d "$dir"
rm -f "$dir/genesis_plus_gx.zip"
echo "fetched $dir/genesis_plus_gx_libretro.so"

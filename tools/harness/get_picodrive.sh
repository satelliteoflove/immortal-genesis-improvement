#!/bin/bash
# Fetches PicoDrive's source at a fixed commit into build/picodrive-src/ and builds its
# libretro core, unchanged, into build/cores/picodrive/. Both are under build/, which git
# ignores. build_trace_core.sh builds its patched copy from the same source.
set -e
root=$(cd "$(dirname "$0")/../.." && pwd)
commit=6c66738e8a66fd4b830d2e579c05eba59fa7c7ab
src=$root/build/picodrive-src
out=$root/build/cores/picodrive
if [ ! -d "$src/.git" ]; then
    git clone -q https://github.com/irixxxx/picodrive.git "$src"
fi
cd "$src"
git checkout -q "$commit"
git submodule update -q --init --recursive
if [ ! -f "$out/picodrive_libretro.so" ]; then
    make -f Makefile.libretro -j"$(nproc)" platform=unix > "$root/build/picodrive-build.log" 2>&1
    mkdir -p "$out"
    cp picodrive_libretro.so "$out/"
    git clean -q -fdx                  # leave the source as fetched, for build_trace_core.sh
fi
echo "PicoDrive $(git rev-parse --short HEAD): source in $src, core in $out/picodrive_libretro.so"

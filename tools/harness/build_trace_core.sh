#!/bin/bash
# Builds build/picodrive_trace_libretro.so: PicoDrive with a count of the
# executions and cycles of every 68000 instruction address. It needs PicoDrive's
# source, which 32xKarts keeps in tools/ref/picodrive (commit 6c66738).
set -e
root=$(cd "$(dirname "$0")/../.." && pwd)
src=${PICODRIVE_SRC:-$root/../32xKarts/tools/ref/picodrive}
rm -rf "$root/build/picodrive"
mkdir -p "$root/build"
cp -r "$src" "$root/build/picodrive"
cd "$root/build/picodrive"
git apply "$root/tools/harness/picodrive-trace.patch"
make -f Makefile.libretro -j"$(nproc)" platform=unix > ../trace-build.log 2>&1
cp picodrive_libretro.so ../picodrive_trace_libretro.so
echo "built build/picodrive_trace_libretro.so"

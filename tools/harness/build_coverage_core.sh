#!/bin/bash
# Builds build/blastem-cov/libblastem.so: a libretro core from the BlastEm fork in
# build/blastem-fork (build_blastem_fork.sh makes it), with the 68000 interpreter in place of
# the recompiler and a count of the executions of every instruction address. The runner's
# "prof FILE" command writes the counts; set PLAY_CORE to this file for play.py to use it.
# The interpreter's timing isn't quite the recompiler's, so a route can play out
# differently on it. It's for seeing which code runs, not for timing.
set -e
root=$(cd "$(dirname "$0")/../.." && pwd)
dir=$root/build/blastem-cov
[ -d "$root/build/blastem-fork" ] || { echo "build the fork first: tools/harness/build_blastem_fork.sh"; exit 1; }
rm -rf "$dir"
cp -r "$root/build/blastem-fork" "$dir"
cd "$dir"
make clean > /dev/null 2>&1 || true
git apply "$root/tools/harness/blastem-fork/coverage/0001-count-instructions.patch"
make CPU=x86_64 NEW_CORE=1 -j"$(nproc)" libblastem.so > ../blastem-cov-build.log 2>&1
echo "built build/blastem-cov/libblastem.so"

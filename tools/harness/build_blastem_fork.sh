#!/bin/bash
# Builds build/blastem-fork/blastem from a clean clone of ulalume/blastem at a fixed
# commit, with our patches on top. Needs SDL2 and GLEW (libsdl2-dev, libglew-dev).
#   blastem-fork/fixes/    bugs we fixed; see docs/blastem-fork-fixes.md
#   blastem-fork/harness/  additions only this project needs
set -e
commit=5702187402276e7f0aea2ad4e6784ffb187c8c10
root=$(cd "$(dirname "$0")/../.." && pwd)
patches=$root/tools/harness/blastem-fork
dir=$root/build/blastem-fork
rm -rf "$dir"
git clone -q https://github.com/ulalume/blastem.git "$dir"
cd "$dir"
git checkout -q "$commit"
for p in "$patches"/fixes/*.patch "$patches"/harness/*.patch; do
    git apply "$p"
done
make CPU=x86_64 -j"$(nproc)" blastem > ../blastem-fork-build.log 2>&1
echo "built build/blastem-fork/blastem"

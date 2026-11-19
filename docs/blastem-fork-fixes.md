# Fixes to the BlastEm fork

We build [ulalume/blastem](https://github.com/ulalume/blastem) at commit `5702187`, which
is synced with BlastEm up to upstream changeset `6e255c36d1fa`. This file tracks what we
fixed there, so the fixes can be offered back later. Nothing has been submitted yet.

`tools/harness/build_blastem_fork.sh` applies these patches to a clean clone. Each fix is
also a single commit on its own branch, made from the fork's commit, in
`build/blastem-fork-src`. That folder can be thrown away, so the patch files are the lasting
copy. Commits meant for those projects carry no AI attribution.

## Fixes

### 1. The build fails with `NOGL=1`

- **Patch:** `tools/harness/blastem-fork/fixes/0001-fix-no-opengl-build.patch`
- **Branch:** `fix/no-opengl-build`
- **Problem:** `render_framebuffer_updated()` reads `texture_buf` from an extra window, but
  that field only exists when OpenGL is enabled, so compiling with `DISABLE_OPENGL` stops
  with an error.
- **Fix:** without OpenGL, pass the main buffer. `process_framebuffer()` only uses the buffer
  for the main picture in that configuration.
- **Tested:** the fork builds with `NOGL=1` and runs the game headless, with the same video
  memory on every frame as the normal OpenGL build. Debug windows weren't tried. Our own build
  uses OpenGL now, so it doesn't rely on this fix.
- **Upstream:** the same line is in upstream `render_sdl.c`, so the same failure is likely
  there. We haven't built upstream to confirm it.

### 2. Headless mode counts every frame twice

- **Patch:** `tools/harness/blastem-fork/fixes/0002-count-each-frame-once-headless.patch`
- **Branch:** `fix/headless-frame-count`
- **Problem:** `pushed_frame` is only set when a frame goes to the renderer, which never
  happens with `-b`. `advance_output_line()` then treats the end of the active display as a
  second end of frame. `-b N` stops after N/2 frames, and per-frame hooks such as the fork's
  profiler and scripts run on a clock going twice as fast as the game.
- **Fix:** set `pushed_frame` whether or not there's a renderer.
- **Tested:** over 100 script frames the game's own vertical blank counter now goes up by
  100, where it went up by 50 before. Each profiler frame reports about 128,000 cycles, where
  before they alternated between about 1,000 and 127,000.
- **Upstream:** the same code is in upstream `vdp.c`. We haven't run upstream to confirm it.

### 3. Generated code can land out of range, stopping the emulator at startup

- **Patch:** `tools/harness/blastem-fork/fixes/0003-keep-generated-code-in-range.patch`
- **Branch:** `fix/code-allocation-range`
- **Problem:** `alloc_code()` passes `mmap` an address near the executable, but without
  `MAP_FIXED` that's only a hint. If the kernel places the block elsewhere, generated code can be
  too far away for a 32-bit call, and the emulator stops with "out of range for a 32-bit
  displacement". With address space randomization it depends on the run.
- **Fix:** check where the block landed, and if it's out of range, release it and try further
  addresses. After 32 tries it keeps what it got, which is what it always did.
- **Tested:** we started the emulator 30,000 times before and after. It failed 37 times without
  the fix and not at all with it.
- **Upstream:** not checked yet, because retrodev.com wasn't reachable when this was written.

## Seen but not looked into

A write to `A14000` crashes the headless build with a segfault in `machine_freeze()`, called
from `unused_write`. A test ROM of ours did this by accident. We haven't worked out why, or
whether it also happens with a window open.

Binding a controller in the menus (Settings, Controllers, Bindings) is close to unusable. As
reported from use: a press is taken at once, the menu moves to the next input, and the same press
is taken for that one too unless the button is already up again. It probably wants to wait for
the button to be let go before listening for the next. Not looked into yet.

## Additions only this project needs

`tools/harness/blastem-fork/harness/0001-control-file-poke-peek.patch` (branch
`immortal-harness`) lets a headless run take its control commands from a file named by
`BLASTEM_KIT_INIT`, and adds `poke` and `peek` of work RAM to scripts. It isn't a bug fix, and
it's kept apart from the fixes above. It might interest the fork's author, but it pokes RAM
without any regard for code translated from it, so it would want a closer look first.

`tools/harness/blastem-fork/harness/0002-control-file-vgm-log.patch` (same branch) adds a
`vgm <path>` control command, which starts the emulator's own VGM log of sound chip writes, and
`vgm off`, which stops it. The emulator could already do this from a key binding, but not from a
headless run. A log that's still open when a `-b` run ends is left with an empty header, though
its data is all there.

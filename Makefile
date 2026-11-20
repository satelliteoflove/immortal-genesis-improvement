# Test harness for the unmodified game. The ROM goes in rom/ (see README.md).
B := build
ROM := $(firstword $(wildcard rom/*))
# PicoDrive's libretro core, as tools/harness/get_picodrive.sh builds it.
CORE ?= build/cores/picodrive/picodrive_libretro.so

all: $(B)/runner

$(B):
	mkdir -p $@

$(B)/runner: tools/harness/runner.c tools/harness/libretro.h | $(B)
	cc -O2 -Wall -Itools/harness -o $@ $< -ldl -lz

check:
	tools/romcheck.py

.PHONY: all check

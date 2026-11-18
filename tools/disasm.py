#!/usr/bin/env python3
"""Disassemble the ROM by following its code from the 68000's vectors.

    tools/disasm.py [--entry HEX]... [--entries FILE]

Writes disasm/immortal.dis, which git ignores, since it is the game's code.
Anything not reached from the entry points is left out, so indirect jumps show
up as gaps until their targets are added with --entry or an entries file (one
hex address a line, # for comments).
"""
import argparse
import glob
import os
import re
import struct

from capstone import CS_ARCH_M68K, CS_MODE_BIG_ENDIAN, CS_MODE_M68K_000, Cs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENDS = {'rts', 'rte', 'rtr', 'illegal', 'stop'}
JUMPS = {'bra', 'bra.b', 'bra.s', 'bra.w', 'jmp'}
TARGET = re.compile(r'\$([0-9a-f]+)(?:\.[wl])?$')


def target_of(ins):
    """The address a branch goes to, if it's written in the instruction."""
    m = TARGET.search(ins.op_str.strip())
    if m:
        return int(m.group(1), 16)
    m = re.fullmatch(r'\$([0-9a-f]+)\(pc\)', ins.op_str.strip())
    return (ins.address + 2 + int(m.group(1), 16)) & 0xffffff if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entry', action='append', default=[])
    ap.add_argument('--entries')
    args = ap.parse_args()
    rom = open(glob.glob(os.path.join(ROOT, 'rom', '*'))[0], 'rb').read()
    md = Cs(CS_ARCH_M68K, CS_MODE_BIG_ENDIAN | CS_MODE_M68K_000)
    vectors = struct.unpack('>64I', rom[:256])
    todo = {v: f'vector_{i}' for i, v in enumerate(vectors) if i >= 1 and 0x200 <= v < len(rom)}
    extra = list(args.entry)
    if args.entries and os.path.exists(args.entries):
        extra += [l.split('#')[0].strip() for l in open(args.entries) if l.split('#')[0].strip()]
    for e in extra:
        todo.setdefault(int(e, 16), f'entry_{int(e, 16):06x}')
    labels, code = dict(todo), {}
    stack = list(todo)
    while stack:
        pc = stack.pop()
        while pc not in code and 0 <= pc < len(rom) - 1 and not pc & 1:
            ins = next(md.disasm(rom[pc:pc + 10], pc, 1), None)
            if ins is None:
                break
            code[pc] = ins
            name = ins.mnemonic
            base = name.split('.')[0]
            is_branch = base in ('bra', 'bsr', 'jmp', 'jsr') or base.startswith('db') or (
                base[0] == 'b' and base not in ('bchg', 'bclr', 'bset', 'btst', 'bkpt'))
            if is_branch:
                t = target_of(ins)
                if t is not None and t < len(rom):
                    labels.setdefault(t, f'{"sub" if base in ("bsr", "jsr") else "loc"}_{t:06x}')
                    stack.append(t)
            if name in JUMPS or base in ('bra', 'jmp') or base in ENDS:
                break
            pc += ins.size
    os.makedirs(os.path.join(ROOT, 'disasm'), exist_ok=True)
    out = os.path.join(ROOT, 'disasm', 'immortal.dis')
    last = None
    with open(out, 'w') as f:
        for pc in sorted(code):
            ins = code[pc]
            if last is not None and pc != last:
                f.write(f'\n; ---- gap of {pc - last} bytes ----\n')
            if pc in labels:
                f.write(f'\n{labels[pc]}:\n')
            f.write(f'{pc:06x}  {ins.bytes.hex():<20} {ins.mnemonic} {ins.op_str}\n')
            last = pc + ins.size
    size = sum(i.size for i in code.values())
    print(f'{len(code)} instructions, {size} bytes of {len(rom)} reached; wrote {os.path.relpath(out, ROOT)}')
    print('vectors of interest:', ' '.join(f'{n}={vectors[i]:06x}' for n, i in
                                           (('reset', 1), ('hblank', 28), ('vblank', 30))))


if __name__ == '__main__':
    main()

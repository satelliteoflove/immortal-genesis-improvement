#!/usr/bin/env python3
"""Make a BPS patch file from the original ROM and the patched one.

    tools/build_rom.py
    tools/make_patch.py          writes build/Immortal-Genesis-Improvement-v1.0.bps

A BPS file carries checksums of the ROM it's for and of the result, so a patcher refuses the
wrong dump. The patch is then applied to the original by a patcher written here, and the
result must be the patched ROM byte for byte.
"""
import hashlib
import os
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romcheck

BUILD = os.path.join(romcheck.ROOT, 'build')
PATCHED = os.path.join(BUILD, 'immortal-patched.md')
PATCH = os.path.join(BUILD, 'Immortal-Genesis-Improvement-v1.0.bps')
JOIN = 8                        # changed stretches this close together go in one record


def stretches(old, new):
    """The stretches where the two differ, as (start, end), joining ones that nearly touch."""
    found, at = [], 0
    while at < len(new):
        if old[at] == new[at]:
            at += 1
            continue
        end = at + 1
        while end < len(new) and old[end] != new[end]:
            end += 1
        if found and at - found[-1][1] < JOIN:
            found[-1][1] = end
        else:
            found.append([at, end])
        at = end
    return found


def number(n):
    """A number as BPS stores it: seven bits a byte, the top bit marking the last."""
    out = bytearray()
    while True:
        low = n & 0x7F
        n >>= 7
        if not n:
            out.append(0x80 | low)
            return bytes(out)
        out.append(low)
        n -= 1


def bps(old, new):
    out = bytearray(b'BPS1') + number(len(old)) + number(len(new)) + number(0)
    at = 0
    for start, end in stretches(old, new) + [[len(new), len(new)]]:
        if start > at:
            out += number((start - at - 1) << 2)                    # the same as the original
        if end > start:
            out += number((end - start - 1) << 2 | 1) + new[start:end]   # these bytes instead
        at = end
    for data in (old, new):
        out += zlib.crc32(data).to_bytes(4, 'little')
    return bytes(out + zlib.crc32(out).to_bytes(4, 'little'))


def apply_bps(old, patch):
    assert patch[:4] == b'BPS1' and zlib.crc32(patch[:-4]) == int.from_bytes(patch[-4:], 'little')
    at = 4

    def read():
        nonlocal at
        value, shift = 0, 1
        while True:
            byte = patch[at]
            at += 1
            value += (byte & 0x7F) * shift
            if byte & 0x80:
                return value
            shift <<= 7
            value += shift

    old_size, new_size, notes = read(), read(), read()
    at += notes
    assert old_size == len(old) and zlib.crc32(old) == int.from_bytes(patch[-12:-8], 'little')
    out = bytearray()
    while at < len(patch) - 12:
        action = read()
        kind, length = action & 3, (action >> 2) + 1
        assert kind < 2                             # the two kinds written above
        if kind == 0:
            out += old[len(out):len(out) + length]
        else:
            out += patch[at:at + length]
            at += length
    assert len(out) == new_size and zlib.crc32(out) == int.from_bytes(patch[-8:-4], 'little')
    return bytes(out)


def main():
    with open(romcheck.find_rom(), 'rb') as f:
        old = f.read()
    if hashlib.sha256(old).hexdigest() != romcheck.EXPECTED_SHA256:
        sys.exit('the ROM in rom/ is not the one the patch is made for; see tools/romcheck.py')
    if not os.path.exists(PATCHED):
        sys.exit('build the patched ROM first: tools/build_rom.py')
    with open(PATCHED, 'rb') as f:
        new = f.read()
    assert len(new) == len(old)
    changed = sum(end - start for start, end in stretches(old, new))
    patch = bps(old, new)
    if apply_bps(old, patch) != new:
        sys.exit('the patch does not give back the patched ROM')
    with open(PATCH, 'wb') as f:
        f.write(patch)
    print(f'wrote {os.path.relpath(PATCH, romcheck.ROOT)}, {len(patch)} bytes, and it turns the original into '
          f'the patched ROM')
    print(f'{changed} bytes of the ROM change, in {len(stretches(old, new))} places')
    print(f'patched ROM: CRC32 {zlib.crc32(new):08x}, SHA-256 {hashlib.sha256(new).hexdigest()}')


if __name__ == '__main__':
    main()

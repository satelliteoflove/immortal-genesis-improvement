#!/usr/bin/env python3
"""Check that a ROM is the one this patch is made for.

    tools/romcheck.py [rom]

With no argument it looks for the one file in rom/. Exits 0 if the ROM matches,
1 if it doesn't. It prints what the cartridge's header says either way, which
helps in working out what a different dump actually is.
"""
import glob
import hashlib
import os
import struct
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# "Immortal, The (USA, Europe)" in the ROM set this came from.
EXPECTED_SIZE = 1048576
EXPECTED_SHA256 = 'b60aa52e46a199f755a1eb99daea543c468acf07d83624c85a84cdd14b786375'


def find_rom():
    found = [p for p in glob.glob(os.path.join(ROOT, 'rom', '*')) if os.path.isfile(p)]
    if len(found) != 1:
        sys.exit(f'expected one file in rom/, found {len(found)}; name the ROM on the command line')
    return found[0]


def text(data, start, end):
    return data[start:end].decode('latin-1').strip()


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else find_rom()
    with open(path, 'rb') as f:
        data = f.read()

    sha256 = hashlib.sha256(data).hexdigest()
    words = (len(data) - 0x200) // 2
    computed = sum(struct.unpack(f'>{words}H', data[0x200:0x200 + words * 2])) & 0xffff
    stored = struct.unpack('>H', data[0x18e:0x190])[0]
    has_sram = data[0x1b0:0x1b2] == b'RA'

    print(f'file      {os.path.basename(path)}')
    print(f'size      {len(data)} bytes')
    print(f'sha256    {sha256}')
    print(f'crc32     {zlib.crc32(data):08x}')
    print(f'title     {text(data, 0x150, 0x180)}')
    print(f'serial    {text(data, 0x180, 0x18e)}')
    print(f'date      {text(data, 0x110, 0x120)}')
    print(f'region    {text(data, 0x1f0, 0x200)}')
    print(f'checksum  header {stored:04x}, computed {computed:04x}')
    print(f'save RAM  {"declared" if has_sram else "none declared"}')

    if len(data) == EXPECTED_SIZE and sha256 == EXPECTED_SHA256:
        print('This is the ROM the patch is made for.')
        return 0
    print('This is NOT the ROM the patch is made for.')
    return 1


if __name__ == '__main__':
    sys.exit(main())

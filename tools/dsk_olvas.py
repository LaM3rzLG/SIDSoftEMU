#!/usr/bin/env python3
"""Fajl kiolvasasa a FAT12 .dsk lemezkepbol (mappakkal). python3 tools/dsk_olvas.py SIDSoftEMU.dsk SID_TVC/LNINJA/05.STC [ki]"""
import sys


def olvas(img, ut):
    fat = img[512:512 + 1536]
    root = 7 * 512
    data = root + 7 * 512
    cl = 1024

    def fatn(n):
        o = n * 3 // 2
        v = fat[o] | (fat[o + 1] << 8)
        return (v >> 4) if n & 1 else v & 0xFFF

    def lanc(c):
        out = []
        while 2 <= c < 0xFF8:
            out.append(c)
            c = fatn(c)
        return out

    def read(c):
        return b''.join(img[data + (x - 2) * cl:data + (x - 1) * cl] for x in lanc(c))

    buf = img[root:root + 112 * 32]
    reszek = ut.replace('\\', '/').split('/')
    for i, r in enumerate(reszek):
        n, _, x = r.upper().partition('.')
        nev = n.ljust(8) + x.ljust(3)
        for k in range(0, len(buf), 32):
            e = buf[k:k + 32]
            if e[0] == 0:
                return None
            if e[:11].decode('latin1') == nev:
                c = e[26] | (e[27] << 8)
                if i == len(reszek) - 1:
                    return read(c)[:int.from_bytes(e[28:32], 'little')]
                buf = read(c)
                break
        else:
            return None


if __name__ == '__main__':
    b = olvas(open(sys.argv[1], 'rb').read(), sys.argv[2])
    if b is None:
        print('nincs meg')
        sys.exit(1)
    print(len(b), 'byte')
    if len(sys.argv) > 3:
        open(sys.argv[3], 'wb').write(b)

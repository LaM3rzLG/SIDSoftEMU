#!/usr/bin/env python3
"""stc2bin - a SIDSoftEMU .STC (1.3) fajlbol a SID unit nyers memoriakepei.

  python3 stc2bin.py [-c CIM] SONG1.STC kimenet_elotag
    -c CIM   a dal cime a TVC memoriajaban (hexa, pl. 5000 vagy $5000; alapbol 2300). A dal belso cimei
             (a fejlec 3 cime, a REF-ek es az ugrasok) erre a cimre lesznek athelyezve.
    -> kimenet_elotag_dal.bin      a dal (a SID::Init Dal parametere = CIM)
    -> kimenet_elotag_paletta.bin  14 x 256 byte (a SID::Init Paletta parametere)
    -> kiirja a cimet, szerzot, kiadast, a hosszt (kepkocka, 50/s) es a hurokpontot

.STC 1.3: $FD $FF, 3 x 32 byte info, 8 byte (N, hurokpont, hurok %, 0, maradek), 3584 byte paletta, 2 byte L,
majd a dal $C000 feletti resze (ha L > $9D00), vegul a $2300..$BFFF resz. A dal $2300-ra keszult.
A dal: 6 byte fejlec (a 3 hang folyamanak cime), aztan hangonkent: $00..$0F rekord (bit 0: +2, bit 1: +1, bit 2: +1,
bit 3: +1 byte), $80+n (1 byte), $10 lo hi n (REF), $11 lo hi (ugras: a hang vege).
"""
import struct
import sys

ALAP = 0x2300
ALSO = 0xC000 - ALAP             # a $2300..$BFFF resz hossza


def athelyez(dal, cel):
    d = bytearray(dal)
    delta = cel - ALAP

    def cim(p):
        v = d[p] | (d[p + 1] << 8)
        if not ALAP <= v < ALAP + len(d):
            sys.exit('hibas cim a dalban: $%04X a +%d helyen' % (v, p))
        v += delta
        d[p], d[p + 1] = v & 0xFF, v >> 8

    kezdet = [(d[2 * k] | (d[2 * k + 1] << 8)) - ALAP for k in range(3)]
    for k in range(3):
        cim(2 * k)
    for p in kezdet:
        while True:
            c = d[p]
            if c == 0x11:
                cim(p + 1)
                break
            if c == 0x10:
                cim(p + 1)
                p += 4
            elif c & 0x80:
                p += 1
            elif c < 0x10:
                p += 1 + (2 if c & 1 else 0) + (1 if c & 2 else 0) + (1 if c & 4 else 0) + (1 if c & 8 else 0)
            else:
                sys.exit('ismeretlen kod a dalban: $%02X a +%d helyen' % (c, p))
    return bytes(d)


def main():
    args = sys.argv[1:]
    cel = ALAP
    if len(args) >= 2 and args[0] == '-c':
        cel = int(args[1].lstrip('$'), 16)
        args = args[2:]
    if len(args) != 2:
        print(__doc__)
        sys.exit(1)
    d = open(args[0], 'rb').read()
    if d[:2] != b'\xfd\xff':
        sys.exit('nem 1.3-as .STC (az elejen $FD $FF kell)')
    info = [d[2 + 32 * i:2 + 32 * i + 32].split(b'\0')[0].decode('latin-1') for i in range(3)]
    n, hurok = struct.unpack_from('<HH', d, 98)
    paletta = d[106:106 + 3584]
    (L,) = struct.unpack_from('<H', d, 106 + 3584)
    p = 106 + 3584 + 2
    if L > ALSO:
        dal = d[p + L - ALSO:p + L] + d[p:p + L - ALSO]
    else:
        dal = d[p:p + L]
    if len(dal) != L:
        sys.exit('rovid fajl')
    if cel + L > 0x10000:
        sys.exit('a dal nem fer el a $%04X cimtol' % cel)
    dal = athelyez(dal, cel)
    open(args[1] + '_dal.bin', 'wb').write(dal)
    open(args[1] + '_paletta.bin', 'wb').write(paletta)
    print('%s / %s / %s' % tuple(info))
    print('dal: %d byte ($%04X-$%04X), %d kepkocka, hurok: %d' % (L, cel, cel + L - 1, n, hurok))


if __name__ == '__main__':
    main()

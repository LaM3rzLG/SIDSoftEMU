#!/usr/bin/env python3
"""stc2bin - a SIDSoftEMU .STC (1.3) fajlbol a lejatszo nyers memoriakepei.

  python3 tools/stc2bin.py SONG1.STC kimenet_elotag
    -> kimenet_elotag_dal.bin      a dal, a $2300-as cimre (hossz = L)
    -> kimenet_elotag_paletta.bin  14 x 256 byte, a $F000-as cimre
    -> kiirja a cimet, szerzot, kiadast, a hosszt (kepkocka) es a hurokpontot

.STC 1.3: $FD $FF, 3 x 32 byte info, 8 byte (N, hurokpont, hurok %, 0, maradek), 3584 byte paletta, 2 byte L,
majd a dal $C000 feletti resze (ha L > $9D00), vegul a $2300..$BFFF resz.
"""
import struct
import sys

DAL_CIM = 0x2300
ALSO = 0xC000 - DAL_CIM          # a $2300..$BFFF resz hossza


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    d = open(sys.argv[1], 'rb').read()
    if d[:2] != b'\xfd\xff':
        sys.exit('nem 1.3-as .STC (az elejen $FD $FF kell)')
    info = [d[2 + 32 * i:2 + 32 * i + 32].split(b'\0')[0].decode('latin-1') for i in range(3)]
    n, hurok = struct.unpack_from('<HH', d, 98)
    paletta = d[106:106 + 3584]
    (L,) = struct.unpack_from('<H', d, 106 + 3584)
    p = 106 + 3584 + 2
    if L > ALSO:
        felso = d[p:p + L - ALSO]
        also = d[p + L - ALSO:p + L]
        dal = also + felso
    else:
        dal = d[p:p + L]
    if len(dal) != L:
        sys.exit('rovid fajl')
    open(sys.argv[2] + '_dal.bin', 'wb').write(dal)
    open(sys.argv[2] + '_paletta.bin', 'wb').write(paletta)
    print('%s / %s / %s' % tuple(info))
    print('dal: %d byte ($%04X-$%04X), %d kepkocka, hurok: %d' % (L, DAL_CIM, DAL_CIM + L - 1, n, hurok))


if __name__ == '__main__':
    main()

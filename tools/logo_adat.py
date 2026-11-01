#!/usr/bin/env python3
"""A forgo logo maszkolt GE sprite-jabol (bmp2ge.py kimenete: 3 byte fejlec + fazisonkent 17 sor x 6 x (maszk, adat))
csak az adat-byte-ok (a hatter mindig fekete, a logo-IT a maszkot nem hasznalja): 16 x 17 x 6 = 1632 byte.
  python3 tools/logo_adat.py resources/images/C64_logo_forog.bin resources/images/C64_logo_adat.bin"""
import sys
d = open(sys.argv[1], 'rb').read()[3:]
open(sys.argv[2], 'wb').write(d[1::2])
print(len(d[1::2]), 'byte ->', sys.argv[2])

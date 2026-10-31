#!/usr/bin/env python3
"""A TVC-s atalakito (atalakito.ras, a SIDSoftEMU.bin-ben) osszevetese a Python-masaval (tools/tvc_atalakito.py).
  python3 tools/z80_at_teszt.py [aldal] [kepkockak]"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from z80 import Z80
from sid_dump import dump
import tvc_atalakito as T
from z80_cpu_teszt import symbols, ROOT

MEZOK = __import__('gen_atalakito').MEZOK


def main():
    song = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    nfr = int(sys.argv[2]) if len(sys.argv) > 2 else 500
    S = symbols()
    d = dump(os.path.join(ROOT, 'sid', 'LNINJA.SID'), song, max_frames=nfr)
    frames = d['frames'][:nfr]
    blob, n, nref, celok = T.atalakit(frames, nfr)
    mem = bytearray(65536)
    b = open(os.path.join(ROOT, 'SIDSoftEMU.bin'), 'rb').read()
    mem[0x19EF:0x19EF + len(b)] = b
    z = Z80(mem)

    def call(a):
        z.sp = 0x1800
        z.push(0)
        z.pc = a
        k = 0
        while z.pc:
            z.step()
            k += 1
        return k

    call(S['AtInit'])
    hb = S['AtHangok']
    off = {m: i for i, m in enumerate(MEZOK)}
    osszes = 0
    for i, fw in enumerate(frames):
        fw = [(r, v) for r, v in fw if r < 25]
        mem[S['CpuLogN']] = len(fw)
        for j, (r, v) in enumerate(fw):
            mem[S['CpuLog'] + 2 * j] = r
            mem[S['CpuLog'] + 2 * j + 1] = v
        osszes += call(S['AtKepkocka'])
        if mem[S['AtStop']]:
            print('megallt a %d. kepkockanal (nincs hely)' % i)
            break
        cel = []
        for v in range(3):
            o = hb + 48 * v
            cel += [mem[o + off['TST0']] | (mem[o + off['TST1']] << 8), mem[o + off['TSL']], mem[o + off['TPW']]]
        if tuple(cel) != celok[i]:
            print('ALLAPOT ELTER a %d. kepkockanal:\n  TVC %s\n  ref %s' % (i, cel, celok[i]))
            raise SystemExit(1)
    call(S['AtVege'])
    L = mem[S['AtHossz']] | (mem[S['AtHossz'] + 1] << 8)
    tvc = bytes(mem[0x5000:0x5000 + L])
    print('%d kepkocka, Z80-lepes/kepkocka: %.0f; TVC: %d byte, ref: %d byte' % (n, osszes / max(1, n), L, len(blob)))
    if tvc == blob:
        print('KIMENET BAJTRA EGYEZIK')
    else:
        k = next(i for i in range(min(len(tvc), len(blob))) if tvc[i] != blob[i])
        print('ELTER a $%04X cimen: TVC %s ref %s' % (0x5000 + k, tvc[k:k + 8].hex(), blob[k:k + 8].hex()))
        raise SystemExit(1)


if __name__ == '__main__':
    main()

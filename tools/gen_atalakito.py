#!/usr/bin/env python3
"""tools/atalakito_src.asm -> atalakito.ras (mezonevek, tablak behelyettesitve). python3 tools/gen_atalakito.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tvc_atalakito as T

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEZOK = ['FLO', 'FHI', 'PWLO', 'PWHI', 'CTRL', 'RA', 'RD', 'RS', 'RR', 'LVLLO', 'LVLHI', 'STATE', 'GATE',
         'WPLO', 'WPHI', 'WEND', 'STLO', 'STHI', 'SST0', 'SST1', 'SSL', 'SPW', 'ELSO', 'QH', 'QN', 'QPG', 'HPG',
         'TST0', 'TST1', 'TSL', 'TPW', 'WACT', 'WA0', 'WA1', 'WP0', 'WP1', 'WS0', 'WS1', 'WSL', 'WPW', 'WU', 'WFR',
         'BU', 'BFR', 'BS0', 'BS1', 'BSL', 'BPW', 'FCLO', 'FCHI', 'SLO', 'SHI']


def irasok(d):
    """SID-regiszterenkenti kezelo (C = ertek), fix cimekkel; a vegen jp AkTov. + ugrotabla AtIrT."""
    o = {m: i for i, m in enumerate(MEZOK)}
    L, T = [], []
    for r in range(25):
        lab = 'AtIr%02d' % r
        T.append(lab)
        L.append('\t%s:' % lab)
        if r < 21:
            v, k = divmod(r, 7)
            B = lambda m: 'AtHangok+%d' % (v * len(MEZOK) + o[m])
            if k in (0, 1, 2):
                L += ['\t\tld\ta,c', '\t\tld\t(%s),a' % B(['FLO', 'FHI', 'PWLO'][k])]
            elif k == 3:
                L += ['\t\tld\ta,c', '\t\tand\t15', '\t\tld\t(%s),a' % B('PWHI')]
            elif k == 4:
                L += ['\t\tld\ta,(%s)' % B('GATE'), '\t\tld\te,a', '\t\tld\ta,c', '\t\tld\t(%s),a' % B('CTRL'),
                      '\t\tand\t1', '\t\tld\t(%s),a' % B('GATE'), '\t\tcp\te', '\t\tjp\tz,AkTov',
                      '\t\tor\ta', '\t\tld\ta,2', '\t\tjp\tz,%sR' % lab, '\t\txor\ta',
                      '\t%sR:' % lab, '\t\tld\t(%s),a' % B('STATE')]
            else:
                hi, lo = ('RA', 'RD') if k == 5 else ('RS', 'RR')
                L += ['\t\tld\ta,c', '\t\trrca', '\t\trrca', '\t\trrca', '\t\trrca', '\t\tand\t15',
                      '\t\tld\t(%s),a' % B(hi), '\t\tld\ta,c', '\t\tand\t15', '\t\tld\t(%s),a' % B(lo)]
        elif r == 24:
            L += ['\t\tld\ta,c', '\t\tand\t15', '\t\tld\t(AtVol),a']
        L.append('\t\tjp\tAkTov')
    L.append('\tAtIrT:')
    for i in range(0, 25, 8):
        L.append('\t\tdw\t' + ', '.join(T[i:i + 8]))
    return '\n'.join(L)


def main():
    src = open(os.path.join(ROOT, 'tools', 'atalakito_src.asm')).read()
    d = {m: str(i) for i, m in enumerate(MEZOK)}
    d['VMERET'] = str(len(MEZOK))
    d['VMERET3'] = str(3 * len(MEZOK))
    d['QMAX'] = str(T.QMAX)
    d['ATT'] = '\n'.join('\t\tdw\t' + ', '.join(str(v) for v in T.ATT[i:i + 8]) for i in range(0, 16, 8))
    d['SZINT'] = '\n'.join('\t\tdb\t' + ','.join(str(v) for v in T.SZINT[i:i + 24]) for i in range(0, 240, 24))
    d['IRASOK'] = irasok(d)
    src = src.format(**d)
    out = []
    for line in src.split('\n'):
        t = line.split()
        if len(t) == 2 and t[0] == 'ds':
            n = int(t[1])
            for i in range(0, n, 16):
                out.append('\t\tdb\t' + ','.join(['0'] * min(16, n - i)))
        else:
            out.append(line)
    out.append('\tAtKodVege:')
    txt = ('/* GENERALT FAJL - ne szerkeszd! Forras: tools/atalakito_src.asm, tools/gen_atalakito.py */\n'
           'procedure AtKod();\nbegin\n\tasm("\n' + '\n'.join(out) + '\n\t");\nend;\n')
    open(os.path.join(ROOT, 'atalakito.ras'), 'w').write(txt)
    print('atalakito.ras: %d sor, hang-struktura %d byte' % (len(out), len(MEZOK)))


if __name__ == '__main__':
    main()

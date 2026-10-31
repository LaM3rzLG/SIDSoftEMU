#!/usr/bin/env python3
"""Z80-as 6502-emulator generatora -> cpu6502.ras (TRSE @include, egy asm-blokk).

  python3 tools/gen_cpu6502.py

Felepites (emulacio kozben di, a Z80 SP = a 6502 PC TVC-cime!):
  SP    = 6502 PC (TVC-cim; "pop hl" = 2 byte egyszerre)     B = X     C = Y
  AF'   = 6502 A + jelzok: S = N, Z = Z, C = C (V kulon: CpuVF, D: CpuDF, I: CpuIF)
  A, F, D, E, H, L = munkaregiszterek; E = az 1. operandusbyte a kiosztaskor
  Memoria: 6502-lap -> CPU_PT tabla (TVC-lap), CPU_TOUCH = erintett lapok (nem 0 = erintve).
  Kulonleges TVC-lapok: CPU_IO ($FE: $D000-$DFFF, benne a SID), CPU_ZERO ($FF: meg nem foglalt, olvasva 0,
  utasitaskent 0 = BRK = megallas). Iraskor ezekre lassu ag: SID-naplo / lapfoglalas + az utasitas ujra.
  Nullas lap es verem kulon TVC-lapon (CPU_ZP, CPU_STK), ezek fordites nelkul.
Hivas: CpuHiv (CpuCim, CpuA) -> a rutin RTS-e a $FFF0-ra ter vissza (CPU_ZERO -> BRK) -> CpuStop.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'cpu6502.ras')

L = []          # kimeneti sorok
n_lbl = [0]


def lbl(p='Cl'):
    n_lbl[0] += 1
    return '%s%d' % (p, n_lbl[0])


def emit(s):
    for line in s.strip('\n').split('\n'):
        line = line.strip()
        if not line:
            continue
        if line.endswith(':'):
            L.append('\t' + line)
        else:
            L.append('\t\t' + line.replace(' ', '\t', 1))


NEXT = """
pop hl
ld e,h
ld h,CPU_JTL
ld a,(hl)
inc h
ld h,(hl)
ld l,a
jp (hl)
"""
FETCH_HI = "pop hl\ndec sp\n"          # L = 2. operandus (cim felso byte), SP a kovetkezo utasitasra


def trans(store=None, ln=3):
    """L = 6502 felso byte, E = also -> HL = TVC-cim. store = 'A'/'X'/'Y'/'M' (iras: lassu ag ellenorzes)."""
    s = "ld h,CPU_PT\nld d,(hl)\ninc h\nld (hl),h\n"
    if store:
        s += "ld a,d\ncp CPU_IO\njp nc,CpuSlow%s%d\n" % (store, ln)
    return s + "ex de,hl\n"


def mode(m, store=None):
    """-> (kod, forras, hossz). Forras: '(hl)' vagy 'e' (azonnali)."""
    if m == 'imm':
        return '', 'e', 2
    if m == 'zp':
        return "ld l,e\nld h,CPU_ZP\n", '(hl)', 2
    if m == 'zpx':
        return "ld a,e\nadd a,b\nld l,a\nld h,CPU_ZP\n", '(hl)', 2
    if m == 'zpy':
        return "ld a,e\nadd a,c\nld l,a\nld h,CPU_ZP\n", '(hl)', 2
    if m == 'abs':
        return FETCH_HI + trans(store, 3), '(hl)', 3
    if m in ('absx', 'absy'):
        r = 'b' if m == 'absx' else 'c'
        k = lbl()
        return (FETCH_HI + "ld a,e\nadd a,%s\nld e,a\njr nc,%s\ninc l\n%s:\n" % (r, k, k) + trans(store, 3)), '(hl)', 3
    if m == 'izx':
        return ("ld a,e\nadd a,b\nld l,a\nld h,CPU_ZP\nld e,(hl)\ninc l\nld l,(hl)\n" + trans(store, 2)), '(hl)', 2
    if m == 'izy':
        k = lbl()
        return ("ld l,e\nld h,CPU_ZP\nld a,(hl)\nadd a,c\nld e,a\ninc l\nld l,(hl)\njr nc,%s\ninc l\n%s:\n" % (k, k)
                + trans(store, 2)), '(hl)', 2
    raise ValueError(m)


H = {}           # opkod -> handler cimke
BCD = {}         # opkod -> decimalis handler cimke


def handler(op, body, name=None, table=H):
    lab = name or ('CpuOp%02X' % op)
    table[op] = lab
    emit(lab + ':')
    emit(body)


def v_store():
    k = lbl()
    return "ld hl,CpuVF\nld (hl),0\njp po,%s\nld (hl),1\n%s:\n" % (k, k)


MODES8 = {'imm': None, 'zp': None, 'zpx': None, 'abs': None, 'absx': None, 'absy': None, 'izx': None, 'izy': None}
OPS8 = {
    'ORA': [0x09, 0x05, 0x15, 0x0D, 0x1D, 0x19, 0x01, 0x11],
    'AND': [0x29, 0x25, 0x35, 0x2D, 0x3D, 0x39, 0x21, 0x31],
    'EOR': [0x49, 0x45, 0x55, 0x4D, 0x5D, 0x59, 0x41, 0x51],
    'ADC': [0x69, 0x65, 0x75, 0x6D, 0x7D, 0x79, 0x61, 0x71],
    'LDA': [0xA9, 0xA5, 0xB5, 0xAD, 0xBD, 0xB9, 0xA1, 0xB1],
    'CMP': [0xC9, 0xC5, 0xD5, 0xCD, 0xDD, 0xD9, 0xC1, 0xD1],
    'SBC': [0xE9, 0xE5, 0xF5, 0xED, 0xFD, 0xF9, 0xE1, 0xF1],
}
M8 = ['imm', 'zp', 'zpx', 'abs', 'absx', 'absy', 'izx', 'izy']
Z80LOG = {'ORA': 'or', 'AND': 'and', 'EOR': 'xor'}


def gen_ops8():
    for name, codes in OPS8.items():
        for op, m in zip(codes, M8):
            code, src, ln = mode(m)
            if name == 'LDA':
                body = code + "ex af,af'\nld a,%s\ninc a\ndec a\nex af,af'\n" % src + NEXT
            elif name in Z80LOG:
                k = lbl()
                z = Z80LOG[name]
                body = (code + "ex af,af'\njr c,%s\n%s %s\nex af,af'\n" % (k, z, src) + NEXT
                        + "%s:\n%s %s\nscf\nex af,af'\n" % (k, z, src) + NEXT)
            elif name == 'CMP':
                body = code + "ex af,af'\ncp %s\nccf\nex af,af'\n" % src + NEXT
            elif name == 'ADC':
                body = code + "ex af,af'\nadc a,%s\n" % src + v_store() + "ex af,af'\n" + NEXT
                code2, src2, _ = mode(m)
                handler(op, code2 + "ex af,af'\nadc a,%s\ndaa\nex af,af'\n" % src2 + NEXT,
                        name='CpuBcd%02X' % op, table=BCD)
            elif name == 'SBC':
                body = code + "ex af,af'\nccf\nsbc a,%s\nccf\n" % src + v_store() + "ex af,af'\n" + NEXT
                code2, src2, _ = mode(m)
                handler(op, code2 + "ex af,af'\nccf\nsbc a,%s\ndaa\nccf\nex af,af'\n" % src2 + NEXT,
                        name='CpuBcd%02X' % op, table=BCD)
            handler(op, body)


def gen_store():
    for name, reg, codes in (('STA', 'A', [(0x85, 'zp'), (0x95, 'zpx'), (0x8D, 'abs'), (0x9D, 'absx'),
                                           (0x99, 'absy'), (0x81, 'izx'), (0x91, 'izy')]),
                             ('STX', 'X', [(0x86, 'zp'), (0x96, 'zpy'), (0x8E, 'abs')]),
                             ('STY', 'Y', [(0x84, 'zp'), (0x94, 'zpx'), (0x8C, 'abs')])):
        for op, m in codes:
            code, src, ln = mode(m, store=reg)
            if reg == 'A':
                st = "ex af,af'\nld (hl),a\nex af,af'\n"
            else:
                st = "ld (hl),%s\n" % ('b' if reg == 'X' else 'c')
            handler(op, code + st + NEXT)


def gen_ldxy():
    for reg, codes in (('b', [(0xA2, 'imm'), (0xA6, 'zp'), (0xB6, 'zpy'), (0xAE, 'abs'), (0xBE, 'absy')]),
                       ('c', [(0xA0, 'imm'), (0xA4, 'zp'), (0xB4, 'zpx'), (0xAC, 'abs'), (0xBC, 'absx')])):
        for op, m in codes:
            code, src, ln = mode(m)
            handler(op, code + "ld %s,%s\nex af,af'\ninc %s\ndec %s\nex af,af'\n" % (reg, src, reg, reg) + NEXT)
    for reg, codes in (('b', [(0xE0, 'imm'), (0xE4, 'zp'), (0xEC, 'abs')]),
                       ('c', [(0xC0, 'imm'), (0xC4, 'zp'), (0xCC, 'abs')])):
        for op, m in codes:
            code, src, ln = mode(m)
            handler(op, code + "ex af,af'\nld d,a\nld a,%s\ncp %s\nccf\nld a,d\nex af,af'\n" % (reg, src) + NEXT)


def gen_bit():
    for op, m in ((0x24, 'zp'), (0x2C, 'abs')):
        code, src, ln = mode(m)
        k1, k2 = lbl(), lbl()
        handler(op, code + """
ld d,(hl)
ld a,d
and $40
ld (CpuVF),a
ex af,af'
ld e,a
ld a,0
adc a,a
ld h,a
ld a,e
and d
ld a,h
jr nz,%s
or $40
%s:
bit 7,d
jr z,%s
or $80
%s:
ld l,a
ld h,e
ld (CpuSPS),sp
ld sp,CpuAuxTop
push hl
pop af
ld sp,(CpuSPS)
ex af,af'
""" % (k1, k1, k2, k2) + NEXT)


SHIFT = {'ASL': ('sla', [0x0A, 0x06, 0x16, 0x0E, 0x1E]), 'LSR': ('srl', [0x4A, 0x46, 0x56, 0x4E, 0x5E]),
         'ROL': ('rl', [0x2A, 0x26, 0x36, 0x2E, 0x3E]), 'ROR': ('rr', [0x6A, 0x66, 0x76, 0x6E, 0x7E])}


def gen_rmw():
    for name, (z, codes) in SHIFT.items():
        for op, m in zip(codes, ['acc', 'zp', 'zpx', 'abs', 'absx']):
            if m == 'acc':
                handler(op, "dec sp\nex af,af'\n%s a\nex af,af'\n" % z + NEXT)
                continue
            code, src, ln = mode(m, store='M')
            handler(op, code + "ex af,af'\n%s (hl)\nex af,af'\n" % z + NEXT)
    for z, codes in (('inc', [(0xE6, 'zp'), (0xF6, 'zpx'), (0xEE, 'abs'), (0xFE, 'absx')]),
                     ('dec', [(0xC6, 'zp'), (0xD6, 'zpx'), (0xCE, 'abs'), (0xDE, 'absx')])):
        for op, m in codes:
            code, src, ln = mode(m, store='M')
            handler(op, code + "ex af,af'\n%s (hl)\nex af,af'\n" % z + NEXT)


def gen_implied():
    one = "dec sp\n"
    nz_b = lambda r: "ex af,af'\ninc %s\ndec %s\nex af,af'\n" % (r, r)
    handler(0xE8, one + nz_b('b').replace("inc b\ndec b", "inc b") + NEXT)        # INX
    handler(0xC8, one + nz_b('c').replace("inc c\ndec c", "inc c") + NEXT)        # INY
    handler(0xCA, one + "ex af,af'\ndec b\nex af,af'\n" + NEXT)                   # DEX
    handler(0x88, one + "ex af,af'\ndec c\nex af,af'\n" + NEXT)                   # DEY
    handler(0xAA, one + "ex af,af'\nld b,a\ninc b\ndec b\nex af,af'\n" + NEXT)    # TAX
    handler(0xA8, one + "ex af,af'\nld c,a\ninc c\ndec c\nex af,af'\n" + NEXT)    # TAY
    handler(0x8A, one + "ex af,af'\nld a,b\ninc a\ndec a\nex af,af'\n" + NEXT)    # TXA
    handler(0x98, one + "ex af,af'\nld a,c\ninc a\ndec a\nex af,af'\n" + NEXT)    # TYA
    handler(0xBA, one + "ld a,(CpuS)\nld b,a\nex af,af'\ninc b\ndec b\nex af,af'\n" + NEXT)   # TSX
    handler(0x9A, one + "ld a,b\nld (CpuS),a\n" + NEXT)                          # TXS
    handler(0x18, one + "ex af,af'\nscf\nccf\nex af,af'\n" + NEXT)               # CLC
    handler(0x38, one + "ex af,af'\nscf\nex af,af'\n" + NEXT)                    # SEC
    handler(0x58, one + "xor a\nld (CpuIF),a\n" + NEXT)                          # CLI
    handler(0x78, one + "ld a,1\nld (CpuIF),a\n" + NEXT)                         # SEI
    handler(0xB8, one + "xor a\nld (CpuVF),a\n" + NEXT)                          # CLV
    handler(0xD8, one + "xor a\njp CpuSetD\n")                                   # CLD
    handler(0xF8, one + "ld a,1\njp CpuSetD\n")                                  # SED
    handler(0xEA, one + NEXT)                                                    # NOP
    # verem
    handler(0x48, one + "ld a,(CpuS)\nld l,a\nld h,CPU_STK\nex af,af'\nld (hl),a\nex af,af'\n"
                        "dec l\nld a,l\nld (CpuS),a\n" + NEXT)                    # PHA
    handler(0x68, one + "ld a,(CpuS)\ninc a\nld (CpuS),a\nld l,a\nld h,CPU_STK\n"
                        "ex af,af'\nld a,(hl)\ninc a\ndec a\nex af,af'\n" + NEXT)  # PLA
    handler(0x08, one + "jp CpuPhp\n")                                          # PHP
    handler(0x28, one + "ld a,(CpuS)\ninc a\nld (CpuS),a\nld l,a\nld h,CPU_STK\nld a,(hl)\n"
                        "jp CpuPlp\n")                                           # PLP
    handler(0x40, one + "ld a,(CpuS)\ninc a\nld l,a\nld h,CPU_STK\nld a,(hl)\nld (CpuRtiP),a\ninc l\n"
                        "ld a,(hl)\nld (CpuRtiLo),a\ninc l\nld a,(hl)\nld (CpuRtiHi),a\nld a,l\nld (CpuS),a\n"
                        "jp CpuRti\n")                                           # RTI


def jump():
    """L = cel felso byte (6502), E = also -> SP, CpuNDelta, NEXT"""
    return """
ld h,CPU_PT
ld a,(hl)
inc h
ld (hl),h
inc l
ld (hl),h
dec l
ld h,a
ld a,l
sub h
ld (CpuNDelta),a
ld l,e
ld sp,hl
""" + NEXT


def gen_flow():
    handler(0x4C, FETCH_HI + jump())                                              # JMP abs
    handler(0x6C, FETCH_HI + trans() + "ld e,(hl)\ninc l\nld l,(hl)\n" + jump())  # JMP (ind), lapon beluli hiba is
    handler(0x20, FETCH_HI + """
ld d,l
ld hl,-1
add hl,sp
ld a,(CpuNDelta)
add a,h
ld h,a
ld (CpuTmp),hl
ld a,(CpuS)
ld l,a
ld h,CPU_STK
ld a,(CpuTmp+1)
ld (hl),a
dec l
ld a,(CpuTmp)
ld (hl),a
dec l
ld a,l
ld (CpuS),a
ld l,d
""" + jump())                                                                     # JSR
    handler(0x60, """
ld a,(CpuS)
inc a
ld l,a
ld h,CPU_STK
ld e,(hl)
inc l
ld d,(hl)
ld a,l
ld (CpuS),a
inc de
ld l,d
""" + jump())                                                                     # RTS
    emit("CpuRtiJmp:")
    emit(jump())
    for op, cond in ((0x10, 'p'), (0x30, 'm'), (0x50, 'vc'), (0x70, 'vs'), (0x90, 'nc'), (0xB0, 'c'),
                     (0xD0, 'nz'), (0xF0, 'z')):
        k = lbl('Cb')
        tk = """
ld l,e
ld a,e
rla
sbc a,a
ld h,a
add hl,sp
ld sp,hl
""" + NEXT
        if cond in ('vc', 'vs'):
            handler(op, "ld a,(CpuVF)\nor a\njr %s,%s\n" % ('z' if cond == 'vc' else 'nz', k) + NEXT
                    + "%s:\n" % k + tk)
        else:
            j = 'jp' if cond in ('p', 'm') else 'jr'
            handler(op, "ex af,af'\n%s %s,%s\nex af,af'\n" % (j, cond, k) + NEXT
                    + "%s:\nex af,af'\n" % k + tk)
    handler(0x00, "jp CpuStop\n")                                                 # BRK = megallas


def gen_slow():
    """Lassu iras: D = TVC-lap (CPU_IO vagy CPU_ZERO), L = 6502 felso byte, E = also, SP a kovetkezo utasitason."""
    for kind in ('A', 'X', 'Y', 'M'):
        for ln in (2, 3):
            emit('CpuSlow%s%d:' % (kind, ln))
            if kind == 'A':
                emit("ex af,af'\nld (CpuSVal),a\nex af,af'\n")
            elif kind == 'X':
                emit("ld a,b\nld (CpuSVal),a\n")
            elif kind == 'Y':
                emit("ld a,c\nld (CpuSVal),a\n")
            emit("ld a,%d\nld (CpuSLen),a\n" % ln)
            emit("jp %s\n" % ('CpuSlowRmw' if kind == 'M' else 'CpuSlowSt'))


def main():
    gen_ops8()
    gen_store()
    gen_ldxy()
    gen_bit()
    gen_rmw()
    gen_implied()
    gen_flow()
    gen_slow()
    handlers = '\n'.join(L)
    jt = []
    for op in range(256):
        jt.append(H.get(op, 'CpuIllegal'))
    bcd_list = sorted(BCD.items())
    out = []
    out.append('/* GENERALT FAJL - ne szerkeszd! Forras: tools/gen_cpu6502.py. 6502-emulator Z80-on. */')
    out.append('procedure CpuKod();')
    out.append('begin')
    out.append('\tasm("')
    keret = []
    for line in open(os.path.join(ROOT, 'tools', 'cpu6502_keret.asm')).read().rstrip().split('\n'):
        t = line.split()
        if len(t) == 2 and t[0] == 'ds':
            n = int(t[1])
            for i in range(0, n, 16):
                keret.append('\t\tdb\t' + ','.join(['0'] * min(16, n - i)))
        else:
            keret.append(line)
    out.append('\n'.join(keret))
    out.append(';\t------------------------------------------------ utasitasok (generalt)')
    out.append(handlers)
    out.append(';\t------------------------------------------------ ugrotabla-forras (CpuInit szetvalogatja CPU_JTL/JTH-ba)')
    out.append('\tCpuJtForras:')
    for i in range(0, 256, 8):
        out.append('\t\tdw\t' + ', '.join(jt[i:i + 8]))
    out.append(';\tdecimalis (SED) valtozatok: opkod, normal, BCD')
    out.append('\tCpuBcdLista:')
    for op, lab in bcd_list:
        out.append('\t\tdb\t$%02X' % op)
        out.append('\t\tdw\t%s, %s' % (H[op], lab))
    out.append('\t\tdb\t0')
    out.append('\tCpuKodVege:')
    out.append('\t");')
    out.append('end;')
    open(OUT, 'w').write('\n'.join(out) + '\n')
    print('%s: %d utasitas, %d sor' % (OUT, len(H), len(out) + len(L)))


if __name__ == '__main__':
    main()

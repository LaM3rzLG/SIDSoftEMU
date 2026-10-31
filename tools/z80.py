#!/usr/bin/env python3
"""Kis Z80-emulator (Python) a TVC-s asm-kod ellenorzesehez a Macen (pl. a 6502-emulator lepesrol lepesre).
A hivatalos utasitasok nagy resze + IX (DD), ED, CB. Jelzok: S Z H P/V N C. Portok: figyelmen kivul."""


def parity(v):
    v ^= v >> 4
    v ^= v >> 2
    v ^= v >> 1
    return 0 if v & 1 else 4


class Z80:
    def __init__(self, mem):
        self.m = mem
        self.a = self.f = self.b = self.c = self.d = self.e = self.h = self.l = 0
        self.a_ = self.f_ = self.b_ = self.c_ = self.d_ = self.e_ = self.h_ = self.l_ = 0
        self.ix = self.iy = 0
        self.sp = 0xFFFF
        self.pc = 0
        self.cyc = 0
        self.iff = 0

    # ---------------- regiszterparok
    def gbc(self): return (self.b << 8) | self.c
    def gde(self): return (self.d << 8) | self.e
    def ghl(self): return (self.h << 8) | self.l
    def sbc_(self, v): self.b, self.c = (v >> 8) & 0xFF, v & 0xFF
    def sde(self, v): self.d, self.e = (v >> 8) & 0xFF, v & 0xFF
    def shl(self, v): self.h, self.l = (v >> 8) & 0xFF, v & 0xFF

    def rb(self, a): return self.m[a & 0xFFFF]
    def wb(self, a, v): self.m[a & 0xFFFF] = v & 0xFF
    def rw(self, a): return self.m[a & 0xFFFF] | (self.m[(a + 1) & 0xFFFF] << 8)
    def ww(self, a, v):
        self.m[a & 0xFFFF] = v & 0xFF
        self.m[(a + 1) & 0xFFFF] = (v >> 8) & 0xFF

    def fetch(self):
        v = self.m[self.pc]
        self.pc = (self.pc + 1) & 0xFFFF
        return v

    def fetchw(self):
        lo = self.fetch()
        return lo | (self.fetch() << 8)

    def push(self, v):
        self.sp = (self.sp - 2) & 0xFFFF
        self.ww(self.sp, v)

    def pop(self):
        v = self.rw(self.sp)
        self.sp = (self.sp + 2) & 0xFFFF
        return v

    # ---------------- 8 bites regiszterek index szerint (B C D E H L (HL) A)
    def gr(self, i):
        return (self.b, self.c, self.d, self.e, self.h, self.l, None, self.a)[i] if i != 6 else self.rb(self.ghl())

    def sr(self, i, v):
        v &= 0xFF
        if i == 0: self.b = v
        elif i == 1: self.c = v
        elif i == 2: self.d = v
        elif i == 3: self.e = v
        elif i == 4: self.h = v
        elif i == 5: self.l = v
        elif i == 6: self.wb(self.ghl(), v)
        else: self.a = v

    # ---------------- ALU
    def szf(self, v):
        return (v & 0x80) | (0x40 if v == 0 else 0)

    def add8(self, v, c=0):
        a = self.a
        r = a + v + c
        f = self.szf(r & 0xFF) | (0x10 if ((a & 0xF) + (v & 0xF) + c) > 0xF else 0)
        f |= 4 if ((~(a ^ v)) & (a ^ r) & 0x80) else 0
        f |= 1 if r > 0xFF else 0
        self.a = r & 0xFF
        self.f = f

    def sub8(self, v, c=0, store=True):
        a = self.a
        r = a - v - c
        f = self.szf(r & 0xFF) | 2 | (0x10 if ((a & 0xF) - (v & 0xF) - c) < 0 else 0)
        f |= 4 if ((a ^ v) & (a ^ r) & 0x80) else 0
        f |= 1 if r < 0 else 0
        if store:
            self.a = r & 0xFF
        self.f = f

    def logic(self, op, v):
        if op == 'and':
            self.a &= v
            self.f = self.szf(self.a) | 0x10 | parity(self.a)
        elif op == 'xor':
            self.a ^= v
            self.f = self.szf(self.a) | parity(self.a)
        else:
            self.a |= v
            self.f = self.szf(self.a) | parity(self.a)

    def alu(self, k, v):
        if k == 0: self.add8(v)
        elif k == 1: self.add8(v, self.f & 1)
        elif k == 2: self.sub8(v)
        elif k == 3: self.sub8(v, self.f & 1)
        elif k == 4: self.logic('and', v)
        elif k == 5: self.logic('xor', v)
        elif k == 6: self.logic('or', v)
        else: self.sub8(v, 0, store=False)

    def inc8(self, v):
        r = (v + 1) & 0xFF
        self.f = (self.f & 1) | self.szf(r) | (0x10 if (v & 0xF) == 0xF else 0) | (4 if v == 0x7F else 0)
        return r

    def dec8(self, v):
        r = (v - 1) & 0xFF
        self.f = (self.f & 1) | self.szf(r) | 2 | (0x10 if (v & 0xF) == 0 else 0) | (4 if v == 0x80 else 0)
        return r

    def cond(self, k):
        f = self.f
        return (not f & 0x40, f & 0x40, not f & 1, f & 1, not f & 4, f & 4, not f & 0x80, f & 0x80)[k]

    def rot(self, k, v):
        c = self.f & 1
        if k == 0: r = ((v << 1) | (v >> 7)) & 0xFF; nc = v >> 7          # rlc
        elif k == 1: r = ((v >> 1) | (v << 7)) & 0xFF; nc = v & 1         # rrc
        elif k == 2: r = ((v << 1) | c) & 0xFF; nc = v >> 7               # rl
        elif k == 3: r = (v >> 1) | (c << 7); nc = v & 1                  # rr
        elif k == 4: r = (v << 1) & 0xFF; nc = v >> 7                     # sla
        elif k == 5: r = (v >> 1) | (v & 0x80); nc = v & 1                # sra
        elif k == 6: r = ((v << 1) | 1) & 0xFF; nc = v >> 7               # sll
        else: r = v >> 1; nc = v & 1                                      # srl
        self.f = self.szf(r) | parity(r) | nc
        return r

    def daa(self):
        a, f = self.a, self.f
        corr, c = 0, f & 1
        if (f & 0x10) or (a & 0xF) > 9:
            corr |= 6
        if c or a > 0x99:
            corr |= 0x60
            c = 1
        if f & 2:
            h = 0x10 if (f & 0x10) and (a & 0xF) < 6 else 0
            a = (a - corr) & 0xFF
        else:
            h = 0x10 if (a & 0xF) > 9 else 0
            a = (a + corr) & 0xFF
        self.a = a
        self.f = self.szf(a) | parity(a) | h | (f & 2) | c

    # ---------------- vegrehajtas
    def step(self):
        op = self.fetch()
        if op == 0xCB: return self.cb(self.fetch(), None)
        if op == 0xDD: return self.ddfd('ix')
        if op == 0xFD: return self.ddfd('iy')
        if op == 0xED: return self.ed(self.fetch())
        x, y, z = op >> 6, (op >> 3) & 7, op & 7
        if x == 1:
            if op == 0x76:
                raise RuntimeError('HALT')
            self.sr(y, self.gr(z))
            return
        if x == 2:
            self.alu(y, self.gr(z))
            return
        if op == 0x00: return
        if op == 0x08:
            self.a, self.a_ = self.a_, self.a
            self.f, self.f_ = self.f_, self.f
            return
        if op == 0x10:
            d = self.fetch()
            self.b = (self.b - 1) & 0xFF
            if self.b:
                self.pc = (self.pc + d - (256 if d > 127 else 0)) & 0xFFFF
            return
        if op in (0x18, 0x20, 0x28, 0x30, 0x38):
            d = self.fetch()
            if op == 0x18 or self.cond((op >> 3) & 3):
                self.pc = (self.pc + d - (256 if d > 127 else 0)) & 0xFFFF
            return
        if x == 0 and z == 1:
            p, q = y >> 1, y & 1
            if q == 0:
                v = self.fetchw()
                (self.sbc_, self.sde, self.shl, lambda w: setattr(self, 'sp', w))[p](v)
            else:
                hl = self.ghl()
                rr = (self.gbc(), self.gde(), hl, self.sp)[p]
                r = hl + rr
                self.f = (self.f & 0xC4) | (0x10 if ((hl & 0xFFF) + (rr & 0xFFF)) > 0xFFF else 0) | (1 if r > 0xFFFF else 0)
                self.shl(r & 0xFFFF)
            return
        if op == 0x02: self.wb(self.gbc(), self.a); return
        if op == 0x12: self.wb(self.gde(), self.a); return
        if op == 0x0A: self.a = self.rb(self.gbc()); return
        if op == 0x1A: self.a = self.rb(self.gde()); return
        if op == 0x22: self.ww(self.fetchw(), self.ghl()); return
        if op == 0x2A: self.shl(self.rw(self.fetchw())); return
        if op == 0x32: self.wb(self.fetchw(), self.a); return
        if op == 0x3A: self.a = self.rb(self.fetchw()); return
        if x == 0 and z == 3:
            p = y >> 1
            g = (self.gbc, self.gde, self.ghl, lambda: self.sp)[p]()
            v = (g + (1 if y & 1 == 0 else -1)) & 0xFFFF
            (self.sbc_, self.sde, self.shl, lambda w: setattr(self, 'sp', w))[p](v)
            return
        if x == 0 and z == 4: self.sr(y, self.inc8(self.gr(y))); return
        if x == 0 and z == 5: self.sr(y, self.dec8(self.gr(y))); return
        if x == 0 and z == 6: self.sr(y, self.fetch()); return
        if op == 0x07:
            self.a = ((self.a << 1) | (self.a >> 7)) & 0xFF; self.f = (self.f & 0xC4) | (self.a & 1); return
        if op == 0x0F:
            c = self.a & 1; self.a = (self.a >> 1) | (c << 7); self.f = (self.f & 0xC4) | c; return
        if op == 0x17:
            c = self.a >> 7; self.a = ((self.a << 1) | (self.f & 1)) & 0xFF; self.f = (self.f & 0xC4) | c; return
        if op == 0x1F:
            c = self.a & 1; self.a = (self.a >> 1) | ((self.f & 1) << 7); self.f = (self.f & 0xC4) | c; return
        if op == 0x27: self.daa(); return
        if op == 0x2F: self.a ^= 0xFF; self.f |= 0x12; return
        if op == 0x37: self.f = (self.f & 0xC4) | 1; return
        if op == 0x3F: self.f = (self.f & 0xC4) | (0x10 if self.f & 1 else 0) | ((self.f & 1) ^ 1); return
        # x == 3
        if z == 0:
            if self.cond(y): self.pc = self.pop()
            return
        if op == 0xC9: self.pc = self.pop(); return
        if z == 1:
            p = y >> 1
            if y & 1 == 0:
                v = self.pop()
                if p == 0: self.sbc_(v)
                elif p == 1: self.sde(v)
                elif p == 2: self.shl(v)
                else: self.a, self.f = v >> 8, v & 0xFF
                return
            if op == 0xD9:
                self.b, self.b_ = self.b_, self.b; self.c, self.c_ = self.c_, self.c
                self.d, self.d_ = self.d_, self.d; self.e, self.e_ = self.e_, self.e
                self.h, self.h_ = self.h_, self.h; self.l, self.l_ = self.l_, self.l
                return
            if op == 0xE9: self.pc = self.ghl(); return
            if op == 0xF9: self.sp = self.ghl(); return
        if z == 2:
            t = self.fetchw()
            if self.cond(y): self.pc = t
            return
        if op == 0xC3: self.pc = self.fetchw(); return
        if op == 0xD3: self.fetch(); return                                  # out (n),a
        if op == 0xDB: self.fetch(); self.a = 0xFF; return                   # in a,(n)
        if op == 0xE3:
            v = self.rw(self.sp); self.ww(self.sp, self.ghl()); self.shl(v); return
        if op == 0xEB:
            self.d, self.h = self.h, self.d; self.e, self.l = self.l, self.e; return
        if op == 0xF3: self.iff = 0; return
        if op == 0xFB: self.iff = 1; return
        if z == 4:
            t = self.fetchw()
            if self.cond(y):
                self.push(self.pc); self.pc = t
            return
        if z == 5:
            if op == 0xCD:
                t = self.fetchw(); self.push(self.pc); self.pc = t; return
            p = y >> 1
            v = (self.gbc(), self.gde(), self.ghl(), (self.a << 8) | self.f)[p]
            self.push(v)
            return
        if z == 6:
            self.alu(y, self.fetch())
            return
        if z == 7:
            self.push(self.pc); self.pc = y * 8; return
        raise RuntimeError('ismeretlen Z80 utasitas %02X @%04X' % (op, (self.pc - 1) & 0xFFFF))

    def cb(self, op, addr):
        x, y, z = op >> 6, (op >> 3) & 7, op & 7
        v = self.rb(addr) if addr is not None else self.gr(z)
        if x == 0:
            r = self.rot(y, v)
        elif x == 1:
            self.f = (self.f & 1) | 0x10 | (0 if v & (1 << y) else 0x44) | (0x80 if y == 7 and v & 0x80 else 0)
            return
        elif x == 2:
            r = v & ~(1 << y)
        else:
            r = v | (1 << y)
        if addr is not None:
            self.wb(addr, r)
        else:
            self.sr(z, r)

    def ddfd(self, reg):
        op = self.fetch()
        ix = getattr(self, reg)
        def disp():
            d = self.fetch()
            return (ix + d - (256 if d > 127 else 0)) & 0xFFFF
        if op == 0x21: setattr(self, reg, self.fetchw()); return
        if op == 0x2A: setattr(self, reg, self.rw(self.fetchw())); return
        if op == 0x22: self.ww(self.fetchw(), ix); return
        if op == 0xE9: self.pc = ix; return
        if op == 0xE1: setattr(self, reg, self.pop()); return
        if op == 0xE5: self.push(ix); return
        if op in (0x09, 0x19, 0x29, 0x39):
            rr = (self.gbc(), self.gde(), ix, self.sp)[(op >> 4) & 3]
            r = ix + rr
            self.f = (self.f & 0xC4) | (0x10 if ((ix & 0xFFF) + (rr & 0xFFF)) > 0xFFF else 0) | (1 if r > 0xFFFF else 0)
            setattr(self, reg, r & 0xFFFF)
            return
        if op == 0x23: setattr(self, reg, (ix + 1) & 0xFFFF); return
        if op == 0x2B: setattr(self, reg, (ix - 1) & 0xFFFF); return
        if op == 0x36:
            a = disp(); self.wb(a, self.fetch()); return
        if op == 0xCB:
            a = disp(); return self.cb(self.fetch(), a)
        if op in (0x34, 0x35):
            a = disp(); self.wb(a, self.inc8(self.rb(a)) if op == 0x34 else self.dec8(self.rb(a))); return
        x, y, z = op >> 6, (op >> 3) & 7, op & 7
        if x == 1 and (z == 6) != (y == 6):
            if z == 6:
                self.sr(y, self.rb(disp()))
            else:
                self.wb(disp(), self.gr(z))
            return
        if x == 2 and z == 6:
            self.alu(y, self.rb(disp())); return
        # IXH/IXL (nem dokumentalt): ld r,ixh/ixl, ld ixh/ixl,r
        if x == 1:
            def g(i):
                if i == 4: return ix >> 8
                if i == 5: return ix & 0xFF
                return self.gr(i)
            v = g(z)
            if y == 4: setattr(self, reg, (ix & 0xFF) | (v << 8))
            elif y == 5: setattr(self, reg, (ix & 0xFF00) | v)
            else: self.sr(y, v)
            return
        raise RuntimeError('ismeretlen %s utasitas %02X @%04X' % (reg, op, (self.pc - 2) & 0xFFFF))

    def ed(self, op):
        if op in (0x43, 0x53, 0x63, 0x73):
            v = (self.gbc(), self.gde(), self.ghl(), self.sp)[(op >> 4) & 3]
            self.ww(self.fetchw(), v); return
        if op in (0x4B, 0x5B, 0x6B, 0x7B):
            v = self.rw(self.fetchw())
            (self.sbc_, self.sde, self.shl, lambda w: setattr(self, 'sp', w))[(op >> 4) & 3](v); return
        if op in (0x42, 0x52, 0x62, 0x72, 0x4A, 0x5A, 0x6A, 0x7A):
            hl = self.ghl()
            rr = (self.gbc(), self.gde(), hl, self.sp)[(op >> 4) & 3]
            c = self.f & 1
            if op & 8:
                r = hl + rr + c
                f = (1 if r > 0xFFFF else 0) | (4 if (~(hl ^ rr) & (hl ^ r) & 0x8000) else 0)
                f |= 0x10 if ((hl & 0xFFF) + (rr & 0xFFF) + c) > 0xFFF else 0
            else:
                r = hl - rr - c
                f = 2 | (1 if r < 0 else 0) | (4 if ((hl ^ rr) & (hl ^ r) & 0x8000) else 0)
                f |= 0x10 if ((hl & 0xFFF) - (rr & 0xFFF) - c) < 0 else 0
            r &= 0xFFFF
            f |= (0x80 if r & 0x8000 else 0) | (0x40 if r == 0 else 0)
            self.shl(r)
            self.f = f
            return
        if op == 0x44:
            v = self.a; self.a = 0; self.sub8(v); return
        if op in (0x46, 0x56, 0x5E): return                                  # im
        if op == 0x47: return                                                # ld i,a
        if op == 0x57: return                                                # ld a,i
        if op in (0x4D, 0x45): self.pc = self.pop(); return                  # reti/retn
        if op == 0xB0:
            while True:
                self.wb(self.gde(), self.rb(self.ghl()))
                self.shl((self.ghl() + 1) & 0xFFFF); self.sde((self.gde() + 1) & 0xFFFF)
                bc = (self.gbc() - 1) & 0xFFFF; self.sbc_(bc)
                if bc == 0: break
            self.f &= 0xC1
            return
        if op == 0x78: self.a = 0xFF; return                                 # in a,(c)
        if op in (0x40, 0x48, 0x50, 0x58, 0x60, 0x68): self.sr((op >> 3) & 7, 0xFF); return    # in r,(c)
        if op in (0x41, 0x49, 0x51, 0x59, 0x61, 0x69, 0x79): return          # out (c),r
        raise RuntimeError('ismeretlen ED utasitas %02X @%04X' % (op, (self.pc - 2) & 0xFFFF))

#!/usr/bin/env python3
"""Kis 6502-emulator a .sid fajlok lejatszo rutinjanak futtatasahoz (csak a hivatalos utasitasok).
A SID-irasokat ($D400-$D41F) a `sid_write` visszahivas kapja meg, sorrendben."""
import random


class CPU6502:
    def __init__(self, mem, sid_write=None):
        self.m = mem
        self.a = self.x = self.y = 0
        self.sp = 0xFF
        self.pc = 0
        self.c = self.z = self.i = self.d = self.v = self.n = 0
        self.sid_write = sid_write
        self.raster = 0
        self.sid_regs = [0] * 32
        self.rnd = random.Random(1)

    # ------------------------------------------------------------ memoria
    def rd(self, a):
        if 0xD000 <= a < 0xE000:
            if a == 0xD012:
                self.raster = (self.raster + 1) & 0xFF
                return self.raster
            if a == 0xD011:
                return 0x1B
            if 0xD400 <= a < 0xD800:
                r = a & 0x1F
                if r == 0x1B:
                    return self.rnd.randrange(256)
                if r == 0x1C:
                    return 0
                return 0
        return self.m[a]

    def wr(self, a, v):
        if 0xD400 <= a < 0xD800:
            r = a & 0x1F
            self.sid_regs[r] = v
            if self.sid_write:
                self.sid_write(r, v)
            return
        self.m[a] = v

    def rw(self, a):
        return self.rd(a) | (self.rd((a + 1) & 0xFFFF) << 8)

    def push(self, v):
        self.m[0x100 + self.sp] = v & 0xFF
        self.sp = (self.sp - 1) & 0xFF

    def pull(self):
        self.sp = (self.sp + 1) & 0xFF
        return self.m[0x100 + self.sp]

    def get_p(self):
        return (self.n << 7) | (self.v << 6) | 0x20 | (self.d << 3) | (self.i << 2) | (self.z << 1) | self.c

    def set_p(self, p):
        self.n, self.v, self.d = (p >> 7) & 1, (p >> 6) & 1, (p >> 3) & 1
        self.i, self.z, self.c = (p >> 2) & 1, (p >> 1) & 1, p & 1

    def nz(self, v):
        self.n = (v >> 7) & 1
        self.z = 1 if v == 0 else 0
        return v

    # ------------------------------------------------------------ cimzes: (cim) a PC utan
    def fetch(self):
        v = self.m[self.pc]
        self.pc = (self.pc + 1) & 0xFFFF
        return v

    def fetchw(self):
        lo = self.fetch()
        return lo | (self.fetch() << 8)

    def ea(self, mode):
        if mode == 'zp':
            return self.fetch()
        if mode == 'zpx':
            return (self.fetch() + self.x) & 0xFF
        if mode == 'zpy':
            return (self.fetch() + self.y) & 0xFF
        if mode == 'abs':
            return self.fetchw()
        if mode == 'abx':
            return (self.fetchw() + self.x) & 0xFFFF
        if mode == 'aby':
            return (self.fetchw() + self.y) & 0xFFFF
        if mode == 'izx':
            z = (self.fetch() + self.x) & 0xFF
            return self.m[z] | (self.m[(z + 1) & 0xFF] << 8)
        if mode == 'izy':
            z = self.fetch()
            return ((self.m[z] | (self.m[(z + 1) & 0xFF] << 8)) + self.y) & 0xFFFF
        raise ValueError(mode)

    def operand(self, mode):
        if mode == 'imm':
            return self.fetch()
        return self.rd(self.ea(mode))

    # ------------------------------------------------------------ aritmetika
    def adc(self, v):
        if self.d:
            lo = (self.a & 0xF) + (v & 0xF) + self.c
            hi = (self.a >> 4) + (v >> 4)
            if lo > 9:
                lo += 6
                hi += 1
            self.z = 1 if ((self.a + v + self.c) & 0xFF) == 0 else 0
            self.n = (hi >> 3) & 1
            self.v = 1 if (~(self.a ^ v) & (self.a ^ (hi << 4)) & 0x80) else 0
            if hi > 9:
                hi += 6
            self.c = 1 if hi > 15 else 0
            self.a = ((hi << 4) | (lo & 0xF)) & 0xFF
            return
        r = self.a + v + self.c
        self.v = 1 if (~(self.a ^ v) & (self.a ^ r) & 0x80) else 0
        self.c = 1 if r > 0xFF else 0
        self.a = self.nz(r & 0xFF)

    def sbc(self, v):
        if self.d:
            r = self.a - v - (1 - self.c)
            lo = (self.a & 0xF) - (v & 0xF) - (1 - self.c)
            hi = (self.a >> 4) - (v >> 4)
            if lo < 0:
                lo -= 6
                hi -= 1
            if hi < 0:
                hi -= 6
            self.v = 1 if ((self.a ^ v) & (self.a ^ r) & 0x80) else 0
            self.c = 1 if r >= 0 else 0
            self.nz(r & 0xFF)
            self.a = ((hi << 4) | (lo & 0xF)) & 0xFF
            return
        r = self.a - v - (1 - self.c)
        self.v = 1 if ((self.a ^ v) & (self.a ^ r) & 0x80) else 0
        self.c = 1 if r >= 0 else 0
        self.a = self.nz(r & 0xFF)

    def cmp(self, reg, v):
        r = reg - v
        self.c = 1 if r >= 0 else 0
        self.nz(r & 0xFF)

    def branch(self, cond):
        off = self.fetch()
        if cond:
            if off > 127:
                off -= 256
            self.pc = (self.pc + off) & 0xFFFF

    def rmw(self, mode, fn):
        if mode == 'acc':
            self.a = fn(self.a)
            return
        a = self.ea(mode)
        self.wr(a, fn(self.rd(a)))

    # ------------------------------------------------------------ hivas
    def call(self, addr, a=0, x=0, y=0, max_steps=2_000_000):
        """JSR addr; addig fut, amig a visszateres a szentinelre er."""
        SENT = 0xFFF0
        self.m[SENT] = 0x00
        self.a, self.x, self.y = a, x, y
        ret = SENT - 1
        self.push(ret >> 8)
        self.push(ret & 0xFF)
        self.pc = addr
        steps = 0
        while self.pc != SENT:
            self.step()
            steps += 1
            if steps > max_steps:
                raise RuntimeError('tul hosszu hivas: $%04X' % addr)
        return steps

    def step(self):
        op = self.fetch()
        f = OPS.get(op)
        if f is None:
            raise RuntimeError('ismeretlen utasitas $%02X a $%04X cimen' % (op, (self.pc - 1) & 0xFFFF))
        f(self)


OPS = {}


def _def(codes, fn):
    for op, mode in codes:
        OPS[op] = (lambda m: (lambda c: fn(c, m)))(mode)


def _asl(c, v):
    c.c = (v >> 7) & 1
    return c.nz((v << 1) & 0xFF)


def _lsr(c, v):
    c.c = v & 1
    return c.nz(v >> 1)


def _rol(c, v):
    r = ((v << 1) | c.c) & 0xFF
    c.c = (v >> 7) & 1
    return c.nz(r)


def _ror(c, v):
    r = (v >> 1) | (c.c << 7)
    c.c = v & 1
    return c.nz(r)


M8 = ['imm', 'zp', 'zpx', 'abs', 'abx', 'aby', 'izx', 'izy']


def _grp(base_codes):
    return list(zip(base_codes, M8))


_def(_grp([0xA9, 0xA5, 0xB5, 0xAD, 0xBD, 0xB9, 0xA1, 0xB1]), lambda c, m: setattr(c, 'a', c.nz(c.operand(m))))
_def(_grp([0x09, 0x05, 0x15, 0x0D, 0x1D, 0x19, 0x01, 0x11]), lambda c, m: setattr(c, 'a', c.nz(c.a | c.operand(m))))
_def(_grp([0x29, 0x25, 0x35, 0x2D, 0x3D, 0x39, 0x21, 0x31]), lambda c, m: setattr(c, 'a', c.nz(c.a & c.operand(m))))
_def(_grp([0x49, 0x45, 0x55, 0x4D, 0x5D, 0x59, 0x41, 0x51]), lambda c, m: setattr(c, 'a', c.nz(c.a ^ c.operand(m))))
_def(_grp([0x69, 0x65, 0x75, 0x6D, 0x7D, 0x79, 0x61, 0x71]), lambda c, m: c.adc(c.operand(m)))
_def(_grp([0xE9, 0xE5, 0xF5, 0xED, 0xFD, 0xF9, 0xE1, 0xF1]), lambda c, m: c.sbc(c.operand(m)))
_def([(0xEB, 'imm')], lambda c, m: c.sbc(c.operand(m)))
_def(_grp([0xC9, 0xC5, 0xD5, 0xCD, 0xDD, 0xD9, 0xC1, 0xD1]), lambda c, m: c.cmp(c.a, c.operand(m)))
_def([(0xE0, 'imm'), (0xE4, 'zp'), (0xEC, 'abs')], lambda c, m: c.cmp(c.x, c.operand(m)))
_def([(0xC0, 'imm'), (0xC4, 'zp'), (0xCC, 'abs')], lambda c, m: c.cmp(c.y, c.operand(m)))
_def([(0xA2, 'imm'), (0xA6, 'zp'), (0xB6, 'zpy'), (0xAE, 'abs'), (0xBE, 'aby')],
     lambda c, m: setattr(c, 'x', c.nz(c.operand(m))))
_def([(0xA0, 'imm'), (0xA4, 'zp'), (0xB4, 'zpx'), (0xAC, 'abs'), (0xBC, 'abx')],
     lambda c, m: setattr(c, 'y', c.nz(c.operand(m))))
_def([(0x85, 'zp'), (0x95, 'zpx'), (0x8D, 'abs'), (0x9D, 'abx'), (0x99, 'aby'), (0x81, 'izx'), (0x91, 'izy')],
     lambda c, m: c.wr(c.ea(m), c.a))
_def([(0x86, 'zp'), (0x96, 'zpy'), (0x8E, 'abs')], lambda c, m: c.wr(c.ea(m), c.x))
_def([(0x84, 'zp'), (0x94, 'zpx'), (0x8C, 'abs')], lambda c, m: c.wr(c.ea(m), c.y))


def _bit(c, m):
    v = c.operand(m)
    c.z = 1 if (c.a & v) == 0 else 0
    c.n, c.v = (v >> 7) & 1, (v >> 6) & 1


_def([(0x24, 'zp'), (0x2C, 'abs')], _bit)
RM = ['acc', 'zp', 'zpx', 'abs', 'abx']
for codes, fn in (([0x0A, 0x06, 0x16, 0x0E, 0x1E], _asl), ([0x4A, 0x46, 0x56, 0x4E, 0x5E], _lsr),
                  ([0x2A, 0x26, 0x36, 0x2E, 0x3E], _rol), ([0x6A, 0x66, 0x76, 0x6E, 0x7E], _ror)):
    _def(list(zip(codes, RM)), (lambda f: (lambda c, m: c.rmw(m, lambda v: f(c, v))))(fn))
_def([(0xE6, 'zp'), (0xF6, 'zpx'), (0xEE, 'abs'), (0xFE, 'abx')], lambda c, m: c.rmw(m, lambda v: c.nz((v + 1) & 0xFF)))
_def([(0xC6, 'zp'), (0xD6, 'zpx'), (0xCE, 'abs'), (0xDE, 'abx')], lambda c, m: c.rmw(m, lambda v: c.nz((v - 1) & 0xFF)))

IMPL = {
    0xE8: lambda c: setattr(c, 'x', c.nz((c.x + 1) & 0xFF)),
    0xCA: lambda c: setattr(c, 'x', c.nz((c.x - 1) & 0xFF)),
    0xC8: lambda c: setattr(c, 'y', c.nz((c.y + 1) & 0xFF)),
    0x88: lambda c: setattr(c, 'y', c.nz((c.y - 1) & 0xFF)),
    0xAA: lambda c: setattr(c, 'x', c.nz(c.a)),
    0x8A: lambda c: setattr(c, 'a', c.nz(c.x)),
    0xA8: lambda c: setattr(c, 'y', c.nz(c.a)),
    0x98: lambda c: setattr(c, 'a', c.nz(c.y)),
    0xBA: lambda c: setattr(c, 'x', c.nz(c.sp)),
    0x9A: lambda c: setattr(c, 'sp', c.x),
    0x48: lambda c: c.push(c.a),
    0x68: lambda c: setattr(c, 'a', c.nz(c.pull())),
    0x08: lambda c: c.push(c.get_p() | 0x10),
    0x28: lambda c: c.set_p(c.pull()),
    0x18: lambda c: setattr(c, 'c', 0), 0x38: lambda c: setattr(c, 'c', 1),
    0x58: lambda c: setattr(c, 'i', 0), 0x78: lambda c: setattr(c, 'i', 1),
    0xB8: lambda c: setattr(c, 'v', 0),
    0xD8: lambda c: setattr(c, 'd', 0), 0xF8: lambda c: setattr(c, 'd', 1),
    0xEA: lambda c: None,
}
for _op, _f in IMPL.items():
    OPS[_op] = _f


def _jsr(c):
    t = c.fetchw()
    r = (c.pc - 1) & 0xFFFF
    c.push(r >> 8)
    c.push(r & 0xFF)
    c.pc = t


def _rts(c):
    lo = c.pull()
    c.pc = ((lo | (c.pull() << 8)) + 1) & 0xFFFF


def _rti(c):
    c.set_p(c.pull())
    lo = c.pull()
    c.pc = lo | (c.pull() << 8)


def _jmpi(c):
    a = c.fetchw()
    c.pc = c.m[a] | (c.m[(a & 0xFF00) | ((a + 1) & 0xFF)] << 8)


OPS[0x20] = _jsr
OPS[0x60] = _rts
OPS[0x40] = _rti
OPS[0x4C] = lambda c: setattr(c, 'pc', c.fetchw())
OPS[0x6C] = _jmpi
for _op, _cond in ((0x10, lambda c: not c.n), (0x30, lambda c: c.n), (0x50, lambda c: not c.v),
                   (0x70, lambda c: c.v), (0x90, lambda c: not c.c), (0xB0, lambda c: c.c),
                   (0xD0, lambda c: not c.z), (0xF0, lambda c: c.z)):
    OPS[_op] = (lambda cond: (lambda c: c.branch(cond(c))))(_cond)

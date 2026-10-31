#!/usr/bin/env python3
"""A TVC-s 6502-emulator (SIDSoftEMU.bin) futtatasa a Python Z80-emulatorban, lepesrol lepesre osszevetve
a referencia 6502-emulatorral (tools/m6502.py).

  python3 tools/z80_cpu_teszt.py [sid] [aldal] [kepkockak]
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from z80 import Z80
from m6502 import CPU6502
from sid_dump import load_sid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SID_IMG = 0x58


def symbols():
    s = {}
    for line in open(os.path.join(ROOT, 'SIDSoftEMU.sym')):
        t = line.split()
        if len(t) == 3 and t[0] == 'al':
            s[t[2].lstrip('.')] = int(t[1].lstrip('$'), 16)
    return s


def main():
    sidp = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'sid', 'LNINJA.SID')
    song = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    nfr = int(sys.argv[3]) if len(sys.argv) > 3 else 20
    S = symbols()
    mem = bytearray(65536)
    binf = open(os.path.join(ROOT, 'SIDSoftEMU.bin'), 'rb').read()
    mem[0x19EF:0x19EF + len(binf)] = binf
    sid = load_sid(sidp)
    raw = open(sidp, 'rb').read()
    load, data = sid['load'], sid['data']
    hdr = raw[:0x7C]
    mem[S['SidFej']:S['SidFej'] + len(hdr)] = hdr
    mem[S['SidLoad']] = load & 0xFF
    mem[S['SidLoad'] + 1] = load >> 8
    mem[S['SidHossz']] = len(data) & 0xFF
    mem[S['SidHossz'] + 1] = len(data) >> 8
    base = (SID_IMG << 8) | (load & 0xFF)
    mem[base:base + len(data)] = data
    z = Z80(mem)
    # CpuInit parameterek (mint a CpuTeszt)
    npages = ((load & 0xFF) + len(data) + 255) >> 8
    mem[S['CpuImgLap']] = SID_IMG
    mem[S['CpuImg6502']] = load >> 8
    mem[S['CpuImgDb']] = npages
    mem[S['CpuPoolMin']] = SID_IMG + npages

    def zcall(addr, limit=50_000_000, hook=None):
        z.sp = 0x1800
        z.push(0x0000)              # visszateres a $0000-ra = vege
        z.pc = addr
        n = 0
        while z.pc != 0x0000:
            if hook:
                hook()
            z.step()
            n += 1
            if n > limit:
                raise RuntimeError('tul sok Z80-lepes')
        return n

    zcall(S['CpuInit'])
    handlers = set()
    for op in range(256):
        handlers.add(mem[0xF800 + op] | (mem[0xF900 + op] << 8))

    ref_mem = bytearray(65536)
    ref_mem[load:load + len(data)] = data
    ref_mem[1] = 0x37
    ref = CPU6502(ref_mem)
    state = {'n': 0, 'started': False}

    def tvc_pc():
        host = (z.sp - 2) & 0xFFFF
        return (host + (mem[S['CpuNDelta']] << 8)) & 0xFFFF

    def hook():
        if z.pc in handlers and state['started']:
            # utasitas eleje: osszevetes
            a6, f6 = z.a_, z.f_
            mine = dict(pc=tvc_pc(), a=a6, x=z.b, y=z.c, n=(f6 >> 7) & 1, z=(f6 >> 6) & 1, c=f6 & 1,
                        sp=mem[S['CpuS']])
            if state.get('lastpc') == mine['pc'] and state.get('pool') != mem[S['CpuPool']]:
                state['pool'] = mem[S['CpuPool']]          # lapfoglalas utan ujra ugyanaz az utasitas
                return
            refs = dict(pc=ref.pc, a=ref.a, x=ref.x, y=ref.y, n=ref.n, z=ref.z, c=ref.c, sp=ref.sp)
            if mine != refs:
                print('ELTERES a(z) %d. utasitasnal:' % state['n'])
                print('  TVC:', {k: hex(v) for k, v in mine.items()})
                print('  ref:', {k: hex(v) for k, v in refs.items()})
                print('  opkod: $%02X (ref mem), elozo: %s' % (ref_mem[ref.pc], state.get('prev')))
                raise SystemExit(1)
            state['prev'] = '$%04X:%02X' % (ref.pc, ref_mem[ref.pc])
            state['lastpc'] = mine['pc']
            state['pool'] = mem[S['CpuPool']]
            state['n'] += 1
            if ref.pc != 0xFFF0:
                ref.step()

    # init
    for fr in range(nfr + 1):
        addr = sid['init'] if fr == 0 else sid['play']
        mem[S['CpuCim']] = addr & 0xFF
        mem[S['CpuCim'] + 1] = addr >> 8
        mem[S['CpuA']] = (song - 1) if fr == 0 else 0
        mem[S['CpuLogN']] = 0
        # a referencia: ugyanaz a hivas kezdete (sentinel a veremre)
        SENT = 0xFFF0
        ref.a, ref.x, ref.y = mem[S['CpuA']], 0, 0
        ret = SENT - 1
        ref.push(ret >> 8)
        ref.push(ret & 0xFF)
        ref.pc = addr
        state['started'] = True
        n = zcall(S['CpuHiv'], hook=hook)
        err = mem[S['CpuErr']]
        print('%s: %d Z80-lepes, %d 6502-utasitas eddig, hiba=%d, pool=$%02X' %
              ('init' if fr == 0 else 'play %d' % fr, n, state['n'], err, mem[S['CpuPool']]))
        if err:
            print('  hibas opkod $%02X @ $%04X' % (mem[S['CpuErrOp']], mem[S['CpuErrCim']] | (mem[S['CpuErrCim'] + 1] << 8)))
            break
    print('OK: %d 6502-utasitas egyezik' % state['n'])


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
""".sid (PSID/RSID) -> kepkockankenti SID-irasok, a 6502-emulatorral (tools/m6502.py).

dump(path, song) -> dict: frames = [[(reg, ertek), ...] kepkockankent], loop = a hurok kezdokockaja
(vagy None), info. A hurkot a teljes 6502-memoria (+ SID-regiszterek) ismetlodesebol talalja meg.
Parancssor: python3 tools/sid_dump.py fajl.sid  -> az osszes aldal hossza es hurokpontja."""
import hashlib, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from m6502 import CPU6502


def load_sid(path):
    b = open(path, 'rb').read()
    magic = b[0:4].decode('latin1')
    ver = b[5]
    off = (b[6] << 8) | b[7]
    load = (b[8] << 8) | b[9]
    init = (b[10] << 8) | b[11]
    play = (b[12] << 8) | b[13]
    songs = (b[14] << 8) | b[15]
    start = (b[16] << 8) | b[17]
    speed = int.from_bytes(b[18:22], 'big')
    name, author, rel = (b[22 + 32 * i:54 + 32 * i].split(b'\0')[0].decode('latin1') for i in range(3))
    data = b[off:]
    if load == 0:
        load = data[0] | (data[1] << 8)
        data = data[2:]
    return dict(magic=magic, ver=ver, load=load, init=init, play=play, songs=songs, start=start,
                speed=speed, name=name, author=author, released=rel, data=data)


def dump(path, song, max_frames=15000):
    s = load_sid(path)
    if s['play'] == 0:
        raise RuntimeError('a play cim 0 (IRQ-t allit be) - meg nincs kezelve')
    if (s['speed'] >> min(song - 1, 31)) & 1:
        raise RuntimeError('CIA-idozitesu aldal - meg nincs kezelve')
    mem = bytearray(65536)
    mem[s['load']:s['load'] + len(s['data'])] = s['data']
    mem[0x01] = 0x37
    cur = []
    cpu = CPU6502(mem, lambda r, v: cur.append((r, v)))
    cpu.call(s['init'], a=song - 1)
    frames, seen, loop = [], {}, None
    init_writes = list(cur)
    for fr in range(max_frames):
        h = hashlib.md5(bytes(mem) + bytes(cpu.sid_regs)).digest()
        if h in seen:
            loop = seen[h]
            break
        seen[h] = fr
        cur.clear()
        cpu.call(s['play'])
        frames.append(list(cur))
    if frames:
        frames[0] = init_writes + frames[0]
    return dict(frames=frames, loop=loop, info=s)


def main():
    path = sys.argv[1]
    s = load_sid(path)
    print('%s / %s / %s  - %d aldal, kezdo: %d, load $%04X init $%04X play $%04X, %d byte'
          % (s['name'], s['author'], s['released'], s['songs'], s['start'], s['load'], s['init'],
             s['play'], len(s['data'])))
    songs = [int(a) for a in sys.argv[2:]] or range(1, s['songs'] + 1)
    for n in songs:
        try:
            d = dump(path, n)
            nf = len(d['frames'])
            lp = d['loop']
            print('  %2d. aldal: %5d kepkocka (%5.1f s), hurok: %s' %
                  (n, nf, nf / 50.0, ('%d. kockatol (%.1f s)' % (lp, lp / 50.0)) if lp is not None else 'nincs'))
        except Exception as e:
            print('  %2d. aldal: HIBA %s' % (n, e))


if __name__ == '__main__':
    main()

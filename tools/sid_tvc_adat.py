#!/usr/bin/env python3
"""A TVC-s SID-teszt adatai (4 valtozat) + a TVC pontos modellje.

Kimenet:
  resources/sid_tablak.bin - 62 lap (256 byte), a TVC $C000-ra (U3) masolja
  resources/sid_adat.bin   - hangmagassag, savok, burkolo, hangszerek, dal; a TVC $7000-ra masolja
  hang_minta/6..9_valtozat_N.wav - pontosan ezt kell szolnia a TVC-n az 1..4 gombra

Tablalapok ($C0 + lap):
  0         csend
  1-15      1. valtozat: fures/haromszog/zaj, amp 1..5, ertek = szint*4 (0..20)
  16-36     2-4. valtozat: fures/haromszog/zaj, amp 1..7, ertek = szint (0..7)
  37-57     3-4. valtozat: "szurt" (savkorlatozott) fures, 3 sav x amp 1..7
  58        keveres, 1. valtozat: osszeg (0..60, 4-esevel) -> port 6 ertek
  59        keveres, 2-4. valtozat: osszeg (0..21) -> port 6, lagy tomorites
  60, 61    tartalek
Adat ($7000):
  $7000 lo/hi lepes 5008 Hz-hez, $7100 lo/hi 3986 Hz-hez, $7200 sav[128] 5008, $7280 sav[128] 3986,
  $7300 amp_A[16] (0..5), $7310 amp_B[16] (0..7), $7320 hangszer[8][5], $7360 dal
"""
import math, os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sid_modell import build_song, midi_hz, write_wav, OUT_RATE, STEP_FRAMES

CPU = 3125000
RATES = [CPU / 16 / 39, CPU / 16 / 49]      # 5008 Hz (port 4 = $D9), 3986 Hz ($CF)
IT_PER_FRAME = [100, 80]
WAVES = {'saw': 0, 'tri': 1, 'noise': 2, 'pulse': 3}
BAND_H = [8, 4, 2]                          # savonkent a felhangok szama (a 3-4. valtozat fureszenel)
NPAGES = 62

def soft_saw(H):
    """Savkorlatozott fures 0..1, H felhang, Lanczos-simitas (kevesebb tulloves)."""
    vals = []
    for i in range(256):
        x = 2 * math.pi * i / 256
        s = 0.0
        for k in range(1, H + 1):
            sig = 1.0 if k == 1 else math.sin(math.pi * k / (H + 1)) / (math.pi * k / (H + 1))
            s += sig * math.sin(k * x) / k
        vals.append(-s)                     # emelkedo fures
    lo, hi = min(vals), max(vals)
    return [(v - lo) / (hi - lo) for v in vals]

def build_tables():
    random.seed(64)
    noise = [random.random() for _ in range(256)]
    saw = [i / 255 for i in range(256)]
    tri = [(t if t < 16 else 31 - t) / 15 for t in ((i >> 3) for i in range(256))]
    pages = [[0] * 256]
    # 1. valtozat (pontosan a regi: 4 bites alak, amp 1..5, *4)
    for shape in ('saw', 'tri', 'noise'):
        for amp in range(1, 6):
            row = []
            for i in range(256):
                w = {'saw': i >> 4, 'tri': (lambda t: t if t < 16 else 31 - t)(i >> 3),
                     'noise': int(noise[i] * 16)}[shape]
                row.append(((w * amp + 7) // 15) * 4)
            pages.append(row)
    # 2-4. valtozat: amp 1..7
    for shape in (saw, tri, noise):
        for amp in range(1, 8):
            pages.append([min(amp, int(shape[i] * amp + 0.5)) for i in range(256)])
    for H in BAND_H:
        s = soft_saw(H)
        for amp in range(1, 8):
            pages.append([min(amp, int(s[i] * amp + 0.5)) for i in range(256)])
    assert len(pages) == 58
    pages.append([((i >> 2) << 2) | 1 for i in range(256)])          # keveres A: az osszeg mar *4
    mixb = []
    for s in range(256):
        x = min(s, 21) / 21
        lvl = round(15 * (1 - math.exp(-2.2 * x)) / (1 - math.exp(-2.2)))
        mixb.append((lvl << 2) | 1)
    pages.append(mixb)
    pages += [[0] * 256] * (NPAGES - len(pages))
    return pages

def adsr_bytes(adsr):
    a, d, s, r = adsr
    sus = round(s * 255)
    att = 255 if a == 0 else max(1, round(255 / a))
    dec = max(1, round((255 - sus) / max(1, d)))
    rel = max(1, round(255 / max(1, r)))
    return att, dec, sus, rel

def build_data():
    song = build_song()
    instr, ikey, events = [], {}, []
    for st in range(len(song[0])):
        for v in range(3):
            ev = song[v][st]
            if ev is None:
                events += [0, 0]
            elif ev[0] == 'off':
                events += [1, 0]
            else:
                n, wf, adsr, _ = ev
                key = (wf, adsr)
                if key not in ikey:
                    ikey[key] = len(instr)
                    instr.append([WAVES[wf], *adsr_bytes(adsr)])
                events += [n, ikey[key]]
    events.append(255)
    blob = bytearray()
    for fs in RATES:
        steps = [min(0xFFFF, round(midi_hz(n) * 65536 / fs)) for n in range(128)]
        blob += bytes(s & 0xFF for s in steps) + bytes(s >> 8 for s in steps)
    for fs in RATES:
        nyq = fs / 2
        band = []
        for n in range(128):
            f = midi_hz(n)
            b = 0
            while b < 2 and BAND_H[b] * f > 0.9 * nyq:
                b += 1
            band.append(b)
        blob += bytes(band)
    blob += bytes((i * 5 + 7) // 15 for i in range(16))
    blob += bytes((i * 7 + 7) // 15 for i in range(16))
    assert len(instr) <= 8
    for ins in instr + [[0] * 5] * (8 - len(instr)):
        blob += bytes(ins)
    blob += bytes(0x360 - len(blob))
    blob += bytes(events)
    return blob

def slot_for(var, wave, amp, band, pw):
    """Mint a Pascal lejatszo: ('t', lap) vagy ('p', PW, AND-ertek)."""
    if amp == 0:
        return ('t', 0)
    if wave == 3:
        return ('p', pw, amp * 4 if var == 0 else amp)
    if var == 0:
        return ('t', 1 + wave * 5 + amp - 1)
    if wave == 0 and var >= 2:
        return ('t', 37 + band * 7 + amp - 1)
    return ('t', 16 + wave * 7 + amp - 1)

def render_exact(pages, data, var):
    ri = 1 if var == 3 else 0
    fs, itpf = RATES[ri], IT_PER_FRAME[ri]
    slo, shi = data[ri * 256:ri * 256 + 128], data[ri * 256 + 128:ri * 256 + 256]
    bandt = data[0x200 + ri * 128:0x280 + ri * 128]
    amp_tab = data[0x300:0x310] if var == 0 else data[0x310:0x320]
    mix = pages[58] if var == 0 else pages[59]
    instr = [data[0x320 + i * 5:0x325 + i * 5] for i in range(8)]
    song = data[0x360:]
    sp, fcnt = 0, 0
    lvl, state, short = [0] * 3, [2] * 3, [0] * 3
    wave, att, dec, sus, rel, band = ([0] * 3 for _ in range(6))
    step, phase = [0] * 3, [0] * 3
    pw, pwdir = 128, 3
    port = []
    for fr in range((len(song) - 1) // 6 * STEP_FRAMES):
        if fcnt == 0:
            if song[sp] == 255:
                sp = 0
            for v in range(3):
                n, ii = song[sp], song[sp + 1]
                sp += 2
                if n == 1:
                    state[v] = 2
                elif n >= 2:
                    step[v] = slo[n] | (shi[n] << 8)
                    band[v] = bandt[n]
                    wave[v], att[v], dec[v], sus[v], rel[v] = instr[ii]
                    state[v], short[v] = 0, (1 if sus[v] == 0 else 0)
        elif fcnt == 1:
            for v in range(3):
                if short[v]:
                    state[v], short[v] = 2, 0
        slots = []
        for v in range(3):
            if state[v] == 0:
                if 255 - lvl[v] <= att[v]:
                    lvl[v], state[v] = 255, 1
                else:
                    lvl[v] += att[v]
            elif state[v] == 1:
                if lvl[v] > sus[v]:
                    lvl[v] = lvl[v] - dec[v] if lvl[v] - sus[v] > dec[v] else sus[v]
            else:
                lvl[v] = lvl[v] - rel[v] if lvl[v] > rel[v] else 0
            slots.append(slot_for(var, wave[v], amp_tab[lvl[v] >> 4], band[v], pw))
        if pw + pwdir > 230 or pw + pwdir < 26:
            pwdir = -pwdir
        pw += pwdir
        fcnt = 0 if fcnt == STEP_FRAMES - 1 else fcnt + 1
        for _ in range(itpf):
            tot = 0
            for v in range(3):
                phase[v] = (phase[v] + step[v]) & 0xFFFF
                hi = phase[v] >> 8
                s = slots[v]
                tot += pages[s[1]][hi] if s[0] == 't' else (s[2] if hi < s[1] else 0)
            port.append(mix[tot] >> 2)
    out = []
    for t in range(int(len(port) * OUT_RATE / fs)):
        out.append((port[min(len(port) - 1, int(t * fs / OUT_RATE))] - 7.5) / 7.5)
    return out

def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pages = build_tables()
    data = build_data()
    with open(os.path.join(root, 'resources', 'sid_tablak.bin'), 'wb') as f:
        f.write(b''.join(bytes(p) for p in pages))
    with open(os.path.join(root, 'resources', 'sid_adat.bin'), 'wb') as f:
        f.write(data)
    print('sid_tablak.bin: %d byte, sid_adat.bin: %d byte ($7000-$%04X)'
          % (NPAGES * 256, len(data), 0x7000 + len(data) - 1))
    dst = os.path.join(root, 'hang_minta')
    os.makedirs(dst, exist_ok=True)
    for f in os.listdir(dst):
        if f.startswith('5_tvc_pontos'):
            os.remove(os.path.join(dst, f))
    for var in range(4):
        write_wav(os.path.join(dst, '%d_valtozat_%d.wav' % (6 + var, var + 1)), render_exact(pages, data, var))

if __name__ == '__main__':
    main()

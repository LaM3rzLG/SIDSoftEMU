#!/usr/bin/env python3
"""A TVC-s SID-teszt adatai + a TVC pontos modellje.

Kimenet:
  resources/sid_adat.bin   - a TVC ezt masolja $6000-ra (lasd SIDSoftEMU.ras)
  hang_minta/5_tvc_pontos.wav - pontosan ezt kell szolnia a TVC-n (ugyanaz a tabla, egesz szamos ADSR)

A bin felepitese ($6000-tol):
  $6000-$6FFF  16 hullamtabla-lap (256 byte): 0 = csend, 1-5 fures amp 1..5, 6-10 haromszog, 11-15 zaj
               ertek = hangonkenti szint 0..5, MAR 4-szeresen (port 6 bit 2-5)
  $7000  step_lo[128]   $7080 step_hi[128]   (MIDI hang -> 16 bites fazislepes 5008 Hz-en)
  $7100  amp_tab[16]    (burkolo-szint >> 4 -> amp 0..5)
  $7110  hangszer[8][5] (hullam, attack, decay, sustain, release; hullam: 0 fures 1 harom 2 zaj 3 negyszog)
  $7140  dal: lepesenkent 3 x (hang, hangszer); hang 0 = tartas, 1 = gate le, 255 = vege (ujra)
"""
import os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sid_modell import build_song, midi_hz, write_wav, OUT_RATE, STEP_FRAMES

IT_HZ = 3125000 / 16 / 39          # 5008 Hz (port 4 = $D9, port 5 also 4 bit = $F)
IT_PER_FRAME = 100
WAVES = {'saw': 0, 'tri': 1, 'noise': 2, 'pulse': 3}

def wave_tables():
    random.seed(64)
    noise = [random.randrange(16) for _ in range(256)]
    pages = [[0] * 256]
    for shape in ('saw', 'tri', 'noise'):
        for amp in range(1, 6):
            row = []
            for hi in range(256):
                if shape == 'saw':
                    w = hi >> 4
                elif shape == 'tri':
                    t = hi >> 3
                    w = t if t < 16 else 31 - t
                else:
                    w = noise[hi]
                row.append(((w * amp + 7) // 15) * 4)
            pages.append(row)
    return pages

def adsr_bytes(adsr):
    a, d, s, r = adsr
    sus = round(s * 255)
    att = 255 if a == 0 else max(1, round(255 / a))
    dec = max(1, round((255 - sus) / max(1, d)))
    rel = max(1, round(255 / max(1, r)))
    return att, dec, sus, rel

def build():
    song = build_song()
    instr, ikey = [], {}
    events = []
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
    steps = [min(0xFFFF, round(midi_hz(n) * 65536 / IT_HZ)) for n in range(128)]
    amp_tab = [(i * 5 + 7) // 15 for i in range(16)]
    assert len(instr) <= 8
    blob = bytearray()
    for p in wave_tables():
        blob += bytes(p)
    blob += bytes(s & 0xFF for s in steps) + bytes(s >> 8 for s in steps)
    blob += bytes(amp_tab)
    for ins in instr + [[0] * 5] * (8 - len(instr)):
        blob += bytes(ins)
    blob += bytes(0x1140 - len(blob))
    assert len(blob) == 0x1140
    blob += bytes(events)
    return blob

def render_exact(blob, seconds=None):
    """A Z80-as kod lepesrol lepesre: IT-enkent 3 hang, kepkockankent (100 IT) a lejatszo."""
    pages = [blob[i * 256:(i + 1) * 256] for i in range(16)]
    slo, shi = blob[0x1000:0x1080], blob[0x1080:0x1100]
    amp_tab = blob[0x1100:0x1110]
    instr = [blob[0x1110 + i * 5:0x1115 + i * 5] for i in range(8)]
    song = blob[0x1140:]
    sp = 0
    lvl, state, short = [0] * 3, [2] * 3, [0] * 3
    wave, att, dec, sus, rel = [0] * 3, [0] * 3, [0] * 3, [0] * 3, [0] * 3
    step, phase = [0] * 3, [0] * 3
    pw, pwdir = 128, 3
    fcnt = 0
    port = []
    nframes = (len(song) - 1) // 6 * STEP_FRAMES
    for fr in range(nframes):
        # --- lejatszo (fo program, kepkockankent)
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
                    wave[v], att[v], dec[v], sus[v], rel[v] = instr[ii]
                    state[v] = 0
                    short[v] = 1 if sus[v] == 0 else 0
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
            amp = amp_tab[lvl[v] >> 4]
            if amp == 0:
                slots.append(('t', 0))
            elif wave[v] == 3:
                slots.append(('p', pw, amp * 4))
            else:
                slots.append(('t', 1 + wave[v] * 5 + amp - 1))
        if pw + pwdir > 230 or pw + pwdir < 26:
            pwdir = -pwdir
        pw += pwdir
        fcnt = 0 if fcnt == STEP_FRAMES - 1 else fcnt + 1
        # --- megszakitasok (100 db)
        for _ in range(IT_PER_FRAME):
            tot = 0
            for v in range(3):
                phase[v] = (phase[v] + step[v]) & 0xFFFF
                hi = phase[v] >> 8
                s = slots[v]
                if s[0] == 't':
                    tot += pages[s[1]][hi]
                else:
                    tot += s[2] if hi < s[1] else 0
            port.append(tot >> 2)
    out = []
    for t in range(int(len(port) * OUT_RATE / IT_HZ)):
        out.append((port[min(len(port) - 1, int(t * IT_HZ / OUT_RATE))] - 7.5) / 7.5)
    return out

def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    blob = build()
    with open(os.path.join(root, 'resources', 'sid_adat.bin'), 'wb') as f:
        f.write(blob)
    print('sid_adat.bin:', len(blob), 'byte ($6000-$%04X)' % (0x6000 + len(blob) - 1))
    os.makedirs(os.path.join(root, 'hang_minta'), exist_ok=True)
    write_wav(os.path.join(root, 'hang_minta', '5_tvc_pontos.wav'), render_exact(blob))

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""SID-szeru szintezis modellje: igy szolna a TVC-n (port 6 = 4 bites kimenet).

Egy rovid probadalt renderel WAV-ba:
  - referencia: 44,1 kHz, finom felbontas (kb. ahogy a SID szol, szuro nelkul)
  - TVC-modell: 4/5/8 kHz mintaveteles, 16 bites fazisszamlalo, 16 szintu kimenet,
    a burkolo (ADSR) 50 Hz-enkent frissul - pontosan, ahogy a Z80-as kod szamolna.
Futtatas: python3 tools/sid_modell.py   (kimenet: hang_minta/*.wav)
"""
import math, os, struct, wave

OUT_RATE = 44100
FRAME_HZ = 50
STEP_FRAMES = 6            # egy 16-od hang = 6 kepkocka (0,12 s)

# ---------------------------------------------------------------- a probadal
def midi_hz(n):
    return 440.0 * 2 ** ((n - 69) / 12)

CHORDS = [(57, [0, 3, 7]), (53, [0, 4, 7]), (48, [0, 4, 7]), (55, [0, 4, 7])]  # Am F C G
MELODY = [0, None, 2, None, 1, None, 2, 3, None, 2, 1, None, 0, None, None, None]  # akkordhang-index

def build_song():
    """Hangonkent lepeslista: (hang, hullamforma, adsr, extra) vagy None = tartas."""
    v1, v2, v3 = [], [], []
    for rep in range(2):
        for root, ch in CHORDS:
            for bar in range(2):
                for s in range(16):
                    # 1. hang: fures szolam
                    m = MELODY[s]
                    if m is None:
                        v1.append(None)
                    else:
                        oct_ = 12 if m < 3 else 24
                        n = root + ch[m % 3] + oct_ + (2 if (bar and s == 9) else 0)
                        v1.append((n, 'saw', (0, 10, 0.55, 8), None))
                    # 2. hang: PWM negyszog basszus, nyolcadok
                    if s % 2 == 0:
                        n = root - 12 + (12 if s in (6, 14) else 0)
                        v2.append((n, 'pulse', (0, 3, 0.7, 2), None))
                    else:
                        v2.append(('off',))
                    # 3. hang: zajdob a 4. es 12. lepesen, hi-hat a paratlanokon, kozte haromszog arpeggio
                    if s in (4, 12):
                        v3.append((84, 'noise', (0, 7, 0.0, 4), None))
                    elif s % 4 == 2:
                        v3.append((100, 'noise', (0, 2, 0.0, 1), None))
                    else:
                        v3.append((root + 12 + ch[(s // 1) % 3], 'tri', (0, 4, 0.3, 3), None))
    return [v1, v2, v3]

# ---------------------------------------------------------------- burkolo (ADSR, kepkockaban)
class Env:
    def __init__(self):
        self.level = 0.0
        self.state = 'rel'
        self.a = self.d = self.r = 1
        self.s = 0.0

    def gate(self, on, adsr=None):
        if on:
            a, d, s, r = adsr
            self.a, self.d, self.s, self.r = a, d, s, r
            self.state = 'att'
        else:
            self.state = 'rel'

    def tick(self):        # egy kepkocka (1/50 s)
        if self.state == 'att':
            self.level = 1.0 if self.a == 0 else min(1.0, self.level + 1.0 / self.a)
            if self.level >= 1.0:
                self.state = 'dec'
        elif self.state == 'dec':
            self.level = max(self.s, self.level - (1.0 - self.s) / max(1, self.d))
        else:
            self.level = max(0.0, self.level - 1.0 / max(1, self.r))
        return self.level

# ---------------------------------------------------------------- kepkockankenti "regiszterallapot"
def frames_from_song(song):
    """Mint a SID-dump: kepkockankent hangonkent (frekv Hz, hullamforma, burkolo-szint 0..1, pw 0..1)."""
    nsteps = len(song[0])
    envs = [Env() for _ in song]
    state = [[0.0, 'saw', 0.5] for _ in song]
    frames = []
    for st in range(nsteps):
        for f in range(STEP_FRAMES):
            row = []
            for vi, voice in enumerate(song):
                ev = voice[st]
                if f == 0 and ev is not None:
                    if ev[0] == 'off':
                        envs[vi].gate(False)
                    else:
                        n, wf, adsr, _ = ev
                        state[vi][0] = midi_hz(n)
                        state[vi][1] = wf
                        envs[vi].gate(True, adsr)
                if f == 1 and ev is not None and ev[0] != 'off' and envs[vi].s == 0.0:
                    envs[vi].gate(False)          # rovid utos hangok: gate rogton le
                lvl = envs[vi].tick()
                fr = len(frames)
                pw = 0.5 + 0.4 * math.sin(fr * 2 * math.pi / 150)   # lassu PWM-sopres (3 s)
                row.append((state[vi][0], state[vi][1], lvl, pw))
            frames.append(row)
    return frames

# ---------------------------------------------------------------- hullamformak
class Lfsr:
    def __init__(self):
        self.r = 0x7FFFF8
    def next(self):        # SID-szeru 23 bites LFSR (22. es 17. bit)
        b = ((self.r >> 22) ^ (self.r >> 17)) & 1
        self.r = ((self.r << 1) | b) & 0x7FFFFF
        return (self.r >> 15) & 0xFF

def render_reference(frames):
    """Finom felbontas, 44,1 kHz, 24 bites fazis, lebegopontos keveres."""
    spf = OUT_RATE // FRAME_HZ
    phase = [0.0] * 3
    noise = [Lfsr() for _ in range(3)]
    nval = [0.0] * 3
    out = []
    prev = [None, None, None]
    for row in frames:
        for i in range(spf):
            acc = 0.0
            for v, (hz, wf, lvl, pw) in enumerate(row):
                old = phase[v]
                phase[v] = (phase[v] + hz / OUT_RATE) % 1.0
                p = phase[v]
                if wf == 'saw':
                    w = p * 2 - 1
                elif wf == 'tri':
                    w = 1 - 4 * abs(p - 0.5)
                elif wf == 'pulse':
                    w = 1.0 if p < pw else -1.0
                else:   # zaj: a SID 16-szor lep periodusonkent
                    if int(p * 16) != int(old * 16) or p < old:
                        nval[v] = noise[v].next() / 127.5 - 1
                    w = nval[v]
                acc += w * lvl
            out.append(acc / 3)
    return out

def render_tvc(frames, fs, mode):
    """TVC-modell. mode 'A': hangonkent 0..5 szint (osszeg max 15, ahogy a music.tru);
    mode 'B': hangonkent 0..15, az osszeget (0..45) tabla kepezi le 0..15-re (+1 tablalepes a Z80-on)."""
    spf = fs / FRAME_HZ
    phase = [0, 0, 0]                       # 16 bites szamlalo, mint IX/IY/HL
    noise = [Lfsr() for _ in range(3)]
    nval = [0, 0, 0]
    port = []
    carry = 0.0
    for row in frames:
        carry += spf
        n = int(carry)
        carry -= n
        steps = [int(round(hz * 65536 / fs)) & 0xFFFF for hz, *_ in row]
        env4 = [int(round(lvl * 15)) for _, _, lvl, _ in row]          # 4 bites burkolo-szint
        pw8 = [int(pw * 256) for *_, pw in row]
        for i in range(n):
            tot = 0
            for v, (hz, wf, lvl, pw) in enumerate(row):
                old = phase[v]
                phase[v] = (phase[v] + steps[v]) & 0xFFFF
                hi = phase[v] >> 8
                if wf == 'saw':
                    w = hi >> 4                                   # 0..15
                elif wf == 'tri':
                    t = hi >> 3                                   # 0..31
                    w = t if t < 16 else 31 - t                   # 0..15
                elif wf == 'pulse':
                    w = 15 if hi < pw8[v] else 0
                else:
                    if (phase[v] >> 12) != (old >> 12):
                        nval[v] = noise[v].next() >> 4
                    w = nval[v]
                if mode == 'A':
                    tot += (w * env4[v] * 5 + 112) // 225          # tabla[env][w] -> 0..5
                else:
                    tot += (w * env4[v] + 7) // 15                 # tabla[env][w] -> 0..15
            if mode == 'B':
                tot = min(15, (tot * 15 * 3 // 2 + 22) // 45)      # keveresi tabla, 1,5x hangosabb, levagas
            port.append(tot)
    # tartas (a port erteke megmarad a kovetkezo IT-ig), atmintavetelezes 44,1 kHz-re
    out = []
    total = len(port)
    for t in range(int(total * OUT_RATE / fs)):
        out.append((port[min(total - 1, int(t * fs / OUT_RATE))] - 7.5) / 7.5)
    return out

# ---------------------------------------------------------------- WAV iras
def write_wav(path, samples, gain=0.6):
    peak = max(1e-9, max(abs(s) for s in samples))
    g = gain / peak
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(OUT_RATE)
        w.writeframes(b''.join(struct.pack('<h', int(max(-1, min(1, s * g)) * 32767)) for s in samples))
    print('  ', os.path.basename(path), f'{len(samples) / OUT_RATE:.1f} s')

def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dst = os.path.join(root, 'hang_minta')
    os.makedirs(dst, exist_ok=True)
    frames = frames_from_song(build_song())
    print('kepkockak:', len(frames))
    write_wav(os.path.join(dst, '0_referencia.wav'), render_reference(frames))
    for fs, mode, name in [(5000, 'A', '1_tvc_5khz_A_hangonkent.wav'),
                           (5000, 'B', '2_tvc_5khz_B_kevert.wav'),
                           (4000, 'B', '3_tvc_4khz_B_kevert.wav'),
                           (8000, 'B', '4_tvc_8khz_B_kevert.wav')]:
        write_wav(os.path.join(dst, name), render_tvc(frames, fs, mode))

if __name__ == '__main__':
    main()

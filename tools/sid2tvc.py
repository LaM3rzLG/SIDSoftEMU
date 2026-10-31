#!/usr/bin/env python3
""".sid -> TVC dal (az "A" valtozat: 5008 Hz, hangonkent 0..5 szint) + a TVC pontos hangja WAV-ban.

  python3 tools/sid2tvc.py sid/Last_Ninja.sid 3        (3 = aldal; alapertelmezes: a .sid kezdo dala)

Lepesek: 6502-emulacio (sid_dump) -> kepkockankenti SID-allapot -> SID-burkolo (ADSR) szimulacio a
valodi SID-idozitesekkel -> hangonkent (lepes, hullam/szint, PW) -> tomoritett esemenyfolyam.
Kimenet: resources/sid_tablak.bin (17 lap, a TVC $EF00-ra masolja), dalok/DALnn.BIN (lemezfajl),
hang_minta/<nev>_<aldal>_tvc.wav (pontosan ez kell szoljon a TVC-n).

A dal formatuma: 6 byte fejlec = a 3 hang folyamanak kezdete (lo,hi, a dal elejetol). Hangonkent
kepkockankent egy rekord:
  c = $00..$0F  bit 0 = lepes (2 byte lo,hi), bit 1 = lepes += elojeles byte, bit 2 = szelet (1 byte: <$80 =
                tablalap 0..15, >=$80 = negyszog, szint = also 3 bit), bit 3 = PW (1 byte)
  $80+n         n kepkocka valtozas nelkul (ez + n-1 tovabbi), n = 1..127
  $10 lo hi n   REF: n rekord lejatszasa a lo/hi eltolasrol (nem agyazhato)
  $11 lo hi     VEGE: ugras a hurokpontra (teljes kulcsrekord), ugyanabban a kepkockaban
Hangszelet a TVC hang-IT-jeben (5 byte): tabla = 5F 16 (C0+lap) 1A 00, negyszog = FE PW 9F E6 (szint*4).
"""
import math, os, random, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sid_dump import dump, load_sid

PAL_CLK = 985248
FRAME_CYC = 19656                    # PAL: 312 sor x 63 ciklus
FS = 3125000 / 16 / 39               # a TVC hang-IT: 5008 Hz
IT_PER_FRAME = 100
STEP_MUL = PAL_CLK * 65536 / (16777216 * FS)
NPAGES = 17
MIX_PAGE = 16
SONG_BASE = 0x4000                   # a dal cime a TVC-n (teljes 64K RAM: U0,U1,U2,U3)
TABLE_BASE = 0xEF00                  # 17 lap: $EF00-$FFFF
SONG_MAX = TABLE_BASE - SONG_BASE
RATE = [9, 32, 63, 95, 149, 220, 267, 313, 392, 977, 1954, 3126, 3907, 11720, 19532, 31251]


# ------------------------------------------------------------------ TVC hangtablak (az 1. valtozat)
def build_tables():
    random.seed(64)
    noise = [random.random() for _ in range(256)]
    pages = [[0] * 256]
    for shape in ('saw', 'tri', 'noise'):
        for amp in range(1, 6):
            row = []
            for i in range(256):
                w = {'saw': i >> 4, 'tri': (lambda t: t if t < 16 else 31 - t)(i >> 3),
                     'noise': int(noise[i] * 16)}[shape]
                row.append(((w * amp + 7) // 15) * 4)
            pages.append(row)
    pages.append([((i >> 2) << 2) | 1 for i in range(256)])     # keveres: osszeg (0..60) -> port 6
    assert len(pages) == NPAGES
    return pages


# ------------------------------------------------------------------ SID-burkolo
class Env:
    def __init__(self):
        self.lvl, self.state, self.rc, self.ec = 0, 'R', 0, 0
        self.a = self.d = self.s = self.r = 0
        self.gate = 0

    def exp_period(self):
        l = self.lvl
        return 1 if l >= 93 else 2 if l >= 54 else 4 if l >= 26 else 8 if l >= 14 else 16 if l >= 6 else 30

    def control(self, ctrl):
        g = ctrl & 1
        if g and not self.gate:
            self.state = 'A'
        elif not g and self.gate:
            self.state = 'R'
        self.gate = g

    def run(self, cyc):
        while cyc > 0:
            rate = RATE[{'A': self.a, 'D': self.d, 'R': self.r}[self.state]]
            need = rate - self.rc
            if need > cyc:
                self.rc += cyc
                return
            cyc -= need
            self.rc = 0
            if self.state == 'A':
                self.lvl += 1
                if self.lvl >= 255:
                    self.lvl, self.state = 255, 'D'
                continue
            if self.state == 'D' and self.lvl <= self.s * 17:
                continue
            if self.lvl == 0:
                continue
            self.ec += 1
            if self.ec >= self.exp_period():
                self.ec = 0
                self.lvl -= 1


def sid_frames(frames):
    """-> kepkockankent hangonkent (F, ctrl, PW, burkolo-szint 0..255), hangero."""
    regs = [0] * 32
    envs = [Env() for _ in range(3)]
    out = []
    for fw in frames:
        for r, v in fw:
            regs[r] = v
            if r < 21:
                vo, k = divmod(r, 7)
                e = envs[vo]
                if k == 4:
                    e.control(v)
                elif k == 5:
                    e.a, e.d = v >> 4, v & 15
                elif k == 6:
                    e.s, e.r = v >> 4, v & 15
        mid = []
        for e in envs:
            e.run(FRAME_CYC // 2)
            mid.append(e.lvl)
            e.run(FRAME_CYC - FRAME_CYC // 2)
        vox = []
        for vo in range(3):
            b = vo * 7
            vox.append((regs[b] | (regs[b + 1] << 8), regs[b + 4], regs[b + 2] | ((regs[b + 3] & 15) << 8), mid[vo]))
        out.append((vox, regs[24] & 15))
    return out


# ------------------------------------------------------------------ SID-allapot -> TVC allapot
def tvc_states(sf):
    """kepkockankent 9-es: (step0, slot0, pw0, step1, ...). Ahol nem szamit (csend / nem negyszog),
    az elozo erteket viszi tovabb - igy kevesebb a valtozas."""
    prev = [0, 0, 128] * 3
    res = []
    for vox, vol in sf:
        cur = list(prev)
        for v, (F, ctrl, pw, lvl) in enumerate(vox):
            wave = ctrl >> 4
            amp = int(lvl / 255 * vol / 15 * 5 + 0.5)
            if ctrl & 8 or wave == 0:
                amp = 0
            step = min(0xFFFF, int(F * STEP_MUL + 0.5))
            if amp == 0:
                cur[v * 3 + 1] = 0
                continue
            if wave & 8:
                cur[v * 3 + 1] = 1 + 2 * 5 + amp - 1
                step = max(1, step // 16)
            elif wave & 4:
                cur[v * 3 + 1] = 0x80 | amp
                cur[v * 3 + 2] = pw >> 4
            elif wave & 2:
                cur[v * 3 + 1] = 1 + 0 * 5 + amp - 1
            else:
                cur[v * 3 + 1] = 1 + 1 * 5 + amp - 1
            cur[v * 3] = step
        res.append(tuple(cur))
        prev = cur
    return res


# ------------------------------------------------------------------ kodolas (hangonkent kulon folyam)
def lit_bytes(S, T, full=False):
    """S, T = (lepes, szelet, PW) egy hangra."""
    c, body = 0, []
    if full or T[0] != S[0]:
        dl = (T[0] - S[0]) & 0xFFFF
        if not full and (dl < 128 or dl >= 0x10000 - 128):
            c |= 2
            body.append(dl & 0xFF)
        else:
            c |= 1
            body += [T[0] & 0xFF, T[0] >> 8]
    if full or T[1] != S[1]:
        c |= 4
        body.append(T[1])
    if full or T[2] != S[2]:
        c |= 8
        body.append(T[2])
    return [c] + body


def apply_lit(S, b, p):
    """Egy rekord alkalmazasa (mint a TVC dekodolo). -> (uj allapot, kovetkezo pozicio)"""
    c = b[p]
    p += 1
    st, sl, pw = S
    if c & 1:
        st = b[p] | (b[p + 1] << 8)
        p += 2
    if c & 2:
        d = b[p]
        st = (st + d - (256 if d > 127 else 0)) & 0xFFFF
        p += 1
    if c & 4:
        sl = b[p]
        p += 1
    if c & 8:
        pw = b[p]
        p += 1
    return (st, sl, pw), p


S0 = (0, 0, 128)


class VoiceDec:
    def __init__(self, b, start):
        self.b, self.p, self.S = b, start, S0
        self.wait = self.refcnt = self.retp = 0

    def frame(self):
        b = self.b
        if self.wait:
            self.wait -= 1
            return self.S
        while True:
            c = b[self.p]
            if c == 0x10:
                self.retp, self.refcnt = self.p + 4, b[self.p + 3]
                self.p = b[self.p + 1] | (b[self.p + 2] << 8)
                continue
            if c == 0x11:
                self.p = b[self.p + 1] | (b[self.p + 2] << 8)
                continue
            break
        if c & 0x80:
            self.wait = (c & 0x7F) - 1
            self.p += 1
        else:
            self.S, self.p = apply_lit(self.S, b, self.p)
        if self.refcnt:
            self.refcnt -= 1
            if self.refcnt == 0:
                self.p = self.retp
        return self.S


def decode(blob, nframes):
    """A TVC dekodolo pontos modellje: -> kepkockankenti 9-es allapot."""
    b = bytes(SONG_BASE) + blob
    decs = [VoiceDec(b, blob[2 * v] | (blob[2 * v + 1] << 8)) for v in range(3)]
    return [sum((d.frame() for d in decs), ()) for _ in range(nframes)]


def encode_voice(T, loop, base):
    """Egy hang folyama; az eltolasok a dal elejetol (base = e folyam kezdete)."""
    N = len(T)
    b = []
    units = []          # (off, frames, contiguous_with_prev)
    index = {}
    S = S0
    lsize = [len(lit_bytes(T[k - 1] if k else S0, T[k])) if (k == 0 or T[k] != T[k - 1]) else 0.3
             for k in range(N)]
    i, prev_was_ref, loop_off, nref = 0, True, None, 0
    while i < N:
        limit = N - i if (loop is None or i >= loop) else loop - i
        best_fr, best_u = 0, None
        if i != 0 and i != loop:
            for j in reversed(index.get(T[i], [])[-80:]):
                SS, fr, k = S, 0, j
                while k < len(units) and k - j < 255:
                    off, nfr, contig = units[k]
                    if k > j and not contig:
                        break
                    if b[off] & 0x80:
                        if fr + nfr > limit or any(T[i + fr + q] != SS for q in range(nfr)):
                            break
                        fr += nfr
                    else:
                        SS2, _ = apply_lit(SS, b, off)
                        if fr >= limit or T[i + fr] != SS2:
                            break
                        SS = SS2
                        fr += 1
                    k += 1
                if fr > best_fr:
                    best_fr, best_u = fr, (j, k - j, SS)
        if best_fr:
            est = sum(lsize[i:i + best_fr])
            if est > 5:
                j, cnt, SS = best_u
                o = units[j][0] + base
                b += [0x10, o & 0xFF, o >> 8, cnt]
                S = SS
                i += best_fr
                nref += 1
                prev_was_ref = True
                continue
        off = len(b)
        if i == loop:
            loop_off = off
        if T[i] == S and i != 0 and i != loop:
            n = 1
            while n < 127 and i + n < N and T[i + n] == S and (loop is None or i + n != loop):
                n += 1
            b.append(0x80 | n)
            units.append((off, n, not prev_was_ref))
        else:
            b += lit_bytes(S, T[i], full=(i == 0 or i == loop))
            S = T[i]
            units.append((off, 1, not prev_was_ref))
        index.setdefault(T[i], []).append(len(units) - 1)
        i += units[-1][1]
        prev_was_ref = False
    o = (loop_off or 0) + base
    b += [0x11, o & 0xFF, o >> 8]
    return b, nref


def encode(T, loop):
    blob, nref, starts = [0] * 6, 0, []
    for v in range(3):
        starts.append(len(blob))
        bv, n = encode_voice([t[v * 3:v * 3 + 3] for t in T], loop, SONG_BASE + len(blob))
        blob += bv
        nref += n
    for v in range(3):
        a = SONG_BASE + starts[v]
        blob[2 * v], blob[2 * v + 1] = a & 0xFF, a >> 8
    assert len(blob) <= SONG_MAX, 'a dal tul nagy: %d byte (max %d)' % (len(blob), SONG_MAX)
    return bytes(blob), nref


# ------------------------------------------------------------------ a TVC hangja
def render(pages, states, path, seconds=None):
    out_rate = 22050
    nfr = len(states) if seconds is None else min(len(states), int(seconds * 50))
    port = []
    phase = [0, 0, 0]
    mix = pages[MIX_PAGE]
    for S in states[:nfr]:
        sl = []
        for v in range(3):
            st, s, pw = S[v * 3:v * 3 + 3]
            sl.append((st, s, pw))
        for _ in range(IT_PER_FRAME):
            tot = 0
            for v in range(3):
                st, s, pw = sl[v]
                phase[v] = (phase[v] + st) & 0xFFFF
                hi = phase[v] >> 8
                if s & 0x80:
                    tot += ((s & 7) * 4) if hi < pw else 0
                else:
                    tot += pages[s][hi]
            port.append(mix[tot] >> 2)
    n_out = int(len(port) * out_rate / FS)
    data = bytearray()
    for t in range(n_out):
        x = port[min(len(port) - 1, int(t * FS / out_rate))]
        data += struct.pack('<h', int((x - 7.5) / 7.5 * 20000))
    with open(path, 'wb') as f:
        f.write(b'RIFF' + struct.pack('<I', 36 + len(data)) + b'WAVEfmt ' +
                struct.pack('<IHHIIHH', 16, 1, 1, out_rate, out_rate * 2, 2, 16) +
                b'data' + struct.pack('<I', len(data)) + data)


def main():
    path = sys.argv[1]
    info = load_sid(path)
    song = int(sys.argv[2]) if len(sys.argv) > 2 else info['start']
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    d = dump(path, song, max_frames=30000)
    frames, loop = d['frames'], d['loop']
    sf = sid_frames(frames)
    T = tvc_states(sf)
    blob, nref = encode(T, loop)
    chk = decode(blob, len(T) + 200)
    assert chk[:len(T)] == T, 'a dekodolo nem egyezik!'
    if loop is not None:
        assert chk[len(T):len(T) + 200] == T[loop:loop + 200], 'a hurok nem egyezik!'
    pages = build_tables()
    with open(os.path.join(root, 'resources', 'sid_tablak.bin'), 'wb') as f:
        f.write(b''.join(bytes(p) for p in pages))
    # lemezfajl: 2 byte hossz, aztan a $C000 feletti resz (a TVC elobb ezt tolti, $8000-ra, es U3-ba masolja),
    # vegul a $4000-$BFFF resz
    split = 0xC000 - SONG_BASE
    fajl = struct.pack('<H', len(blob)) + blob[split:] + blob[:split]
    os.makedirs(os.path.join(root, 'dalok'), exist_ok=True)
    dalfajl = os.path.join(root, 'dalok', 'DAL%02d.BIN' % song)
    with open(dalfajl, 'wb') as f:
        f.write(fajl)
    nev = os.path.splitext(os.path.basename(path))[0]
    wav = os.path.join(root, 'hang_minta', '%s_%d_tvc.wav' % (nev, song))
    render(pages, T, wav)
    print('%s, %d. aldal: %d kepkocka (%.0f s), hurok: %s; dal: %d byte (%d REF) -> %s'
          % (info['name'], song, len(T), len(T) / 50, loop, len(blob), nref, dalfajl))
    print('WAV:', wav)


if __name__ == '__main__':
    main()

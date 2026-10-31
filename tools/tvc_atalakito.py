#!/usr/bin/env python3
"""A TVC-s atalakito PONTOS Python-masa (referencia a Z80-kodhoz): SID-irasok -> .STC.

  python3 tools/tvc_atalakito.py sid/LNINJA.SID 3 [kepkockak]

Ugyanazt kell adnia, mint a TVC-n futo atalakitonak, bajtra. Elteresek a tools/sid2tvc.py-hoz kepest
(az a "legjobb" PC-s valtozat marad): Z80-barat burkolo es lepeskoz, online (elore nem latott) tomorites.
  - burkolo: 8.8 fixpontos szint, fel kepkockankent (9828 ciklus) frissitve, a fel kepkockanal mintavetelezve;
    tamadas +ATT[r]; lecsenges/elengedes -(ATT[r] >> eltolas(szint)), eltolas 0..5 a SID exp. periodusa szerint
  - szint 0..5 = SZINT[(szint * hangero) >> 4]
  - lepeskoz = F - F/4 + F/64 + F/512 (~F * 0,7676; 5008 Hz-en F * 0,7685 lenne: -2 cent), zaj: lepes / 16
  - tomorites hangonkent: varakozo sor (max 64 kepkocka), hash (256) -> korabbi rekord, abbol "visszajatszas"
    a sorral szemben; ha a REF megeri (> 5 byte), REF; kulonben rekord / varakozas. 256 byte-os, lapra igazitott blokkok (a 0. elejen a fejlec), a blokk
    vegen $11 ugras a kovetkezore (a dekodolo amugy is koveti).
"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sid_dump import dump, load_sid
import sid2tvc

SONG_BASE = sid2tvc.SONG_BASE
SONG_END = 0xEF00
HALF = 9828
RATE = sid2tvc.RATE
ATT = [min(0xFFFF, (HALF * 256 + RATE[r] // 2) // RATE[r]) for r in range(16)]
SZINT = [int((k * 16 + 8) / 765 + 0.5) for k in range(240)]
QMAX = 64
BLOKK = 256


def exp_shift(hi):
    return 0 if hi >= 93 else 1 if hi >= 54 else 2 if hi >= 26 else 3 if hi >= 14 else 4 if hi >= 6 else 5


class Hang:
    """Egy SID-hang regiszterei + burkoloja (TVC-modell)."""

    def __init__(self):
        self.F = self.pw = self.ctrl = 0
        self.a = self.d = self.s = self.r = 0
        self.lvl = 0          # 8.8
        self.state = 2        # 0 tamadas, 1 lecsenges/tartas, 2 elengedes
        self.gate = 0

    def iras(self, k, v):
        if k == 0: self.F = (self.F & 0xFF00) | v
        elif k == 1: self.F = (self.F & 0xFF) | (v << 8)
        elif k == 2: self.pw = (self.pw & 0xF00) | v
        elif k == 3: self.pw = (self.pw & 0xFF) | ((v & 15) << 8)
        elif k == 4:
            g = v & 1
            if g and not self.gate:
                self.state = 0
            elif not g and self.gate:
                self.state = 2
            self.gate = g
            self.ctrl = v
        elif k == 5: self.a, self.d = v >> 4, v & 15
        elif k == 6: self.s, self.r = v >> 4, v & 15

    def fel(self):
        if self.state == 0:
            self.lvl += ATT[self.a]
            if self.lvl >= 0xFF00:
                self.lvl, self.state = 0xFF00, 1
        elif self.state == 1:
            cel = (self.s * 17) << 8
            if self.lvl > cel:
                self.lvl = max(cel, self.lvl - (ATT[self.d] >> exp_shift(self.lvl >> 8)))
        else:
            self.lvl = max(0, self.lvl - (ATT[self.r] >> exp_shift(self.lvl >> 8)))


def lepes(F):
    return (F - (F >> 2) + (F >> 6) + (F >> 9)) & 0xFFFF


def tvc_allapot(h, szint_hi, vol, elozo):
    """-> (lepes, szelet, pw) egy hangra; csendben / nem negyszognel az elozot viszi tovabb."""
    st, sl, pw = elozo
    wave = h.ctrl >> 4
    amp = SZINT[(szint_hi * vol) >> 4]
    if h.ctrl & 8 or wave == 0:
        amp = 0
    if amp == 0:
        return (st, 0, pw)
    s = lepes(h.F)
    if wave & 8:
        return (max(1, s >> 4), 1 + 2 * 5 + amp - 1, pw)
    if wave & 4:
        return (s, 0x80 | amp, h.pw >> 4)
    if wave & 2:
        return (s, 1 + amp - 1, pw)
    return (s, 1 + 5 + amp - 1, pw)


def hash_(t):
    st, sl, pw = t
    return ((st & 0xFF) ^ (st >> 8) ^ ((sl << 1) & 0xFF) ^ pw) & 0xFF


lit_bytes = sid2tvc.lit_bytes
apply_lit = sid2tvc.apply_lit


def litkoltseg(S, frames):
    c, i = 0, 0
    while i < len(frames):
        if frames[i] == S:
            n = 1
            while n < 127 and i + n < len(frames) and frames[i + n] == S:
                n += 1
            c += 1
            i += n
        else:
            c += len(lit_bytes(S, frames[i]))
            S = frames[i]
            i += 1
    return c


class Kimenet:
    """256 byte-os, lapra igazitott blokkok a SONG_BASE-tol; a 0. blokk elejen a 6 byte-os fejlec."""

    def __init__(self):
        self.mem = bytearray(65536)
        self.next = SONG_BASE
        self.tele = False

    def blokk(self):
        if self.next + BLOKK > SONG_END:
            self.tele = True
            return None
        b = self.next
        self.next += BLOKK
        return b


class Kodolo:
    """Egy hang online kodoloja (a TVC-n ugyanez, Z80-ban)."""

    def __init__(self, ki):
        self.ki = ki
        b = ki.blokk()
        self.wp = b + (6 if b == SONG_BASE else 0)
        self.start = self.wp
        self.wend = b + BLOKK
        self.S = sid2tvc.S0
        self.Q = []
        self.H = [0] * 256
        self.elso = True
        self.nref = 0

    def ir(self, b):
        """b byte-ok kiirasa (a blokk vegen ugras). -> a rekord cime"""
        m = self.ki.mem
        if self.wp + len(b) + 3 > self.wend:
            nb = self.ki.blokk()
            if nb is None:
                raise MemoryError
            m[self.wp:self.wp + 3] = bytes([0x11, nb & 0xFF, nb >> 8])
            self.wp, self.wend = nb, nb + BLOKK
        a = self.wp
        m[a:a + len(b)] = bytes(b)
        self.wp += len(b)
        return a

    def setal(self, a, final):
        """REF-jelolt: a = rekordcim. -> 'more' vagy (egysegek, kepkockak, allapot)"""
        m, Q = self.ki.mem, self.Q
        p, SS, u, fr = a, self.S, 0, 0
        best = (0, 0, self.S)
        while True:
            if p == self.wp:
                break
            c = m[p]
            while c == 0x11:
                p = m[p + 1] | (m[p + 2] << 8)
                if p == self.wp:
                    return best
                c = m[p]
            if c == 0x10:
                break
            if c & 0x80:
                n = c & 0x7F
                if fr + n > len(Q):
                    if final or len(Q) >= QMAX:
                        break
                    return 'more'
                if any(Q[fr + q] != SS for q in range(n)):
                    break
                fr += n
                p += 1
            else:
                SS2, p2 = apply_lit(SS, m, p)
                if fr >= len(Q):
                    if final or len(Q) >= QMAX:
                        break
                    return 'more'
                if Q[fr] != SS2:
                    break
                SS, p = SS2, p2
                fr += 1
            u += 1
            best = (u, fr, SS)
            if u == 255:
                break
        return best

    def dont(self, final=False):
        Q = self.Q
        while Q:
            if self.elso:
                a = self.ir(lit_bytes(self.S, Q[0], full=True))
                self.H[hash_(Q[0])] = a
                self.S = Q.pop(0)
                self.elso = False
                continue
            a = self.H[hash_(Q[0])]
            if a:
                r = self.setal(a, final)
                if r == 'more':
                    return
                u, fr, SS = r
                if u and litkoltseg(self.S, Q[:fr]) > 5:
                    self.ir([0x10, a & 0xFF, a >> 8, u])
                    self.S = SS
                    del Q[:fr]
                    self.nref += 1
                    continue
            if Q[0] == self.S:
                n = 1
                while n < 127 and n < len(Q) and Q[n] == self.S:
                    n += 1
                if n == len(Q) and not final and n < 127 and len(Q) < QMAX:
                    return
                a = self.ir([0x80 | n] if n > 1 else [0])
                self.H[hash_(self.S)] = a
                del Q[:n]
            else:
                a = self.ir(lit_bytes(self.S, Q[0]))
                self.H[hash_(Q[0])] = a
                self.S = Q.pop(0)

    def kepkocka(self, t):
        self.Q.append(t)
        self.dont()

    def vege(self):
        self.dont(final=True)
        self.ir([0x11, self.start & 0xFF, self.start >> 8])


def atalakit(frames, max_frames=None, tartalek=3 * 1024):
    """frames: kepkockankenti [(reg, ertek)] (az 1. tartalmazza az init irasait is). -> (blob, kepkockak, nref)"""
    ki = Kimenet()
    hangok = [Hang() for _ in range(3)]
    kod = [Kodolo(ki) for _ in range(3)]
    vol = 0
    allapot = [sid2tvc.S0] * 3
    celok = []
    n = 0
    for fw in frames[:max_frames]:
        if SONG_END - ki.next < tartalek:
            break
        for r, v in fw:
            if r < 21:
                hangok[r // 7].iras(r % 7, v)
            elif r == 24:
                vol = v & 15
        for v in range(3):
            h = hangok[v]
            h.fel()
            allapot[v] = tvc_allapot(h, h.lvl >> 8, vol, allapot[v])
            h.fel()
            kod[v].kepkocka(allapot[v])
        celok.append(allapot[0] + allapot[1] + allapot[2])
        n += 1
    for k in kod:
        k.vege()
    blob = bytearray(ki.mem[SONG_BASE:ki.next])
    for v in range(3):
        blob[2 * v], blob[2 * v + 1] = kod[v].start & 0xFF, kod[v].start >> 8
    return bytes(blob), n, sum(k.nref for k in kod), celok


def main():
    path = sys.argv[1]
    info = load_sid(path)
    song = int(sys.argv[2]) if len(sys.argv) > 2 else info['start']
    maxf = int(sys.argv[3]) if len(sys.argv) > 3 else 15000
    d = dump(path, song, max_frames=maxf)
    blob, n, nref, celok = atalakit(d['frames'], maxf)
    # ellenorzes: a dekodolo ugyanazt adja-e, mint az atalakito allapotai (+ a hurok: vissza az elejere)
    chk = sid2tvc.decode(blob, n + 100)
    assert chk[:n] == celok, 'a dekodolo nem egyezik!'
    assert chk[n:n + 100] == celok[:100], 'a hurok nem egyezik!'
    print('%s %d. aldal: %d kepkocka (%.0f s) -> %d byte (%d REF)' % (info['name'], song, n, n / 50, len(blob), nref))
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    wav = os.path.join(root, 'hang_minta', 'tvc_atalakito_%d.wav' % song)
    sid2tvc.render(sid2tvc.build_tables(), chk, wav, seconds=60)
    print('WAV (1 perc):', wav)
    return blob, chk


if __name__ == '__main__':
    main()

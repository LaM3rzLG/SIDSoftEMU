# sid2tvc

C64 `.sid` zenékből a Videoton TV-Computer **SIDSoftEMU** lejátszójának dalfájlja (`.STC`).
Egyetlen C99 forrásfájl (`sid2tvc.c`), külső könyvtár nélkül; Macen, Linuxon és Windowson is fordítható.

## Fordítás

| Rendszer | Mi kell | Parancs (ebben a mappában) |
|---|---|---|
| macOS | Xcode parancssori eszközök (`xcode-select --install`) | `cc -O2 -std=c99 -ffp-contract=off -o sid2tvc sid2tvc.c -lm` |
| Linux | gcc vagy clang (pl. `sudo apt install build-essential`) | `gcc -O2 -std=c99 -ffp-contract=off -o sid2tvc sid2tvc.c -lm` |
| Windows (MSYS2 / MinGW-w64) | <https://www.msys2.org>, majd `pacman -S mingw-w64-ucrt-x86_64-gcc` | `gcc -O2 -std=c99 -ffp-contract=off -o sid2tvc.exe sid2tvc.c -lm` |
| Windows (Visual Studio) | "Developer Command Prompt" | `cl /O2 /fp:precise sid2tvc.c` |

Make-kel: `make` (Mac/Linux/MSYS2).

A `-ffp-contract=off` (MSVC-n `/fp:precise`) azért kell, hogy a lebegőpontos számítás minden gépen bitre
ugyanazt adja (így a kimenet is bájtra azonos).

## Használat

```
sid2tvc [-s N | -a] [-o MAPPA] [-n NÉV] [-w] [-f N] [-m] [-q] fajl.sid
  -s N      aldal (alapértelmezés: a .sid kezdő dala)
  -a        az összes aldal
  -o MAPPA  kimenet: MAPPA/<NÉV>/SONG<n>.STC   (alapértelmezés: SID_TVC)
  -n NÉV    a mappa neve (legfeljebb 8 betű; alapértelmezés: a .sid fájlnevéből)
  -w        WAV-előnézet is, pontosan a TVC hangjával: MAPPA/<NÉV>/SONG<n>.WAV
  -f N      hurok nélkül legfeljebb N képkocka (50/mp; alapértelmezés 30000 = 10 perc)
  -m        csak a memória-hurok (a hang ismétlődését nem keresi)
  -q        csak a hibákat írja ki
```

Példa: `sid2tvc -a -w Last_Ninja.sid` → `SID_TVC/LASTNINJ/SONG1.STC ... SONG11.STC` (+ WAV).
A `<NÉV>` a .sid fájlnevéből jön (nagybetű, legfeljebb 8 karakter), mert a TVC lemezén 8.3-as nevek vannak.
A `SID_TVC` mappát változatlan szerkezetben kell a TVC lemezére / SD-kártyájára másolni.

## Mit tud

- **6502-emuláció** a hivatalos és a stabil illegális utasításokkal; PSID és RSID; `play = 0` esetén az
  init által beállított IRQ-rutin ($0314 vagy $FFFE) fut képkockánként.
- **Hurok, két módszerrel** (a TVC-n a dal a hurokponttól ismétlődik):
  1. *memória:* a teljes C64-memória (+ SID-regiszterek) első pontos ismétlődése - biztos, de sok lejátszó
     közben számlálót léptet, így gyakran nem talál (vagy csak későn);
  2. *hang:* a hallható TVC-állapot (3 hang: lépésköz, szelet, PW) ismétlődése - a legrövidebb dalt adja
     (legkisebb hurokpont + hossz). Memória-hurok esetén ez is biztos; ha nincs, a 20 perces mintában legalább
     2 teljes ismétlés és 30 s egyezés kell hozzá.
  A kettőből a rövidebb dal nyer (a kiírásban `[memoria]` / `[hang]`). Hurok nélkül 10 perc, aztán elölről;
  ha a hurok csak 10 perc után jön, és úgy nem fér el, szintén 10 perc.
- **SID-burkoló (ADSR)** a valódi SID-időzítésekkel; hullámforma, impulzusszélesség, hangerő.
- **Hangszínpaletta (1.2):** a PC hangonként, képkockánként kiszámolja a SID valódi hangjának egy ciklusát (szűrő a
  6581-es görbével, kevert hullámformák, gyűrűmoduláció és szinkron közelítve), és dalonként 14 táblát választ
  (súlyozott k-közép a felharmonikus-spektrumon); + zaj; a tiszta, szűretlen négyszög PW-összehasonlítás marad.
- **Hangerő (1.2):** hangonként 16 szint; a DAC 15 szintje dalonként állandó erősítéssel (a hangos képkockák
  99. percentilise = 15), hiszterézissel (kevesebb változás = kisebb fájl); DC-kiegyenlítés a TVC-n.
- **Tömörítés** hangonként (ismétlődő részek visszahivatkozással); a kész dal legfeljebb 51 456 bájt ($2300-$EBFF) lehet.
- Minden kimenetet visszaellenőriz a TVC lejátszójának pontos mására.

Nem kezeli (egyelőre): többszörös sebességű (CIA-val gyorsított) dalok, digi-hangok.
A 2,5 kHz feletti hangokat a TVC (5008 Hz-es mintavétel) nem tudja tisztán lejátszani.

## A .STC formátum

**1.3 (2026-11-02):** `$FD $FF`, aztán 3 × 32 bájt info a .sid fejlécéből: cím, szerző, kiadás (31 jel + 0; ami a
TVC-s fontban nincs, az szóköz), 8 bájt a lejátszás-kijelzőhöz (N = képkockák, a hurokpont, a hurokpont százaléka, 0, a
maradék), 14 × 256 bájt paletta (érték × 16; a TVC-n `$F000-$FDFF`), 2 bájt hossz (L), a dal
`$C000` feletti része, végül a `$2300..$BFFF` rész (így a TVC ROM-jával egyszerűen betölthető). A régi 1.2-es (`$FE $FF`), 1.1-es
(`$FF $FF` + info) és 1.0-s (rögtön L) fájlt a SIDSoftEMU már nem játssza le („Régi .STC”). A dal `$2300`-tól:
6 bájtos fejléc (a 3 hang folyamának címe), majd hangonként képkockánként egy rekord:

| Kód | Jelentés |
|---|---|
| `$00..$0F` | bit 0: lépésköz (2 bájt); bit 1: lépésköz += előjeles bájt; bit 2: szelet (1 bájt: felső 4 bit tábla - 0..13 paletta, 14 zaj, 15 négyszög -, alsó 4 bit szint 0..15); bit 3: PW (1 bájt) |
| `$80+n` | n képkocka változás nélkül |
| `$10 lo hi n` | REF: n rekord lejátszása a lo/hi címről |
| `$11 lo hi` | ugrás (hurok) |

Licenc: GPL-3.0-or-later.

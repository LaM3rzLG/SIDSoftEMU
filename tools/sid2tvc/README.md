# sid2tvc

C64 `.sid` zenékből a Videoton TV-Computer **SIDSoftEMU** lejátszójának dalfájlja (`.STC`).
Egyetlen C99 forrásfájl (`sid2tvc.c`), külső könyvtár nélkül; Macen, Linuxon és Windowson is fordítható.

## Fordítás

| Rendszer | Mi kell | Parancs (ebben a mappában) |
|---|---|---|
| macOS | Xcode parancssori eszközök (`xcode-select --install`) | `cc -O2 -std=c99 -ffp-contract=off -o sid2tvc sid2tvc.c` |
| Linux | gcc vagy clang (pl. `sudo apt install build-essential`) | `gcc -O2 -std=c99 -ffp-contract=off -o sid2tvc sid2tvc.c` |
| Windows (MSYS2 / MinGW-w64) | <https://www.msys2.org>, majd `pacman -S mingw-w64-ucrt-x86_64-gcc` | `gcc -O2 -std=c99 -ffp-contract=off -o sid2tvc.exe sid2tvc.c` |
| Windows (Visual Studio) | "Developer Command Prompt" | `cl /O2 /fp:precise sid2tvc.c` |

Make-kel: `make` (Mac/Linux/MSYS2).

A `-ffp-contract=off` (MSVC-n `/fp:precise`) azért kell, hogy a lebegőpontos számítás minden gépen bitre
ugyanazt adja (így a kimenet is bájtra azonos).

## Használat

```
sid2tvc [-s N | -a] [-o MAPPA] [-w] [-f N] [-q] fajl.sid
  -s N      aldal (alapértelmezés: a .sid kezdő dala)
  -a        az összes aldal
  -o MAPPA  kimenet: MAPPA/<NÉV>/<nn>.STC   (alapértelmezés: SID_TVC)
  -w        WAV-előnézet is, pontosan a TVC hangjával: MAPPA/<NÉV>/<nn>.WAV
  -f N      legfeljebb N képkocka (50/mp; alapértelmezés 30000 = 10 perc)
  -q        csak a hibákat írja ki
```

Példa: `sid2tvc -a -w Last_Ninja.sid` → `SID_TVC/LASTNINJ/01.STC ... 11.STC` (+ WAV).
A `<NÉV>` a .sid fájlnevéből jön (nagybetű, legfeljebb 8 karakter), mert a TVC lemezén 8.3-as nevek vannak.
A `SID_TVC` mappát változatlan szerkezetben kell a TVC lemezére / SD-kártyájára másolni.

## Mit tud

- **6502-emuláció** a hivatalos és a stabil illegális utasításokkal; PSID és RSID; `play = 0` esetén az
  init által beállított IRQ-rutin ($0314 vagy $FFFE) fut képkockánként.
- **Hurok:** a dal első pontos ismétlődése (a teljes C64-memória alapján); a TVC-n a dal onnan ismétlődik.
  Ha 10 percen belül nincs ismétlődés, a dal a végén elölről indul.
- **SID-burkoló (ADSR)** a valódi SID-időzítésekkel; hullámforma, impulzusszélesség, hangerő.
- **Tömörítés** hangonként (ismétlődő részek visszahivatkozással); a kész dal legfeljebb ~40 KB lehet.
- Minden kimenetet visszaellenőriz a TVC lejátszójának pontos mására.

Nem kezeli (egyelőre): többszörös sebességű (CIA-val gyorsított) dalok, digi-hangok, a SID szűrője.

## A .STC formátum

2 bájt hossz (L), majd a dal `$C000` feletti része, végül a `$5000..$BFFF` rész (így a TVC ROM-jával
egyszerűen betölthető). A dal `$5000`-tól: 6 bájtos fejléc (a 3 hang folyamának címe), majd hangonként
képkockánként egy rekord:

| Kód | Jelentés |
|---|---|
| `$00..$0F` | bit 0: lépésköz (2 bájt); bit 1: lépésköz += előjeles bájt; bit 2: szelet (1 bájt: `<$80` táblalap 0..15, `>=$80` négyszög, szint = alsó 3 bit); bit 3: PW (1 bájt) |
| `$80+n` | n képkocka változás nélkül |
| `$10 lo hi n` | REF: n rekord lejátszása a lo/hi címről |
| `$11 lo hi` | ugrás (hurok) |

Licenc: GPL-3.0-or-later.

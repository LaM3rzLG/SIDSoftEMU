# SIDLEJATSZO – C64-es SID-zene lejátszó TVC-programokba

A [SIDSoftEMU](../) lejátszója önállóan, fájlkezelés nélkül, **saját TVC-programba (TRSE / Z80) építéshez**. A C64-es
SID-zenét a TVC saját 4 bites hangkimenetén játssza le, 3 hangon, 5008 Hz-en, SID-kártya nélkül. A zenét előbb PC-n
kell átalakítani a [`sid2tvc`](https://github.com/LaM3rzLG/TVC-Programok/tree/main/sid2tvc)-vel.

## A mappa tartalma

| Fájl | Mi ez |
|---|---|
| `SIDLejatszo.ras` | **a lejátszó** (TRSE Rascal + Z80 asm). Az elején a teljes leírás: adatok, paraméterek, belépési pontok, szabályok. A végén egy törölhető minta. |
| `SIDLejatszo.trse` | TRSE-projektfájl (rendszer: TVC) |
| `resources/sid_zaj.bin` | a zaj-tábla (256 byte), a lejátszó `incbin`-nel beolvassa – **kell** |
| `resources/lejatszo/demo_dal.bin`, `demo_paletta.bin` | a minta zenéje (Last Ninja 1. dal, 1 perc) – csak a mintához |
| `tools/stc2bin.py` | átalakító: `.STC` → nyers dal + paletta (Python 3) |
| `SIDLejatszo.cas`, `SIDLejatszo.dsk` | a lefordított minta: lemezen `LOAD "SIDLEJ"`, bármely gomb leállítja |

## A zene elkészítése

1. `.sid` → `.STC`: `sid2tvc -s 1 zene.sid` → `SID_TVC/ZENE/SONG1.STC`
   (`.sid` zenék: [HVSC](https://www.hvsc.c64.org/)).
2. `.STC` → nyers memóriaképek: `python3 tools/stc2bin.py SONG1.STC zene`
   → `zene_dal.bin` (a **`$2300`**-as címre) és `zene_paletta.bin` (3584 byte, a **`$F000`**-ra).
   Kiírja a címet, a szerzőt, a hosszt (képkocka, 50/s) és a hurokpontot is.

## Használat a programban

```pascal
SidMod := 2;                    { a port 6 módbitjei: 0 = GRAPHICS 2, 1 = GRAPHICS 4, 2 = GRAPHICS 16 }
{ a zene_dal.bin legyen a $2300-on (saját betöltővel vagy incbin("zene_dal.bin", $2300)) }
SidPalettaMasol(#Paletta);      { a zene_paletta.bin -> $F000 }
SidInit();
SidStart();                     { innentől szól }
{ ... másodpercenként 50-szer: SidKepkocka() - megvárja a következő képkockát és dekódol egyet ... }
SidStop();                      { csend, a rendszer IT-je és lapozása vissza }
```

| Belépési pont | Mit csinál |
|---|---|
| `SidPalettaMasol(cím)` | a 14 × 256 byte-os paletta a `$F000`-ra |
| `SidInit()` | táblák (`$FE00` zaj, `$FF00` szintlap), a dekódoló alaphelyzete a `$2300`-as dalból |
| `SidStart()` | saját IT a `$38`-ra, hang-IT be (5008 Hz), lapozás `$B0` |
| `SidKepkocka()` | megvárja a `SidFlag`-et (50 Hz), és dekódol egy képkockát |
| `SidStop()` | leállítás, minden vissza |

Asm-ből ugyanezek: `call SidStartK`, `call SidKepK`, `call SidStopK` (a `SidInit` és a `SidPalettaMasol` Rascal-eljárás).

## Szabályok lejátszás közben

- A hang-IT használja az **IX, IY** regisztereket, a **második regiszterkészletet** (BC' DE' HL') és az **AF'**-et: a
  főprogram ne nyúljon hozzájuk (a TRSE által fordított kód sem!), ROM-hívás se legyen. A mintában ezért asm a hurok.
- **Memória:** a dal `$2300`-tól (legfeljebb `$EBFF`-ig), a táblák `$F000–$FFFF`. A lejátszó kódja, változói és a verem
  ne essenek ide (a minta kódja `$1A03–$1F8C`).
- **Lapozás:** `$B0` (U0, U1, U2, U3). Az IT csak a `$F000–$FFFF`-et olvassa; a `SidKepkocka` a dal teljes területét. A
  képernyő (VID) csak két `SidKepkocka` között lapozható be, ha a dal `$8000` fölé ér.
- **CPU:** a hang-IT a processzoridő ~53%-a, a `SidKepkocka` ~2–3%.
- A `SidStart` a CRTC kurzor-IT-jét kikapcsolja, a `SidStop` visszakapcsolja (R10/R11 = 3).
- A zene a végén a hurokpontra ugrik, a `SidStop`-ig szól.

## Fordítás

TRSE-ben nyisd meg a `SIDLejatszo.trse`-t, és fordítsd le (Build). Parancssorból:
`trse -cli op=project project=SIDLejatszo.trse input_file=SIDLejatszo.ras assemble=yes`.

---
SIDSoftEMU / SIDLEJATSZO – L@M3rZ (LaM3rzLG), 2026.

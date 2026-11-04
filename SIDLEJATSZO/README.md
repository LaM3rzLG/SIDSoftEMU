# SIDLEJATSZO – SID unit: C64-es háttérzene TVC-játékokhoz

A [SIDSoftEMU](../) lejátszója **TRSE-unitként** (`SID.tru`), ahogy a GE: `@use "SID"`, és `SID::Start` / `SID::Play` /
`SID::Stop`. A C64-es SID-zenét a TVC saját 4 bites hangkimenetén játssza le, 3 hangon, SID-kártya nélkül, **miközben a
játék fut**: a `SID::Play`-t képkockánként kell hívni a játék fő hurkából. A zenét előbb PC-n kell átalakítani a
[`sid2tvc`](https://github.com/LaM3rzLG/TVC-Programok/tree/main/sid2tvc)-vel.

## A mappa tartalma

| Fájl | Mi ez |
|---|---|
| `SID.tru` | **a unit** – az elején a teljes leírás (paraméterek, belépési pontok, szabályok). Másold a programod mellé. |
| `SIDPelda.ras`, `SIDPelda.trse` | minta: egy négyzet pattog a képen, közben szól a zene (bármely gomb = vége) |
| `SIDPelda.cas`, `SIDPelda.dsk` | a lefordított minta: lemezen `LOAD "SIDPELDA"` |
| `resources/lejatszo/demo_*.bin` | a minta zenéje (Last Ninja 1. dal, 1 perc; a dal `$6000`-ra áthelyezve) |
| `tools/stc2bin.py` | átalakító: `.STC` → a dal a kívánt címre + paletta (Python 3) |
| `LICENSE` | MIT licenc |

## A zene elkészítése

1. `.sid` → `.STC`: `sid2tvc -s 1 zene.sid` → `SID_TVC/ZENE/SONG1.STC`
   (`.sid` zenék: [HVSC](https://www.hvsc.c64.org/)).
2. `.STC` → a memóriába: `python3 tools/stc2bin.py -c 6000 SONG1.STC zene`
   → `zene_dal.bin` (**a `$6000`-ra áthelyezve** – a `-c` a dal címe a programodban) és `zene_paletta.bin` (3584 byte).
   Kiírja a címet, a szerzőt, a hosszt (képkocka, 50/s) és a hurokpontot is.

## Használat

```pascal
@use "GE"
@use "SID"

var
  Dal     : incbin("zene_dal.bin", $6000);      { ugyanaz a cím, mint a stc2bin -c }
  Paletta : incbin("zene_paletta.bin");

begin
  GE::Init(GE::DIRECT_TO_SCREEN);
  GE::SetMemory(GE::MEM_48K_VID);               { U0, U1, VID, U3: a táblák az U3-ban ($F000) }
  SID::Init(#Dal, #Paletta, $F0);
  SID::Start();
  while (...) do
  begin
    SID::Sync();                                { vár a következő képkockára - a GE::WaitForSync helyett }
    { ... rajzolás, játéklogika ... }
    SID::Play();                                { a zene léptetése }
  end;
  SID::Stop();
end.
```

| Belépési pont | Mit csinál |
|---|---|
| `SID::Init(Dal, Paletta, Lap)` | a dal címe, a paletta címe, a táblák lapja (felső byte; `$F0` = `$F000–$FFFF`, vagy pl. `$70` = `$7000–$7FFF`). Táblákat készít, a dekódolót alaphelyzetbe teszi. |
| `SID::Start()` | saját hang-IT a `$38`-ra (5008 Hz, a kép aljához igazítva) – innentől szól |
| `SID::Sync()` | vár a következő képkockára (50/s) – a játék képkocka-szinkronja |
| `SID::Play()` | a zene léptetése; ha a játék lekésett egy-két képkockát, behozza (a tempó nem csúszik) |
| `SID::Stop()` | csend, a régi IT, a CRTC és a hang-port vissza |

Asm-ből: `call SdStartK`, `call SdWaitK` (Sync), `call SdStepK` (Play), `call SdStopK`.

## Szabályok lejátszás közben

- **Regiszterek:** a hang-IT foglalja a második regiszterkészletet (BC' DE' HL') és az AF'-et. **IX és IY szabad** (a GE
  sprite-jai is használhatják). A GE digi-hangja ugyanezt foglalja, ezért a kettő egyszerre nem mehet.
- **IT:** a `$38`-on a lejátszó IT-je van, ezért a `GE::WaitForSync` (`halt`, bármely IT-re továbblép), a
  `GE::EnableTVCITHandler`, a `GE::DigiSoundOn` és a ROM-hívások nem használhatók. Szinkron: `SID::Sync`.
- **Memória:** a táblák (`Lap`, 4 KB) és a unit kódja mindig látsszon; a dal csak a `SID::Play` alatt kell (a Play
  ideiglenesen `$B0`-ra lapoz). `Lap = $F0` esetén a 3. lapon U3 kell (`GE::MEM_48K_VID`); `Lap = $70`-nel bármilyen
  lapozás jó.
- **di-szakasz** legfeljebb ~600 T lehet: a hang-IT 624 T-nként jön, ha kettő összeér, egy elvész.
- **CPU:** a hang-IT a processzoridő kb. **63%-a**, a `SID::Play` kb. 2–3% képkockánként – a többi a játéké.
- A `Start` a CRTC-t a hang-IT-hez igazítja (R5 = 0, kurzor-IT ki), a `Stop` visszaállítja.
- A zene a végén a hurokpontra ugrik, a `SID::Stop`-ig szól.

## Fordítás

TRSE-ben nyisd meg a `SIDPelda.trse`-t, és fordítsd le (Build): a TRSE a `SID.tru`-t a projekt mappájából veszi.
Parancssorból: `trse -cli op=project project=SIDPelda.trse input_file=SIDPelda.ras assemble=yes`.

## Licenc

**MIT** ([LICENSE](LICENSE)): szabadon használható és beépíthető bármilyen programba, a forrását sem kell
kiadni. A minta zenéje (Last Ninja, Ben Daglish & Anthony Lees, System 3) a szerzőké.

---
SIDSoftEMU / SIDLEJATSZO – L@M3rZ (LaM3rzLG), 2026.

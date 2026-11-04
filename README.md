# SIDSoftEMU

**Commodore 64-es SID-zenék a Videoton TV-Computeren, SID-kártya nélkül** – a TVC saját 4 bites hangkimenetén, 3 hangon.
Ez a fejlesztés forrása (TRSE / Z80, C, Python).

- **Kész program, letöltés:** [TVC-Programok / SIDSoftEMU](https://github.com/LaM3rzLG/TVC-Programok/tree/main/SIDSoftEMU)
  (`SIDTVC.CAS`, `SIDTVC.dsk`, zenék) és a PC-s átalakító, a
  [SID2TVC Converter](https://github.com/LaM3rzLG/TVC-Programok/tree/main/SID2TVC_Converter) (sid2tvc; Windows, macOS, Linux).
- **Háttérzene saját programba / játékba:** [SID2TVC TRSE Unit](https://github.com/LaM3rzLG/TVC-Programok/tree/main/SID2TVC_TRSE_Unit)
  (forrás: [SID-Player-for-TRSE](https://github.com/LaM3rzLG/SID-Player-for-TRSE)) – a `SID` unit (`@use "SID"`, `SID::Start` / `SID::Play` / `SID::Stop`), mintával és leírással.
- **Hogyan működik:** [MUKODES.md](https://github.com/LaM3rzLG/TVC-Programok/blob/main/SIDSoftEMU/MUKODES.md).

| Hol | Mi |
|---|---|
| `SIDSoftEMU.ras` | a teljes program: fájlkezelő (lemez VT-DOS 1.1/1.2, SD Dual, NanoSD, TVC256k++) + lejátszó |
| `tools/sid2tvc/` | a `.sid` → `.STC` átalakító (C99, GPL-3) |
| `sid_tvc/` | a Last Ninja 1–2 zenéi átalakítva (`.STC`); az eredeti `.sid` fájlok jogdíj miatt nincsenek a repóban ([HVSC](https://www.hvsc.c64.org/)) |
| `docs/` | a kezdeti kutatás és terv |

## Licenc

**MIT** ([LICENSE](LICENSE)): szabadon használható, módosítható és beépíthető bármilyen programba. Kivételek:
`tools/sid2tvc/` GPL-3.0-or-later; `tvc_units/` a TRSE és a GE unit (Bertók Zsolt) saját licence szerint; a zenék
(`sid_tvc/`) szerzői jogai a szerzőké és a kiadóé.

---
L@M3rZ (LaM3rzLG), 2026.

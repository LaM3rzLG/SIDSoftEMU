# SIDSoftEMU

**Commodore 64-es SID-zenék a Videoton TV-Computeren, SID-kártya nélkül** – a TVC saját 4 bites hangkimenetén, 3 hangon.
Ez a fejlesztés forrása (TRSE / Z80, C, Python).

- **Kész program, letöltés:** [TVC-Programok / SIDSoftEMU](https://github.com/LaM3rzLG/TVC-Programok/tree/main/SIDSoftEMU)
  (`SIDTVC.CAS`, `SIDTVC.dsk`, zenék) és a PC-s átalakító, a
  [sid2tvc](https://github.com/LaM3rzLG/TVC-Programok/tree/main/sid2tvc) (Windows, macOS, Linux).
- **Lejátszó saját programba:** [`SIDLEJATSZO/`](SIDLEJATSZO/) – fájlkezelés nélkül, beépíthető, leírással.
- **Hogyan működik:** [MUKODES.md](https://github.com/LaM3rzLG/TVC-Programok/blob/main/SIDSoftEMU/MUKODES.md).

| Hol | Mi |
|---|---|
| `SIDSoftEMU.ras` | a teljes program: fájlkezelő (lemez VT-DOS 1.1/1.2, SD Dual, NanoSD, TVC256k++) + lejátszó |
| `SIDLEJATSZO/` | az önálló lejátszó |
| `tools/sid2tvc/` | a `.sid` → `.STC` átalakító (C99, GPL-3) |
| `sid/`, `sid_tvc/` | a Last Ninja 1–2 zenéi (`.sid` a HVSC-ből) és átalakítva |
| `docs/` | a kezdeti kutatás és terv |

A zenék szerzői jogai a szerzőké és a kiadóé.

---
L@M3rZ (LaM3rzLG), 2026.

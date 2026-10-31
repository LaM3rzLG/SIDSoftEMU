# SIDSoftEMU — projekt-memória (CLAUDE.md, indulás: 2026-10-30)

Rövid, minden munkamenet elején betöltődik. Érdemi változás után frissítsd röviden.
**Git: https://github.com/LaM3rzLG/SIDSoftEMU (privát).**
**A felhasználó NEM gitel: a pull/commit/push mindig a Claude dolga, a felhasználót soha ne kérd git-parancsra.**
**KÉT GÉP, KÖZÖS MUNKATERÜLET:** Windows 11 (WinTVC) és Mac (ep128emu); részletek a **tvc-trse** skill
"Two machines, one shared workspace" részében.
**Skillek: KÖZÖS, egy példány: `TVC_Kozos/skills`** (https://github.com/LaM3rzLG/TVC_Skills). A `.claude/skills/` mappában
csak linkek vannak (gitignore; bekötés: Mac `bash ../TVC_Kozos/skills/bekot.sh .`, Windows `bekot.ps1` junctionnel).
Mindig töltsd be: **tvc-trse** (Macen + **tvc-trse-mac**); PC-s eszközök: **tvc-utils**.
Testvérprojektek és minták: `../Ugh`, `../WaterPumpGame`.

## A projekt
- Videoton TV-Computer (Z80, 3 MHz), TRSE/Rascal. **Cél: a C64 SID szoftveres utánzása** (3 hang, hullámformák,
  ADSR), lépésenként. 1. lépés kész: `docs/01_SID_kutatas.md` (terv: PC-n .sid -> regiszterdump, TVC-n csak
  szintézis táblákkal, IT-ből, port 6 = 4 bites DAC; minta: `tvc_units/music.tru`, GE digi, AVR SID).
  Modell: `tools/sid_modell.py` -> `hang_minta/*.wav`. **Döntés (2026-10-31): "A" változat** = 5008 Hz IT,
  hangonként 0..5 szint, összeg port 6-ra; becslés ~265 ciklus/minta = ~42% CPU (+~5% a 50 Hz-es lejátszó).
- **1. TVC-teszt (2026-10-31, ep128emu-ben fut):** `SIDSoftEMU.ras` = hang-IT (IX/IY/HL' fázis, 5 byte-os
  önmódosító "rés" hangonként: tábla vagy négyszög-PWM) + Pascal lejátszó; adat `tools/sid_tvc_adat.py` ->
  `resources/sid_adat.bin` ($6000-ra másolva), pontos várt hang: `hang_minta/5_tvc_pontos.wav`.
  **Mérés a keretben** (a felhasználó így kéri mindig): IT = piros, lejátszó = zöld. Mért: piros 36%
  (+ belépés/kilépés ≈ 41-48% az IT), zöld 11,6% (a Pascal lejátszó - asm-mel gyorsítható).
- Alap (2026-10-31, emulátorban kipróbálva): `SIDSoftEMU.ras`, GE unit, **Graphics 4** (paletta: fekete, cián, piros,
  sárga), memória **U0,U1,VID,SYS** (`GE::MEM_VID_ON` = $50). A ROM a $C000-on, a képernyő a $8000-on van, ezért
  a program kódja és adata csak $0000-$7FFF lehet (most $19EF-$1CA3). `GE::Init` kikapcsolja a firmware IT-t;
  ROM-hívás előtt `GE::EnableTVCITHandler()`.
- Build: Mac `bash resources/build_mac.sh` (Cmd+Shift+B), Windows `resources\build.ps1`; lemezen: `load"SIDSOFT"`.
  A váz az Ugh-ból jött (`tvc_units/`, `resources/kozos.ps1`, `make_dsk.ps1`, `.vscode/tasks.json`).

## Munkastílus
Magyarul, tömören; a lemez az igazság; `.bak_<név>` minden változtatás előtt; kétértelmű kérésnél az értelmezést egy
mondatban kimondani; a felhasználó tesztel; a CLAUDE.md-t frissíteni.

## Állapot (2026-10-31, munkamenet lezárva - új projekt jött)
- **4 változatos teszt kész és fut** (ep128emu): `SIDSoftEMU.ras`, 1..4 gomb élőben vált; táblák 15,5 KB az U3-ban
  (`GE::MEM_48K_VID`, ROM nincs bent), adat $7000-tól, programvég $6C1F. Keret: IT piros ~38%, lejátszó zöld ~12%.
  1 = 6 szint/hang (5008 Hz), 2 = 8 szint + lágy tömörítő keverés, 3 = 2 + sávkorlátozott fűrész, 4 = 3 @ 3986 Hz.
- **A felhasználó ítélete: a minőség alig különbözik, az 1-es a legjobb fülre.** -> a 2-4 nem éri meg; maradjon az
  "A" (1-es) út, a keverőtábla (+~2% IT) elhagyható.
- WAV-ok a Macen: `python3 tools/sid_modell.py` (0-4), `python3 tools/sid_tvc_adat.py` (6-9 = a 4 változat pontos modellje).
- Folytatás (ha visszatérünk): lejátszó asm-be (12% -> 2-3%); táblák generálása induláskor (a program kisebb);
  PC-s .sid -> regiszterdump -> TVC dal formátum (siddump/cRSID); ADSR a SID valódi időzítéseivel.
- **A GitHub-repó (LaM3rzLG/SIDSoftEMU) még NEM létezik** - minden commit csak helyben van; létrehozáshoz a
  felhasználó engedélye kell (az auto mód letiltotta).

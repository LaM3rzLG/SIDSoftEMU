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
  A `dalok/DAL*.BIN` fájlokat mindkét build magától a lemezre teszi.
  A váz az Ugh-ból jött (`tvc_units/`, `resources/kozos.ps1`, `make_dsk.ps1`, `.vscode/tasks.json`).

## Munkastílus
Magyarul, tömören; a lemez az igazság; `.bak_<név>` minden változtatás előtt; kétértelmű kérésnél az értelmezést egy
mondatban kimondani; a felhasználó tesztel; a CLAUDE.md-t frissíteni.

## SID-fájl lejátszás (2026-10-31, ep128emu-ben fut; a felhasználó: "működik, elég jól szól, lehetne jobb" - szünet)
- `sid/Last_Ninja.sid` (HVSC, 11 aldal). PC: `python3 tools/sid2tvc.py sid/Last_Ninja.sid <aldal>` = 6502-emu
  (`tools/m6502.py`, `sid_dump.py`: hurok a teljes memória ismétlődéséből) -> SID-ADSR szimuláció -> hangonként
  (lépés, szelet, PW) -> hangonként külön, visszahivatkozásos (REF) folyam -> `dalok/DALnn.BIN` + pontos WAV
  `hang_minta/Last_Ninja_<n>_tvc.wav`. Formátum a `sid2tvc.py` fejében.
- **A felhasználó döntése: a dalok lemezfájlból töltődnek** (aldalanként egy fájl), nem a programba fordítva.
- TVC (`SIDSoftEMU.ras`, a régi 4 változatos teszt: `.bak_teszt4`): menü ROM-mal (1-9, 0=10, A=11) -> betöltés
  (Lemmings-sorrend; a $C000 feletti rész előbb $8000-ra, onnan U3-ba) -> lejátszás **$B0 lapozással (teljes 64K
  RAM)**, dal $4000-tól (max 44800 B), táblák $EF00-$FFFF; bármely gomb = vissza a ROM-nak ($38 = F5 3E 70,
  port 5, CRTC R10/R11 = 3) és a menübe. Dekódoló asm-ben: zöld sáv ~2-3%.
- Méretek: 26-41 KB; **az 5. aldal 47 KB, nem fér el** (nincs a lemezen) - jobb tömörítés kell (pl. 2 szintű REF).
  A 2. és 9. aldalnak 10 percen belül nincs hurka (10 perc után elölről).
- **TVC-s .sid-átalakítás: ELVETVE (a felhasználó döntése, 2026-10-31)** - megépült, működött (freeTVC-ben bájtra
  egyezett), de lassú (~1,3x a dal hossza) és gyengébben tömörít; kód: git címke `tvc-atalakito`, terv: `docs/02_...md`.
  **Az új irány:** (1) a TVC csak lejátszik (`SID_TVC\<NÉV>\<nn>.STC`, .sid nincs a lemezen); (2) **önálló, több
  platformon (Mac, Linux, Windows) futó `sid2tvc` alkalmazás** a PC-n; (3) SIDSoftEMU: **hangminőség + hurkok**.
  A program most $2295-ig tart -> a dal kezdete $5000 helyett ~$2300 lehet (~51 KB hely, az 5. aldal is elfér).
  Tanulságok (a skillben): fájlírás asm-ből, IY/AF' visszaállítás ROM-hívás előtt, ep128emu lemezkép-puffer,
  freeTVC headless + monitor `profile` a pontos méréshez, OrgAsm `(ix+NEV+1)` hiba.
- Folytatási ötletek: hangminőség (szűrő közelítése táblával, finomabb szintek/keverés, zaj), 5. aldal
  tömörítése, más .sid-ek kipróbálása, dal neve a fájlból a menüben.

## Állapot (2026-10-31, munkamenet lezárva - új projekt jött)
- **4 változatos teszt kész és fut** (ep128emu): `SIDSoftEMU.ras`, 1..4 gomb élőben vált; táblák 15,5 KB az U3-ban
  (`GE::MEM_48K_VID`, ROM nincs bent), adat $7000-tól, programvég $6C1F. Keret: IT piros ~38%, lejátszó zöld ~12%.
  1 = 6 szint/hang (5008 Hz), 2 = 8 szint + lágy tömörítő keverés, 3 = 2 + sávkorlátozott fűrész, 4 = 3 @ 3986 Hz.
- **A felhasználó ítélete: a minőség alig különbözik, az 1-es a legjobb fülre.** -> a 2-4 nem éri meg; maradjon az
  "A" (1-es) út, a keverőtábla (+~2% IT) elhagyható.
- WAV-ok a Macen: `python3 tools/sid_modell.py` (0-4), `python3 tools/sid_tvc_adat.py` (6-9 = a 4 változat pontos modellje).
- Folytatás (ha visszatérünk): lejátszó asm-be (12% -> 2-3%); táblák generálása induláskor (a program kisebb);
  PC-s .sid -> regiszterdump -> TVC dal formátum (siddump/cRSID); ADSR a SID valódi időzítéseivel.
- **GitHub-repó NEM kell (a felhasználó döntése, 2026-10-31)** - csak helyi git, ne hozd létre, ne kérdezd.

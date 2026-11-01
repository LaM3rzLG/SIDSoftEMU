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
  A `sid_tvc/<NÉV>/*.STC` fájlokat mindkét build magától a lemezre teszi (`SID_TVC\<NÉV>\`).
  A váz az Ugh-ból jött (`tvc_units/`, `resources/kozos.ps1`, `make_dsk.ps1`, `.vscode/tasks.json`).

## KÖVETKEZŐ LÉPÉS (2026-11-01, a felhasználó kérése: ha azt kérdezi „mi a következő?”, EZZEL kezdünk)
**Szebb hang csak a TVC saját 4 bites kimenetével** (SID-kártya NEM kell), a PC előre kiszámol mindent:
1. **Dalonkénti hangszínpaletta:** a PC a valódi SID-hangot számolja (szűrő, kevert hullámformák, gyűrűmoduláció, PW),
   dalonként 8–16 egyciklusú hangszín-táblát készít (256 B/tábla, 2–4 KB/dal), képkockánként a legközelebbit választja.
   TVC: a tábla értéke 0–15, a hangerő egy MÁSODIK táblakereséssel (`ld e,a / ld d,SZINTLAP / ld a,(de)`, ~7% CPU).
2. **Okos hangerő-elosztás:** a PC képkockánként osztja szét a DAC 16 szintjét a szóló hangok között (egy hang = mind a 16).
3. (utána) **Dobok mintából:** a PC felismeri a dobütéseket, rövid 4 bites minták (1–3 KB/dal); 4. **tempó** a gyorsított
   (CIA) zenéknél (lépés/s a fejlécben).
**Állapot (2026-11-01): az 1+2 KÉSZ a TVC-n is (.STC 1.2), a felhasználó tesztje hátravan.** A/B (`hang_minta/AB/`,
60 s: A = valódi SID `tools/sid_ref` (brew libsidplayfp, SIDLite), B = régi, C/D/E = kísérletek, F = végleges): a felhasználó
az **E**-t választotta (sávkorlát nélkül, fényes). A dinamikus (képkockánkénti) erősítéssel a dalok ~2x nagyobbak lettek
(a REF nem talál) -> **dalonként állandó erősítés** (99. percentilis = 15) + szint-hiszterézis (0,9) + tábla-hiszterézis
(1,3x): mérve ugyanolyan jó (log-spektrum 60-2500 Hz), méret ~ a régi + 15%. 33/34 dal fér el (LN2/12: 53 742 > 52 480).
TVC: rés 10 byte (`ld e,a / ld d,$F0+t / ld a,(de) / or szint / ld e,a / ld d,$FF / ld a,(de)` vagy négyszög
`cp PW / sbc a,a / and szint*4 / jr +3`, `db`-vel, hogy a TRSE optimalizálója ne nyúljon hozzá), keverőlap helyett
`SidOfs: add a,K` (K = (15 - szintek)/2*4 + 2 = DC + GR16 modbit). IT ~330 T / 624 (~53%, régi ~44%). RezVege $22DC.
freeTVC headless-ben ellenőrizve: paletta/zaj/szintlap/dal a memóriában bájtra, a rések és a K helyes.
freeTVC headless Macen: `--preset 64k-1.2 --rom-dir ~/Documents/FreeTVC/build/mac-release/src/roms --disk-card --disk-rom 1.2
--disk X.dsk --type '\n@600' --type 'load"SIDSOFT"\n@700' --key DOWN@4550 --key RETURN@4600 ... --wav/--screenshot/--save-snapshot`
(preset nélkül nem indul; az első gépelt betűk elvesznek, ezért előbb egy \n); memória: `--moncommands` `undump`, `bsave`.
Menet: MINDENT előbb a PC-n, WAV A/B-vel (valódi SID-referencia / mostani TVC / új TVC) - a felhasználó dönt, csak ami
neki jobb, az megy a TVC-re. Az 1+2 együtt (ugyanaz a lejátszó-módosítás). A HVSC tömeges átalakítása (61 159 SID,
~6–10 óra párhuzamosan) KÉSŐBBRE halasztva.

## Munkastílus
Magyarul, tömören; a lemez az igazság; mentés = git (a felhasználó 2026-11-01: `.bak`-ok és átmeneti fájlok NEM kellenek); kétértelmű kérésnél az értelmezést egy
mondatban kimondani; a felhasználó tesztel; a CLAUDE.md-t frissíteni.

## SIDSoftEMU = új fájlkezelő + lejátszó (2026-11-01, freeTVC-ben kipróbálva)
- A `SIDSoftEMU.ras` most: GE unit, GRAPHICS16, a FajlTeszt16 fájlkezelője (Ir16, csúszó sáv, forgó logó IT-ből) + a régi
  Betolt/Lejatszas (változatlan, csak a port 6 modbitje 2 = GR16). Enter .STC-n: `Jatszik` -> FkFajl, firmware IT,
  `DalJatszas`, elengedésre vár, `SetMemory($50)`, lista újra (a kijelölés marad), logó-IT vissza.
- Memória: rezidens vége `RezVege` $229F (< $2300, 97 B tartalék!); kód vége $3115 (< $5000); font $5000, logó $6180
  (`incbin(fájl, cím)` - asm-ben az incbin relatív útja nem működik); lista $7000. Lejátszás alatt a VID $8A00-tól: kód +
  font/logó (~11,8 KB, max 12 288; mentés $8C00-tól), R6 = 12: a felső 48 pontsor = cím, szerző, kiadás, könyvtár\fájl,
  jobbra a logó 0. fázisa (a felhasználó kérése). **.STC 1.1** (sid2tvc 1.1): `$FF $FF` + 3 × 32 bájt info a .sid fejlécéből,
  aztán a régi formátum; a Betolt átugorja, az `InfoOlvas` lejátszás előtt $6F00-ra olvassa (1.0-s fájlnál csak könyvtár\fájl).
  A tempó NEM változhat (50 lépés/s a hang-IT-ből) - a felhasználó kiemelte. „<Könyvtár>” a 39. oszlopon (jobb széle = a KB-é). A keret fekete: a mérés (IT piros, lejátszó zöld) kivéve (2026-11-01). A `build_mac.sh` ellenőrzi a határokat.
- Kipróbálva freeTVC-ben (VT-DOS 1.2): LN1/1 és LN1/5 (47 KB, bájtra egyezik a memóriában), LN3/1, vissza a listába,
  ESC, könyvtárváltás, logó forog lejátszás után. Lejátszás alatt a logó áll (a hang-IT fut). Windows: a build.ps1-ben
  nincs memória-ellenőrzés.

## Kiadás (2026-11-02): NYILVÁNOS repó `../TVC-Programok` (https://github.com/LaM3rzLG/TVC-Programok)
A felhasználó kész programjai programonként egy mappában (csak futtatható fájlok, forrás nem). SIDSoftEMU 1.0 = `SIDSOFT.CAS`
+ `SID_TVC/` + a két .dsk + README + `kepek/`; GitHub-release `sidsoftemu-1.0` (ZIP). Frissítés menete: a TVC-Programok
CLAUDE.md-jében. A `sid2tvc` később kerül ki (Win/Mac/Linux, felülettel; GPL-3 -> a forrás is mellé).

## A LEJÁTSZÓ VÉGLEGES (2026-11-02, a felhasználó: „végleges lejátszó”; git címke `lejatszo-kesz`)
.STC 1.3, hangszínpaletta + 16 szintű hangerő, keretcsík a szöveg mellett, százalék, csúszás, kilépés-kérdés.
Valódi TVC-n (312 soros kép, NanoSD, FISH) még nincs kipróbálva.

## Lejátszás-kijelző, csúszás, .STC 1.3 (2026-11-02, freeTVC headless-ben kipróbálva)
- **Százalék a fájlnév mellett** (a felhasználó kérése: csak szám, „0%...100%”, ne vegyen el képsort). A .STC 1.3 (`$FD $FF`)
  az info után 8 byte-ot hoz: N (képkockák), hurokpont, a hurokpont %-a, 0, maradéka (×100 mod N) - a TVC osztás nélkül,
  maradékkal lépteti (R += 100; amíg R ≥ N: R -= N, % + 1), a végén a hurokpont %-ára ugrik. A `Jatszik` előkészít: az Ir16
  a 0-9 jegyeket az 50. sorba rajzolja, onnan cellánként (3 byte × 10 sor) a `$ECD0`-ra, a 11. cella üres; a `%` jelet egyszer
  kiírja; a képkockánkénti kód (`PrKod`, 163 byte, helyfüggetlen) a `$EC00`-ra, változók `$ECB0..$ECC3`. A főciklus
  `call $EC00`; rajzoláskor `$90` lapozás (U0,U1,VID,U3). **A dal ezért legfeljebb $EBFF-ig** (51 456 B; 33/34 elfér).
- **Csúszás** (a felhasználó kérése): az infó után a szövegsáv lecsúszik a kép közepére - CRTC **R7** 66 -> 42 (24 karaktersor
  = 96 pontsor), 30 képkocka, lassulva (`Csusztatas`, k = 0 le / 1 fel; a képkockát a kurzor-IT a 47. sor végén jelzi, DI
  mellett pollozva), a lejátszás után vissza. R6 = 12 már az `InfoOlvas` után (a lista és a segédrajz ne látsszon).
- **A logó maszk nélkül** (`resources/images/C64_logo_adat.bin`, 1632 B = `python3 tools/logo_adat.py
  resources/images/C64_logo_forog.bin resources/images/C64_logo_adat.bin`; a háttér fekete, a maszk fölösleges): a VID-be
  mentett rész így 12 081 B (a határ 13 312) - enélkül a kijelző + csúszás nem fért el. **Ha a BMP-k frissülnek: bmp2ge.py,
  aztán logo_adat.py!**
- asm-ben a `*` szorzást a TRSE elrontja (`$8000+50*64` -> hiba): kiszámolt konstans kell; `jr` > 127 byte -> `jp`.

## Keret-sáv lejátszás közben (2026-11-02, freeTVC-ben kipróbálva; a felhasználó: „a szöveg alatt, max 50 pixel”)
A hang-IT a kimenet színét (`$EF00` tábla, a középszinttől való eltérés: fekete…fehér) a keretre írja, de csak a
képkocka 13 IT-jében (C' = 15..3) = kb. a 3..44. sor, a szöveg mellett (2026-11-02: 20%-kal vékonyabb, ne lógjon ki) (a felhasználó 2026-11-02: alatta zavaró); máskor fekete. Ehhez: lejátszás közben
**R5 = 0** (312 sor = 62 400 T = pontosan 100 hang-IT), indításkor `KsSync` ($EF40, a Jatszik másolja oda): kurzor-IT
a 47. sor végére (R14/R15 = $02FF), arra vár, INSTART (`in a,($5B)`), hang-IT be, kurzor-IT ki; kilépéskor R5 = 2,
R14/R15 = $0EFF. **Tanulság:** a főciklus di/ei szakasza < 624 T kell (különben egy hang-IT elvész: a tempó 1%-kal
lassabb volt), és `ei` után legalább egy utasítás a `di` előtt (`ei / di` egymás után = egyetlen tiltott szakasz).
Mérés: MCP `run {until: SidKep}` + `machine_info` beam, ill. `trace`.

## Kilépés (2026-11-01, freeTVC headless-ben kipróbálva)
ESC a gyökérben -> `Kilepes`: doboz középen „Biztosan kilépsz?” I/N (a felhasználó kérése). N vagy ESC (nincs kiírva) = `Rajz()`. I = elengedésre
vár, `GE::EnableTVCITHandler`, $70 lapozás, a BASIC IX/IY/második regiszterkészlete vissza (`IndMent` a főprogram elején:
`IndSP` ...), `GE::SetGraphics(GRAPHICS4)` (ROM VMODE), `ld sp,(IndSP) / ret` -> a „10 PRINT USR(6659)” kiír egy számot
(pl. 85), aztán `ok`. A szövegek asm `db`-ben (a TRSE a "..." konstansokat a rezidens részbe tenné: +48 B, túlcsordult);
asm-ben a `p` változónév nem használható (feltételkód).

## NanoSD (2026-11-01, freeTVC-ben kipróbálva: lista, LN1/5 és LN2/10 bájtra, info; a lemezes mód is megy)
- Indításkor `NsKeres`: a 4 foglalat IOMEM-jében ($C000, port 2 = $D0, port 3 bit 6-7 = foglalat) a „MOPS 6 NANOSD” fejléc
  -> `NsPort` = $10 × (foglalat+1), `Eszkoz` = 1. Ekkor a lista a Nano saját parancsaival: CHDIR (02h, út `/`-rel, 00h) ->
  8Ch, LIST (03h) -> bejegyzésenként 00h + 17 bájt („NEV.KIT” 12, típus 0 = könyvtár, méret 4), ACK 04h, vége 84h; az OUT
  utáni első IN elavult. A betöltés a ROM CAS-hívásaival megy (a NanoSD ROM-ja átveszi), a fájlnév csak `SONGn.STC` (relatív).
  Forrás: FreeTVC `docs/design/cards.md` „NanoSD” + `src/core/cards/nanosd.cpp`. Valódi NanoSD-n még NINCS kipróbálva.
- A build `SD_KARTYA/` mappát is ír (SIDSOFT.CAS + SID_TVC, minden dal) - ezt kell a kártyára másolni. A NanoSD a
  kártya (FAT) sorrendjében listáz; freeTVC-ben név szerint (SONG1, SONG10, SONG11, SONG2...).
- freeTVC NanoSD-próba: `./freetvc --nanosd --nanosd-sd <mappa> --mcp-http ...`, a `freetvc.ini`-ben `disk_card = no`
  (utána vissza!); a NanoSD menüjében Enter a SIDSOFT.CAS-on. Mentés a VID-ben most max $C000-ig (13 312 B).

## SID-fájl lejátszás (2026-10-31, ep128emu-ben fut; a felhasználó: "működik, elég jól szól, lehetne jobb" - szünet)
- `sid/Last_Ninja.sid` (HVSC, 11 aldal). PC: `python3 tools/sid2tvc.py sid/Last_Ninja.sid <aldal>` = 6502-emu
  (`tools/m6502.py`, `sid_dump.py`: hurok a teljes memória ismétlődéséből) -> SID-ADSR szimuláció -> hangonként
  (lépés, szelet, PW) -> hangonként külön, visszahivatkozásos (REF) folyam -> `dalok/DALnn.BIN` + pontos WAV
  `hang_minta/Last_Ninja_<n>_tvc.wav`. Formátum a `sid2tvc.py` fejében.
- **A felhasználó döntése: a dalok lemezfájlból töltődnek** (aldalanként egy fájl), nem a programba fordítva.
- TVC (`SIDSoftEMU.ras`, a régi 4 változatos teszt: git `b6ad113:SIDSoftEMU.ras.bak_teszt4`): menü ROM-mal (1-9, 0=10, A=11) -> betöltés
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
- **`tools/sid2tvc/` = az önálló C-s átalakító (C99, egy fájl, Mac/Linux/Windows; README + Makefile)** - a
  felhasználó döntése: C, fordítási útmutatóval. A Last Ninja 9 aldalán BÁJTRA egyezik a Python-referenciával
  (`tools/sid2tvc.py` + `m6502.py` + `sid_dump.py` - befagyasztva, a fejlesztés a C-ben megy tovább). Tud: illegális
  6502-utasítások, RSID / play=0 (IRQ-vektor), `-a` összes aldal, `-w` WAV, `-o` mappa. Bináris: gitignore.
  Próba más dalokkal (HVSC: Hubbard, Galway, Tel): **a legtöbbnek nincs pontos memória-hurka 10 percen belül ->
  58-80 KB, nem fér el -> HUROKKERESÉS a legfontosabb** (pl. a kimenet ismétlődése); Tel "Wizzy": BRK az 1.
  képkockán (vizsgálni); kell `-n NÉV` (a 8 karakteres név ütközhet).
- **2026-11-02: a Last Ninja 3 KIKERÜLT** (a felhasználó kérése: a .sid és a `sid_tvc/LNINJA3` is); most LN1 (11 dal) +
  LN2 (12 dal). A lenti LN3-as sorok történetiek.
- **Last Ninja 1-2-3 (2026-10-31):** `sid/Last_Ninja_{1,2,3}.sid` -> `sid_tvc/LNINJA{1,2,3}/SONGn.STC`
  (`sid2tvc -a -n LNINJAj -o sid_tvc`), lemezen `SID_TVC\LNINJAj\SONGn.STC`. 33/34 dal; hiányzik az **LN2 12.** (59 KB).
  Két lemezkép (~1 MB): `SIDSoftEMU.dsk` (LN1; 2026-11-02 előtt LN1+LN3), `SIDSOFT2.dsk` (LN2; build: LEMEZ2 / $Lemez2); a dalok természetes
  sorrendben (sort -V) kerülnek fel, mert a fájlkezelő a lemez sorrendjében listáz.
- **Hurok két módszerrel (2026-10-31, sid2tvc.c `hang_hurok`):** memória-hurok + a hallható TVC-állapot ismétlődése, a
  rövidebb dal nyer (`[memoria]`/`[hang]` a kiírásban; `-m` = csak memória). Hurok nélküli dalnál 20 percet elemez.
  Eredmény: 17 dal rövidebb, az LN3 4/7/8/10 kapott hurkot; LN2/12 60,9 -> 59,4 KB, így sem fér el (tömörítés kell).
- **A dal kezdete $2300 (max 52 224 B) + mini fájlkezelő (2026-10-31, ep128emu-ben kipróbálva):** a régi menü helyett
  `Fajlkezelo` (asm): a meghajtó könyvtárai a lemez-ROM FISH hívásaival (`rst $30`/`$DB`, FPB; 04H/05H = első/következő
  keresés), Fel/Le, Balra/Jobbra = lapozás, Enter = könyvtár / .STC, ESC = feljebb; nyílkódok (KBD_CHIN): fel 5, le 24,
  bal 19, jobb 4. **Memória:** rezidens rész (TVC unit, Betolt, Lejatszas, DalJatszas) vége `RezVege` ($1F61) < $2300
  KELL; a `RezVege..FkVege` rész (fájlkezelő, ~1,4 KB) lejátszás előtt a VID-be ($8A00, $50 lapozás) mentődik, közben
  CRTC R6 = 10 (csak a felső 4 szöveges sor látszik), utána vissza. Lista: $6000, FCB-k $7000/$7040, FPB $7080.
  Kipróbálva: könyvtárváltás, LN1/5 (47 KB) bájtra egyezik, LN3/1, LN2/4 szól, vissza a listába, ESC, nem .STC üzenet.
  Valódi gépen (SD) a FISH-hívás még NINCS kipróbálva - ha ott nem megy, a lista üres/hibakód.
- **A próbaprogramok (FajlTeszt, Ir16Teszt, FajlTeszt16) 2026-11-02 óta KÜLÖN privát repóban:** `../FajlTeszt`
  (https://github.com/LaM3rzLG/FajlTeszt; a felhasználó kérése). Itt a régi állapot a `fajlteszt16-kesz` címkén. A tudásanyag
  a közös skillekben: **tvc-fajlkezeles**, **tvc-grafika**. A forgó logó BMP-i és a `tools/bmp2ge.py` itt maradtak.
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
- **GitHub-repó KELL (a felhasználó kérése, 2026-11-01):** https://github.com/LaM3rzLG/SIDSoftEMU (privát). A commitok a
  felhasználó nevében: `LaM3rzLG <lorinczg77@gmail.com>` (repo-szintű git config; a régi commitok is átírva). Munka végén push.

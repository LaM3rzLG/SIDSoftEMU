# 2. lépés: teljes TVC-s SID-lejátszó – terv (2026-10-31)

> **ELVETVE (a felhasználó döntése, 2026-10-31):** megépült és működött (6502-emu + átalakító a TVC-n, freeTVC-ben
> bájtra egyezett, ~1,3x a dal hossza), de lassú és gyengébben tömörít, mint a PC-s átalakítás. A kód a git
> `tvc-atalakito` címkéjén megvan. Helyette: önálló, több platformon futó `sid2tvc` (PC), a TVC csak lejátszik.

Cél: a TVC **maga** tölti be az eredeti `.sid` fájlt, lejátszás előtt **ő** alakítja át a saját dalformátumára,
elmenti, és utána veszteség nélkül lejátssza. A PC csak referenciának és a lemez összeállításához kell.

## 1. Hogyan néz ki a felhasználónak

```
load"sidsoft"
  ┌─ Menü ──────────────────────────────┐
  │ The Last Ninja (1987)               │   a .sid fejlécéből: cím, szerző, aldalak száma
  │ Ben Daglish & Anthony Lees          │
  │ Aldal: 1-9, 0 = 10, A = 11          │
  └─────────────────────────────────────┘
        │ aldal kiválasztva
        ▼
  van SID_TVC\LNINJ03.DAL ? ──igen──► betöltés (pár mp) ──► SZÓL
        │ nem
        ▼
  "Számolás... 37%"  (a dal hosszának kb. 0,6-1,0-szerese, első alkalommal)
        ▼
  mentés: SID_TVC\LNINJ03.DAL ──► SZÓL      (legközelebb már nem kell számolni)
```

Lejátszás közben bármely gomb = vissza a menübe (mint most).

## 2. A lemez

| Mappa | Tartalom | Példa |
|---|---|---|
| gyökér | a program | `SIDSOFT.CAS` |
| `SID` | az eredeti .sid fájlok (8.3-as név) | `SID\LNINJA.SID` (35 KB) |
| `SID_TVC` | a kiszámolt dalok, aldalanként egy | `SID_TVC\LNINJ03.DAL` (26-41 KB) |

- A kiszámolt fájl neve: a .sid nevének első 5 betűje + az aldal 2 jeggyel + `.DAL`.
- A VT-DOS tud mappát (MKDIR / CD / PATH, `\` elválasztó). **Nem próbáltuk még**, hogy a programból hívott
  fájlnyitás (`rst $30` / `$D3`) elfogadja-e az elérési utat – ez az 1. lépés.
- A `.DAL` formátum = a mostani `DALnn.BIN` (2 byte hossz + a $C000 feletti rész + a $4000-es rész; leírás a
  `tools/sid2tvc.py` fejében). Így a lejátszó változatlan marad.

## 3. Mit csinál a TVC a számolás alatt

Képkockánként (= 1/50 s zene):

1. **6502-emuláció:** a dal `play` rutinja lefut a Z80-on írt 6502-emulátorban (LN: átlag ~470, max ~1400 utasítás).
2. **SID-írások elkapása:** a $D400-$D418 írások egy 25 bájtos regiszterképbe mennek; a kapuváltások (gate)
   sorrendben a burkolóhoz.
3. **Burkoló (ADSR):** hangonként szint + állapot, a SID valódi sebességeivel, képkockánként táblákból
   (lépés/képkocka sebességenként, az exponenciális lecsengés a szint szerint).
4. **TVC-állapot:** hangonként lépésköz (frekvenciából), szelet (hullámforma + szint 0..5 vagy négyszög),
   PW – pontosan úgy, mint a `sid2tvc.py`.
5. **Tömörítés (online):** hangonként külön folyam, "változatlan n képkocka" és **visszahivatkozás (REF)** a korábbi
   részekre. A TVC-n nem ismerjük előre a jövőt, ezért *folyamatos egyezéskeresés*: ha a mostani állapot egy korábbi
   egységgel kezdődik, megyünk vele, amíg egyezik; ha megszakad, eldől, hogy REF vagy sima rekordok kerülnek ki.
   Jelölt: állapot-hash -> a legutóbbi 1-2 egység ugyanazzal az állapottal (256 bejegyzéses tábla hangonként).
6. **Hurok-keresés:** futó ellenőrzőösszeg a 6502-memóriára (minden íráskor: régi érték ki, új be) + a
   SID-regiszterek + a burkolóállapot. Ellenőrzőpontok a 2 hatványain (1, 2, 4, ... 8192. képkocka): ha a mostani
   összeg egyezik az ellenőrzőpontéval, megvan a hurok (onnan ismétlődik a dal pontosan). Az ellenőrzőpontokon
   teljes kulcsrekord kerül a folyamba, így a VÉGE oda ugorhat. Ha nincs hurok: legfeljebb 10 perc, aztán elölről.

### Sebesség (becslés, a 3. lépés méri meg)

| Rész | Z80-ciklus / képkocka |
|---|---|
| 6502-emu (470 utasítás x 70-110) | 33 000 – 52 000 |
| SID-írások, burkoló, átváltás | ~3 000 |
| tömörítés | ~3 000 – 8 000 |
| **összesen** | **~40 000 – 63 000** (egy képkocka valós ideje: 62 500) |

-> a számolás a dal hosszának **kb. 0,6-1,0-szerese**, plusz a hurok-keresés túlfutása (LN 3. aldal: ~5 perc
helyett ~5,7 perc zenét kell végigszámolni). Valós idejű lejátszásra ezért nem jó (a hang-IT is ~40%).

## 4. A 6502-emulátor (Z80)

- **Regiszterek:** a 6502 A, X, Y, P, SP memóriában vagy Z80-regiszterekben (pl. A=A, X=B, Y=C, PC=DE);
  a lehető legtöbb a regiszterekben marad. Kiértékelés: utasításkód -> 256 elemű ugrótábla.
- **Jelzők:** N, Z, C közvetlenül a Z80 jelzőiből (a C kivonásnál fordítva!), V külön; decimális mód (`sed`)
  ritka - lassú ágon.
- **Memória-fordítás:** a 6502-cím felső bájtja -> 256 bájtos laptábla -> TVC-lap. 0 = "nincs bent" -> hiba
  (lásd alább). A $D4xx lap = SID (írás a regiszterképbe), $D012 / $D41B / $DCxx olvasás = álérték (raszter,
  véletlen), mint a PC-s `m6502.py`.
- **Ismeretlen (illegális) utasítás:** megáll, kiírja a kódot és a címet ("ez a dal nem támogatott").
- Hívás: `init` (A = aldal-1), majd képkockánként `play`, ahogy a `sid_dump.py`. A visszatérés egy figyelt címre.

## 5. Memória

**Számolás alatt** (lapozás $B0 = teljes 64K RAM, hang nincs, a rendszer-IT ki):

| Terület | Tartalom |
|---|---|
| $0000-$19EE | rendszer (érintetlen marad, a lemezíráshoz kell) |
| $19EF-~$4FFF | program: menü, betöltő, lejátszó, 6502-emu, átalakító (+ a hangtáblák, amíg nem generáljuk őket) |
| $5000-$DFFF | a készülő dal (36 KB) |
| $E000-$FFFF | a 6502 memóriája, tömörítve (8 KB) |

A .sid az elején egészében betöltődik (LN: 35 KB, a $5000-től), lefut az `init`, majd ~10 s zene "próbaüzemben",
miközben a laptábla figyeli, mely lapokhoz nyúl a `play`. Ezután **csak a használt lapok** maradnak meg
(a $E000-ra másolva; LN: nullás lap, verem, $20, $B0-$BA = ~14 lap = 3,5 KB), a többi felszabadul a kimenetnek.
Ha később mégis egy kidobott lapot kér a `play` -> hiba, "a dal túl nagy" (ritka; LN-nél mérten nem fordul elő).

**Lejátszás alatt:** mint most (dal a $4000-tól vagy a $5000-től, táblák $EF00-$FFFF). Ha a program $4000 fölé
nő, a dal max. mérete 44,8 KB-ról ~40 KB-ra csökken (LN: max 41 KB -> a 9. aldal határeset; megoldás: a hangtáblák
generálása induláskor - 4,3 KB -, vagy erősebb tömörítés).

## 6. Lemezre írás

Új dolog, még sosem próbáltuk: a ROM fájl-létrehozás / blokkírás / zárás (a TVC unit `CreateFile`, `BlockWrite`,
`CloseFile` hívásai alapján; az olvasásnál a Bery-féle hívások a valódi gépen nem működtek, ezért itt is a ROM
hívásait közvetlenül, asm-ben). Íráskor a rendszert vissza kell adni (ROM be, rendszer-IT be), mint a mostani
"vissza a menübe" ágon. A kész dal a RAM-ban van, egyben kiírható.

## 7. Lépések (mindegyik végén mérhető eredmény)

| # | Lépés | Kész, ha |
|---|---|---|
| 1 | `make_dsk.ps1` mappákkal (`SID`, `SID_TVC`); a mostani lejátszó a `SID_TVC\LNINJ03.DAL`-ból tölt | szól az emulátorban **és a valódi gépen (SD)** |
| 2 | lemezírás-próba: kis program ír egy fájlt a `SID_TVC`-be, visszaolvassa | a fájl bájtra egyezik, a lemezen látszik (emu + valódi gép) |
| 3 | 6502-emu a TVC-n (külön tesztprogram): `LNINJA.SID` betöltés, `init` + 500 képkocka, a SID-írások naplója a RAM-ba | a napló bájtra egyezik a PC-s dumppal (`ep.sh mem`); **a sebesség a keretben megmérve** |
| 4 | a PC-n: a TVC-s algoritmus pontos Python-mása (online tömörítés, 2-hatvány hurok) | a Python-más kimenete lejátszható, mérete ismert |
| 5 | átalakító a TVC-n (burkoló, átváltás, tömörítés, hurok, lapfigyelés) | a TVC kimenete bájtra egyezik a 4. lépés Python-másával |
| 6 | összerakás: menü (.sid fejléc), gyorsítótár-ellenőrzés, "Számolás %", mentés, lejátszás | a teljes út megy emulátorban |
| 7 | valódi gép | a felhasználó meghallgatja |

**A 3. lépés a döntő:** ha a számolás jóval lassabb a dal hosszánál, ott állunk meg és gondoljuk újra
(pl. gyorsabb emulátor, csak az első N perc, vagy a PC-s átalakítás marad).

## 8. Kockázatok, nyitott kérdések

- **Elérési út a programból** (`SID_TVC\...`) - a VT-DOS parancssorban megy, programból nem próbáltuk; a valódi gép
  SD-s eszközének DOS-a is kezelje.
- **Lemezírás** a programból - nem próbáltuk; a valódi gépen (SD) külön tesztelni.
- **Sebesség** - csak becslés (0,6-1,0x); a 3. lépés dönt.
- **Melyik .sid megy:** PSID, 50 Hz-es (VBI) `play`, hivatalos 6502-utasítások, a használt memória <= ~8 KB a
  `play` alatt. Nem megy (egyelőre): RSID, CIA-időzítés, többszörös sebesség, digi, illegális utasítások.
- **Fájllista:** v1 = egy rögzített fájl (`SID\LNINJA.SID`); később könyvtárlista a menüben (a DOS-hívás még
  ismeretlen).
- A hangminőség és a lejátszás gépideje **nem változik** (ugyanaz a lejátszó); javítani külön lehet.

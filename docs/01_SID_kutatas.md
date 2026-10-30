# 1. lépés: szoftveres SID-ek és a TVC hangja (2026-10-31)

Cél: a C64 SID nagyjából hű utánzása a TVC-n (3,125 MHz Z80, 1 hangcsatorna + 4 bites "DAC").

## A SID, amit utánozni kell
- 3 hang, mindegyik: 16 bites frekvencia (fázisakkumulátor), hullámforma **háromszög / fűrész / négyszög
  (12 bites kitöltéssel, PWM) / zaj** (23 bites LFSR), ADSR burkoló (8 bites szint), gate, sync, ring-mod.
- Közös: multimód szűrő (LP/BP/HP, rezonancia), 4 bites hangerő. A zene 50 Hz-enként írja a regisztereket
  (néhány dal többszörös sebességgel, vagy digit a hangerő-regiszteren keresztül).

## Talált szoftveres SID-ek
| Név | Mi | Hasznunkra |
|---|---|---|
| reSID / reSIDfp (libsidplayfp) | C++, ciklus-pontos, analóg modellel | **túl nehéz**, csak referencia-hangzás a PC-n |
| cRSID (Hermit, CSDb) | kompakt, csak egész számos C | jó PC-s referencia/dumpoló alap; forrás a CSDb-n |
| TinySID (Tammo Hinrichs) | kicsi C, 6510 CPU + 6581, szűrővel | 6510-emu + egyszerű szintézis, PC-oldali eszköznek jó |
| **AVR SID** (Christoph Haberer, sid-arduino-lib) | ATmega8-on valós idejű, 16 kHz | **a legközelebbi minta**: 3 fázisakkumulátor, hullámforma a fázis felső bitjeiből, LFSR zaj, ADSR 1 kHz-en, **szűrő nincs** |
| siddump (Cadaver) | .sid -> regiszter/hang-dump képkockánként | PC-oldali előkészítés |
| **TVC `music.tru`** (Szalontai Béla, 2024) + SidDumpTVCGUI (kks) | már létező TVC SID-lejátszó! | 3 négyszög hang, csak elengedés (release), lásd lent |

Következtetés: valós idejű 6510-emuláció a TVC-n kizárt (a C64 CPU-ja maga is 1 MHz, és a SID-et is
számolni kéne). Az út: **PC-n** a .sid-ből képkockánkénti regiszter-dump, tömörítve; **TVC-n** csak a
szintézis (AVR SID-szerű), megszakításból.

## Mit tud a TVC
- Port `$04`/`$05`: hanggenerátor osztója (12 bit), `$05` bit 5 = hang-IT engedélyezése. Ezt a generátort
  **időzítőnek** használjuk: ~2-8,5 kHz-es megszakítás.
- Port `$06` bit 2-5: hangerő, 16 szint. Ezt **4 bites DAC-ként** írjuk minden mintánál (a GE digi és a
  `music.tru` is így csinálja). Ez a teljes felbontás: a 3 hang összege is csak 16 szinten szólhat.
- Meglévő kódok:
  - **GE digi** (`tvc_units/GE.tru`, `DigiSoundOn`): kész mintát küld ki 2/4/8 kHz-en, 4 kHz-en ~12,6% CPU.
  - **`music.tru`**: 8491 Hz-es IT, 280 ciklus/minta (~77% CPU!), 3 fázisakkumulátor (IX, IY, HL'),
    négyszög = a fázis felső bitje, hangonként 0/20 szint, összeadva -> port 6. 50 Hz-es lejátszó az IT-ben,
    adat: hangjegy-sorszám + kódok (frekv. csúszás, release). Hullámforma, PWM, zaj, attack/decay/sustain: nincs.

## CPU-keret (Z80, 3,125 MHz)
| Mintavétel | ciklus/minta (100%) | becsült szintézis (3 hang + kimenet) | CPU |
|---|---|---|---|
| 4 kHz | 781 | ~200-250 | ~30% |
| 5 kHz | 625 | ~200-250 | ~35-40% |
| 8 kHz | 390 | ~200-250 | ~55-65% |

Becslés hangonként ~50-60 ciklus: `add` a fázishoz (16 bit), a fázis felső bájtja index egy
**táblába, amibe a hullámforma ÉS a burkoló-szint is be van sütve** (`tabla[szint][fázis]`), összeadás.
Szorzás nincs (a Z80-nak nincs szorzója, az AVR-nek van - itt táblával pótoljuk). Mivel a kimenet csak 16
szintű, hangonként 0-5 szint elég, a táblák kicsik maradnak (pl. 16 szint x 64 lépés).

## Hangszer-/minta-alapú ötlet (a te irányod)
- **Egész dal előre renderelve digiként**: 4 kHz x 4 bit = 2 KB/s, 3 perc ~360 KB - nem fér el. Csak rövid
  effekteknek (dob, "digi" a dalban).
- **Hullámtábla (wavetable)**: hangszerenként 1 periódus, burkoló-szintenként előre számolva, a fázis-
  akkumulátor lépteti. Ez lényegében ugyanaz, mint fent - ez a jó irány. A szűrőt is ide lehet "sütni":
  egy szűrt fűrész = másik tábla (nem valós idejű szűrő, de a hangszín közelít).
- Ütősök / zaj: rövid előre renderelt minta vagy LFSR-tábla.

## Javasolt lépések
1. **Hardverteszt** (emulátor + valódi gép): port 6 linearitása, mi a generátor kimenete az IT-üzemben
   (sípol-e a mintavételi frekvencián), mekkora mintavétel szól elfogadhatóan.
2. **PC-eszköz**: .sid -> képkockánkénti regiszterdump (cRSID / siddump / TinySID alapon), majd TVC-formátum.
3. **TVC szintetizátor v1**: 3 hang, fűrész/háromszög/négyszög(PWM)/zaj tábla, ADSR 50 Hz-en, 5 kHz.
4. Hangzás összevetése a reSID-del (PC-n mindkettőt WAV-ba renderelni, a TVC-oldalit egy PC-s modellel).

Nyitott kérdés: a kks-féle SidDumpTVCGUI fellelhető-e (nem találtam a neten).

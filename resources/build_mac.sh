#!/bin/bash
# SIDSoftEMU - Mac build: a kozos mag (TVC_Kozos/mac/build_kozos.sh) + a projekt beallitasai.
#   bash resources/build_mac.sh          (emulatorral)     bash resources/build_mac.sh --no-emu (csak build)
# Uj lemezfajl: a LEMEZ_FAJLOK-ba ES a build.ps1 -Files listajaba is. A sid_tvc/<NEV>/*.STC -> SID_TVC\<NEV>\ magatol kerul fel (LEMEZ2: 2. lemez).
cd "$(dirname "$0")/.." || exit 1
KOZOS="${TVC_KOZOS:-$(cd .. && pwd)/TVC_Kozos}"
[ -f "$KOZOS/mac/build_kozos.sh" ] || { echo "nincs meg a kozos mappa: $KOZOS (TVC_KOZOS=...)"; exit 1; }
NEV=SIDSoftEMU
TRSE_PROJEKT=SIDSoftEMU.trse
# A dalok ~1 MB-ok, egy 720 KB-os lemezre nem ferenek: a LEMEZ2 mappai a 2. lemezre (SIDSOFT2.dsk) kerulnek,
# a program mindkettore. (SD-kartyan / valodi gepen mind egy SID_TVC mappaba mehet.)
LEMEZ2="LNINJA2"
LEMEZ_FAJLOK="'SIDSoftEMU.cas=SIDSOFT.CAS'"
LEMEZ2_FAJLOK="'SIDSoftEMU.cas=SIDSOFT.CAS'"
# termeszetes sorrend a lemezen (SONG1, SONG2, ... SONG10): a fajlkezelo a lemez sorrendjeben listaz
for f in $(ls sid_tvc/*/*.STC 2>/dev/null | sort -V); do
  [ -f "$f" ] || continue
  d="${f#sid_tvc/}"; d="${d%%/*}"
  if [[ " $LEMEZ2 " == *" $d "* ]]; then LEMEZ2_FAJLOK="$LEMEZ2_FAJLOK,'$f=SID_TVC/${f#sid_tvc/}'"
  else LEMEZ_FAJLOK="$LEMEZ_FAJLOK,'$f=SID_TVC/${f#sid_tvc/}'"; fi
done
BETOLTO=SIDSOFT
utana() {
  # memoria-ellenorzes (lasd SIDSoftEMU.ras feje): rezidens vege < $2300, kod vege < $5000, mentes <= 12800 byte
  python3 - <<'PY' || return 1
import re,sys
s={m.group(2):int(m.group(1),16) for m in re.finditer(r'al\s+\$([0-9a-f]+)\s+\.(\S+)',open('SIDSoftEMU.sym').read())}
rez,kod=s['RezVege'],s['EndBlock19ef']; ment=kod-rez+s['end_incbin_Logo_Data']-s['Font16_Data']
print('memoria: RezVege $%04X (< $2300), kod vege $%04X (< $5000), mentes %d byte (<= 12288)'%(rez,kod,ment))
if rez>=0x2300 or kod>=0x5000 or ment>12288: print('HIBA: memoria-hatar tullepve!'); sys.exit(1)
PY
  pwsh -NoProfile -Command "& ./resources/make_dsk.ps1 -Out 'SIDSOFT2.dsk' -Template '$TEMPLATE' -Files @($LEMEZ2_FAJLOK) | Select-Object -Last 1"
}
source "$KOZOS/mac/build_kozos.sh"

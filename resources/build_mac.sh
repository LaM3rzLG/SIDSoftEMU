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
  pwsh -NoProfile -Command "& ./resources/make_dsk.ps1 -Out 'SIDSOFT2.dsk' -Template '$TEMPLATE' -Files @($LEMEZ2_FAJLOK) | Select-Object -Last 1"
}
source "$KOZOS/mac/build_kozos.sh"

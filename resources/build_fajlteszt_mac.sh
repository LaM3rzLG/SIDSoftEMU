#!/bin/bash
# FajlTeszt - a fajlkezelo probaprogramja (Mac build): bash resources/build_fajlteszt_mac.sh [--no-emu]
# Lemez: FajlTeszt.dsk = FAJLTESZ.CAS + SID_TVC\LNINJA1, LNINJA3 (a TVC-n: load"FAJLTESZ")
cd "$(dirname "$0")/.." || exit 1
KOZOS="${TVC_KOZOS:-$(cd .. && pwd)/TVC_Kozos}"
[ -f "$KOZOS/mac/build_kozos.sh" ] || { echo "nincs meg a kozos mappa: $KOZOS (TVC_KOZOS=...)"; exit 1; }
NEV=FajlTeszt
TRSE_PROJEKT=SIDSoftEMU.trse
LEMEZ_FAJLOK="'FajlTeszt.cas=FAJLTESZ.CAS'"
for f in $(ls sid_tvc/LNINJA1/*.STC sid_tvc/LNINJA3/*.STC 2>/dev/null | sort -V); do
  LEMEZ_FAJLOK="$LEMEZ_FAJLOK,'$f=SID_TVC/${f#sid_tvc/}'"
done
BETOLTO=FAJLTESZ
source "$KOZOS/mac/build_kozos.sh"

#!/bin/bash
# FajlTeszt16 - a fajlkezelo 16 szinu probaprogramja (Mac build): bash resources/build_fajlteszt16_mac.sh [--no-emu]
# Lemez: FajlTeszt16.dsk = FAJLT16.CAS + SID_TVC\LNINJA1, LNINJA3 (a TVC-n: load"FAJLT16")
cd "$(dirname "$0")/.." || exit 1
KOZOS="${TVC_KOZOS:-$(cd .. && pwd)/TVC_Kozos}"
[ -f "$KOZOS/mac/build_kozos.sh" ] || { echo "nincs meg a kozos mappa: $KOZOS (TVC_KOZOS=...)"; exit 1; }
NEV=FajlTeszt16
TRSE_PROJEKT=SIDSoftEMU.trse
LEMEZ_FAJLOK="'FajlTeszt16.cas=FAJLT16.CAS'"
for f in $(ls sid_tvc/LNINJA1/*.STC sid_tvc/LNINJA3/*.STC 2>/dev/null | sort -V); do
  LEMEZ_FAJLOK="$LEMEZ_FAJLOK,'$f=SID_TVC/${f#sid_tvc/}'"
done
BETOLTO=FAJLT16
source "$KOZOS/mac/build_kozos.sh"

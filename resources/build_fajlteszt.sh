#!/bin/bash
# FajlTeszt (lemezmuveletek proba) - Mac build: bash resources/build_fajlteszt.sh [--no-emu]; a TVC-n: load"FAJLTST"
cd "$(dirname "$0")/.." || exit 1
KOZOS="${TVC_KOZOS:-$(cd .. && pwd)/TVC_Kozos}"
NEV=FajlTeszt
TRSE_PROJEKT=SIDSoftEMU.trse
LEMEZ_FAJLOK="'FajlTeszt.cas=FAJLTST.CAS'"
for f in sid/*.SID; do [ -f "$f" ] && LEMEZ_FAJLOK="$LEMEZ_FAJLOK,'$f=SID/$(basename "$f")'"; done
for f in sid_tvc/*/*.STC; do [ -f "$f" ] && LEMEZ_FAJLOK="$LEMEZ_FAJLOK,'$f=SID_TVC/${f#sid_tvc/}'"; done
BETOLTO=FAJLTST
source "$KOZOS/mac/build_kozos.sh"

#!/bin/bash
# Ir16Teszt - a 16 szinu aranyos kiiro (Ir16) probaprogramja (Mac build): bash resources/build_ir16teszt_mac.sh [--no-emu]
# Lemez: Ir16Teszt.dsk = IR16TESZ.CAS (a TVC-n: load"IR16TESZ")
cd "$(dirname "$0")/.." || exit 1
KOZOS="${TVC_KOZOS:-$(cd .. && pwd)/TVC_Kozos}"
[ -f "$KOZOS/mac/build_kozos.sh" ] || { echo "nincs meg a kozos mappa: $KOZOS (TVC_KOZOS=...)"; exit 1; }
NEV=Ir16Teszt
TRSE_PROJEKT=SIDSoftEMU.trse
LEMEZ_FAJLOK="'Ir16Teszt.cas=IR16TESZ.CAS'"
BETOLTO=IR16TESZ
source "$KOZOS/mac/build_kozos.sh"

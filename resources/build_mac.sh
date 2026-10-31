#!/bin/bash
# SIDSoftEMU - Mac build: a kozos mag (TVC_Kozos/mac/build_kozos.sh) + a projekt beallitasai.
#   bash resources/build_mac.sh          (emulatorral)     bash resources/build_mac.sh --no-emu (csak build)
# Uj lemezfajl: a LEMEZ_FAJLOK-ba ES a build.ps1 -Files listajaba is. A dalok (dalok/DAL*.BIN) maguktol kerulnek fel.
cd "$(dirname "$0")/.." || exit 1
KOZOS="${TVC_KOZOS:-$(cd .. && pwd)/TVC_Kozos}"
[ -f "$KOZOS/mac/build_kozos.sh" ] || { echo "nincs meg a kozos mappa: $KOZOS (TVC_KOZOS=...)"; exit 1; }
NEV=SIDSoftEMU
TRSE_PROJEKT=SIDSoftEMU.trse
LEMEZ_FAJLOK="'SIDSoftEMU.cas=SIDSOFT.CAS'"
for f in dalok/DAL*.BIN; do [ -f "$f" ] && LEMEZ_FAJLOK="$LEMEZ_FAJLOK,'$f=$(basename "$f")'"; done
BETOLTO=SIDSOFT
source "$KOZOS/mac/build_kozos.sh"

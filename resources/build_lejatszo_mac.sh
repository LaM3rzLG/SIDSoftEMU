#!/bin/bash
# SIDLejatszo (az onallo lejatszo + minta) - Mac build:  bash resources/build_lejatszo_mac.sh [--no-emu]
# Lemezkep: SIDLejatszo.dsk, rajta SIDLEJ.CAS (load"SIDLEJ").
cd "$(dirname "$0")/.." || exit 1
KOZOS="${TVC_KOZOS:-$(cd .. && pwd)/TVC_Kozos}"
NEV=SIDLejatszo
TRSE_PROJEKT=SIDLejatszo.trse
LEMEZ_FAJLOK="'SIDLejatszo.cas=SIDLEJ.CAS'"
BETOLTO=SIDLEJ
utana() {
  # a lejatszo kodja es valtozoi a dal ala ($2300) kell, hogy essenek
  python3 - <<'PY' || return 1
import re,sys
s={m.group(2):int(m.group(1),16) for m in re.finditer(r'al\s+\$([0-9a-f]+)\s+\.(\S+)',open('SIDLejatszo.sym').read())}
v=s['EndBlock19ef']
print('a program kodja vege: $%04X (< $2300)'%v)
if v>=0x2300: print('HIBA: a lejatszo belelog a dalba!'); sys.exit(1)
PY
}
source "$KOZOS/mac/build_kozos.sh"

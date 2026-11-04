#!/bin/bash
# SIDLEJATSZO (az onallo lejatszo + minta) - Mac build:  bash resources/build_lejatszo_mac.sh
# A SIDLEJATSZO mappaban fordit (az onallo, mas is hasznalhatja), ellenorzi, hogy a kod a $2300 ala esik,
# es lemezkepet ir: SIDLEJATSZO/SIDLejatszo.dsk, rajta SIDLEJ.CAS (load"SIDLEJ").
cd "$(dirname "$0")/.." || exit 1
ROOT="$(pwd)"
KOZOS="${TVC_KOZOS:-$(cd .. && pwd)/TVC_Kozos}"
D="$ROOT/SIDLEJATSZO"
LOG="${TMPDIR:-/tmp}/trse_out_sidlejatszo.txt"
cd "$D" || exit 1
rm -f SIDLejatszo.cas
/Applications/trse.app/Contents/MacOS/trse -cli op=project settings="$KOZOS/mac/trse_mac.ini" project="$D/SIDLejatszo.trse" \
  input_file="$D/SIDLejatszo.ras" assemble=yes > "$LOG" 2>&1
if [ ! -f SIDLejatszo.cas ] || grep -v '^Warning' "$LOG" | grep -q -i -E 'error|fatal'; then
  echo "FORDITASI HIBA:"; grep -v '^Warning' "$LOG" | tail -15; exit 1
fi
python3 - <<'PY' || exit 1
import re,sys
s={m.group(2):int(m.group(1),16) for m in re.finditer(r'al\s+\$([0-9a-f]+)\s+\.(\S+)',open('SIDLejatszo.sym').read())}
v=s['EndBlock19ef']
print('a program kodja vege: $%04X (< $2300)'%v)
if v>=0x2300: print('HIBA: a lejatszo belelog a dalba!'); sys.exit(1)
PY
cd "$ROOT" && pwsh -NoProfile -Command "& ./resources/make_dsk.ps1 -Out 'SIDLEJATSZO/SIDLejatszo.dsk' -Template '$KOZOS/mac/dsk_sablon.dsk' -Files @('SIDLEJATSZO/SIDLejatszo.cas=SIDLEJ.CAS') | Select-Object -Last 1"

#!/bin/bash
# SIDLEJATSZO (a SID unit + a minta: SIDPelda) - Mac build:  bash resources/build_lejatszo_mac.sh
# A SIDLEJATSZO mappaban fordit (az onallo, mas is hasznalhatja), ellenorzi, hogy a kod a $2300 ala esik,
# es lemezkepet ir: SIDLEJATSZO/SIDPelda.dsk, rajta SIDPELDA.CAS (load"SIDPELDA").
cd "$(dirname "$0")/.." || exit 1
ROOT="$(pwd)"
KOZOS="${TVC_KOZOS:-$(cd .. && pwd)/TVC_Kozos}"
D="$ROOT/SIDLEJATSZO"
LOG="${TMPDIR:-/tmp}/trse_out_sidlejatszo.txt"
cd "$D" || exit 1
rm -f SIDPelda.cas
/Applications/trse.app/Contents/MacOS/trse -cli op=project settings="$KOZOS/mac/trse_mac.ini" project="$D/SIDPelda.trse" \
  input_file="$D/SIDPelda.ras" assemble=yes > "$LOG" 2>&1
if [ ! -f SIDPelda.cas ] || grep -v '^Warning' "$LOG" | grep -q -i -E 'error|fatal'; then
  echo "FORDITASI HIBA:"; grep -v '^Warning' "$LOG" | tail -15; exit 1
fi
python3 - <<'PY' || exit 1
import re,sys
s={m.group(2):int(m.group(1),16) for m in re.finditer(r'al\s+\$([0-9a-f]+)\s+\.(\S+)',open('SIDPelda.sym').read())}
v=s['EndBlock19ef']
print('a program kodja vege: $%04X (< $5000, a minta paletta)'%v)
if v>=0x5000: print("HIBA: a kod belelog a minta adataiba!"); sys.exit(1)
PY
cd "$ROOT" && pwsh -NoProfile -Command "& ./resources/make_dsk.ps1 -Out 'SIDLEJATSZO/SIDPelda.dsk' -Template '$KOZOS/mac/dsk_sablon.dsk' -Files @('SIDLEJATSZO/SIDPelda.cas=SIDPELDA.CAS') | Select-Object -Last 1"

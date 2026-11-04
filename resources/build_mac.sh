#!/bin/bash
# SIDSoftEMU - Mac build: a kozos mag (TVC_Kozos/mac/build_kozos.sh) + a projekt beallitasai.
#   bash resources/build_mac.sh          (emulatorral)     bash resources/build_mac.sh --no-emu (csak build)
# Uj lemezfajl: a lemez_lista-ba ES a build.ps1-be is. A sid_tvc/<NEV>/*.STC -> SID_TVC\<NEV>\ magatol kerul fel, amig fer.
cd "$(dirname "$0")/.." || exit 1
KOZOS="${TVC_KOZOS:-$(cd .. && pwd)/TVC_Kozos}"
[ -f "$KOZOS/mac/build_kozos.sh" ] || { echo "nincs meg a kozos mappa: $KOZOS (TVC_KOZOS=...)"; exit 1; }
NEV=SIDSoftEMU
TRSE_PROJEKT=SIDSoftEMU.trse
# Egy lemez (SIDTVC.dsk, 720 KB = 713 klaszter): SIDTVC.CAS + a dalok termeszetes sorrendben (sort -V), amig ferenek;
# ami nem fer, kimarad (kiirja). A lista a forditas utan kesz (a .cas merete kell hozza) - lasd lemez_lista. Az SD_KARTYA-ba minden dal.
LEMEZ_FAJLOK="'SIDSoftEMU.cas=SIDTVC.CAS'"
lemez_lista() {
  local szabad=$(( 713 - ( $(wc -c < SIDSoftEMU.cas) + 1023 ) / 1024 - 1 )) kimaradt="" d k f elozo=""   # -1: SID_TVC
  LEMEZ_FAJLOK="'SIDSoftEMU.cas=SIDTVC.CAS'"
  for f in $(ls sid_tvc/*/*.STC 2>/dev/null | sort -V); do
    d="${f#sid_tvc/}"; d="${d%%/*}"
    k=$(( ( $(wc -c < "$f") + 1023 ) / 1024 ))
    [ "$d" != "$elozo" ] && k=$((k + 1))          # az uj konyvtar is egy klaszter
    if [ $k -le $szabad ]; then
      szabad=$((szabad - k)); elozo="$d"
      LEMEZ_FAJLOK="$LEMEZ_FAJLOK,'$f=SID_TVC/${f#sid_tvc/}'"
    else kimaradt="$kimaradt ${f#sid_tvc/}"; fi
  done
  [ -n "$kimaradt" ] && echo "a lemezre nem fert (csak az SD_KARTYA-ban):$kimaradt"
}
BETOLTO=SIDTVC
utana() {
  # memoria-ellenorzes (lasd SIDSoftEMU.ras feje): rezidens vege < $2300, kod vege < $5000, mentes <= 12800 byte
  python3 - <<'PY' || return 1
import re,sys
s={m.group(2):int(m.group(1),16) for m in re.finditer(r'al\s+\$([0-9a-f]+)\s+\.(\S+)',open('SIDSoftEMU.sym').read())}
rez,kod=s['RezVege'],s['EndBlock19ef']; ment=kod-rez+s['end_incbin_Logo_Data']-s['Font16_Data']
print('memoria: RezVege $%04X (< $2300), kod vege $%04X (< $5000), mentes %d byte (<= 13312)'%(rez,kod,ment))
if rez>=0x2300 or kod>=0x5000 or ment>13312: print('HIBA: memoria-hatar tullepve!'); sys.exit(1)
PY
  # SD-kartya (NanoSD, TVC256k++): SD_KARTYA/ = SIDTVC.CAS + SID_TVC/<NEV>/SONGn.STC (minden dal; termeszetes sorrendben masolva)
  rm -rf SD_KARTYA && mkdir -p SD_KARTYA/SID_TVC && cp SIDSoftEMU.cas SD_KARTYA/SIDTVC.CAS || return 1
  for f in $(ls sid_tvc/*/*.STC 2>/dev/null | sort -V); do d="${f#sid_tvc/}"; mkdir -p "SD_KARTYA/SID_TVC/${d%%/*}"; cp "$f" "SD_KARTYA/SID_TVC/$d"; done
  echo "SD_KARTYA kesz: $(ls SD_KARTYA/SID_TVC/*/*.STC | wc -l | tr -d ' ') dal"
  lemez_lista
  # a kiadasi lemezkep: SIDTVC.dsk (a kozos build utana ugyanezt SIDSoftEMU.dsk neven is megirja - azt inditja az emulator)
  pwsh -NoProfile -Command "& ./resources/make_dsk.ps1 -Out 'SIDTVC.dsk' -Template '$TEMPLATE' -Files @($LEMEZ_FAJLOK) | Select-Object -Last 1"
}
source "$KOZOS/mac/build_kozos.sh"

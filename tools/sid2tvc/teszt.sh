#!/bin/sh
# A lefordított sid2tvc kimenete bájtra egyezik-e a sid_tvc/ mappában lévő dalokkal.
#   sh tools/sid2tvc/teszt.sh <program> [gyors]     (a repó gyökeréből)
# "gyors" = csak 3 dal (emulált processzoron, qemu alatt)
BIN=$1; MOD=$2; KI=${TMPDIR:-/tmp}/sid2tvc_teszt_$$; HIBA=0
rm -rf "$KI"
if [ "$MOD" = gyors ]; then
  $BIN -q -s 1 -n LNINJA1 -o "$KI" sid/Last_Ninja_1.sid
  $BIN -q -s 5 -n LNINJA1 -o "$KI" sid/Last_Ninja_1.sid
  $BIN -q -s 3 -n LNINJA2 -o "$KI" sid/Last_Ninja_2.sid
else
  $BIN -q -a -n LNINJA1 -o "$KI" sid/Last_Ninja_1.sid
  $BIN -q -a -n LNINJA2 -o "$KI" sid/Last_Ninja_2.sid   # a 12. dal nem fér el: hibát ír, az rendben van
fi
N=0
for f in "$KI"/*/*.STC; do
  r=sid_tvc/$(basename "$(dirname "$f")")/$(basename "$f")
  N=$((N+1))
  if cmp -s "$f" "$r"; then echo "ok    $r"; else echo "ELTER $r"; HIBA=1; fi
done
[ "$N" -gt 0 ] || { echo "nem keszult dal"; HIBA=1; }
rm -rf "$KI"
[ $HIBA = 0 ] && echo "MINDEN EGYEZIK ($N dal)"
exit $HIBA

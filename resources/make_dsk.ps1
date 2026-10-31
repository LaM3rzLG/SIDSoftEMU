# FAT12 lemezkep (720 KB, 2 oldalas DD, 80 x 9 x 512 bajt = mint a Lemmings.dsk) keszitese fajlokkal - WinTVC + HBF kartya (hbf.rom) hasznalja.
# A fajlok 8.3-as nevvel kerulnek fel (nagybetusen); "MAPPA/AL/FAJL.EXT" celnev = (al)konyvtarba, tetszoleges melyseg. Az ELSO fajl az, amit a WinTVC "autostart" (LOAD"*") betolt -> a jatek .cas-a legyen elol.
# Hasznalat: powershell -File resources\make_dsk.ps1                  (alapertelmezett: SIDSoftEMU.cas -> SIDSOFT.CAS)
#            powershell -File resources\make_dsk.ps1 -Out X.dsk -Files @("a.cas=A.CAS","b.bin=B.BIN")
param(
  [string]$Out = "SIDSoftEMU.dsk",
  [string[]]$Files = @("SIDSoftEMU.cas=SIDSOFT.CAS"),
  [string]$Template   # mukodo lemezkep: ebbol a BOOT SZEKTORT (BPB + boot kod) vesszuk at, a tobbit kiuritjuk; "" = sajat, tiszta boot szektor;
                      # megadas nelkul: $DskSablon a kozos.ps1-bol (gepenkent mas: Windows C:\TVC\Cas\..., Mac ~/Downloads/TVC/...)
)
. (Join-Path $PSScriptRoot 'kozos.ps1')
if (-not $PSBoundParameters.ContainsKey('Template')) { $Template = $DskSablon }
$root = $Gyoker
$BPS = 512; $SPC = 2; $RES = 1; $NFAT = 2; $ROOTENT = 112; $TOTSEC = 1440; $SPF = 3; $SPT = 9; $HEADS = 2
$img = New-Object byte[] ($TOTSEC * $BPS)
# --- boot szektor (BPB a Lemmings.dsk-val azonos) ---
$boot = @(0xEB,0x3C,0x90) + [Text.Encoding]::ASCII.GetBytes("TVCDISK ")
[Array]::Copy([byte[]]$boot, 0, $img, 0, $boot.Length)
[BitConverter]::GetBytes([uint16]$BPS).CopyTo($img, 11)
$img[13] = $SPC
[BitConverter]::GetBytes([uint16]$RES).CopyTo($img, 14)
$img[16] = $NFAT
[BitConverter]::GetBytes([uint16]$ROOTENT).CopyTo($img, 17)
[BitConverter]::GetBytes([uint16]$TOTSEC).CopyTo($img, 19)
$img[21] = 0xF9
[BitConverter]::GetBytes([uint16]$SPF).CopyTo($img, 22)
[BitConverter]::GetBytes([uint16]$SPT).CopyTo($img, 24)
[BitConverter]::GetBytes([uint16]$HEADS).CopyTo($img, 26)
$img[510] = 0x55; $img[511] = 0xAA
if ($Template -ne "" -and (Test-Path $Template)) {
  $tpl = [IO.File]::ReadAllBytes($Template)
  [Array]::Copy($tpl, 0, $img, 0, 512)   # boot szektor (BPB: 512 B/szektor, 2 szektor/klaszter, 2 FAT, 112 gyokerbejegyzes, 1440 szektor, F9, 3 szektor/FAT, 9 szektor/sav, 2 fej)
  "boot szektor a sablonbol: $Template"
}
# --- elrendezes ---
$fat1 = $RES * $BPS
$rootDir = ($RES + $NFAT * $SPF) * $BPS
$rootSecs = [math]::Ceiling($ROOTENT * 32 / $BPS)
$dataStart = ($RES + $NFAT * $SPF + $rootSecs) * $BPS
$clSize = $SPC * $BPS
$fat = New-Object byte[] ($SPF * $BPS)
$fat[0] = 0xF9; $fat[1] = 0xFF; $fat[2] = 0xFF
function Set-Fat([int]$n, [int]$v) {
  $o = [int][math]::Floor($n * 3 / 2)
  if (($n % 2) -eq 0) { $fat[$o] = $v -band 0xFF; $fat[$o+1] = ($fat[$o+1] -band 0xF0) -bor (($v -shr 8) -band 0x0F) }
  else { $fat[$o] = ($fat[$o] -band 0x0F) -bor (($v -shl 4) -band 0xF0); $fat[$o+1] = ($v -shr 4) -band 0xFF }
}
$next = 2; $entry = 0
$now = Get-Date
$dosDate = [uint16]((($now.Year - 1980) -shl 9) -bor ($now.Month -shl 5) -bor $now.Day)
$dosTime = [uint16](($now.Hour -shl 11) -bor ($now.Minute -shl 5) -bor [int]($now.Second / 2))
function To83([string]$nev) {
  $p = $nev.Split('.')
  $e = ""; if ($p.Length -gt 1) { $e = $p[1] }
  return $p[0].ToUpper().PadRight(8).Substring(0,8) + $e.ToUpper().PadRight(3).Substring(0,3)
}
# egy 32 bajtos konyvtarbejegyzes a $buf tombbe, $off-tol
function Write-Entry([byte[]]$buf, [int]$off, [string]$n83, [byte]$attr, [int]$first, [int]$size) {
  [Text.Encoding]::ASCII.GetBytes($n83).CopyTo($buf, $off)
  $buf[$off + 11] = $attr   # fajl: 00, mint a Lemmings.dsk-ben (a 0x20 archiv jelzot a TVC DOS LOAD"*" nem fogadta el: 236-os hiba); mappa: 10
  [BitConverter]::GetBytes($dosTime).CopyTo($buf, $off + 22)
  [BitConverter]::GetBytes($dosDate).CopyTo($buf, $off + 24)
  [BitConverter]::GetBytes([uint16]$first).CopyTo($buf, $off + 26)
  [BitConverter]::GetBytes([uint32]$size).CopyTo($buf, $off + 28)
}
# klaszterlanc foglalasa + adat beirasa; visszaad: az elso klaszter
function Add-Data([byte[]]$data) {
  $ncl = [math]::Max(1, [math]::Ceiling($data.Length / $clSize))
  $first = $script:next
  for ($i = 0; $i -lt $ncl; $i++) {
    $c = $first + $i
    Set-Fat $c ($(if ($i -eq $ncl - 1) { 0xFFF } else { $c + 1 }))
    $len = [math]::Min($clSize, $data.Length - $i * $clSize)
    if ($len -gt 0) { [Array]::Copy($data, $i * $clSize, $img, $dataStart + ($c - 2) * $clSize, $len) }
  }
  $script:next += $ncl
  return $first
}
# a fajlok fa szerkezetbe (cel: "MAPPA/AL/FAJL.EXT", "/" vagy "\" elvalasztoval; a mappak a gyokerbol nyilnak)
function New-Node { return @{ fajlok = @(); mappak = [ordered]@{} } }
$gyoker = New-Node
foreach ($spec in $Files) {
  $src, $dst = $spec.Split('=')
  $reszek = $dst.Replace('\', '/').Split('/')
  $n = $gyoker
  for ($i = 0; $i -lt $reszek.Length - 1; $i++) {
    $m = $reszek[$i].ToUpper()
    if (-not $n.mappak.Contains($m)) { $n.mappak[$m] = New-Node }
    $n = $n.mappak[$m]
  }
  $n.fajlok += ,@($src, $reszek[$reszek.Length - 1], $dst)
}
function Read-Src([string]$src, [string]$dst) {
  $data = [IO.File]::ReadAllBytes((Join-Path $root $src))
  # A TRSE .cas fejleceben a blokkszam (2-3. bajt) es az utolso blokk hossza (4. bajt) ROSSZ (164 bajttal rovidebb fajlt mond);
  # a mukodo Lemmings-fajlokban: blokkszam = felkerekitve (fajlhossz - 128) / 128, utolso blokk = (fajlhossz - 128) mod 128.
  # A lemezre kerulo masolatban kijavitjuk (az eredeti .cas nem valtozik).
  if ($dst -match '\.cas$' -and $data.Length -gt 144 -and $data[0] -eq 0x11) {
    $h = $data.Length - 128
    $blk = [int][math]::Ceiling($h / 128)
    $data[2] = $blk -band 0xFF; $data[3] = ($blk -shr 8) -band 0xFF; $data[4] = $h % 128
    "  CAS-fejlec javitva: {0} blokk, az utolsoban {1} bajt" -f $blk, ($h % 128) | Write-Host
  }
  return ,$data
}
# egy alkonyvtar (rekurzivan); visszaad: az elso klasztere
function Build-Dir($node, [int]$parentFirst, [string]$ut) {
  $db = $node.fajlok.Count + $node.mappak.Count + 2
  $dirLen = [math]::Max(1, [math]::Ceiling(($db * 32) / $clSize)) * $clSize
  $dir = New-Object byte[] $dirLen
  $dirFirst = Add-Data $dir
  Write-Entry $dir 0 ".          " 0x10 $dirFirst 0
  Write-Entry $dir 32 "..         " 0x10 $parentFirst 0
  $k = 2
  foreach ($gf in $node.fajlok) {
    $data = Read-Src $gf[0] $gf[1]
    $n83 = To83 $gf[1]
    $first = Add-Data $data
    Write-Entry $dir ($k * 32) $n83 0 $first $data.Length
    "{0} -> {1}{2}: {3} bajt (elso klaszter: {4})" -f $gf[0], $ut, $n83, $data.Length, $first | Write-Host
    $k++
  }
  foreach ($m in $node.mappak.Keys) {
    $sub = Build-Dir $node.mappak[$m] $dirFirst ($ut + $m + '\')
    Write-Entry $dir ($k * 32) (To83 $m) 0x10 $sub 0
    $k++
  }
  for ($i = 0; $i -lt $dirLen / $clSize; $i++) {
    [Array]::Copy($dir, $i * $clSize, $img, $dataStart + ($dirFirst + $i - 2) * $clSize, $clSize)
  }
  return $dirFirst
}
foreach ($gf in $gyoker.fajlok) {
  $data = Read-Src $gf[0] $gf[1]
  $n83 = To83 $gf[1]
  $first = Add-Data $data
  Write-Entry $img ($rootDir + $entry * 32) $n83 0 $first $data.Length
  "{0} -> {1}: {2} bajt (elso klaszter: {3})" -f $gf[0], $n83, $data.Length, $first
  $entry++
}
foreach ($m in $gyoker.mappak.Keys) {
  $sub = Build-Dir $gyoker.mappak[$m] 0 ('\' + $m + '\')
  Write-Entry $img ($rootDir + $entry * 32) (To83 $m) 0x10 $sub 0
  $entry++
}
for ($f = 0; $f -lt $NFAT; $f++) { $fat.CopyTo($img, $fat1 + $f * $SPF * $BPS) }
$outPath = Join-Path $root $Out
[IO.File]::WriteAllBytes($outPath, $img)
"{0} kesz ({1} bajt), szabad klaszter: {2}" -f $outPath, $img.Length, ((($TOTSEC * $BPS - $dataStart) / $clSize) - ($next - 2))

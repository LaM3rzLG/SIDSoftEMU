# FAT12 lemezkep (720 KB, 2 oldalas DD, 80 x 9 x 512 bajt = mint a Lemmings.dsk) keszitese fajlokkal - WinTVC + HBF kartya (hbf.rom) hasznalja.
# A fajlok 8.3-as nevvel kerulnek fel (nagybetusen). Az ELSO fajl az, amit a WinTVC "autostart" (LOAD"*") betolt -> a jatek .cas-a legyen elol.
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
foreach ($spec in $Files) {
  $src, $dst = $spec.Split('=')
  $data = [IO.File]::ReadAllBytes((Join-Path $root $src))
  # A TRSE .cas fejleceben a blokkszam (2-3. bajt) es az utolso blokk hossza (4. bajt) ROSSZ (164 bajttal rovidebb fajlt mond);
  # a mukodo Lemmings-fajlokban: blokkszam = felkerekitve (fajlhossz - 128) / 128, utolso blokk = (fajlhossz - 128) mod 128.
  # A lemezre kerulo masolatban kijavitjuk (az eredeti .cas nem valtozik).
  if ($dst -match '\.cas$' -and $data.Length -gt 144 -and $data[0] -eq 0x11) {
    $h = $data.Length - 128
    $blk = [int][math]::Ceiling($h / 128)
    $data[2] = $blk -band 0xFF; $data[3] = ($blk -shr 8) -band 0xFF; $data[4] = $h % 128
    "  CAS-fejlec javitva: {0} blokk, az utolsoban {1} bajt" -f $blk, ($h % 128)
  }
  $name, $ext = $dst.Split('.')
  $n83 = $name.ToUpper().PadRight(8).Substring(0,8) + $ext.ToUpper().PadRight(3).Substring(0,3)
  $ncl = [math]::Ceiling($data.Length / $clSize)
  $first = $next
  for ($i = 0; $i -lt $ncl; $i++) {
    $c = $first + $i
    Set-Fat $c ($(if ($i -eq $ncl - 1) { 0xFFF } else { $c + 1 }))
    $len = [math]::Min($clSize, $data.Length - $i * $clSize)
    [Array]::Copy($data, $i * $clSize, $img, $dataStart + ($c - 2) * $clSize, $len)
  }
  $next += $ncl
  $d = $rootDir + $entry * 32
  [Text.Encoding]::ASCII.GetBytes($n83).CopyTo($img, $d)
  $img[$d + 11] = 0x00   # attributum: 00, mint a Lemmings.dsk-ben (a 0x20 archiv jelzot a TVC DOS LOAD"*" nem fogadta el: 236-os hiba)
  [BitConverter]::GetBytes($dosTime).CopyTo($img, $d + 22)
  [BitConverter]::GetBytes($dosDate).CopyTo($img, $d + 24)
  [BitConverter]::GetBytes([uint16]$first).CopyTo($img, $d + 26)
  [BitConverter]::GetBytes([uint32]$data.Length).CopyTo($img, $d + 28)
  "{0} -> {1}: {2} bajt, {3} klaszter (elso: {4})" -f $src,$n83,$data.Length,$ncl,$first
  $entry++
}
for ($f = 0; $f -lt $NFAT; $f++) { $fat.CopyTo($img, $fat1 + $f * $SPF * $BPS) }
$outPath = Join-Path $root $Out
[IO.File]::WriteAllBytes($outPath, $img)
"{0} kesz ({1} bajt), szabad klaszter: {2}" -f $outPath, $img.Length, ((($TOTSEC * $BPS - $dataStart) / $clSize) - ($next - 2))

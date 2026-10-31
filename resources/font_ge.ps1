# resources\font.bin (1 bites, aranyos font: 1 byte magassag (bit7 = jelzo) + 109 byte szelesseg + kep: magassag x 109 byte,
# kodok 32..122 + 123..140 = ekezetes AEIOOOUUU aeiooouuu) -> resources\font_ge.bin a GE::WriteText-hez (GRAPHICS4, 1-es szin).
# A GE sorrendje: 32..90, 97..122, 9 nagy + 9 kis ekezetes; a vegere 2 kulon jel: \ (kod 153) es _ (kod 154),
# mert a GE a 91..96 kodokat nem kezeli. Karakterenkent 2 byte (8 px, balra igazitva), 105 karakter -> 210 byte szeles.
# A TVC-n: GE::InitCharSet(#Font, 210, 2, magassag)
param([string]$In = (Join-Path $PSScriptRoot "font.bin"), [string]$Out = (Join-Path $PSScriptRoot "font_ge.bin"))
$d = [IO.File]::ReadAllBytes($In)
$h = $d[0] -band 0x7F; $n = 109; $kep = 1 + $n
$sorrend = @()
for ($c = 32; $c -le 90; $c++) { $sorrend += $c }
for ($c = 97; $c -le 122; $c++) { $sorrend += $c }
for ($c = 123; $c -le 140; $c++) { $sorrend += $c }
$sorrend += 92; $sorrend += 95
$w = $sorrend.Count * 2
$o = New-Object byte[] ($w * $h)
for ($y = 0; $y -lt $h; $y++) {
  for ($i = 0; $i -lt $sorrend.Count; $i++) {
    $b = $d[$kep + $y * $n + ($sorrend[$i] - 32)]
    $o[$y * $w + $i * 2] = [byte]($b -band 0xF0)
    $o[$y * $w + $i * 2 + 1] = [byte](($b -shl 4) -band 0xF0)
  }
}
[IO.File]::WriteAllBytes($Out, $o)
"$Out : $($o.Length) byte; GE::InitCharSet(#Font, $w, 2, $h)"

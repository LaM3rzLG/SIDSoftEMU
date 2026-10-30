# Kozos segedfajl a resources\*.ps1 szkriptekhez - Windows PowerShell 5.1 (Windows) ES pwsh 7 (Mac) alatt is fut.
# Betoltes a szkript elejen (a param blokk utan):   . (Join-Path $PSScriptRoot 'kozos.ps1')
# Ad:  $Gyoker   - a projekt gyokere (a resources mappa szuloje)
#      $Mac      - $true Macen, $false Windowson
#      $Temp     - ideiglenes mappa (a $env:TEMP Macen nincs)
#      $PsExe    - az eppen futo PowerShell: & $PsExe -NoProfile -File (Ut 'resources/x.ps1')  (a kilepesi kod igy jo)
#      Ut 'resources/x/y.bin'  - a gyokerhez relativ utvonal -> teljes utvonal (a / es a \ is jo, mindket gepen)
#      $TrseExe, $DskSablon, $Bongeszo - gepfuggo utak (alapertek gepenkent; felulirhato: resources\gep_beallitas.ps1, nincs a gitben)
#      Bmp-Olvas / Bmp-Pixel / Bmp-Ir  - BMP olvasas/iras System.Drawing nelkul (az Macen nincs)
# A fajl CSAK ASCII karaktert tartalmazzon (a PowerShell 5.1 BOM nelkul ANSI-kent olvassa).

$Gyoker = Split-Path $PSScriptRoot -Parent
$Mac = ($PSVersionTable.PSVersion.Major -ge 6) -and $IsMacOS
$Temp = [IO.Path]::GetTempPath()
$PsExe = (Get-Process -Id $PID).Path   # az eppen futo PowerShell (Windows: powershell.exe, Mac: pwsh) - gyerek-szkript hivasahoz

function Ut([string]$Rel) {
  $sep = [string][IO.Path]::DirectorySeparatorChar
  return [IO.Path]::Combine($Gyoker, ($Rel -replace '[\\/]', $sep))
}

# --- gepfuggo utak (alapertekek) ---
if ($Mac) {
  $TrseExe   = '/Applications/trse.app/Contents/MacOS/trse'
  $DskSablon = Join-Path $HOME 'Downloads/TVC/TVC_CEmu/roms/Lemmings.dsk'
  $Bongeszo  = @('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                 '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge') | Where-Object { Test-Path $_ } | Select-Object -First 1
} else {
  $TrseExe   = 'C:\TVC\TRSE_Nightly\trse.exe'
  $DskSablon = 'C:\TVC\Cas\2025\Lemmings\Lemmings.dsk'
  $WinTvcExe = 'C:\TVC\Emu\WinTVCx64.exe'   # a build.ps1 inditja; a hbf.rom az exe mappajaban van -> a HBF automatikusan csatolodik
  $Bongeszo  = @('C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
                 'C:\Program Files\Microsoft\Edge\Application\msedge.exe') | Where-Object { Test-Path $_ } | Select-Object -First 1
}
# gepenkenti felulbiralas (pl. $DskSablon = 'D:\valami\Lemmings.dsk'); a .gitignore-ban van
$gepBeall = Join-Path $PSScriptRoot 'gep_beallitas.ps1'
if (Test-Path $gepBeall) { . $gepBeall }

# --- BMP olvasas: 1/4/8/24/32 bites, tomorites nelkuli (BI_RGB; 32 bitnel BITFIELDS is) ---
# Eredmeny: @{ W; H; Px } ahol Px[y*W+x] = 0xRRGGBB (y = 0 a kep teteje)
function Bmp-Olvas([string]$Fajl) {
  $d = [IO.File]::ReadAllBytes($Fajl)
  if ($d.Length -lt 54 -or $d[0] -ne 0x42 -or $d[1] -ne 0x4D) { throw "nem BMP fajl: $Fajl" }
  $off = [BitConverter]::ToInt32($d, 10)
  $hs  = [BitConverter]::ToInt32($d, 14)
  $w   = [BitConverter]::ToInt32($d, 18)
  $h   = [BitConverter]::ToInt32($d, 22)
  $bpp = [BitConverter]::ToUInt16($d, 28)
  $tom = [BitConverter]::ToInt32($d, 30)
  if (-not ($tom -eq 0 -or ($tom -eq 3 -and $bpp -eq 32))) { throw "tomoritett BMP nem tamogatott ($Fajl, tomorites $tom)" }
  if (@(1, 4, 8, 24, 32) -notcontains $bpp) { throw "$bpp bites BMP nem tamogatott ($Fajl)" }
  $fentrol = $h -lt 0; $h = [math]::Abs($h)
  $pal = @()
  if ($bpp -le 8) {
    $n = [BitConverter]::ToInt32($d, 46); if ($n -eq 0) { $n = 1 -shl $bpp }
    $p0 = 14 + $hs
    for ($i = 0; $i -lt $n; $i++) { $q = $p0 + 4 * $i; $pal += (([int]$d[$q + 2]) -shl 16) -bor (([int]$d[$q + 1]) -shl 8) -bor $d[$q] }
  }
  $sor = [int][math]::Floor(($w * $bpp + 31) / 32) * 4
  $px = New-Object int[] ($w * $h)
  for ($y = 0; $y -lt $h; $y++) {
    $sy = if ($fentrol) { $y } else { $h - 1 - $y }
    $p = $off + $sy * $sor
    for ($x = 0; $x -lt $w; $x++) {
      switch ($bpp) {
        24 { $q = $p + 3 * $x; $c = (([int]$d[$q + 2]) -shl 16) -bor (([int]$d[$q + 1]) -shl 8) -bor $d[$q] }
        32 { $q = $p + 4 * $x; $c = (([int]$d[$q + 2]) -shl 16) -bor (([int]$d[$q + 1]) -shl 8) -bor $d[$q] }
        8  { $c = $pal[$d[$p + $x]] }
        4  { $c = $pal[($d[$p + ($x -shr 1)] -shr (4 * (1 - ($x -band 1)))) -band 15] }
        1  { $c = $pal[($d[$p + ($x -shr 3)] -shr (7 - ($x -band 7))) -band 1] }
      }
      $px[$y * $w + $x] = $c
    }
  }
  return @{ W = $w; H = $h; Px = $px }
}

# egy pixel R/G/B mezokkel (mint a System.Drawing GetPixel eredmenye)
function Bmp-Pixel($Bmp, [int]$X, [int]$Y) {
  $c = $Bmp.Px[$Y * $Bmp.W + $X]
  return @{ R = ($c -shr 16) -band 255; G = ($c -shr 8) -band 255; B = $c -band 255 }
}

# 24 bites BMP irasa; Px[y*W+x] = 0xRRGGBB
function Bmp-Ir([string]$Fajl, [int]$W, [int]$H, [int[]]$Px) {
  $sor = [int][math]::Floor(($W * 24 + 31) / 32) * 4
  $meret = 54 + $sor * $H
  $d = New-Object byte[] $meret
  $d[0] = 0x42; $d[1] = 0x4D
  [BitConverter]::GetBytes([int]$meret).CopyTo($d, 2)
  [BitConverter]::GetBytes([int]54).CopyTo($d, 10)
  [BitConverter]::GetBytes([int]40).CopyTo($d, 14)
  [BitConverter]::GetBytes([int]$W).CopyTo($d, 18)
  [BitConverter]::GetBytes([int]$H).CopyTo($d, 22)
  [BitConverter]::GetBytes([uint16]1).CopyTo($d, 26)
  [BitConverter]::GetBytes([uint16]24).CopyTo($d, 28)
  [BitConverter]::GetBytes([int]3780).CopyTo($d, 38); [BitConverter]::GetBytes([int]3780).CopyTo($d, 42)   # 96 dpi, mint a System.Drawing
  for ($y = 0; $y -lt $H; $y++) {
    $p = 54 + ($H - 1 - $y) * $sor
    for ($x = 0; $x -lt $W; $x++) {
      $c = $Px[$y * $W + $x]; $q = $p + 3 * $x
      $d[$q] = [byte]($c -band 255); $d[$q + 1] = [byte](($c -shr 8) -band 255); $d[$q + 2] = [byte](($c -shr 16) -band 255)
    }
  }
  [IO.File]::WriteAllBytes($Fajl, $d)
}

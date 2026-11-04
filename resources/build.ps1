# Teljes build: forditas (TRSE nightly) -> lemezkep (SIDTVC.dsk) -> WinTVC inditasa a lemezzel. Futtatas csak lemezrol (a .cas gyorsbetoltesenel nincs fajleszkoz).
# Hasznalat (a projekt gyokereben): powershell -NoProfile -File resources\build.ps1          (emulator nelkul: ... build.ps1 -NoEmu)
# Ha a program adatfajlokat tolt, ird hozza oket a -Files listahoz ("forras=LEMEZNEV.BIN", 8.3-as nev). Az ELSO a .cas legyen.
param([switch]$NoEmu)
. (Join-Path $PSScriptRoot 'kozos.ps1')
Set-Location $Gyoker
$cas = Join-Path $Gyoker "SIDSoftEMU.cas"
$elotte = if (Test-Path $cas) { (Get-Item $cas).LastWriteTime } else { [datetime]::MinValue }
$ki = Join-Path $Temp "trse_out_sidsoftemu.txt"
$p = Start-Process -FilePath $TrseExe -ArgumentList "-cli op=project project=SIDSoftEMU.trse input_file=SIDSoftEMU.ras assemble=yes" -RedirectStandardOutput $ki -Wait -NoNewWindow -PassThru
$hibak = Get-Content $ki | Select-String -Pattern "rror|Line \d+"
if ($p.ExitCode -ne 0 -or $hibak -or -not (Test-Path $cas) -or (Get-Item $cas).LastWriteTime -le $elotte) {
  "FORDITASI HIBA (exit $($p.ExitCode)):"; Get-Content $ki | Select-Object -Last 15; exit 1
}
"forditas OK"
# Egy lemez (SIDTVC.dsk, 720 KB = 713 klaszter): SIDTVC.CAS + a dalok termeszetes sorrendben, amig ferenek; ami nem fer, kimarad.
$lemez = @("SIDSoftEMU.cas=SIDTVC.CAS")
$szabad = 713 - [math]::Ceiling((Get-Item $cas).Length / 1024) - 1      # -1: SID_TVC
$kimaradt = @()
Get-ChildItem (Join-Path $Gyoker "sid_tvc") -Directory -ErrorAction SilentlyContinue | Sort-Object Name | ForEach-Object {
  $d = $_.Name; $uj = $true
  Get-ChildItem $_.FullName -Filter "*.STC" | Sort-Object { [regex]::Replace($_.Name, '\d+', { $args[0].Value.PadLeft(5, '0') }) } | ForEach-Object {
    $k = [math]::Ceiling($_.Length / 1024); if ($uj) { $k++ }
    if ($k -le $szabad) { $szabad -= $k; $uj = $false; $lemez += ("sid_tvc/" + $d + "/" + $_.Name + "=SID_TVC/" + $d + "/" + $_.Name) }
    else { $kimaradt += ($d + "/" + $_.Name) }
  }
}
if ($kimaradt) { "a lemezre nem fert: " + ($kimaradt -join " ") }
& (Join-Path $PSScriptRoot "make_dsk.ps1") -Out "SIDTVC.dsk" -Files $lemez | Select-Object -Last 1

# --- WinTVC: a regi peldany bezarasa, uj inditas a friss lemezzel (/d = A: lemez, /a = LOAD"*" -> az elso fajl, SIDTVC.CAS) ---
if (-not $NoEmu -and -not $Mac) {
  if (-not $WinTvcExe -or -not (Test-Path $WinTvcExe)) { "WinTVC nem talalhato: '$WinTvcExe' (allitsd be: resources\gep_beallitas.ps1)"; exit 0 }
  Get-Process -Name ([IO.Path]::GetFileNameWithoutExtension($WinTvcExe)) -ErrorAction SilentlyContinue | Stop-Process -Force
  $dsk = Join-Path $Gyoker "SIDTVC.dsk"
  Start-Process -FilePath $WinTvcExe -ArgumentList "/d `"$dsk`" /a" -WorkingDirectory (Split-Path $WinTvcExe -Parent)
  "WinTVC elinditva: $dsk"
}

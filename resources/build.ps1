# Teljes build: forditas (TRSE nightly) -> lemezkep (SIDSoftEMU.dsk) -> WinTVC inditasa a lemezzel. Futtatas csak lemezrol (a .cas gyorsbetoltesenel nincs fajleszkoz).
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
# A dalok ~1 MB-ok, egy 720 KB-os lemezre nem ferenek: a $Lemez2 mappai a 2. lemezre (SIDSOFT2.dsk), a program mindkettore.
$Lemez2 = @("LNINJA2")
$lemez = @("SIDSoftEMU.cas=SIDSOFT.CAS")
$lemez2 = @("SIDSoftEMU.cas=SIDSOFT.CAS")
Get-ChildItem (Join-Path $Gyoker "sid_tvc") -Directory -ErrorAction SilentlyContinue | ForEach-Object { $d = $_.Name; Get-ChildItem $_.FullName -Filter "*.STC" | Sort-Object { [regex]::Replace($_.Name, '\d+', { $args[0].Value.PadLeft(5, '0') }) } | ForEach-Object { $e = ("sid_tvc/" + $d + "/" + $_.Name + "=SID_TVC/" + $d + "/" + $_.Name); if ($Lemez2 -contains $d) { $lemez2 += $e } else { $lemez += $e } } }
& (Join-Path $PSScriptRoot "make_dsk.ps1") -Out "SIDSoftEMU.dsk" -Files $lemez | Select-Object -Last 1
& (Join-Path $PSScriptRoot "make_dsk.ps1") -Out "SIDSOFT2.dsk" -Files $lemez2 | Select-Object -Last 1

# --- WinTVC: a regi peldany bezarasa, uj inditas a friss lemezzel (/d = A: lemez, /a = LOAD"*" -> az elso fajl, SIDSOFT.CAS) ---
if (-not $NoEmu -and -not $Mac) {
  if (-not $WinTvcExe -or -not (Test-Path $WinTvcExe)) { "WinTVC nem talalhato: '$WinTvcExe' (allitsd be: resources\gep_beallitas.ps1)"; exit 0 }
  Get-Process -Name ([IO.Path]::GetFileNameWithoutExtension($WinTvcExe)) -ErrorAction SilentlyContinue | Stop-Process -Force
  $dsk = Join-Path $Gyoker "SIDSoftEMU.dsk"
  Start-Process -FilePath $WinTvcExe -ArgumentList "/d `"$dsk`" /a" -WorkingDirectory (Split-Path $WinTvcExe -Parent)
  "WinTVC elinditva: $dsk"
}

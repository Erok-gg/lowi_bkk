# test-session.ps1 - scrap de VALIDATION, entierement isole de la production.
#
# ASCII strict : PowerShell relit ce fichier avec l'encodage de la console, et
# un caractere accentue mal decode casse le PARSING avant toute execution.
#
# Rien de ce que fait ce script ne touche Supabase ni scraper/output/ :
#   - LOWI_OUTPUT_DIR redirige base SQLite, images et fiches vers le dossier de test
#   - --store sqlite (jamais supabase)
#   - PAS de --full  ->  aucun delistage possible
#
# Usage :  powershell -NoProfile -ExecutionPolicy Bypass -File ops\test-session.ps1
#          ... -Nombre 500 -Source ddproperty -Deal rent

param(
    [int]$Nombre = 500,
    [string]$Source = "ddproperty",
    [ValidateSet('sale', 'rent')][string]$Deal = "rent",
    [string]$Dossier = ""
)

$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root "scraper\.venv\Scripts\python.exe"

if (-not $Dossier) {
    $stamp = Get-Date -Format "yyyy-MM-dd-HHmm"
    $Dossier = Join-Path $root "tests-scrap\$stamp-$Source-$Deal-$Nombre"
}
New-Item -ItemType Directory -Force $Dossier | Out-Null
$log = Join-Path $Dossier "scrap.log"

Write-Host "=== SESSION DE TEST ISOLEE ==="
Write-Host "  source    : $Source ($Deal)"
Write-Host "  volume    : $Nombre annonces"
Write-Host "  dossier   : $Dossier"
Write-Host "  store     : SQLite local (production INTOUCHEE)"
Write-Host "  delistage : DESACTIVE (pas de --full)"
Write-Host ""

$env:LOWI_OUTPUT_DIR = $Dossier
$debut = Get-Date
Set-Content -Path $log -Value "=== TEST $Source $Deal x$Nombre - debut $debut ==="

& $py (Join-Path $root "scraper\run.py") `
    --source $Source --deal-type $Deal --limit $Nombre `
    --store sqlite --geocode *>&1 | Tee-Object -Append $log

$code = $LASTEXITCODE
$duree = (Get-Date) - $debut
Add-Content -Path $log -Value "--- exit=$code duree=$($duree.ToString('hh\:mm\:ss')) ---"
Remove-Item Env:\LOWI_OUTPUT_DIR -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "=== TERMINE en $($duree.ToString('hh\:mm\:ss')) (code $code) ==="
$cmd = '{0} ops\juge-test.py "{1}"' -f $py, $Dossier
Write-Host "  Analyser :  $cmd"

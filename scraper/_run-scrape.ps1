param([ValidateSet('sale','rent')][string]$Deal = 'sale')

# Empeche la mise en veille du SYSTEME pendant le scrap, mais LAISSE l'ecran
# s'eteindre (on ne pose pas ES_DISPLAY_REQUIRED). On ne modifie PAS le plan
# d'alimentation : a la fin du script, on libere le maintien eveille et les
# conditions d'origine reprennent automatiquement (rien a restaurer a la main).

$ErrorActionPreference = 'Continue'
Set-Location $PSScriptRoot
$py = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) {
  Write-Host "[ERREUR] Python du venv introuvable : $py"
  Write-Host "Recree-le : python -m venv .venv  puis  .venv\Scripts\pip install -r requirements.txt"
  exit 1
}

$sig = '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint esFlags);'
$es  = Add-Type -MemberDefinition $sig -Name Power -Namespace Win32 -PassThru
# valeurs en decimal : 0x80000000 = 2147483648 (les litteraux hex 8 chiffres
# sont vus comme Int32 negatif par PowerShell -> cast uint32 impossible).
$ES_CONTINUOUS = [uint32]2147483648
$ES_SYSTEM_REQ = [uint32]1
$KEEP_AWAKE    = [uint32]($ES_CONTINUOUS -bor $ES_SYSTEM_REQ)

$log = Join-Path $PSScriptRoot ("output\fullscrape-$Deal.log")
"===== FULL SCRAP $Deal - $(Get-Date) =====" | Set-Content $log

try {
  # maintien eveille : systeme oui, ecran non
  [void]$es::SetThreadExecutionState($KEEP_AWAKE)
  Write-Host "Veille systeme suspendue (l'ecran peut s'eteindre)."

  foreach ($s in 'fazwaz','ddproperty','propertyscout','nestopa') {
    Write-Host ""
    Write-Host "============================================================"
    Write-Host "  SOURCE : $s   ($Deal)"
    Write-Host "============================================================"
    & $py run.py --source $s --deal-type $Deal --full --geocode --store supabase
    "--- $s termine (code $LASTEXITCODE) ---" | Add-Content $log
    # rafraichit le maintien eveille entre deux sources
    [void]$es::SetThreadExecutionState($KEEP_AWAKE)
  }
}
finally {
  # libere le maintien -> la veille systeme reprend selon tes reglages d'origine
  [void]$es::SetThreadExecutionState($ES_CONTINUOUS)
  Write-Host ""
  Write-Host "===== TERMINE. Veille systeme reactivee (conditions d'origine). Resume : $log ====="
}

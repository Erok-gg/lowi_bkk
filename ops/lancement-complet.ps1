# lancement-complet.ps1 - premier cycle complet du systeme d'agents.
#
# ASCII strict (voir test-session.ps1 : un accent mal decode casse le parsing).
#
# Passe les 12 agents des deux lanes, en ignorant les cadences (--all), dans
# l'ordre ou l'orchestrateur les declare. Concretement :
#   lane sale : fazwaz sale --full + couloirs, ddproperty sale --full + couloirs,
#               watch-health, analyze-sale, organize, overseer
#   lane rent : fazwaz rent --full + couloirs, ddproperty rent --full + couloirs,
#               propertyscout, nestopa, watch-health, analyze-rent, organize,
#               report (etude datee), overseer
#   lane weekly : watch-sources, storage (archive + purge), overseer
#
# DUREE ATTENDUE : 6 a 10 heures. La tache a une limite de 10 h.
#
# GARDE-FOUS ACTIFS :
#   - run.py annule le delistage si le scan voit moins de 50% des actives en base
#   - l'agent storage refuse de purger si un extracteur n'a pas fini en 'ok'
#   - chaque agent est journalise dans agents/ledger.db, l'overseer relit le cycle
#
# Usage direct :  powershell -NoProfile -ExecutionPolicy Bypass -File ops\lancement-complet.ps1
# Verification a blanc :  ... -DryRun

param(
    [switch]$DryRun,
    [ValidateSet('tout', 'sale', 'rent', 'weekly')][string]$Portee = 'tout',
    # -Local : scrap vers un store SQLite isole. AUCUNE ecriture Supabase.
    #          Les agents qui LISENT Supabase sont sautes (ils analyseraient la
    #          production, pas le test). Remontee ensuite par ops\remonter-local.py
    [switch]$Local,
    [string]$DossierLocal = "",
    # Le dashboard s'ouvre en fenetre au demarrage du scrap. -SansDashboard l'evite.
    [switch]$SansDashboard
)

$ErrorActionPreference = 'Continue'
# Les logs sortaient en mojibake : Tee-Object n'ecrit pas dans le meme encodage
# que la console. On force UTF-8 des deux cotes.
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'
$PSDefaultParameterValues['Tee-Object:Encoding'] = 'utf8'
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root "scraper\.venv\Scripts\python.exe"
$orch = Join-Path $root "agents\orchestrator.py"
$logDir = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir ("lancement-complet-{0}.log" -f (Get-Date -Format "yyyy-MM-dd-HHmm"))

$lanes = switch ($Portee) {
    'tout'   { @('sale', 'rent', 'weekly') }
    default  { @($Portee) }
}

# Empeche la mise en veille du SYSTEME (l'ecran peut s'eteindre). Libere a la fin.
$sig = '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint esFlags);'
$es = Add-Type -MemberDefinition $sig -Name PowerLC -Namespace Win32 -PassThru
$KEEP_AWAKE = [uint32]2147483648 -bor [uint32]1

if ($Local -and -not $DossierLocal) {
    $stamp = Get-Date -Format "yyyy-MM-dd-HHmm"
    $DossierLocal = Join-Path $root "tests-scrap\$stamp-FULL-LOCAL"
}
if ($Local) { New-Item -ItemType Directory -Force $DossierLocal | Out-Null }

# Notification locale au demarrage ET a la fin. Ne depend d'aucun module externe
# ni d'une application ouverte : c'est le filet de securite si la tache Claude
# de verification ne se declenche pas.
function Notifier([string]$titre, [string]$texte) {
    try {
        Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
        $n = New-Object System.Windows.Forms.NotifyIcon
        $n.Icon = [System.Drawing.SystemIcons]::Information
        $n.BalloonTipTitle = $titre
        $n.BalloonTipText = $texte
        $n.Visible = $true
        $n.ShowBalloonTip(20000)
        Start-Sleep -Seconds 6
        $n.Dispose()
    } catch { }   # une notification qui echoue ne doit jamais bloquer un scrap
    # Trace fichier : lisible meme si la bulle a ete manquee
    $marqueur = Join-Path $PSScriptRoot "logs\NOTIFICATIONS.log"
    Add-Content -Path $marqueur -Value ("[{0}] {1} - {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $titre, $texte)
}

# Dashboard de supervision : ouvert EN FENETRE au demarrage du scrap (pas en
# plein ecran, pour ne pas voler le focus). Lecture seule, aucun impact.
# -SansDashboard pour s'en passer.
if (-not $DryRun -and -not $SansDashboard) {
    $pyw = Join-Path $root "scraper\.venv\Scripts\pythonw.exe"
    $dash = Join-Path $PSScriptRoot "dashboard.py"
    if ((Test-Path $pyw) -and (Test-Path $dash)) {
        try {
            Start-Process -FilePath $pyw -ArgumentList $dash -WorkingDirectory $root | Out-Null
            Write-Host "  dashboard : ouvert en fenetre"
        } catch { Write-Host "  dashboard : non ouvert ($($_.Exception.Message))" }
    }
}

$debut = Get-Date
Set-Content -Path $log -Value "=== LANCEMENT COMPLET - debut $debut - portee $Portee - local=$Local ==="
$modeTxt = if ($Local) { "LOCAL (aucune ecriture Supabase)" } else { "EN LIGNE (ecriture Supabase)" }
Notifier "Lowi BKK - cycle demarre" "Mode $modeTxt. Portee $Portee. Duree attendue 6-10 h. Log : $log"
Write-Host "=== LANCEMENT COMPLET ($Portee) - $debut ==="
Write-Host "  log : $log"
if ($Local) {
    Write-Host "  MODE LOCAL : aucune ecriture Supabase"
    Write-Host "  dossier    : $DossierLocal"
    Write-Host "  ATTENTION  : prevoir ~5 Go de disque (images des 4 sources)"
}
if ($DryRun) { Write-Host "  MODE A BLANC : rien ne sera execute" }

try {
    [void]$es::SetThreadExecutionState($KEEP_AWAKE)
    foreach ($lane in $lanes) {
        Write-Host ""
        Write-Host "--- lane $lane ---"
        Add-Content -Path $log -Value "`n--- lane $lane - $(Get-Date) ---"
        $args = @($orch, 'run-lane', $lane, '--all')
        if ($DryRun) { $args += '--dry-run' }
        if ($Local) { $args += @('--local', $DossierLocal) }
        & $py $args *>&1 | Tee-Object -Append $log
        Add-Content -Path $log -Value "--- lane $lane exit=$LASTEXITCODE ---"
        [void]$es::SetThreadExecutionState($KEEP_AWAKE)   # rafraichit entre lanes
    }
}
finally {
    [void]$es::SetThreadExecutionState([uint32]2147483648)   # libere le maintien eveille
}

$duree = (Get-Date) - $debut
Add-Content -Path $log -Value "=== FIN - duree $($duree.ToString('hh\:mm\:ss')) ==="

# BILAN DE FIN DE SCRAP : ce qui a change depuis le dernier etat connu
# (opportunites, tension, rendements par khet, courbes par date).
if ($Local -and (Test-Path (Join-Path $DossierLocal "bangkok.db"))) {
    Write-Host ""
    Write-Host "=== BILAN ==="
    & $py (Join-Path $PSScriptRoot "bilan-scrap.py") $DossierLocal --md *>&1 | Tee-Object -Append $log
    & $py (Join-Path $PSScriptRoot "juge-test.py") $DossierLocal *>&1 | Tee-Object -Append $log
}

Notifier "Lowi BKK - cycle termine" ("Duree $($duree.ToString('hh\:mm\:ss')). Bilan ecrit dans le dossier du scrap.")
Write-Host ""
Write-Host "=== TERMINE en $($duree.ToString('hh\:mm\:ss')) ==="
Write-Host "  Etat    : $py $orch status"
Write-Host "  Audit   : agents\audits\$(Get-Date -Format 'yyyy-MM-dd').md"
Write-Host "  Journal : $log"
if ($Local) {
    Write-Host ""
    Write-Host "  --- SUITE (apres relecture des resultats) ---"
    Write-Host "  Juger   : $py ops\juge-test.py `"$DossierLocal`""
    Write-Host "  Remonter: $py ops\remonter-local.py `"$DossierLocal`" --dry-run"
    Write-Host "            (puis sans --dry-run pour ecrire dans Supabase)"
}

# rotation : garde 10 logs de lancement
Get-ChildItem $logDir -Filter "lancement-complet-*.log" | Sort-Object Name -Descending |
    Select-Object -Skip 10 | Remove-Item -Force -ErrorAction SilentlyContinue

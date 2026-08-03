# install-agents-task.ps1 — remplace les 3 tâches mortes par UNE tâche d'orchestration.
#
# POURQUOI CE SCRIPT EXISTE
# Les tâches LowiBKK-ScrapVente / ScrapLocation / ArchiveSync, créées le 2026-07-11,
# n'ont JAMAIS tourné. Leur XML contenait des guillemets échappés littéraux :
#     <Arguments>-NoProfile -ExecutionPolicy Bypass -File \"C:\...\scrap-vente.ps1\"</Arguments>
# PowerShell recevait un chemin introuvable et sortait avant la première ligne du
# script. Preuve matérielle : ops/logs/ n'a jamais existé, alors que chaque wrapper
# le crée en première instruction. Les trois tâches remontaient LastTaskResult
# 0xFFFD0000 et personne ne le voyait.
#
# CAUSE : l'enregistrement passait par la CHAÎNE de commande `schtasks`, dont le
# parsing a inséré les backslashes. Ce script utilise les CMDLETS
# (New-ScheduledTaskAction / Register-ScheduledTask), qui prennent les arguments
# comme des données et non comme une ligne de commande à re-parser.
#
# Le script VÉRIFIE ensuite le XML réellement enregistré. Sans cette vérification,
# on ne saurait pas plus qu'en juillet que la tâche est cassée.
#
# Usage :  powershell -NoProfile -ExecutionPolicy Bypass -File ops\install-agents-task.ps1
#          ... -WhatIf     pour voir sans rien changer

[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$Heure = "08:00",
    [switch]$GarderAnciennes
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root "scraper\.venv\Scripts\python.exe"
$orch = Join-Path $root "agents\orchestrator.py"
$nom = "LowiBKK-Agents"
$anciennes = @("LowiBKK-ScrapVente", "LowiBKK-ScrapLocation", "LowiBKK-ArchiveSync")

if (-not (Test-Path $py))   { throw "Python du venv introuvable : $py" }
if (-not (Test-Path $orch)) { throw "Orchestrateur introuvable : $orch" }

# ── 1. Sauvegarder puis retirer les anciennes ─────────────────────────────
$backupDir = Join-Path $PSScriptRoot "taches-supprimees"
New-Item -ItemType Directory -Force $backupDir | Out-Null

foreach ($t in $anciennes) {
    $task = Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue
    if (-not $task) { Write-Host "  · $t : absente, rien a faire"; continue }

    $xml = Export-ScheduledTask -TaskName $t
    $dest = Join-Path $backupDir "$t.xml"
    $xml | Set-Content -Path $dest -Encoding UTF8
    Write-Host "  · $t : sauvegardee dans $dest"

    if ($GarderAnciennes) { Write-Host "    (conservee sur demande)"; continue }
    if ($PSCmdlet.ShouldProcess($t, "Unregister-ScheduledTask")) {
        Unregister-ScheduledTask -TaskName $t -Confirm:$false
        Write-Host "    supprimee"
    }
}

# ── 2. Enregistrer la tache unique ────────────────────────────────────────
# `--due` : l'orchestrateur lit le ledger, calcule ce qui est du, et ne lance que
# ca. Le rattrapage vient de la BASE, pas de StartWhenAvailable — qui ne rattrape
# rien quand c'est la tache elle-meme qui est cassee.
$action = New-ScheduledTaskAction -Execute $py -Argument "`"$orch`" --due" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Daily -At $Heure
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 10) `
    -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

if ($PSCmdlet.ShouldProcess($nom, "Register-ScheduledTask")) {
    Register-ScheduledTask -TaskName $nom -Action $action -Trigger $trigger `
        -Settings $settings -Principal $principal -Force `
        -Description "Orchestrateur des 12 agents Lowi BKK. Lit agents/agents.json et le ledger, lance ce qui est du." | Out-Null
    Write-Host "`n  $nom enregistree (quotidienne a $Heure)"
}

# ── 3. VERIFIER le XML reellement enregistre ──────────────────────────────
# C'est l'etape qui manquait en juillet.
$verif = Export-ScheduledTask -TaskName $nom -ErrorAction SilentlyContinue
if (-not $verif) { Write-Host "`n  [!] Tache non relue (mode -WhatIf ?)"; return }

$argLine = ([xml]$verif).Task.Actions.Exec.Arguments
$exeLine = ([xml]$verif).Task.Actions.Exec.Command
Write-Host "`n--- XML enregistre ---"
Write-Host "  Command   : $exeLine"
Write-Host "  Arguments : $argLine"

if ($argLine -match '\\"') {
    Write-Host "`n  [ECHEC] Des guillemets echappes sont presents — c'est le defaut de juillet." -ForegroundColor Red
    Write-Host "          La tache ne se lancera pas. Ne pas la laisser en l'etat."
    exit 1
}
if (-not (Test-Path $exeLine)) {
    Write-Host "`n  [ECHEC] Commande introuvable : $exeLine" -ForegroundColor Red
    exit 1
}
Write-Host "`n  [OK] Aucun guillemet echappe, executable present." -ForegroundColor Green
Write-Host "  Test a chaud :  Start-ScheduledTask -TaskName $nom"
Write-Host "  Puis verifier : $py $orch status"

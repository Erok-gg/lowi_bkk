# install-boot-task.ps1 - tache de rattrapage au demarrage/logon, SANS extraction.
#
# POURQUOI CE SCRIPT EXISTE (2026-08-17)
# LowiBKK-Agents (quotidienne 01:00) peut manquer son creneau si la machine est
# eteinte ou en veille a ce moment-la - StartWhenAvailable la rattrape alors au
# demarrage suivant, MAIS en relancant TOUT, extracteurs compris : un scrap
# complet de plusieurs heures peut alors demarrer a une heure imprevisible
# (en pleine journee, pendant un usage actif du PC).
#
# Cette tache-ci appelle `orchestrator.py --boot` : meme logique de rattrapage
# (is_due() lit le ledger), mais SANS toucher aux extracteurs ni a
# verifie-backup (voir orchestrator.py:run_lane, parametre skip_extraction).
# Elle rejoue seulement la suite du cycle qui n'aurait pas pu partir :
# watch-health, analyze-sale/rent, organize, report, backup-apres-cycle,
# overseer. Si rien n'est du, c'est un no-op rapide (quelques secondes).
#
# Meme methode d'enregistrement que install-agents-task.ps1 (cmdlets, pas la
# chaine schtasks) - c'est ce qui evite le bug des guillemets echappes qui a
# laisse 3 taches mortes pendant 3 semaines en juillet. Le script VERIFIE le
# XML reellement enregistre, comme l'autre.
#
# Usage :  powershell -NoProfile -ExecutionPolicy Bypass -File ops\install-boot-task.ps1
#          ... -WhatIf     pour voir sans rien changer

[CmdletBinding(SupportsShouldProcess)]
param()

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root "scraper\.venv\Scripts\python.exe"
$orch = Join-Path $root "agents\orchestrator.py"
$nom = "LowiBKK-RattrapageBoot"

if (-not (Test-Path $py))   { throw "Python du venv introuvable : $py" }
if (-not (Test-Path $orch)) { throw "Orchestrateur introuvable : $orch" }

$action = New-ScheduledTaskAction -Execute $py -Argument "`"$orch`" --boot" -WorkingDirectory $root
# Declencheur "a l'ouverture de session" (demarrage OU reconnexion apres une
# veille profonde qui a ferme la session) - pas "au demarrage systeme" (At
# Startup), qui tournerait avant l'ouverture de session utilisateur et sans
# le contexte reseau/Ollama pret.
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

if ($PSCmdlet.ShouldProcess($nom, "Register-ScheduledTask")) {
    Register-ScheduledTask -TaskName $nom -Action $action -Trigger $trigger `
        -Settings $settings -Principal $principal -Force `
        -Description "Rattrapage au demarrage/logon pour Lowi BKK : rejoue analyse/organisation/rapport/backup/overseer SANS relancer les extracteurs (orchestrator.py --boot). Complement de LowiBKK-Agents, pas un remplacement." | Out-Null
    Write-Host "`n  $nom enregistree (declencheur : ouverture de session)"
}

# VERIFIER le XML reellement enregistre - meme controle que pour LowiBKK-Agents.
$verif = Export-ScheduledTask -TaskName $nom -ErrorAction SilentlyContinue
if (-not $verif) { Write-Host "`n  [!] Tache non relue (mode -WhatIf ?)"; return }

$argLine = ([xml]$verif).Task.Actions.Exec.Arguments
$exeLine = ([xml]$verif).Task.Actions.Exec.Command
Write-Host "`n--- XML enregistre ---"
Write-Host "  Command   : $exeLine"
Write-Host "  Arguments : $argLine"

if ($argLine -match '\\"') {
    Write-Host "`n  [ECHEC] Des guillemets echappes sont presents." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $exeLine)) {
    Write-Host "`n  [ECHEC] Commande introuvable : $exeLine" -ForegroundColor Red
    exit 1
}
Write-Host "`n  [OK] Aucun guillemet echappe, executable present." -ForegroundColor Green
Write-Host "  Test a chaud :  Start-ScheduledTask -TaskName $nom"
Write-Host "  Puis verifier : $py $orch status"

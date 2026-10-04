# install-facebook-task.ps1 - tache Windows du collecteur Facebook immo.
#
# POURQUOI CE SCRIPT EXISTE (2026-09-13)
# LowiBKK-ScrapeImmoFacebook pointait sur C:\agentic\agents\agent2_scraper\
# scrape-immo-facebook.ps1, hors de ce depot : l'audit du 2026-09-13 l'a
# trouvee en echec (0x1) chaque nuit, inconnue du CLAUDE.md. Le script vit
# desormais dans scraper\social\ ; ce fichier reenregistre la tache dessus,
# avec la meme methode que install-agents-task.ps1 (cmdlets, relecture du
# XML, refus des guillemets echappes).
#
# Usage :  powershell -NoProfile -ExecutionPolicy Bypass -File ops\install-facebook-task.ps1
#          ... -WhatIf     pour voir sans rien changer

[CmdletBinding(SupportsShouldProcess)]
param([string]$Heure = "02:30")   # aligne sur LowiBKK-Agents depuis le 2026-10-04 (reveil RTC commun)

$ErrorActionPreference = 'Stop'
$root   = Split-Path -Parent $PSScriptRoot
$script = Join-Path $root "scraper\social\scrape-immo-facebook.ps1"
$nom    = "LowiBKK-ScrapeImmoFacebook"
$ps     = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"

if (-not (Test-Path $script)) { throw "Script introuvable : $script" }
if (-not (Test-Path (Join-Path $root "scraper\social\node_modules"))) {
    throw "node_modules absent : lancer npm install dans scraper\social d abord"
}

$action = New-ScheduledTaskAction -Execute $ps `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`"" `
    -WorkingDirectory (Split-Path -Parent $script)
$trigger = New-ScheduledTaskTrigger -Daily -At $Heure
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -MultipleInstances IgnoreNew
# Interactive : Chrome a besoin d'une session ouverte (profil, fenetre CDP).
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

if ($PSCmdlet.ShouldProcess($nom, "Register-ScheduledTask")) {
    Register-ScheduledTask -TaskName $nom -Action $action -Trigger $trigger `
        -Settings $settings -Principal $principal -Force `
        -Description "Lowi BKK : collecte brute des groupes Facebook immo Bangkok (scraper\social\scrape-immo-facebook.ps1). Ferme Chrome, ouvre le profil d'automatisation, node facebook/agent.js, 30 min max. Code retour = celui du scrape." | Out-Null
    Write-Host "`n  $nom enregistree (quotidienne $Heure)"
}

$verif = Export-ScheduledTask -TaskName $nom -ErrorAction SilentlyContinue
if (-not $verif) { Write-Host "`n  [!] Tache non relue (mode -WhatIf ?)"; return }
$argLine = ([xml]$verif).Task.Actions.Exec.Arguments
$exeLine = ([xml]$verif).Task.Actions.Exec.Command
Write-Host "`n--- XML enregistre ---"
Write-Host "  Command   : $exeLine"
Write-Host "  Arguments : $argLine"
if ($argLine -match '\\"') { Write-Host "`n  [ECHEC] Guillemets echappes presents." -ForegroundColor Red; exit 1 }
if ($argLine -notmatch [regex]::Escape($script)) { Write-Host "`n  [ECHEC] La tache ne pointe pas sur $script" -ForegroundColor Red; exit 1 }
Write-Host "`n  [OK] Tache relue, chemin correct." -ForegroundColor Green
Write-Host "  Test a chaud :  Start-ScheduledTask -TaskName $nom   (ferme TOUT Chrome !)"

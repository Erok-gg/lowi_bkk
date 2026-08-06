# install-agents-task.ps1 - remplace les 3 taches mortes par UNE tache d'orchestration.
#
# POURQUOI CE SCRIPT EXISTE
# Les taches LowiBKK-ScrapVente / ScrapLocation / ArchiveSync, creees le 2026-07-11,
# n'ont JAMAIS tourne. Leur XML contenait des guillemets echappes litteraux :
#     <Arguments>-NoProfile -ExecutionPolicy Bypass -File \"C:\...\scrap-vente.ps1\"</Arguments>
# PowerShell recevait un chemin introuvable et sortait avant la premiere ligne du
# script. Preuve materielle : ops/logs/ n'a jamais existe, alors que chaque wrapper
# le cree en premiere instruction. Les trois taches remontaient LastTaskResult
# 0xFFFD0000 et personne ne le voyait.
#
# CAUSE : l'enregistrement passait par la CHAINE de commande `schtasks`, dont le
# parsing a insere les backslashes. Ce script utilise les CMDLETS
# (New-ScheduledTaskAction / Register-ScheduledTask), qui prennent les arguments
# comme des donnees et non comme une ligne de commande a re-parser.
#
# Le script VERIFIE ensuite le XML reellement enregistre. Sans cette verification,
# on ne saurait pas plus qu'en juillet que la tache est cassee.
#
# Usage :  powershell -NoProfile -ExecutionPolicy Bypass -File ops\install-agents-task.ps1
#          ... -WhatIf     pour voir sans rien changer

[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$Heure = "01:00",
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

# -- 1. Sauvegarder puis retirer les anciennes -----------------------------
$backupDir = Join-Path $PSScriptRoot "taches-supprimees"
New-Item -ItemType Directory -Force $backupDir | Out-Null

foreach ($t in $anciennes) {
    $task = Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue
    if (-not $task) { Write-Host "  * $t : absente, rien a faire"; continue }

    $xml = Export-ScheduledTask -TaskName $t
    $dest = Join-Path $backupDir "$t.xml"
    $xml | Set-Content -Path $dest -Encoding UTF8
    Write-Host "  * $t : sauvegardee dans $dest"

    if ($GarderAnciennes) { Write-Host "    (conservee sur demande)"; continue }
    if ($PSCmdlet.ShouldProcess($t, "Unregister-ScheduledTask")) {
        Unregister-ScheduledTask -TaskName $t -Confirm:$false
        Write-Host "    supprimee"
    }
}

# -- 2. Enregistrer la tache unique ----------------------------------------
# `--due` : l'orchestrateur lit le ledger, calcule ce qui est du, et ne lance que
# ca. Le rattrapage vient de la BASE, pas de StartWhenAvailable - qui ne rattrape
# rien quand c'est la tache elle-meme qui est cassee.
$action = New-ScheduledTaskAction -Execute $py -Argument "`"$orch`" --due" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Daily -At $Heure
# Declencheur QUOTIDIEN : la cadence de 4 jours (et le "decale au lendemain si
# manque") vit dans orchestrator.py --due (is_due() lit le LEDGER), pas ici -
# c'est deja le design d'origine, voir le commentaire au-dessus de l'action.
# -WakeToRun : reveille la machine si les minuteurs RTC sont autorises au
# niveau du plan d'alimentation Windows (reglage systeme, hors de portee d'un
# script : powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP RTCWAKE 1, en
# console ADMINISTRATEUR - verifie desactive sur cette machine le 2026-08-03,
# jamais reactive depuis). Sans ce reglage, WakeToRun est ignore et la tache ne
# se declenche que si le PC est deja allume a l'heure dite (StartWhenAvailable
# rattrape alors au demarrage suivant).
$settings = New-ScheduledTaskSettingsSet `
    -WakeToRun `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 10) `
    -MultipleInstances IgnoreNew `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 15)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

if ($PSCmdlet.ShouldProcess($nom, "Register-ScheduledTask")) {
    Register-ScheduledTask -TaskName $nom -Action $action -Trigger $trigger `
        -Settings $settings -Principal $principal -Force `
        -Description "Orchestrateur des 12 agents Lowi BKK. Lit agents/agents.json et le ledger, lance ce qui est du. Cadence reelle par agent geree par le ledger (every_days dans agents.json), pas par ce declencheur." | Out-Null
    Write-Host "`n  $nom enregistree (quotidienne a $Heure, reveil demande)"
}

# -- 3. VERIFIER le XML reellement enregistre ------------------------------
# C'est l'etape qui manquait en juillet.
$verif = Export-ScheduledTask -TaskName $nom -ErrorAction SilentlyContinue
if (-not $verif) { Write-Host "`n  [!] Tache non relue (mode -WhatIf ?)"; return }

$argLine = ([xml]$verif).Task.Actions.Exec.Arguments
$exeLine = ([xml]$verif).Task.Actions.Exec.Command
Write-Host "`n--- XML enregistre ---"
Write-Host "  Command   : $exeLine"
Write-Host "  Arguments : $argLine"

if ($argLine -match '\\"') {
    Write-Host "`n  [ECHEC] Des guillemets echappes sont presents - c'est le defaut de juillet." -ForegroundColor Red
    Write-Host "          La tache ne se lancera pas. Ne pas la laisser en l'etat."
    exit 1
}
if (-not (Test-Path $exeLine)) {
    Write-Host "`n  [ECHEC] Commande introuvable : $exeLine" -ForegroundColor Red
    exit 1
}
if ($verif -notmatch '<WakeToRun>true</WakeToRun>') {
    Write-Host "`n  [!] WakeToRun absent du XML enregistre." -ForegroundColor Yellow
}
Write-Host "`n  [OK] Aucun guillemet echappe, executable present." -ForegroundColor Green
Write-Host "  Test a chaud :  Start-ScheduledTask -TaskName $nom"
Write-Host "  Puis verifier : $py $orch status"

# Les minuteurs de reveil sont-ils reellement autorises au niveau du plan
# d'alimentation ? WakeToRun sur la tache ne suffit pas sans ca.
$rtc = (powercfg /query SCHEME_CURRENT SUB_SLEEP RTCWAKE) -join "`n"
$valeurs = [regex]::Matches($rtc, '0x0000000\d') | ForEach-Object { $_.Value }
if ($valeurs -and $valeurs[0] -eq '0x00000000') {
    Write-Host "`n  !! LES MINUTEURS DE REVEIL SONT DESACTIVES AU NIVEAU DU PLAN D'ALIMENTATION." -ForegroundColor Yellow
    Write-Host "     La tache ne se declenchera QUE si le PC est deja allume a l'heure dite."
    Write-Host "     A executer une fois, en console ADMINISTRATEUR :"
    Write-Host "         powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP RTCWAKE 1"
    Write-Host "         powercfg /setactive SCHEME_CURRENT"
} else {
    Write-Host "`n  Minuteurs de reveil autorises. Verifier avec : powercfg /waketimers"
}

# install-soir-task.ps1 - tache du soir LowiBKK-Soir (21:00) : lane `soir`.
#
# POURQUOI CE SCRIPT EXISTE (2026-10-22)
# Demande : scraper DotProperty le soir, "jusqu'au bout de la nuit", pour
# rattraper son stock (~180 000 annonces, dont ~27 000 absentes de nos autres
# sources). Le cycle de nuit (LowiBKK-Agents, 02:30) REPORTE TOUT s'il trouve
# un scrap encore en vol (orchestrator.py, extraction_en_cours) : les agents de
# cette lane s'arretent donc seuls a 02:00 (run.py --jusqua), 30 min de marge.
#
# Choix du declencheur :
#  - WakeToRun : le poste peut etre en veille a 21:00, comme a 02:30.
#  - PAS de StartWhenAvailable : un poste rallume a 09:00 lancerait le scrap en
#    pleine journee, jusqu'a 02:00 le lendemain. Un soir manque est rattrape le
#    soir suivant (la dedup reprend ou on en etait).
#  - ExecutionTimeLimit 6 h : filet si l'arret de 02:00 ne jouait pas.
#
# Meme methode d'enregistrement que install-agents-task.ps1 (cmdlets, pas la
# chaine schtasks : bug des guillemets echappes de juillet), XML relu a la fin.
#
# Usage :  powershell -NoProfile -ExecutionPolicy Bypass -File ops\install-soir-task.ps1
#          ... -WhatIf     pour voir sans rien changer
# Retour : Unregister-ScheduledTask -TaskName LowiBKK-Soir -Confirm:$false

[CmdletBinding(SupportsShouldProcess)]
param()

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root "scraper\.venv\Scripts\python.exe"
$orch = Join-Path $root "agents\orchestrator.py"
$nom = "LowiBKK-Soir"

if ($env:COMPUTERNAME -ne "REMIZDABOSS") {
    throw "Cette tache ne s'installe que sur PC2 (REMIZDABOSS), le poste coureur. Poste actuel : $env:COMPUTERNAME"
}
if (-not (Test-Path $py))   { throw "Python du venv introuvable : $py" }
if (-not (Test-Path $orch)) { throw "Orchestrateur introuvable : $orch" }

$action = New-ScheduledTaskAction -Execute $py -Argument "`"$orch`" run-lane soir" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Daily -At "21:00"
$settings = New-ScheduledTaskSettingsSet `
    -WakeToRun `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 6) `
    -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

if ($PSCmdlet.ShouldProcess($nom, "Register-ScheduledTask")) {
    Register-ScheduledTask -TaskName $nom -Action $action -Trigger $trigger `
        -Settings $settings -Principal $principal -Force `
        -Description "Lowi BKK : scrap du soir (lane soir, DotProperty), 21:00 -> arret propre a 02:00 avant le cycle de 02:30." | Out-Null
    Write-Host "`n  $nom enregistree (quotidienne 21:00, reveil du poste)"
}

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

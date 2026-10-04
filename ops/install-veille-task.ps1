# install-veille-task.ps1 - tache Windows de la veille Claude du cycle.
#
# POURQUOI CE SCRIPT EXISTE (2026-10-04, demande de l'utilisateur)
# Claude reste "eveille" pendant le cycle : un passage toutes les 30 min a
# partir de l'heure du cycle (02:30), Haiku verifie, Opus est appele en cas de
# probleme, et la veille s'eteint une fois le cycle fini et verifie (marqueur
# agents\state\veille\<jour>.json : les passages suivants sortent sans appeler
# de modele). Detail : ops\veille-cycle.py.
#
# Pas de -WakeToRun : la veille ne doit pas reveiller le poste toutes les
# 30 min. C'est LowiBKK-Agents qui le reveille ; la veille suit tant qu'il est
# debout. Pas de -StartWhenAvailable : des passages rates ne se rattrapent pas
# en rafale au reveil, le suivant suffit.
#
# Usage :  powershell -NoProfile -ExecutionPolicy Bypass -File ops\install-veille-task.ps1
#          ... -WhatIf     pour voir sans rien changer
# Retour arriere :  Unregister-ScheduledTask -TaskName LowiBKK-VeilleClaude -Confirm:$false

[CmdletBinding(SupportsShouldProcess)]
param([string]$Heure = "02:30")

$ErrorActionPreference = 'Stop'
$root   = Split-Path -Parent $PSScriptRoot
$script = Join-Path $root "ops\veille-cycle.py"
$py     = Join-Path $root "scraper\.venv\Scripts\python.exe"
$nom    = "LowiBKK-VeilleClaude"

if (-not (Test-Path $script)) { throw "Script introuvable : $script" }
if (-not (Test-Path $py))     { throw "Python du venv introuvable : $py" }

$action = New-ScheduledTaskAction -Execute $py -Argument "`"$script`"" -WorkingDirectory $root
# Repetition 30 min sur 23 h 30 : le cycle le plus long mesure (28,6 h, capot
# ferme le 30/09) deborde quand meme ; le declenchement du lendemain reprend
# alors la meme fenetre (debut lu sur la tache, pas sur la date).
$trigger = New-ScheduledTaskTrigger -Daily -At $Heure
$rep = New-ScheduledTaskTrigger -Once -At $Heure -RepetitionInterval (New-TimeSpan -Minutes 30) `
    -RepetitionDuration (New-TimeSpan -Hours 23 -Minutes 30)
$trigger.Repetition = $rep.Repetition
$settings = New-ScheduledTaskSettingsSet `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 20) `
    -MultipleInstances IgnoreNew
# Interactive : `claude` lit ses identifiants dans le profil de l'utilisateur.
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

if ($PSCmdlet.ShouldProcess($nom, "Register-ScheduledTask")) {
    Register-ScheduledTask -TaskName $nom -Action $action -Trigger $trigger `
        -Settings $settings -Principal $principal -Force `
        -Description "Lowi BKK : veille Claude du cycle (ops\veille-cycle.py). Toutes les 30 min des $Heure : Haiku verifie, Opus si probleme, silence une fois le cycle fini et verifie." | Out-Null
    Write-Host "`n  $nom enregistree (des $Heure, toutes les 30 min)"
}

$t = Get-ScheduledTask -TaskName $nom -ErrorAction SilentlyContinue
if (-not $t) { Write-Host "`n  [!] Tache non relue (mode -WhatIf ?)"; return }
$x = [xml](Export-ScheduledTask -TaskName $nom)
$argLine = $x.Task.Actions.Exec.Arguments
Write-Host "  Arguments : $argLine"
Write-Host "  Repetition : $($t.Triggers[0].Repetition.Interval) pendant $($t.Triggers[0].Repetition.Duration)"
if ($argLine -match '\\"') { Write-Host "`n  [ECHEC] Guillemets echappes presents." -ForegroundColor Red; exit 1 }
if ($t.Triggers[0].Repetition.Interval -ne 'PT30M') { Write-Host "`n  [ECHEC] Repetition absente." -ForegroundColor Red; exit 1 }
Write-Host "`n  [OK] Tache relue." -ForegroundColor Green

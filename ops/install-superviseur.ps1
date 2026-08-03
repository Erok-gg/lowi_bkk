# install-superviseur.ps1 - reprise automatique du scrap apres coupure.
#
# ASCII strict (un accent mal decode casse le PARSING avant execution).
#
# Enregistre une tache qui relance le superviseur :
#   - au DEMARRAGE de la session (retour de courant, redemarrage)
#   - au DEVERROUILLAGE (sortie de veille)
#   - toutes les 30 minutes en filet de securite
#
# Le superviseur lui-meme verifie toutes les 30 s : internet, processus vivants,
# avancement. Il sort tout seul quand toutes les sources sont terminees, et
# MultipleInstances=IgnoreNew empeche d'en lancer deux.
#
# Usage :  powershell -NoProfile -ExecutionPolicy Bypass -File ops\install-superviseur.ps1 -Dossier <chemin>
#          ... -Desinstaller

[CmdletBinding()]
param(
    [string]$Dossier = "",
    [switch]$Desinstaller
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$nom = "LowiBKK-Superviseur"

if ($Desinstaller) {
    if (Get-ScheduledTask -TaskName $nom -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $nom -Confirm:$false
        Write-Host "  $nom supprimee"
    } else { Write-Host "  $nom absente" }
    return
}

$pyw = Join-Path $root "scraper\.venv\Scripts\pythonw.exe"
$sup = Join-Path $root "ops\superviseur.py"
if (-not (Test-Path $pyw)) { throw "Python introuvable : $pyw" }
if (-not (Test-Path $sup)) { throw "Superviseur introuvable : $sup" }

if (-not $Dossier) {
    $d = Get-ChildItem (Join-Path $root "tests-scrap") -Directory -ErrorAction SilentlyContinue |
         Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $d) { throw "Aucun dossier de scrap - passer -Dossier" }
    $Dossier = $d.FullName
}
Write-Host "  dossier surveille : $Dossier"

$arg = '"{0}" --dossier "{1}"' -f $sup, $Dossier
$action = New-ScheduledTaskAction -Execute $pyw -Argument $arg -WorkingDirectory $root

# Trois declencheurs : ouverture de session (retour de courant), deverrouillage
# (sortie de veille), et une repetition de securite si les deux ont ete manques.
$t1 = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$t2 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) `
        -RepetitionInterval (New-TimeSpan -Minutes 30)
$declencheurs = @($t1, $t2)

# StartWhenAvailable : si la machine etait eteinte a l'heure prevue, on rattrape.
# RestartCount : si la tache elle-meme meurt, Windows la relance.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries `
    -MultipleInstances IgnoreNew `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 72)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $nom -Action $action -Trigger $declencheurs `
    -Settings $settings -Principal $principal -Force `
    -Description "Reprend le scrap Lowi BKK apres coupure de courant, de reseau ou mise en veille. Verifie toutes les 30 s." | Out-Null

# VERIFICATION du XML reellement enregistre (le defaut de juillet : des
# guillemets echappes rendaient trois taches inoperantes, en silence).
$x = [xml](Export-ScheduledTask -TaskName $nom)
Write-Host ""
Write-Host "  Command   : $($x.Task.Actions.Exec.Command)"
Write-Host "  Arguments : $($x.Task.Actions.Exec.Arguments)"
if ($x.Task.Actions.Exec.Arguments -match '\\"') {
    Write-Host "  [ECHEC] guillemets echappes presents" -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] tache enregistree et verifiee" -ForegroundColor Green
Write-Host ""
Write-Host "  Etat du scrap :  $pyw $sup --dossier `"$Dossier`" --etat"
Write-Host "  Desinstaller  :  ...\install-superviseur.ps1 -Desinstaller"

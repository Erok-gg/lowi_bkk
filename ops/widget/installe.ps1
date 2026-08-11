#Requires -Version 7.0
<#
.SYNOPSIS
    Installe (ou retire) le widget au demarrage de session, et le lance.

.DESCRIPTION
    Depose un raccourci vers garde.vbs dans le dossier Demarrage de
    l'utilisateur. Pas de tache planifiee, pas de droits administrateur : un
    widget d'affichage n'a aucune raison d'en demander.

    Le demarrage de session couvre l'allumage du PC et l'ouverture de session ;
    la sortie de veille est geree par le widget lui-meme (il ecoute
    PowerModeChanged / SessionSwitch et recollecte au reveil), car aucune
    session ne se rouvre dans ce cas et un declencheur de tache ne suffirait pas.

.EXAMPLE
    pwsh -File installe.ps1
    pwsh -File installe.ps1 -Desinstalle
#>
[CmdletBinding()]
param([switch]$Desinstalle)

$ErrorActionPreference = 'Stop'
$ICI       = Split-Path -Parent $MyInvocation.MyCommand.Path
$Demarrage = [Environment]::GetFolderPath('Startup')
$Raccourci = Join-Path $Demarrage 'Widget Lowi.lnk'
$Arret     = Join-Path $ICI '.arret'

function Arreter-Existant {
    # Le gardien est un wscript.exe, le widget un pwsh.exe : on pose le drapeau
    # d'arret (le gardien le lit avant de relancer) puis on ferme les deux.
    New-Item $Arret -ItemType File -Force | Out-Null
    Get-CimInstance Win32_Process -Filter "Name='wscript.exe' OR Name='pwsh.exe'" |
        Where-Object { $_.CommandLine -and ($_.CommandLine -like '*ops\widget\garde.vbs*' -or
                                            $_.CommandLine -like '*ops\widget\widget.ps1*') } |
        ForEach-Object {
            Write-Host "  arret du processus $($_.ProcessId) ($($_.Name))"
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
    Start-Sleep -Milliseconds 400
}

if ($Desinstalle) {
    Arreter-Existant
    if (Test-Path $Raccourci) { Remove-Item $Raccourci -Force; Write-Host "  raccourci retire" }
    Write-Host "`nWidget desinstalle. Les fichiers restent dans $ICI." -ForegroundColor Green
    return
}

if (-not (Get-Command pwsh -ErrorAction SilentlyContinue)) {
    throw "pwsh.exe (PowerShell 7) est introuvable dans le PATH — le widget en depend."
}

Arreter-Existant

$sh = New-Object -ComObject WScript.Shell
$lnk = $sh.CreateShortcut($Raccourci)
$lnk.TargetPath       = Join-Path $env:WINDIR 'System32\wscript.exe'
$lnk.Arguments        = '"{0}"' -f (Join-Path $ICI 'garde.vbs')
$lnk.WorkingDirectory = $ICI
$lnk.Description      = 'Widget des routines Lowi BKK'
$lnk.IconLocation     = "$env:WINDIR\System32\shell32.dll,13"
$lnk.Save()
Write-Host "  raccourci cree : $Raccourci"

Remove-Item $Arret -ErrorAction SilentlyContinue
Start-Process -FilePath (Join-Path $env:WINDIR 'System32\wscript.exe') `
              -ArgumentList ('"{0}"' -f (Join-Path $ICI 'garde.vbs')) -WindowStyle Hidden

Write-Host @"

Widget installe et lance.

  · Il apparait sur le bureau, derriere les fenetres : montre le bureau
    (Win+D) pour le voir.
  · Clic droit dessus : Rafraichir, Deplacer, Reglages, Quitter.
  · Reglages : $ICI\config.json (relu a chaud, pas besoin de redemarrer).
  · Retrait  : pwsh -File "$ICI\installe.ps1" -Desinstalle
"@ -ForegroundColor Green

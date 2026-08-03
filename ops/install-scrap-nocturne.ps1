# install-scrap-nocturne.ps1 - cycle complet tous les 4 jours, la nuit,
# avec REVEIL de la machine.
#
# ASCII strict (voir test-session.ps1 : un accent mal decode casse le parsing).
#
# PREREQUIS QUE CE SCRIPT NE PEUT PAS POSER LUI-MEME
# --------------------------------------------------
# Les minuteurs de reveil sont DESACTIVES sur cette machine (verifie le
# 2026-08-03 : RTCWAKE a 0x00000000 sur secteur ET sur batterie). Tant qu'ils le
# sont, `WakeToRun` est ignore et la tache ne se declenchera que si le PC est
# deja allume. Modifier un reglage d'alimentation est une action systeme : elle
# se fait a la main, en console ADMINISTRATEUR :
#
#     powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP RTCWAKE 1
#     powercfg /setactive SCHEME_CURRENT
#
# (Le premier active le reveil sur SECTEUR uniquement. Sur batterie, c'est
# deconseille : reveiller un portable debranche pour six heures de scrap le vide.)
#
# Verification apres coup :
#     powercfg /waketimers          -> doit lister la tache
#
# La machine est en VEILLE MODERNE (S0, "Connecte au reseau") : le reseau reste
# actif en veille, donc un scrap peut reellement s'executer. Sur une machine en
# S3 classique, il faudrait en plus autoriser la sortie de veille par le BIOS.
#
# CE QUE FAIT LA TACHE
# --------------------
# Toutes les 96 h a 02:00, lance ops/superviseur.py sur un dossier date. Le
# superviseur gere la reprise apres coupure reseau ou courant, et produit bilan,
# jugement et referentiel d'immeubles en fin de cycle.
#
# ENREGISTREMENT PAR CMDLETS, JAMAIS PAR LA CHAINE `schtasks` : c'est son parsing
# qui avait insere des guillemets echappes litteraux (`-File \"C:\...\"`) dans
# les trois taches du 11/07, restees mortes DIX-SEPT JOURS sans que rien ne le
# signale. Le script relit le XML apres coup et REFUSE tout `\"`.
#
# Usage :  powershell -NoProfile -ExecutionPolicy Bypass -File ops\install-scrap-nocturne.ps1
# Suppression : Unregister-ScheduledTask -TaskName LowiBKK-ScrapNocturne -Confirm:$false

param(
    [string]$Heure = '02:00',
    [int]$Jours = 4,
    [switch]$Supprimer
)

$ErrorActionPreference = 'Stop'
$Nom = 'LowiBKK-ScrapNocturne'
$Racine = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Racine 'scraper\.venv\Scripts\pythonw.exe'
$Script = Join-Path $Racine 'ops\superviseur.py'

if ($Supprimer) {
    Unregister-ScheduledTask -TaskName $Nom -Confirm:$false -ErrorAction SilentlyContinue
    "Tache $Nom supprimee."
    return
}

foreach ($p in @($Python, $Script)) {
    if (-not (Test-Path $p)) { throw "Introuvable : $p" }
}

# Un dossier date par cycle : le superviseur reprend un cycle interrompu s'il
# retrouve son etat, et n'en relance jamais un deja termine.
$Action = New-ScheduledTaskAction -Execute $Python -Argument "`"$Script`"" -WorkingDirectory $Racine

$Declencheur = New-ScheduledTaskTrigger -Daily -DaysInterval $Jours -At $Heure

$Reglages = New-ScheduledTaskSettingsSet `
    -WakeToRun `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries:$false `
    -DontStopIfGoingOnBatteries:$false `
    -ExecutionTimeLimit (New-TimeSpan -Hours 10) `
    -MultipleInstances IgnoreNew `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 15)

Unregister-ScheduledTask -TaskName $Nom -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $Nom -Action $Action -Trigger $Declencheur `
    -Settings $Reglages -Description "Lowi BKK - cycle de scrap complet tous les $Jours jours, la nuit. Reveille la machine si les minuteurs RTC sont autorises." | Out-Null

# CONTROLE OBLIGATOIRE : relire ce qui a REELLEMENT ete enregistre.
$xml = Export-ScheduledTask -TaskName $Nom
if ($xml -match '\\"') {
    Unregister-ScheduledTask -TaskName $Nom -Confirm:$false
    throw "XML corrompu (guillemets echappes) - tache supprimee. C'est le defaut du 11/07."
}
if ($xml -notmatch '<WakeToRun>true</WakeToRun>') {
    "ATTENTION : WakeToRun absent du XML enregistre."
}

$info = Get-ScheduledTaskInfo -TaskName $Nom
"Tache $Nom enregistree."
"  prochaine execution : $($info.NextRunTime)"
"  cadence             : tous les $Jours jours a $Heure"
"  reveil demande      : oui"

# Les minuteurs de reveil sont-ils reellement autorises ?
$rtc = (powercfg /query SCHEME_CURRENT SUB_SLEEP RTCWAKE) -join "`n"
$valeurs = [regex]::Matches($rtc, '0x0000000\d') | ForEach-Object { $_.Value }
if ($valeurs -and $valeurs[0] -eq '0x00000000') {
    ""
    "!! LES MINUTEURS DE REVEIL SONT DESACTIVES."
    "   La tache ne se declenchera QUE si le PC est deja allume."
    "   A executer une fois, en console ADMINISTRATEUR :"
    "       powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP RTCWAKE 1"
    "       powercfg /setactive SCHEME_CURRENT"
} else {
    ""
    "Minuteurs de reveil autorises. Verifier avec : powercfg /waketimers"
}

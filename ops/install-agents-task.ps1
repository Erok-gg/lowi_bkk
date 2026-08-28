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
    [switch]$GarderAnciennes,
    # RENDORMIR EN FIN DE CYCLE : DESACTIVE PAR DEFAUT depuis le 2026-08-25.
    #
    # L'idee etait bonne (ne pas laisser un portable allume toute la nuit apres
    # un cycle de ~5 h) mais la mesure l'a demolie sur CE poste :
    #   - `powercfg /a` : seul l'etat S0 « faible consommation, connecte au
    #     reseau » existe, ni S1 ni S2 ni S3 ;
    #   - test du 2026-08-25 09:11 : la machine entre en veille (Kernel-Power 42
    #     a 09:11:10) et en RESSORT 3 SECONDES PLUS TARD (107 a 09:11:13). Elle
    #     ne dort donc pas vraiment — l'economie d'energie est imaginaire ;
    #   - et c'est dans cet etat ambigu que le cycle du 2026-08-25 01:00 n'a PAS
    #     demarre, laissant une nuit entiere sans scrap sans que rien ne le dise.
    # Le reveil programme, lui, FONCTIONNE : `powercfg /lastwake` designe
    # nommement le minuteur de la tache comme cause du reveil. Le probleme
    # n'etait pas de se reveiller, mais de s'endormir.
    #
    # Une journee de marche perdue coute plus qu'une nuit de veille d'un
    # portable sur secteur. Reactivable par -VeilleALaFin si le compromis change.
    [switch]$VeilleALaFin,
    [switch]$SansVeilleALaFin   # conserve pour compatibilite : sans effet, c'est le defaut
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
$argOrch = "`"$orch`" --due"
if ($VeilleALaFin) { $argOrch += " --veille-a-la-fin" }
$action = New-ScheduledTaskAction -Execute $py -Argument $argOrch -WorkingDirectory $root
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
# ExecutionTimeLimit ILLIMITE (TimeSpan zero = PT0S, "ne jamais arreter la
# tache" selon la doc Task Scheduler) depuis le 2026-08-28, sur consigne
# explicite de l'utilisateur. AVANT : 10h, calibrees le 2026-07-31 pour une
# duree de cycle de ~7h15 (journal du 2026-08-22). La duree a grossi a
# ~11h35 le 2026-08-26 (ajout de remonter-supabase) sans que cette limite
# soit remontee en consequence -> Windows a tue l'orchestrateur en cours de
# route 3 nuits de suite (26, 27, 28/08 - agents/audits/reparations-2026-08-2{7,8}.md),
# emportant avec lui watch-health/report/backup-apres-cycle/overseer a
# chaque fois. Le vrai correctif de fond est le batching de
# remonter-local.py (SupabaseStore.upsert_listings_bulk, meme session) qui
# fait tomber sa duree de ~4h20 a quelques minutes - la limite de 10h
# redeviendrait large. Elle est retiree quand meme : un cycle DDproperty
# anormalement lent (deja mesure a 7h47 le 2026-08-27, cause jamais
# etablie) peut a lui seul recreer la meme marge insuffisante. La
# contrepartie EST le garde-fou de remplacement : `ops/pouls.py
# --verifier` alerte desormais si un cycle tourne encore apres 16h (voir
# pouls.py, verifier_cycle_long) - la protection se deplace d'un couperet
# aveugle vers un signal qui laisse le cycle finir tout en prevenant si
# quelque chose ne termine vraiment pas.
$settings = New-ScheduledTaskSettingsSet `
    -WakeToRun `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 15)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

if ($PSCmdlet.ShouldProcess($nom, "Register-ScheduledTask")) {
    Register-ScheduledTask -TaskName $nom -Action $action -Trigger $trigger `
        -Settings $settings -Principal $principal -Force `
        -Description "Orchestrateur des 12 agents Lowi BKK. Lit agents/agents.json et le ledger, lance ce qui est du. Cadence reelle par agent geree par le ledger (every_days dans agents.json), pas par ce declencheur." | Out-Null
    $mentionVeille = if ($VeilleALaFin) { "rendort la machine en fin de cycle" } else { "sans rendormissement (defaut depuis le 2026-08-25)" }
    Write-Host "`n  $nom enregistree (quotidienne a $Heure, reveil demande, $mentionVeille)"
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
# Deux valeurs, pas une : secteur ET batterie. Le controle d'origine ne lisait
# que la premiere ($valeurs[0]) et declarait donc "autorises" un poste qui ne se
# reveille pas sur batterie - mesure du 2026-08-22 sur REMIZDABOSS : AC=0x1,
# DC=0x0. Un reveil qui ne survient qu'une fois sur deux selon que le cable est
# branche est exactement le genre de panne qu'on ne remarque pas.
$rtc = (powercfg /query SCHEME_CURRENT SUB_SLEEP RTCWAKE) -join "`n"
$valeurs = [regex]::Matches($rtc, '0x0000000\d') | ForEach-Object { $_.Value }
$ac = if ($valeurs.Count -ge 1) { $valeurs[0] } else { $null }
$dc = if ($valeurs.Count -ge 2) { $valeurs[1] } else { $null }
Write-Host ""
if ($ac -eq '0x00000000') {
    Write-Host "  !! MINUTEURS DE REVEIL DESACTIVES SUR SECTEUR." -ForegroundColor Yellow
    Write-Host "     La tache ne se declenchera QUE si le PC est deja allume a l'heure dite."
    Write-Host "     A executer une fois :  powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP RTCWAKE 1"
    Write-Host "                            powercfg /setactive SCHEME_CURRENT"
} else {
    Write-Host "  Minuteurs de reveil autorises SUR SECTEUR."
}
if ($dc -eq '0x00000000') {
    Write-Host "  !  Sur BATTERIE ils restent interdits : endormie sur batterie, la machine" -ForegroundColor Yellow
    Write-Host "     ne se reveillera pas a $Heure - le cycle repartira au prochain logon"
    Write-Host "     via LowiBKK-RattrapageBoot. Pour l'autoriser aussi sur batterie :"
    Write-Host "         powercfg /setdcvalueindex SCHEME_CURRENT SUB_SLEEP RTCWAKE 1"
    Write-Host "         powercfg /setactive SCHEME_CURRENT"
}
Write-Host "  Minuteurs armes (console ADMINISTRATEUR) :  powercfg /waketimers"

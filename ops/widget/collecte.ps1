#Requires -Version 7.0
<#
.SYNOPSIS
    Collecte l'état des routines Lowi BKK et l'écrit en JSON pour le widget.

.DESCRIPTION
    Trois sources, trois natures différentes :

      · Tâches Windows   — interrogées en direct (Get-ScheduledTaskInfo). Fiable.
      · Routines Claude  — elles vivent côté serveur Claude, ce PC n'en a aucune
                           trace horaire. Les échéances sont RECALCULÉES depuis
                           le cron déposé dans config.json. Si tu changes une
                           routine côté Claude sans reporter le cron ici, le
                           widget affichera l'ancienne échéance : c'est la limite
                           assumée, signalée dans l'entête du panneau.
      · Agents Lowi      — cadence lue dans agents.json, dernier succès lu dans
                           agents/ledger.db (etat_agents.py). Un agent « dû » ne
                           tourne pas pour autant : il attend le prochain
                           déclenchement de la tâche orchestrateur. C'est CE
                           créneau-là qui est affiché, pas la date d'échéance.

    S'exécute seul (`pwsh -File collecte.ps1`) pour vérifier la sortie.

.PARAMETER Sortie
    Chemin du JSON à écrire. Par défaut ops/widget/etat.json.
#>
[CmdletBinding()]
param(
    [string]$Sortie,
    [switch]$Ecran   # affiche le JSON au lieu de l'écrire
)

$ErrorActionPreference = 'Stop'
$ICI     = Split-Path -Parent $MyInvocation.MyCommand.Path
$PROJET  = Split-Path -Parent (Split-Path -Parent $ICI)
if (-not $Sortie) { $Sortie = Join-Path $ICI 'etat.json' }

# ─────────────────────────────── cron ───────────────────────────────
function Expand-ChampCron {
    param([string]$Champ, [int]$Min, [int]$Max)
    $vals = [System.Collections.Generic.HashSet[int]]::new()
    foreach ($part in $Champ.Split(',')) {
        $p = $part.Trim(); $pas = 1
        if ($p -match '^(.*)/(\d+)$') { $p = $Matches[1]; $pas = [int]$Matches[2] }
        if ($p -eq '*' -or $p -eq '') { $lo = $Min; $hi = $Max }
        elseif ($p -match '^(\d+)-(\d+)$') { $lo = [int]$Matches[1]; $hi = [int]$Matches[2] }
        elseif ($p -match '^\d+$') { $lo = [int]$p; $hi = $lo }
        else { throw "champ cron incompris : '$part'" }
        for ($v = $lo; $v -le $hi; $v += $pas) { [void]$vals.Add($v) }
    }
    # La virgule est indispensable : sans elle PowerShell déroule le HashSet, et
    # un champ à une seule valeur (« jour 1 du mois ») revient en Int32 nu.
    return , $vals
}

function Get-ProchainCron {
    <# Prochaine occurrence d'un cron « m h jour mois jsem », en heure locale.
       Le jitter est le décalage fixe que Claude applique à chaque routine (il
       est propre à la tâche, pas tiré à chaque exécution : vérifié en comparant
       les nextRunAt du serveur aux crons, les trois routines actives tombent
       à la seconde). #>
    param([string]$Cron, [int]$JitterS = 0, [datetime]$Depuis = (Get-Date))

    $c = ($Cron -replace '\s+', ' ').Trim().Split(' ')
    if ($c.Count -ne 5) { throw "cron attendu à 5 champs, reçu $($c.Count)" }

    $minutes = Expand-ChampCron $c[0] 0 59
    $heures  = Expand-ChampCron $c[1] 0 23
    $jours   = Expand-ChampCron $c[2] 1 31
    $mois    = Expand-ChampCron $c[3] 1 12
    $jsem = [System.Collections.Generic.HashSet[int]]::new()
    foreach ($j in (Expand-ChampCron $c[4] 0 7)) { [void]$jsem.Add($(if ($j -eq 7) { 0 } else { $j })) }

    # Règle cron historique : si jour-du-mois ET jour-de-semaine sont tous deux
    # restreints, ils s'additionnent (OU), ils ne se croisent pas.
    $jourRestreint = $c[2] -ne '*'
    $jsemRestreint = $c[4] -ne '*'

    $depart = $Depuis.AddSeconds(-$JitterS).AddMinutes(1)
    $depart = [datetime]::new($depart.Year, $depart.Month, $depart.Day, $depart.Hour, $depart.Minute, 0)

    for ($d = 0; $d -lt 400; $d++) {
        $jour = $depart.Date.AddDays($d)
        if (-not $mois.Contains($jour.Month)) { continue }
        $okJour = $jours.Contains($jour.Day)
        $okSem  = $jsem.Contains([int]$jour.DayOfWeek)
        $passe = if ($jourRestreint -and $jsemRestreint) { $okJour -or $okSem }
                 elseif ($jourRestreint) { $okJour }
                 elseif ($jsemRestreint) { $okSem }
                 else { $true }
        if (-not $passe) { continue }

        foreach ($h in ($heures | Sort-Object)) {
            foreach ($m in ($minutes | Sort-Object)) {
                $t = $jour.AddHours($h).AddMinutes($m)
                if ($t -ge $depart) { return $t.AddSeconds($JitterS) }
            }
        }
    }
    return $null
}

# ────────────────────────── tâches Windows ──────────────────────────
function Get-TachesWindows {
    param([string[]]$Motifs, [bool]$MasquerDesactivees)
    $lignes = @()
    $toutes = Get-ScheduledTask -ErrorAction SilentlyContinue
    foreach ($motif in $Motifs) {
        foreach ($t in ($toutes | Where-Object { $_.TaskName -like $motif })) {
            $desactivee = $t.State -eq 'Disabled'
            if ($MasquerDesactivees -and $desactivee) { continue }
            $info = $null
            try { $info = $t | Get-ScheduledTaskInfo -ErrorAction Stop } catch { }

            # Windows renvoie 30/11/1999 pour « jamais » et garde une NextRunTime
            # sur les tâches désactivées : les deux mentiraient sur le panneau.
            $prochain = $null
            if ($info -and $info.NextRunTime -and $info.NextRunTime.Year -gt 2000 -and -not $desactivee) {
                $prochain = $info.NextRunTime
            }
            $dernier = $null
            if ($info -and $info.LastRunTime -and $info.LastRunTime.Year -gt 2000) {
                $dernier = $info.LastRunTime
            }
            $res = if ($info) { $info.LastTaskResult } else { $null }

            $lignes += [ordered]@{
                nom       = $t.TaskName
                etat      = [string]$t.State
                prochain  = if ($prochain) { $prochain.ToString('o') } else { $null }
                dernier   = if ($dernier) { $dernier.ToString('o') } else { $null }
                resultat  = $res
                # 0 = succès, 267009 = en cours, 267011 = jamais exécutée.
                echec     = ($null -ne $res -and $res -ne 0 -and $res -ne 267009 -and $res -ne 267011)
                encours   = ($t.State -eq 'Running')
                desactivee = $desactivee
            }
        }
    }
    # Deux motifs peuvent attraper la même tâche : on dédoublonne sur le nom,
    # pas sur l'horaire (deux tâches distinctes partagent souvent une heure).
    $vus = [System.Collections.Generic.HashSet[string]]::new()
    $lignes = @($lignes | Where-Object { $vus.Add($_.nom) })
    return , @($lignes | Sort-Object { if ($_.prochain) { $_.prochain } else { '9999' } })
}

function Get-DeclenchementsTache {
    <# Suite des déclenchements à venir d'une tâche quotidienne, pour situer
       les agents. On repart de la NextRunTime que donne Windows (elle tient
       compte des rattrapages) et on avance par l'intervalle du déclencheur. #>
    param([string]$Nom, [int]$Combien = 40)
    $t = Get-ScheduledTask -TaskName $Nom -ErrorAction SilentlyContinue
    if (-not $t -or $t.State -eq 'Disabled') { return @() }
    $info = $t | Get-ScheduledTaskInfo -ErrorAction SilentlyContinue
    if (-not $info -or -not $info.NextRunTime -or $info.NextRunTime.Year -le 2000) { return @() }

    $pas = 1
    foreach ($d in $t.Triggers) {
        if ($d.PSObject.Properties.Name -contains 'DaysInterval' -and $d.DaysInterval) {
            $pas = [int]$d.DaysInterval; break
        }
    }
    if ($pas -lt 1) { $pas = 1 }
    return @(0..($Combien - 1) | ForEach-Object { $info.NextRunTime.AddDays($_ * $pas) })
}

function Get-LaneUtc {
    <# Réplique current_lane() d'orchestrator.py : weekly si l'ordinal UTC du
       jour est multiple de 7. Le calcul se fait sur l'instant UTC du
       déclenchement — à 01:00 heure de Bangkok on est encore la VEILLE en UTC,
       donc la lane d'un cycle n'est pas celle de sa date affichée. #>
    param([datetime]$Local)
    $utc = $Local.ToUniversalTime()
    $ordinal = [int]($utc.Date - [datetime]'0001-01-01').TotalDays + 1
    if ($ordinal % 7 -eq 0) { 'weekly' } else { 'daily' }
}

# ─────────────────────────────── ollama ───────────────────────────────
function Test-Ollama {
    param([string]$Modele)
    try {
        $r = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3 -ErrorAction Stop
        $noms = @($r.models | ForEach-Object { $_.name })
        if ($noms | Where-Object { $_ -like "$Modele*" }) {
            return @{ ok = $true; message = "$Modele en place" }
        }
        return @{ ok = $false; message = "$Modele absent ($($noms.Count) modele(s))" }
    } catch {
        return @{ ok = $false; message = 'service arrete' }
    }
}

# ──────────────────────────────── main ────────────────────────────────
$erreurs = @()
$cfg = Get-Content (Join-Path $ICI 'config.json') -Raw -Encoding utf8 | ConvertFrom-Json

# 1 — tâches Windows
$taches = @()
try {
    $taches = Get-TachesWindows -Motifs $cfg.taches_windows -MasquerDesactivees ([bool]$cfg.masquer_taches_desactivees)
} catch { $erreurs += "taches Windows : $_" }

# 2 — routines Claude
$claude = @()
foreach ($r in $cfg.routines_claude) {
    $prochain = $null
    if ($r.actif -and $r.cron) {
        try { $prochain = Get-ProchainCron -Cron $r.cron -JitterS ([int]$r.jitter_s) }
        catch { $erreurs += "cron $($r.id) : $_" }
    }
    $claude += [ordered]@{
        nom      = $r.libelle
        id       = $r.id
        prochain = if ($prochain) { $prochain.ToString('o') } else { $null }
        actif    = [bool]$r.actif
    }
}
$claude = @($claude | Sort-Object { if ($_.prochain) { $_.prochain } else { '9999' } })

# 3 — agents Lowi
$agents = @(); $escalades = 0; $constats = 0
if ($cfg.afficher_agents) {
    $py = Join-Path $PROJET 'scraper\.venv\Scripts\python.exe'
    if (-not (Test-Path $py)) { $py = 'python' }
    try {
        $brut = & $py (Join-Path $ICI 'etat_agents.py') 2>$null
        $etat = $brut | ConvertFrom-Json
        foreach ($e in $etat.erreurs) { $erreurs += "agents : $e" }
        $escalades = [int]$etat.escalades
        $constats  = [int]$etat.constats_hauts

        $creneaux = Get-DeclenchementsTache -Nom $cfg.tache_orchestrateur
        foreach ($a in $etat.agents) {
            # ConvertFrom-Json convertit déjà les chaînes ISO 8601 en DateTime :
            # les re-parser les ferait passer par un rendu culture-dépendant et
            # échouerait. On n'analyse que ce qui est resté du texte.
            $duLe = if ($a.du_a_partir_de_utc -is [datetime]) { $a.du_a_partir_de_utc }
                    else { [datetime]::Parse([string]$a.du_a_partir_de_utc, [cultureinfo]::InvariantCulture,
                                             [System.Globalization.DateTimeStyles]::RoundtripKind) }
            $prochain = $null
            foreach ($c in $creneaux) {
                if ($c.ToUniversalTime() -lt $duLe.ToUniversalTime()) { continue }
                if ($a.lanes -notcontains (Get-LaneUtc $c)) { continue }
                $prochain = $c; break
            }
            $agents += [ordered]@{
                nom        = $a.nom
                tier       = $a.tier
                famille    = $a.famille
                every_days = $a.every_days
                du         = [bool]$a.du
                statut     = $a.dernier_statut
                jours      = $a.jours_depuis_ok
                prochain   = if ($prochain) { $prochain.ToString('o') } else { $null }
            }
        }
    } catch { $erreurs += "etat_agents.py : $_" }
}

# 4 — modèle local
$ollama = @{ ok = $null; message = 'non verifie' }
if ($cfg.verifier_ollama) { $ollama = Test-Ollama -Modele $cfg.modele_local }

$resultat = [ordered]@{
    genere_le      = (Get-Date).ToString('o')
    taches         = $taches
    claude         = $claude
    agents         = $agents
    escalades      = $escalades
    constats_hauts = $constats
    ollama         = $ollama
    erreurs        = $erreurs
}

$json = $resultat | ConvertTo-Json -Depth 6
if ($Ecran) { $json }
else {
    # Écriture atomique : le widget lit peut-être le fichier en ce moment même.
    $tmp = "$Sortie.tmp"
    Set-Content -Path $tmp -Value $json -Encoding utf8 -NoNewline
    Move-Item -Path $tmp -Destination $Sortie -Force
}

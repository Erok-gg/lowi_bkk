# exporte-poste.ps1 - fabrique le colis de transfert vers le 2e poste.
#
# POURQUOI CE SCRIPT EXISTE
# Le depot suffit pour le CODE (git clone), pas pour faire REPARTIR le systeme.
# Quatre familles de choses vivent hors du depot et se perdent silencieusement :
#   1. la memoire de Claude et les permissions accordees au projet ;
#   2. l'etat d'execution des agents (ledger, reprises, file de tickets) - sans
#      lui, is_due() croit que RIEN n'a jamais tourne et relance les 5
#      extracteurs en --full des le premier cycle (mesure du 2026-08-20 :
#      6 h 30 de scrap, 4 497 + 4 495 + 2 643 + 1 240 + 600 pages) ;
#   3. les secrets (.env.local, scraper/.env) - gitignores a dessein ;
#   4. les taches planifiees Windows.
#
# CE QUI N'EST PAS DANS LE COLIS, ET POURQUOI
#   - Les connecteurs MCP : VERIFIE le 2026-08-21, mcpServers est VIDE dans
#     ~/.claude.json (global ET projet). Les six connecteurs (Supabase, Gmail,
#     Drive, Vercel, Agenda, visualize) sont des connecteurs de COMPTE claude.ai,
#     stockes cote serveur. Ils reviennent avec "claude login". Le script en pose
#     l'INVENTAIRE pour pouvoir verifier au bout, pas pour les copier.
#   - Les routines Claude planifiees : idem, cote serveur. ~/.claude/scheduled-tasks
#     n'en contient que le SKILL.md local, copie ici a titre de reference.
#   - scraper/.venv et node_modules : se reconstruisent (pip install -r, npm ci).
#     Les copier transporterait des binaires lies a l'ancienne machine.
#   - archive/lowi-archive.db (708 Mo) : hors colis par defaut, -AvecArchive
#     pour l'inclure. C'est la reference historique complete - a transporter une
#     fois, pas a chaque export.
#
# Usage :
#   powershell -NoProfile -ExecutionPolicy Bypass -File ops\migration\exporte-poste.ps1
#   ... -AvecSecrets     inclut .env.local et scraper/.env (voir avertissement)
#   ... -AvecArchive     inclut l'archive SQLite de 708 Mo
#   ... -Destination D:\transfert

[CmdletBinding()]
param(
    [string]$Destination = (Join-Path $env:USERPROFILE "Desktop"),
    [switch]$AvecSecrets,
    [switch]$AvecArchive,
    [switch]$AvecLogs
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$stamp = Get-Date -Format "yyyy-MM-dd"
$colis = Join-Path $Destination "lowi-transfert-$stamp"

Write-Host "Racine du depot : $root"
Write-Host "Colis           : $colis`n"

$inv = [ordered]@{
    genere_le    = (Get-Date -Format "yyyy-MM-ddTHH:mm:sszzz")
    machine      = $env:COMPUTERNAME
    utilisateur  = $env:USERNAME
    racine       = $root
    avec_secrets = [bool]$AvecSecrets
    avec_archive = [bool]$AvecArchive
    elements     = @()
    absents      = @()
    connecteurs  = $null
}

function New-Dossier([string]$p) {
    if (-not (Test-Path $p)) { New-Item -ItemType Directory -Path $p -Force | Out-Null }
}

function Copie-Element {
    param([string]$Source, [string]$Cible, [string]$Etiquette)
    if (-not (Test-Path $Source)) {
        Write-Host "  -  absent : $Etiquette"
        $script:inv.absents += $Etiquette
        return
    }
    New-Dossier (Split-Path -Parent $Cible)
    if ((Get-Item $Source).PSIsContainer) {
        Copy-Item $Source $Cible -Recurse -Force
        $fichiers = Get-ChildItem $Cible -Recurse -File -ErrorAction SilentlyContinue
        $n = ($fichiers | Measure-Object).Count
        $o = ($fichiers | Measure-Object -Sum Length).Sum
        if (-not $o) { $o = 0 }
        Write-Host ("  OK $Etiquette  ({0} fichiers, {1:N1} Mo)" -f $n, ($o / 1MB))
        $script:inv.elements += [ordered]@{ etiquette = $Etiquette; type = "dossier"; fichiers = $n; octets = $o }
    }
    else {
        Copy-Item $Source $Cible -Force
        $o = (Get-Item $Cible).Length
        $h = (Get-FileHash $Cible -Algorithm SHA256).Hash
        Write-Host ("  OK $Etiquette  ({0:N1} Ko)" -f ($o / 1KB))
        $script:inv.elements += [ordered]@{ etiquette = $Etiquette; type = "fichier"; octets = $o; sha256 = $h }
    }
}

New-Dossier $colis

# ---------------------------------------------------------------- 1. Claude
Write-Host "[1/5] Configuration et memoire de Claude"
$claudeHome = Join-Path $env:USERPROFILE ".claude"
$cible = Join-Path $colis "claude"

Copie-Element (Join-Path $claudeHome "settings.json") (Join-Path $cible "settings.json") "settings global (~/.claude/settings.json)"
Copie-Element (Join-Path $root ".claude\settings.local.json") (Join-Path $cible "projet-settings.local.json") "permissions du projet (.claude/settings.local.json)"
Copie-Element (Join-Path $root ".claude\launch.json") (Join-Path $cible "projet-launch.json") "launch.json du projet"
Copie-Element (Join-Path $claudeHome "scheduled-tasks") (Join-Path $cible "scheduled-tasks") "SKILL.md des routines Claude (reference)"
Copie-Element (Join-Path $claudeHome "skills") (Join-Path $cible "skills") "skills utilisateur"

# La memoire vit dans un dossier dont le NOM ENCODE LE CHEMIN du projet
# (C:\Users\schoe\++FILES++\Lowi_bkk -> C--Users-schoe---FILES---Lowi-bkk :
# tout caractere non alphanumerique devient un tiret). On copie le contenu a
# plat ; c'est l'import qui recalcule le nom pour la machine cible - sinon la
# memoire atterrit dans un dossier que Claude ne lira jamais.
$cle = ($root.ToCharArray() | ForEach-Object { if ($_ -match '[A-Za-z0-9]') { $_ } else { '-' } }) -join ''
$mem = Join-Path $claudeHome "projects\$cle\memory"
Copie-Element $mem (Join-Path $cible "memory") "memoire du projet ($cle)"

# ------------------------------------------------------ 2. Inventaire MCP
Write-Host "`n[2/5] Inventaire des connecteurs (inventaire seul : rien a copier)"
$cfg = Join-Path $env:USERPROFILE ".claude.json"
if (Test-Path $cfg) {
    try {
        $j = Get-Content $cfg -Raw -Encoding UTF8 | ConvertFrom-Json
        $globaux = @()
        if ($j.mcpServers) { $globaux = @($j.mcpServers.PSObject.Properties.Name) }
        $duProjet = @()
        foreach ($k in $j.projects.PSObject.Properties.Name) {
            if (($k -replace '\\', '/') -eq ($root -replace '\\', '/')) {
                $p = $j.projects.$k
                if ($p.mcpServers) { $duProjet = @($p.mcpServers.PSObject.Properties.Name) }
            }
        }
        $inv.connecteurs = [ordered]@{
            mcp_locaux_globaux = $globaux
            mcp_locaux_projet  = $duProjet
            note               = "Vide = normal. Les connecteurs Supabase/Gmail/Drive/Vercel/Agenda sont lies au COMPTE claude.ai et reviennent avec claude login. Rien a copier."
        }
        $sg = if ($globaux.Count) { $globaux -join ', ' } else { "(aucun)" }
        $sp = if ($duProjet.Count) { $duProjet -join ', ' } else { "(aucun)" }
        Write-Host "  MCP locaux globaux : $sg"
        Write-Host "  MCP locaux projet  : $sp"
    }
    catch {
        Write-Host "  !  .claude.json illisible : $_"
        $inv.connecteurs = @{ erreur = "$_" }
    }
}
else {
    Write-Host "  -  ~/.claude.json absent"
}

# ------------------------------------------------------- 3. Etat des agents
Write-Host "`n[3/5] Etat d'execution des agents"
$etat = Join-Path $colis "etat"
New-Dossier $etat

# ledger.db est en mode WAL : une copie brute du seul .db perdrait les dernieres
# transactions restees dans le -wal. On passe par l'API backup de sqlite, qui
# rend un fichier coherent. Repli sur la copie des trois fichiers si le venv
# n'est pas la.
$ledger = Join-Path $root "agents\ledger.db"
$py = Join-Path $root "scraper\.venv\Scripts\python.exe"
if (Test-Path $ledger) {
    $dst = Join-Path $etat "ledger.db"
    $fait = $false
    if (Test-Path $py) {
        $code = "import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.close(); s.close()"
        & $py -c $code $ledger $dst
        if ($LASTEXITCODE -eq 0 -and (Test-Path $dst)) { $fait = $true }
    }
    if ($fait) {
        $o = (Get-Item $dst).Length
        Write-Host ("  OK agents/ledger.db (copie coherente sqlite, {0:N1} Ko)" -f ($o / 1KB))
        $inv.elements += [ordered]@{ etiquette = "agents/ledger.db"; type = "fichier"; octets = $o; methode = "sqlite backup" }
    }
    else {
        Write-Host "  !  API backup indisponible - copie brute .db + -wal + -shm"
        foreach ($suf in @("", "-wal", "-shm")) {
            if (Test-Path "$ledger$suf") { Copy-Item "$ledger$suf" (Join-Path $etat "ledger.db$suf") -Force }
        }
        $inv.elements += [ordered]@{ etiquette = "agents/ledger.db"; type = "fichier"; methode = "copie brute + wal/shm" }
    }
}
else {
    Write-Host "  -  absent : agents/ledger.db"
    $inv.absents += "agents/ledger.db"
}

Copie-Element (Join-Path $root "agents\state") (Join-Path $etat "state") "agents/state (journaux de reprise)"
Copie-Element (Join-Path $root "agents\queue") (Join-Path $etat "queue") "agents/queue (tickets T2 en attente)"
Copie-Element (Join-Path $root "agents\audits") (Join-Path $etat "audits") "agents/audits"
Copie-Element (Join-Path $root "ops\widget\config.json") (Join-Path $etat "widget-config.json") "ops/widget/config.json (crons Claude recopies a la main)"
Copie-Element (Join-Path $root "scraper\output\geocode-cache.json") (Join-Path $etat "geocode-cache.json") "cache Nominatim (evite de refaire du 1 req/s)"
Copie-Element (Join-Path $root "scraper\output\bangkok.db") (Join-Path $etat "bangkok.db") "store SQLite local"

if ($AvecLogs) { Copie-Element (Join-Path $root "agents\logs") (Join-Path $etat "logs") "agents/logs" }
if ($AvecArchive) { Copie-Element (Join-Path $root "archive\lowi-archive.db") (Join-Path $etat "lowi-archive.db") "archive/lowi-archive.db" }

# ------------------------------------------------------------- 4. Secrets
Write-Host "`n[4/5] Secrets"
if ($AvecSecrets) {
    $sec = Join-Path $colis "secrets"
    New-Dossier $sec
    Copie-Element (Join-Path $root ".env.local") (Join-Path $sec "env.local") ".env.local"
    Copie-Element (Join-Path $root "scraper\.env") (Join-Path $sec "scraper.env") "scraper/.env"
    Write-Host "  !! Le colis contient des identifiants Supabase en clair."
    Write-Host "     Transport par support physique, suppression du colis apres import."
}
else {
    Write-Host "  -  ignores (relancer avec -AvecSecrets)."
    Write-Host "     .env.local et scraper/.env sont OBLIGATOIRES cote 2e poste :"
    Write-Host "     sans SUPABASE_DB_URL le scrap n'ecrit nulle part."
    $inv.absents += ".env.local (non demande)"
    $inv.absents += "scraper/.env (non demande)"
}

# ------------------------------------------------- 5. Taches Windows (ref)
Write-Host "`n[5/5] Taches Windows (export de reference)"
$tdir = Join-Path $colis "taches-windows"
New-Dossier $tdir
$n = 0
foreach ($t in (Get-ScheduledTask -TaskName "LowiBKK-*" -ErrorAction SilentlyContinue)) {
    $xml = Export-ScheduledTask -TaskName $t.TaskName
    $f = Join-Path $tdir "$($t.TaskName).xml"
    [System.IO.File]::WriteAllText($f, $xml, [System.Text.Encoding]::UTF8)
    $i = $t | Get-ScheduledTaskInfo
    Write-Host ("  OK {0}  (etat {1}, dernier {2})" -f $t.TaskName, $t.State, $i.LastRunTime)
    $inv.elements += [ordered]@{ etiquette = "tache $($t.TaskName)"; etat = "$($t.State)"; dernier_run = "$($i.LastRunTime)" }
    $n++
}
Write-Host "  $n tache(s) exportee(s) - REFERENCE SEULEMENT."
Write-Host "  La reinstallation passe par ops\install-agents-task.ps1 et"
Write-Host "  ops\install-boot-task.ps1, qui derivent leurs chemins de leur"
Write-Host "  propre emplacement. Reimporter le XML figerait les chemins de"
Write-Host "  l'ancienne machine - c'est exactement le defaut du 2026-07-11."

# ------------------------------------------------------------- inventaire
$inv | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $colis "inventaire.json") -Encoding UTF8

$taille = (Get-ChildItem $colis -Recurse -File | Measure-Object -Sum Length).Sum
Write-Host ("`nColis pret : {0}" -f $colis)
Write-Host ("Taille     : {0:N1} Mo" -f ($taille / 1MB))
if ($inv.absents.Count) {
    Write-Host "`nAbsents du colis :"
    $inv.absents | ForEach-Object { Write-Host "   - $_" }
}
Write-Host "`nEtape suivante, sur le 2e poste, depot deja clone :"
Write-Host "  powershell -NoProfile -ExecutionPolicy Bypass -File ops\migration\importe-poste.ps1 -Colis <chemin du colis>"

# importe-poste.ps1 - reinstalle le colis sur le 2e poste.
#
# A LANCER DEPUIS LE DEPOT DEJA CLONE sur la nouvelle machine :
#   git clone https://github.com/Erok-gg/lowi_bkk.git
#   cd lowi_bkk
#   powershell -NoProfile -ExecutionPolicy Bypass -File ops\migration\importe-poste.ps1 -Colis D:\lowi-transfert-2026-08-21
#
# PRINCIPE : ne rien ecraser en silence. Tout element deja present est
# SIGNALE et laisse en place ; -Ecraser force le remplacement apres sauvegarde
# horodatee. Un import qui detruit un ledger deja peuple couterait un cycle de
# scrap complet en --full.
#
# CE QUE CE SCRIPT NE PEUT PAS FAIRE, et qu'il faut faire a la main ensuite :
#   - "claude login" : les connecteurs (Supabase, Gmail, Drive, Vercel, Agenda)
#     sont lies au compte, pas a la machine. Aucun fichier ne les porte.
#   - Les routines Claude planifiees (drain-agent-queue, rapport mensuel, veille)
#     vivent cote serveur Claude : elles tournent deja, independamment du poste.
#     Ne PAS les recreer, sous peine de doublon.
#   - Reconstruire les dependances : voir le rapport de fin.

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Colis,
    [switch]$Ecraser,
    [switch]$SansTaches
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

if (-not (Test-Path $Colis)) { throw "Colis introuvable : $Colis" }
$manifeste = Join-Path $Colis "inventaire.json"
if (-not (Test-Path $manifeste)) { throw "inventaire.json absent : $Colis n'est pas un colis produit par exporte-poste.ps1" }

$inv = Get-Content $manifeste -Raw -Encoding UTF8 | ConvertFrom-Json
Write-Host "Colis genere le $($inv.genere_le) sur $($inv.machine) (utilisateur $($inv.utilisateur))"
Write-Host "Racine d'origine : $($inv.racine)"
Write-Host "Racine cible     : $root`n"

$rapport = @()
$aFaire = @()

function New-Dossier([string]$p) {
    if (-not (Test-Path $p)) { New-Item -ItemType Directory -Path $p -Force | Out-Null }
}

function Pose-Element {
    param([string]$Source, [string]$Cible, [string]$Etiquette)
    if (-not (Test-Path $Source)) {
        Write-Host "  -  pas dans le colis : $Etiquette"
        return
    }
    if ((Test-Path $Cible) -and -not $Ecraser) {
        Write-Host "  =  deja present, laisse en place : $Etiquette"
        $script:rapport += "laisse : $Etiquette"
        return
    }
    if (Test-Path $Cible) {
        $bak = "$Cible.avant-import-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
        Move-Item $Cible $bak -Force
        Write-Host "  ~  sauvegarde de l'existant -> $(Split-Path -Leaf $bak)"
    }
    New-Dossier (Split-Path -Parent $Cible)
    Copy-Item $Source $Cible -Recurse -Force
    Write-Host "  OK $Etiquette"
    $script:rapport += "pose : $Etiquette"
}

# ---------------------------------------------------------------- 1. Claude
Write-Host "[1/5] Configuration et memoire de Claude"
$claudeHome = Join-Path $env:USERPROFILE ".claude"
New-Dossier $claudeHome
$src = Join-Path $Colis "claude"

Pose-Element (Join-Path $src "settings.json") (Join-Path $claudeHome "settings.json") "~/.claude/settings.json"
Pose-Element (Join-Path $src "projet-settings.local.json") (Join-Path $root ".claude\settings.local.json") ".claude/settings.local.json (permissions)"
Pose-Element (Join-Path $src "projet-launch.json") (Join-Path $root ".claude\launch.json") ".claude/launch.json"
Pose-Element (Join-Path $src "skills") (Join-Path $claudeHome "skills") "skills utilisateur"

# Le dossier de memoire porte le chemin du projet dans son NOM. On le recalcule
# pour CETTE machine : si l'utilisateur ou le chemin different, reutiliser le nom
# d'origine deposerait la memoire dans un dossier que Claude n'ouvrira jamais.
$cle = ($root.ToCharArray() | ForEach-Object { if ($_ -match '[A-Za-z0-9]') { $_ } else { '-' } }) -join ''
$cibleMem = Join-Path $claudeHome "projects\$cle\memory"
$cleOrig = ($inv.racine.ToCharArray() | ForEach-Object { if ($_ -match '[A-Za-z0-9]') { $_ } else { '-' } }) -join ''
if ($cle -ne $cleOrig) {
    Write-Host "  i  cle de projet recalculee : $cleOrig -> $cle"
}
Pose-Element (Join-Path $src "memory") $cibleMem "memoire du projet ($cle)"

# scheduled-tasks : copie de REFERENCE seulement. Les routines tournent cote
# serveur Claude et sont deja actives ; les reposer ici ne les recreerait pas et
# les recreer a la main ferait doublon.
if (Test-Path (Join-Path $src "scheduled-tasks")) {
    $refDir = Join-Path $Colis "claude\scheduled-tasks"
    $noms = (Get-ChildItem $refDir -Directory | Select-Object -ExpandProperty Name) -join ', '
    Write-Host "  i  routines Claude cote serveur (NE PAS recreer) : $noms"
}

# ------------------------------------------------------- 2. Etat des agents
Write-Host "`n[2/5] Etat d'execution des agents"
$etat = Join-Path $Colis "etat"

Pose-Element (Join-Path $etat "ledger.db") (Join-Path $root "agents\ledger.db") "agents/ledger.db"
foreach ($suf in @("-wal", "-shm")) {
    $f = Join-Path $etat "ledger.db$suf"
    if (Test-Path $f) { Copy-Item $f (Join-Path $root "agents\ledger.db$suf") -Force }
}
Pose-Element (Join-Path $etat "state") (Join-Path $root "agents\state") "agents/state"
Pose-Element (Join-Path $etat "queue") (Join-Path $root "agents\queue") "agents/queue"
Pose-Element (Join-Path $etat "audits") (Join-Path $root "agents\audits") "agents/audits"
Pose-Element (Join-Path $etat "widget-config.json") (Join-Path $root "ops\widget\config.json") "ops/widget/config.json"
Pose-Element (Join-Path $etat "geocode-cache.json") (Join-Path $root "scraper\output\geocode-cache.json") "cache Nominatim"
Pose-Element (Join-Path $etat "bangkok.db") (Join-Path $root "scraper\output\bangkok.db") "store SQLite local"
Pose-Element (Join-Path $etat "lowi-archive.db") (Join-Path $root "archive\lowi-archive.db") "archive/lowi-archive.db"
New-Dossier (Join-Path $root "agents\logs")
New-Dossier (Join-Path $root "ops\logs")

# ------------------------------------------------------------- 3. Secrets
Write-Host "`n[3/5] Secrets"
$sec = Join-Path $Colis "secrets"
if (Test-Path $sec) {
    Pose-Element (Join-Path $sec "env.local") (Join-Path $root ".env.local") ".env.local"
    Pose-Element (Join-Path $sec "scraper.env") (Join-Path $root "scraper\.env") "scraper/.env"
    Write-Host "  !! Supprimer le colis apres verification : il porte des identifiants en clair."
}
else {
    Write-Host "  -  aucun secret dans le colis."
    $aFaire += "Copier .env.local et scraper/.env a la main (SUPABASE_DB_URL, cles Storage) - sans eux le scrap n'ecrit nulle part."
}

# ------------------------------------------------------- 4. Prerequis
Write-Host "`n[4/5] Prerequis de la machine"
$py = Join-Path $root "scraper\.venv\Scripts\python.exe"
if (Test-Path $py) {
    $v = & $py --version 2>&1
    Write-Host "  OK venv Python : $v"
}
else {
    Write-Host "  !  venv Python absent"
    $aFaire += "Creer le venv : python -m venv scraper\.venv puis scraper\.venv\Scripts\pip install -r scraper\requirements.txt"
}
foreach ($outil in @("git", "node", "npm")) {
    $c = Get-Command $outil -ErrorAction SilentlyContinue
    if ($c) { Write-Host "  OK $outil : $($c.Source)" }
    else { Write-Host "  !  $outil introuvable"; $aFaire += "Installer $outil" }
}
if (-not (Test-Path (Join-Path $root "node_modules"))) {
    $aFaire += "npm ci (dependances Next.js)"
}
$claude = Get-Command claude -ErrorAction SilentlyContinue
if ($claude) { Write-Host "  OK claude CLI : $($claude.Source)" }
else { Write-Host "  !  claude CLI introuvable"; $aFaire += "Installer Claude Code puis 'claude login' (c'est ce login qui ramene les connecteurs)" }

# T1 : on SONDE, on ne suppose pas. Le marqueur est pose seulement si Ollama ne
# repond pas - sinon un poste qui a bien son modele basculerait en tickets pour
# rien. Sans ce marqueur, l'absence d'Ollama se lit comme une panne et
# ask_safe journalise jusqu'a 6 constats de severite HAUTE par cycle,
# quotidiennement (agents/core/local_llm.py, garde-fou de la regle 2).
$marqueur = Join-Path $root "agents\t1-absent"
$ollama = $false
try {
    $r = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -TimeoutSec 3 -UseBasicParsing
    if ($r.StatusCode -eq 200) { $ollama = $true }
}
catch { $ollama = $false }

if ($ollama) {
    Write-Host "  OK Ollama repond sur ce poste - T1 local conserve"
    if (Test-Path $marqueur) {
        Remove-Item $marqueur -Force
        Write-Host "  ~  marqueur agents/t1-absent retire (le modele est la)"
    }
}
else {
    Set-Content $marqueur "Ce poste n'heberge aucun modele local. organize depose ses paires en ticket.`nPose par ops\migration\importe-poste.ps1 le $(Get-Date -Format 'yyyy-MM-dd').`n" -Encoding UTF8
    Write-Host "  i  Ollama injoignable -> marqueur agents/t1-absent pose."
    Write-Host "     organize deposera ses paires dans agents/queue/ (lots de 60),"
    Write-Host "     drainees par la routine drain-agent-queue-lowi-bkk."
    $aFaire += "Verifier au 1er cycle qu'un ticket 'comparaison_deleguee' apparait dans agents\queue\"
}

# ------------------------------------------------------- 5. Taches Windows
Write-Host "`n[5/5] Taches Windows"
if ($SansTaches) {
    Write-Host "  -  ignore (-SansTaches)."
    $aFaire += "Enregistrer les taches : ops\install-agents-task.ps1 et ops\install-boot-task.ps1"
}
else {
    foreach ($s in @("install-agents-task.ps1", "install-boot-task.ps1")) {
        $f = Join-Path $root "ops\$s"
        if (-not (Test-Path $f)) { Write-Host "  !  $s introuvable"; continue }
        Write-Host "  -> $s"
        try {
            & powershell -NoProfile -ExecutionPolicy Bypass -File $f
            Write-Host "  OK $s"
        }
        catch {
            Write-Host "  !  echec de $s : $_"
            $aFaire += "Relancer ops\$s en console administrateur"
        }
    }
    Get-ScheduledTask -TaskName "LowiBKK-*" -ErrorAction SilentlyContinue | ForEach-Object {
        $i = $_ | Get-ScheduledTaskInfo
        Write-Host ("     {0,-28} {1,-10} prochain : {2}" -f $_.TaskName, $_.State, $i.NextRunTime)
    }
}

# ------------------------------------------------------------- rapport
Write-Host "`n=============== RAPPORT ==============="
Write-Host "$($rapport.Count) element(s) traite(s)."

$aFaire += "claude login (ramene les connecteurs de compte : Supabase, Gmail, Drive, Vercel, Agenda)"
$aFaire += "Verifier l'etat : scraper\.venv\Scripts\python.exe agents\orchestrator.py status"
$aFaire += "Repondre au 1er ticket de comparaison et appliquer : python -m agents.bots.organize --appliquer <reponses.json> (voir ops\migration\README.md, section T1)"
$aFaire += "Eteindre les taches LowiBKK-* de l'ANCIEN poste, sinon les deux machines scrapent en parallele."

Write-Host "`nRESTE A FAIRE A LA MAIN :"
$i = 1
foreach ($t in $aFaire) { Write-Host "  $i. $t"; $i++ }

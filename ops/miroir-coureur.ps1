# miroir-coureur.ps1 - rapatrier l'etat du COUREUR sur le poste de controle.
#
# POURQUOI CE SCRIPT EXISTE
# Depuis le 2026-08-21, un seul poste execute le cycle (le COUREUR, remidaboss)
# et detient le ledger, les audits, la file de tickets et l'archive. L'autre
# poste lit les memes DONNEES (Supabase, commun) mais ne voit RIEN de
# l'execution : ni si le cycle a tourne, ni ce que les agents ont constate.
#
# Ce script transporte cet etat, dans UN SEUL SENS : coureur -> controle.
#
# POURQUOI PAS UNE SYNCHRO BIDIRECTIONNELLE
# ledger.db est du SQLite en WAL, ecrit en continu ; agents/state/*.txt sont des
# journaux en ajout seul ; agents/state/organize.lock est un verrou. Deux
# ecrivains sur ces fichiers, c'est des lignes perdues et des bases tronquees.
# Et surtout : le ledger est la source unique de "ce qui est du". Deux
# exemplaires vivants, c'est deux is_due() qui divergent, donc deux machines qui
# scrapent les 5 memes sources.
#
# D'ou le depot dans ops\miroir\ (gitignore) et JAMAIS dans agents\ : le miroir
# ne peut pas etre confondu avec l'etat reel du poste qui le lit.
#
# Usage :
#   SUR LE COUREUR (PC2), vers une cle USB ou un dossier partage :
#     powershell -File ops\miroir-coureur.ps1 -Exporter E:\miroir
#
#   SUR LE POSTE DE CONTROLE (PC1) :
#     powershell -File ops\miroir-coureur.ps1 -Importer E:\miroir
#
#   Puis, pour la vue complete depuis le poste de controle :
#     scraper\.venv\Scripts\python.exe ops\verifie-synchro.py --ledger ops\miroir\ledger.db
#
#   -AvecArchive  ajoute archive\lowi-archive.db (708 Mo) - a ne faire que
#                 ponctuellement, pas a chaque rapatriement.

[CmdletBinding(DefaultParameterSetName = 'Exporter')]
param(
    [Parameter(ParameterSetName = 'Exporter', Mandatory = $true)][string]$Exporter,
    [Parameter(ParameterSetName = 'Importer', Mandatory = $true)][string]$Importer,
    [switch]$AvecArchive
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

function New-Dossier([string]$p) {
    if (-not (Test-Path $p)) { New-Item -ItemType Directory -Path $p -Force | Out-Null }
}

# ═══════════════════════════════════════════════════ EXPORT (sur le coureur)
if ($PSCmdlet.ParameterSetName -eq 'Exporter') {
    New-Dossier $Exporter
    Write-Host "Coureur : $env:COMPUTERNAME"
    Write-Host "Miroir  : $Exporter`n"

    # ledger.db est en WAL : une copie brute du seul .db perdrait les dernieres
    # transactions, restees dans le -wal. API backup de sqlite, comme l'export
    # de migration.
    $ledger = Join-Path $root "agents\ledger.db"
    $py = Join-Path $root "scraper\.venv\Scripts\python.exe"
    if ((Test-Path $ledger) -and (Test-Path $py)) {
        $dst = Join-Path $Exporter "ledger.db"
        $code = "import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.close(); s.close()"
        & $py -c $code $ledger $dst
        if ($LASTEXITCODE -eq 0) {
            Write-Host ("  OK ledger.db  ({0:N0} Ko, copie coherente)" -f ((Get-Item $dst).Length / 1KB))
        }
        else { Write-Host "  !! echec de la copie sqlite du ledger" }
    }
    else { Write-Host "  !! ledger.db ou le venv est introuvable - ce poste est-il bien le coureur ?" }

    foreach ($paire in @(
            @{ src = "agents\audits"; dst = "audits"; quoi = "audits lisibles" },
            @{ src = "agents\queue"; dst = "queue"; quoi = "file de tickets" },
            @{ src = "docs\etudes"; dst = "etudes"; quoi = "editions d'etude" },
            # Les snapshots sont la MEMOIRE LONGUE : run_study.py construit ses
            # tables d'evolution sur toute la serie anterieure. S'ils ne vivent
            # que sur le disque du coureur, une panne de disque efface l'histoire
            # et les tables d'evolution repartent de zero. Le miroir en est la
            # seconde copie - c'est peu volumineux et ca ne se refabrique pas.
            @{ src = "study\snapshots"; dst = "snapshots"; quoi = "snapshots (memoire longue)" })) {
        $s = Join-Path $root $paire.src
        if (Test-Path $s) {
            $d = Join-Path $Exporter $paire.dst
            if (Test-Path $d) { Remove-Item $d -Recurse -Force }
            Copy-Item $s $d -Recurse -Force
            $n = (Get-ChildItem $d -Recurse -File | Measure-Object).Count
            Write-Host "  OK $($paire.quoi)  ($n fichiers)"
        }
    }

    $revue = Join-Path $root "agents\state\organize\revue.jsonl"
    if (Test-Path $revue) {
        Copy-Item $revue (Join-Path $Exporter "revue.jsonl") -Force
        $n = (Get-Content $revue | Measure-Object -Line).Lines
        Write-Host "  OK file de revue  ($n entree(s))"
    }

    if ($AvecArchive) {
        $ar = Join-Path $root "archive\lowi-archive.db"
        if (Test-Path $ar) {
            Write-Host "  .. copie de l'archive (708 Mo), patienter"
            Copy-Item $ar (Join-Path $Exporter "lowi-archive.db") -Force
            Write-Host "  OK archive"
        }
    }

    # Le miroir doit dire D'OU il vient et DE QUAND il date. Sans ca, on lit un
    # etat perime en le croyant frais - exactement le defaut que ce dispositif
    # cherche a eviter.
    $infos = [ordered]@{
        coureur    = $env:COMPUTERNAME
        exporte_le = (Get-Date -Format "yyyy-MM-ddTHH:mm:sszzz")
        racine     = $root
        branche    = (git -C $root branch --show-current)
        commit     = (git -C $root log -1 --format="%h %s")
        non_commit = @(git -C $root status --short)
        avec_archive = [bool]$AvecArchive
    }
    $infos | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $Exporter "infos.json") -Encoding UTF8

    Write-Host "`nMiroir pret. Sur le poste de controle :"
    Write-Host "  powershell -File ops\miroir-coureur.ps1 -Importer <ce dossier>"
    if ($infos.non_commit.Count) {
        Write-Host "`n  ATTENTION : $($infos.non_commit.Count) fichier(s) non commite(s) sur le coureur."
        Write-Host "  Les etudes et snapshots ne parviendront a l'autre poste par git"
        Write-Host "  que s'ils sont commites et pousses. Rien ne le fait tout seul."
    }
    return
}

# ═══════════════════════════════════════════ IMPORT (sur le poste de controle)
if (-not (Test-Path (Join-Path $Importer "infos.json"))) {
    throw "infos.json absent : $Importer n'est pas un miroir produit par -Exporter"
}
$infos = Get-Content (Join-Path $Importer "infos.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$age = (New-TimeSpan -Start ([datetime]$infos.exporte_le) -End (Get-Date))

Write-Host "Miroir du coureur '$($infos.coureur)'"
Write-Host ("Exporte il y a {0:N1} h  ({1})" -f $age.TotalHours, $infos.exporte_le)
Write-Host "Commit du coureur : $($infos.commit)`n"
if ($age.TotalHours -gt 30) {
    Write-Host "  ATTENTION : ce miroir a plus de 30 h. Il ne reflete pas le dernier cycle.`n"
}

$cible = Join-Path $root "ops\miroir"
New-Dossier $cible
foreach ($item in (Get-ChildItem $Importer)) {
    $d = Join-Path $cible $item.Name
    if (Test-Path $d) { Remove-Item $d -Recurse -Force }
    Copy-Item $item.FullName $d -Recurse -Force
}
Write-Host "  Depose dans ops\miroir\ (gitignore, jamais dans agents\)"

# ------------------------------------------------- resume immediat du ledger
$py = Join-Path $root "scraper\.venv\Scripts\python.exe"
$ledger = Join-Path $cible "ledger.db"
if ((Test-Path $py) -and (Test-Path $ledger)) {
    # Le code Python part dans un FICHIER, pas en -c : PowerShell reecrit les
    # guillemets quand il passe une chaine a un executable natif, et le script
    # arrivait tronque ("SyntaxError: ( was never closed"). Trouve en testant.
    $codeFile = Join-Path $env:TEMP "lowi-miroir-resume.py"
    $code = @'
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
runs = c.execute("select agent, started_at, status from agent_runs order by id desc limit 400").fetchall()
if not runs:
    print("  aucun run dans le miroir")
    raise SystemExit
print(f"  Dernier run        : {runs[0][1][:16]} UTC")
vus, ko = {}, []
for ag, st, stt in runs:
    if ag not in vus:
        vus[ag] = (st, stt)
        if stt != "ok":
            ko.append(f"{ag} ({stt})")
print(f"  Agents distincts   : {len(vus)}")
print("  En echec           : " + (", ".join(ko) if ko else "aucun"))
n = c.execute("select count(distinct agent||subject) from findings "
              "where severity='high' and created_at >= datetime('now','-7 day')").fetchone()[0]
print(f"  Sujets de severite haute (7 j) : {n}")
esc = c.execute("select count(*) from escalations where resolved_at is null").fetchone()[0]
print(f"  Escalades ouvertes : {esc}")
'@
    Set-Content -Path $codeFile -Value $code -Encoding UTF8
    Write-Host "`n--- Etat du cycle, lu dans le miroir ---"
    & $py $codeFile $ledger
    Remove-Item $codeFile -Force -ErrorAction SilentlyContinue
}

$q = Join-Path $cible "queue"
if (Test-Path $q) {
    $t = @(Get-ChildItem $q -Filter *.json -File)
    $comp = @($t | Where-Object { $_.Name -like "*comparaison_deleguee*" })
    Write-Host "`n  Tickets en attente : $($t.Count)$(if ($comp.Count) { " (dont $($comp.Count) de comparaison deleguee)" })"
}

Write-Host "`nVue complete depuis ce poste :"
Write-Host "  scraper\.venv\Scripts\python.exe ops\verifie-synchro.py --ledger ops\miroir\ledger.db"

# sync-archive.ps1 — wrapper planifié : réplique Supabase en local puis purge le serveur
# (rétention 90 j, copies vérifiées). Journalise dans ops/logs/.
# Tâche Windows : "LowiBKK-ArchiveSync" (hebdo, dimanche 21:00). Supprimer :
#   schtasks /Delete /TN "LowiBKK-ArchiveSync" /F
$root = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir ("sync-{0}.log" -f (Get-Date -Format "yyyy-MM-dd"))
& (Join-Path $root "scraper\.venv\Scripts\python.exe") (Join-Path $PSScriptRoot "sync_supabase_local.py") --prune *>> $log
"exit=$LASTEXITCODE" | Add-Content $log
# rotation simple : garde 26 logs
Get-ChildItem $logDir -Filter "sync-*.log" | Sort-Object Name -Descending | Select-Object -Skip 26 | Remove-Item -Force

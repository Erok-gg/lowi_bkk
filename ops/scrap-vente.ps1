# scrap-vente.ps1 — Journée VENTE (tâche Windows "LowiBKK-ScrapVente", tous les 4 jours, 08:00)
# Ordre important : scan global --full PUIS passe ciblée couloirs (restaure les annonces
# des districts ciblés que la fenêtre 150 pages du scan global aurait délistées à tort —
# touch/upsert les repasse en active avec images).
# Supprimer la tâche : schtasks /Delete /TN "LowiBKK-ScrapVente" /F
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root "scraper\.venv\Scripts\python.exe"
$run = Join-Path $root "scraper\run.py"
$logDir = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir ("scrap-vente-{0}.log" -f (Get-Date -Format "yyyy-MM-dd"))

"=== VENTE $(Get-Date) ===" | Add-Content $log
& $py $run --source fazwaz --deal-type sale --full --store supabase *>> $log
"--- fazwaz sale exit=$LASTEXITCODE ---" | Add-Content $log
& $py $run --source fazwaz --config config/targets/fazwaz-corridors.json --store supabase *>> $log
"--- fazwaz corridors (restauration) exit=$LASTEXITCODE ---" | Add-Content $log
& $py $run --source ddproperty --deal-type sale --full --geocode --store supabase *>> $log
"--- ddproperty sale exit=$LASTEXITCODE ---" | Add-Content $log
"=== FIN $(Get-Date) ===" | Add-Content $log
Get-ChildItem $logDir -Filter "scrap-vente-*.log" | Sort-Object Name -Descending | Select-Object -Skip 15 | Remove-Item -Force

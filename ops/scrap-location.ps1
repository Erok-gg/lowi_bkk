# scrap-location.ps1 — Journée LOCATION (tâche Windows "LowiBKK-ScrapLocation", tous les 4 jours, 08:00)
# Location sur les 2 grosses sources + PropertyScout/Nestopa complets (petites sources,
# les 2 deal_types), passes ciblées couloirs en restauration, puis ÉTUDE framework
# (les 2 deal_types sont alors frais de ≤4 jours → snapshot + rapport + exports).
# Supprimer la tâche : schtasks /Delete /TN "LowiBKK-ScrapLocation" /F
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root "scraper\.venv\Scripts\python.exe"
$run = Join-Path $root "scraper\run.py"
$logDir = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir ("scrap-location-{0}.log" -f (Get-Date -Format "yyyy-MM-dd"))

"=== LOCATION $(Get-Date) ===" | Add-Content $log
& $py $run --source fazwaz --deal-type rent --full --store supabase *>> $log
"--- fazwaz rent exit=$LASTEXITCODE ---" | Add-Content $log
& $py $run --source fazwaz --config config/targets/fazwaz-corridors.json --store supabase *>> $log
"--- fazwaz corridors (restauration) exit=$LASTEXITCODE ---" | Add-Content $log
& $py $run --source ddproperty --deal-type rent --full --geocode --store supabase *>> $log
"--- ddproperty rent exit=$LASTEXITCODE ---" | Add-Content $log
& $py $run --source ddproperty --config config/targets/ddproperty-corridors.json --store supabase *>> $log
"--- ddproperty corridors (restauration) exit=$LASTEXITCODE ---" | Add-Content $log
& $py $run --source propertyscout --full --store supabase *>> $log
"--- propertyscout exit=$LASTEXITCODE ---" | Add-Content $log
& $py $run --source nestopa --full --geocode --store supabase *>> $log
"--- nestopa exit=$LASTEXITCODE ---" | Add-Content $log

# Étude framework sur données fraîches (snapshot + rapport + CSV/xlsx)
& $py (Join-Path $root "study\run_study.py") *>> $log
"--- run_study exit=$LASTEXITCODE ---" | Add-Content $log
"=== FIN $(Get-Date) ===" | Add-Content $log
Get-ChildItem $logDir -Filter "scrap-location-*.log" | Sort-Object Name -Descending | Select-Object -Skip 15 | Remove-Item -Force

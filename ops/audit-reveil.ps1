# audit-reveil.ps1 - Le poste peut-il se reveiller pour son cycle de 01:00 ?
#
# POURQUOI CE SCRIPT
# Trois nuits d'affilee (23, 24, 25 aout 2026) le cycle n'est pas parti a 01:00 :
# il a toujours ete rattrape plus tard par StartWhenAvailable. La cause n'a pas
# ete etablie. Le reveil depend de SIX conditions independantes, dont deux ne se
# lisent qu'en console admin ; les verifier une par une a la main, c'est en
# oublier une. D'ou ce script : il les affiche toutes, et dit ce qui manque.
#
# Lecture seule - ne modifie AUCUN reglage. Les commandes correctives sont
# imprimees a la fin, jamais executees : la valeur batterie en particulier est
# un arbitrage (reveiller sur batterie = vider la batterie en scrapant 6 h).
#
# Lancement : powershell -NoProfile -ExecutionPolicy Bypass -File ops\audit-reveil.ps1

$TACHE = 'LowiBKK-Agents'
function Ligne($etiquette, $valeur, $ok) {
  $couleur = if ($null -eq $ok) { 'Gray' } elseif ($ok) { 'Green' } else { 'Red' }
  Write-Host ("  {0,-46} " -f $etiquette) -NoNewline
  Write-Host $valeur -ForegroundColor $couleur
}

Write-Host "`n=== AUDIT DU REVEIL - $env:COMPUTERNAME - $(Get-Date -Format 'dd/MM/yyyy HH:mm') ===`n"

# 1. Source d'alimentation. Determinante : les reglages qui suivent ont DEUX
#    valeurs, secteur et batterie, et c'est la valeur batterie qui bloque ici.
$batt = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue
$surSecteur = (-not $batt) -or ($batt.BatteryStatus -ne 1)
$srcTxt = if (-not $batt) { 'poste fixe (toujours secteur)' }
          elseif ($surSecteur) { "SECTEUR (batterie a $($batt.EstimatedChargeRemaining) %)" }
          else { "BATTERIE ($($batt.EstimatedChargeRemaining) %)" }
Ligne 'Alimentation actuelle' $srcTxt $surSecteur

# 2. Les trois reglages du plan qui decident. On lit les DEUX index a chaque
#    fois : ne lire que le secteur etait le defaut corrige le 2026-08-22.
function Idx($guid) {
  $v = @(powercfg /q SCHEME_CURRENT SUB_SLEEP $guid | Select-String 'Index actuel')
  if ($v.Count -lt 2) { return @($null, $null) }
  return @(($v[0] -replace '.*:\s*',''), ($v[1] -replace '.*:\s*',''))
}
$rtc  = Idx 'bd3b718a-0680-4d9d-8ab2-e1d2b4ac806d'   # minuteurs de reveil
$idle = Idx '29f6c1db-86da-48c5-9fdb-f2b67b1f44da'   # veille par inactivite
$rtcAC = [int]$rtc[0]; $rtcDC = [int]$rtc[1]
Ligne 'Minuteurs de reveil - SECTEUR' "$($rtc[0]) (1 = autorise)" ($rtcAC -ge 1)
Ligne 'Minuteurs de reveil - BATTERIE' "$($rtc[1]) (1 = autorise)" ($rtcDC -ge 1)
Ligne 'Veille par inactivite - SECTEUR' ("{0} s" -f [int]$idle[0]) $null
Ligne 'Veille par inactivite - BATTERIE' ("{0} s" -f [int]$idle[1]) $null

# 3. La tache elle-meme.
$t = Get-ScheduledTask -TaskName $TACHE -ErrorAction SilentlyContinue
if (-not $t) {
  Ligne "Tache $TACHE" 'INTROUVABLE' $false
} else {
  $info = Get-ScheduledTaskInfo -TaskName $TACHE
  $args = ($t.Actions | Select-Object -First 1).Arguments
  $decl = ($t.Triggers | Select-Object -First 1).StartBoundary
  Ligne 'Tache - etat' $t.State ($t.State -eq 'Ready')
  Ligne 'Tache - WakeToRun (reveille la machine)' $t.Settings.WakeToRun $t.Settings.WakeToRun
  Ligne 'Tache - refuse de partir sur batterie' $t.Settings.DisallowStartIfOnBatteries (-not $t.Settings.DisallowStartIfOnBatteries)
  Ligne 'Tache - stoppe si passage sur batterie' $t.Settings.StopIfGoingOnBatteries (-not $t.Settings.StopIfGoingOnBatteries)
  Ligne 'Tache - heure declenchement' $decl $null
  Ligne 'Tache - prochain passage' $info.NextRunTime $null
  Ligne 'Tache - dernier depart REEL' $info.LastRunTime $null
  Ligne 'Tache - se rendort a la fin' ($args -match '--veille-a-la-fin') ($args -match '--veille-a-la-fin')
}

# 4. Ce qui permettra de DIAGNOSTIQUER la prochaine nuit ratee. Sans ce journal,
#    une nuit sans reveil ne laisse aucune trace exploitable - c'est ce qui a
#    rendu les trois nuits d'aout inexplicables.
$log = Get-WinEvent -ListLog 'Microsoft-Windows-TaskScheduler/Operational' -ErrorAction SilentlyContinue
Ligne 'Journal TaskScheduler operationnel' $(if ($log.IsEnabled) { 'active' } else { 'DESACTIVE (aucune trace)' }) $log.IsEnabled

# 5. Le dernier reveil constate, s'il y en a un.
Write-Host "`n  Dernier reveil enregistre :"
(powercfg /lastwake) | Where-Object { $_.Trim() } | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }

# 6. Verdict + ce qui reste hors de portee sans elevation.
Write-Host "`n=== VERDICT ==="
if ($surSecteur -and $rtcAC -ge 1) {
  Write-Host "  Sur SECTEUR : le reveil est autorise." -ForegroundColor Green
} elseif (-not $surSecteur -and $rtcDC -lt 1) {
  Write-Host "  Sur BATTERIE : le reveil est INTERDIT - la machine ne partira pas a 01:00." -ForegroundColor Red
}
if ([int]$idle[0] -eq 0) {
  Write-Host "  Sur secteur la machine ne s'endort jamais d'elle-meme : branchee, il n'y a" -ForegroundColor Gray
  Write-Host "  meme pas de reveil a faire. Un echec a 01:00 vient alors d'ailleurs" -ForegroundColor Gray
  Write-Host "  (capot ferme, arret, ou refus de la tache) - d'ou le journal du point 4." -ForegroundColor Gray
}
Write-Host "`n  A verifier en console ADMIN (impossible ici) :" -ForegroundColor Yellow
Write-Host "    powercfg /waketimers                                  # le minuteur est-il ARME ?"
Write-Host "    wevtutil sl Microsoft-Windows-TaskScheduler/Operational /e:true   # tracer la prochaine nuit"
Write-Host "`n  Pour autoriser le reveil SUR BATTERIE (arbitrage - vide la batterie" -ForegroundColor Yellow
Write-Host "  si un scrap de 6 h part sans le cable) :" -ForegroundColor Yellow
Write-Host "    powercfg /setdcvalueindex SCHEME_CURRENT SUB_SLEEP RTCWAKE 1; powercfg /setactive SCHEME_CURRENT"
Write-Host ""

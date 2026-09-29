# test-reveil.ps1 — preuve qu'un reveil programme fonctionne sur ce poste.
#
# POURQUOI CE SCRIPT EXISTE
# Nuit du 2026-08-25 : la machine ne s'est PAS reveillee a 01:00 pour son cycle,
# alors qu'elle etait sur secteur (aucun changement de source d'alimentation en
# 3 jours), que le reveil RTC y est autorise (0x1) et que la tache porte bien
# WakeToRun. Aucune explication trouvee dans les journaux. Tant que ce n'est pas
# reproduit et mesure, « le reveil marche » reste une supposition.
#
# Ce script est appele par une tache jetable (LowiBKK-TestReveil) : il ecrit
# l'heure exacte de son declenchement et l'etat d'alimentation dans un temoin.
param([string]$Temoin = "C:\Lowi_bkk\ops\logs\test-reveil.jsonl")

New-Item -ItemType Directory -Force -Path (Split-Path $Temoin) | Out-Null
$batt = (Get-CimInstance Win32_Battery | Select-Object -First 1).BatteryStatus
$ligne = [pscustomobject]@{
  declenche_a   = (Get-Date).ToString('o')
  alimentation  = if ($batt -eq 1) { 'batterie' } else { 'secteur' }
  # 107 = reprise de veille. S'il y en a un dans la minute, c'est bien un
  # REVEIL qui a lance la tache, et non une tache lancee machine deja eveillee.
  reveil_recent = [bool](Get-WinEvent -FilterHashtable @{
      LogName='System'; ProviderName='Microsoft-Windows-Kernel-Power'; Id=107;
      StartTime=(Get-Date).AddMinutes(-2)} -ErrorAction SilentlyContinue)
}
$ligne | ConvertTo-Json -Compress | Add-Content -Path $Temoin -Encoding utf8

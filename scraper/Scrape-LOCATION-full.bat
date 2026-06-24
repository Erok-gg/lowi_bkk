@echo off
REM ============================================================
REM  FULL SCRAP - LOCATION (rent) - 4 sources, vers Supabase
REM  Double-clique ce fichier. La fenetre reste ouverte a la fin.
REM  Empeche la veille systeme pendant le scrap (l'ecran peut s'eteindre),
REM  puis remet les conditions d'origine a la fin.
REM  A lancer un jour different du scrap VENTE (anti-ban).
REM ============================================================
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0_run-scrape.ps1" -Deal rent
pause

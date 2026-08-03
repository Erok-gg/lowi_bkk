@echo off
REM ============================================================
REM  LOWI BKK - Dashboard de supervision du scrap
REM  Double-clique ce fichier. Lecture seule : aucun impact
REM  sur un scrap en cours.
REM    F = plein ecran   R = rafraichir   S = changer de source
REM    Q / Echap = quitter
REM ============================================================
cd /d "%~dp0.."
REM Ouverture en FENETRE 1920x1080. Touche F pour basculer en plein ecran.
start "" "%~dp0..\scraper\.venv\Scripts\pythonw.exe" "%~dp0dashboard.py"

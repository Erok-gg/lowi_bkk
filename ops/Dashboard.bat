@echo off
REM ============================================================
REM  LOWI BKK - Dashboard du scrap EN COURS
REM  Double-clique ce fichier. Lecture seule : aucun impact
REM  sur un scrap en cours.
REM    F = plein ecran   R = rafraichir   Q / Echap = quitter
REM  Une seule base : scraper\output\bangkok.db (celle du cycle).
REM  Pas de rotation de sources - cf. en-tete de ops\dashboard.py.
REM ============================================================
cd /d "%~dp0.."
REM Ouverture en FENETRE 1920x1080. Touche F pour basculer en plein ecran.
start "" "%~dp0..\scraper\.venv\Scripts\pythonw.exe" "%~dp0dashboard.py"

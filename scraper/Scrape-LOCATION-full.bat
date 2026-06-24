@echo off
REM ============================================================
REM  FULL SCRAP - LOCATION (rent) - 4 sources, vers Supabase
REM  Double-clique ce fichier. La fenetre reste ouverte a la fin.
REM  A lancer un jour different du scrap VENTE (anti-ban).
REM ============================================================
cd /d "%~dp0"
set PY=.venv\Scripts\python.exe

if not exist "%PY%" (
  echo [ERREUR] Python du venv introuvable : %PY%
  echo Ouvre une invite dans ce dossier et fais : python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
  pause
  exit /b 1
)

set LOG=output\fullscrape-rent.log
echo ===== FULL SCRAP LOCATION - %DATE% %TIME% ===== > "%LOG%"

for %%S in (fazwaz ddproperty propertyscout nestopa) do (
  echo.
  echo ============================================================
  echo   SOURCE : %%S   ^(LOCATION^)
  echo ============================================================
  "%PY%" run.py --source %%S --deal-type rent --full --geocode --store supabase
  echo --- %%S termine ^(code %ERRORLEVEL%^) --- >> "%LOG%"
)

echo.
echo ===== TERMINE. Resume des runs dans %LOG% =====
pause

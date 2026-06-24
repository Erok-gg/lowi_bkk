@echo off
REM ============================================================
REM  TEST RAPIDE - 10 annonces vente FazWaz vers Supabase (~1 min)
REM  Sert juste a verifier que le double-clic fonctionne.
REM ============================================================
cd /d "%~dp0"
set PY=.venv\Scripts\python.exe

if not exist "%PY%" (
  echo [ERREUR] Python du venv introuvable : %PY%
  pause
  exit /b 1
)

echo --- TEST : fazwaz vente, 10 annonces ---
"%PY%" run.py --source fazwaz --deal-type sale --limit 10 --store supabase

echo.
echo ===== TEST TERMINE =====
pause

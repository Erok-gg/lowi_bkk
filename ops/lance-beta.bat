@echo off
rem Lance l'app Next en local (PC2) et ouvre le bilan beta dans le navigateur.
rem Port 3001 : le 3000 est souvent tenu par un autre "next dev" qui ne repond
rem plus (mesure le 2026-10-20 : 3000 muet 60 s, 3001 en 200 en 3 s).
rem Lit la base LOCALE (LOWI_SQLITE_DB de .env.local prime sur Supabase) :
rem ce n'est pas ce que voit le public.
setlocal
set PORT=3001
set URL=http://localhost:%PORT%/beta
cd /d C:\Lowi_bkk

rem Serveur deja lance sur ce port -> on ouvre juste la page, sans en
rem empiler un second (deux "next dev" sur le meme .next se marchent dessus).
netstat -ano | findstr /R /C:":%PORT% .*LISTENING" >nul
if %errorlevel%==0 (
  echo Serveur deja actif sur le port %PORT%.
  start "" "%URL%"
  "%SystemRoot%\System32\timeout.exe" /t 3 >nul
  exit /b 0
)

echo Demarrage du serveur sur %URL% ...
echo (fermer cette fenetre arrete le serveur)
rem Le navigateur s'ouvre apres 8 s : la 1re compilation de /beta prend
rem quelques secondes, la page se recharge d'elle-meme ensuite.
start "" /min cmd /c ""%SystemRoot%\System32\timeout.exe" /t 8 >nul & start "" "%URL%""
call npx next dev -p %PORT%
pause

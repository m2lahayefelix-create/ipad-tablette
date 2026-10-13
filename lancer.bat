@echo off
title Tablette iPad
cd /d "%~dp0pc"
:debut
python serveur.py %*
echo.
echo Le programme s'est arrete (capture d'ecran coupee par Windows ?). Redemarrage dans 2 s...
echo Ferme cette fenetre pour arreter.
timeout /t 2 /nobreak >nul
goto debut

@echo off
chcp 65001 >nul
setlocal
REM ============================================================
REM  HMD - Profil COMPTABLE / GESTION (Anissa)
REM  Lettres dediees : S: Support   P: Partage   D: Depot-Support
REM ============================================================
set SERVER=192.168.1.4

echo ================================================
echo   HMD - Profil COMPTABLE / GESTION
echo ================================================
echo.
set /p LOGIN=Votre identifiant (ex: anissa) :
echo.
echo Nettoyage des connexions existantes...
net use * /delete /y >nul 2>&1
echo Connexion (mot de passe demande une fois)...
net use S: \\%SERVER%\Support /user:%LOGIN% * /persistent:no
if errorlevel 1 goto erreur
net use P: \\%SERVER%\Partage /persistent:no >nul 2>&1
net use D: \\%SERVER%\Depot-Support /persistent:no >nul 2>&1
echo.
echo  OK ! Lecteurs :  S: (Support)   P: (Partage)   D: (Depot-Support)
echo.
goto fin

:erreur
echo.
echo  *** ECHEC. Verifiez identifiant et mot de passe. ***
echo.

:fin
pause
endlocal

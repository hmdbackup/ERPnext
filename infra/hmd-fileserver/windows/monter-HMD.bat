@echo off
chcp 65001 >nul
setlocal
REM ============================================================
REM  HMD - Montage du lecteur racine (tout l'espace autorise)
REM  Pour : staff + admin (pas les invites)
REM  Vous ne verrez que les dossiers auxquels vous avez droit.
REM ============================================================
set SERVER=192.168.1.4

echo ================================================
echo   HMD - Connexion au serveur de fichiers
echo ================================================
echo.
set /p LOGIN=Votre identifiant (ex: samir, anissa, yassine...) :
echo.
echo Nettoyage des connexions existantes vers %SERVER%...
net use * /delete /y >nul 2>&1
echo.
echo Connexion (le mot de passe sera demande une fois)...
net use H: \\%SERVER%\HMD /user:%LOGIN% * /persistent:no
if errorlevel 1 goto erreur
net use P: \\%SERVER%\Partage /persistent:no >nul 2>&1
echo.
echo  OK ! Lecteurs montes :
echo     H:  = votre espace HMD (vous ne voyez que vos dossiers autorises)
echo     P:  = Partage commun
echo.
goto fin

:erreur
echo.
echo  *** ECHEC de la connexion. Verifiez votre identifiant et mot de passe. ***
echo.

:fin
pause
endlocal

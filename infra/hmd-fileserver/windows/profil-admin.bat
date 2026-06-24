@echo off
chcp 65001 >nul
setlocal
REM ============================================================
REM  HMD - Profil ADMIN (Samir, Aziz)
REM  Lettres dediees : H: racine   T: IT   P: Partage
REM ============================================================
set SERVER=192.168.1.4

echo ================================================
echo   HMD - Profil ADMIN
echo ================================================
echo.
set /p LOGIN=Votre identifiant (samir ou aziz) :
echo.
echo Nettoyage des connexions existantes...
net use * /delete /y >nul 2>&1
echo Connexion (mot de passe demande une fois)...
net use H: \\%SERVER%\HMD /user:%LOGIN% * /persistent:no
if errorlevel 1 goto erreur
net use T: \\%SERVER%\IT /persistent:no >nul 2>&1
net use P: \\%SERVER%\Partage /persistent:no >nul 2>&1
echo.
echo  OK ! Lecteurs :  H: (tout HMD)   T: (IT)   P: (Partage)
echo.
goto fin

:erreur
echo.
echo  *** ECHEC. Verifiez identifiant et mot de passe. ***
echo.

:fin
pause
endlocal

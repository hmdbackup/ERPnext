@echo off
chcp 65001 >nul
setlocal
REM ============================================================
REM  HMD - Profil FROMAGERIE (Tawfiq)
REM  Lettres dediees : F: Fromagerie  P: Partage  D: Depot-Fromagerie
REM ============================================================
set SERVER=192.168.1.4

echo ================================================
echo   HMD - Profil FROMAGERIE
echo ================================================
echo.
set /p LOGIN=Votre identifiant (ex: tawfiq) :
echo.
echo Nettoyage des connexions existantes...
net use * /delete /y >nul 2>&1
echo Connexion (mot de passe demande une fois)...
net use F: \\%SERVER%\Fromagerie /user:%LOGIN% * /persistent:no
if errorlevel 1 goto erreur
net use P: \\%SERVER%\Partage /persistent:no >nul 2>&1
net use D: \\%SERVER%\Depot-Fromagerie /persistent:no >nul 2>&1
echo.
echo  OK ! Lecteurs :  F: (Fromagerie)   P: (Partage)   D: (Depot-Fromagerie)
echo.
goto fin

:erreur
echo.
echo  *** ECHEC. Verifiez identifiant et mot de passe. ***
echo.

:fin
pause
endlocal

@echo off
chcp 65001 >nul
setlocal
REM ============================================================
REM  HMD - Profil ELEVAGE (Amen Allah, Siwar)
REM  Lettres dediees : E: Elevage   P: Partage   D: Depot-Elevage
REM ============================================================
set SERVER=192.168.1.4

echo ================================================
echo   HMD - Profil ELEVAGE
echo ================================================
echo.
set /p LOGIN=Votre identifiant (amen_allah ou siwar) :
echo.
echo Nettoyage des connexions existantes...
net use * /delete /y >nul 2>&1
echo Connexion (mot de passe demande une fois)...
net use E: \\%SERVER%\Elevage /user:%LOGIN% * /persistent:no
if errorlevel 1 goto erreur
net use P: \\%SERVER%\Partage /persistent:no >nul 2>&1
net use D: \\%SERVER%\Depot-Elevage /persistent:no >nul 2>&1
echo.
echo  OK ! Lecteurs :  E: (Elevage)   P: (Partage)   D: (Depot-Elevage)
echo.
goto fin

:erreur
echo.
echo  *** ECHEC. Verifiez identifiant et mot de passe. ***
echo.

:fin
pause
endlocal

@echo off
chcp 65001 >nul
setlocal
REM ============================================================
REM  HMD - Profil PRODUCTION VEGETALE (Yassine)
REM  Lettres dediees : V: Prod.Vegetale  P: Partage  D: Depot-Vegetale
REM ============================================================
set SERVER=192.168.1.4

echo ================================================
echo   HMD - Profil PRODUCTION VEGETALE
echo ================================================
echo.
set /p LOGIN=Votre identifiant (ex: yassine) :
echo.
echo Nettoyage des connexions existantes...
net use * /delete /y >nul 2>&1
echo Connexion (mot de passe demande une fois)...
net use V: \\%SERVER%\Production_Vegetale /user:%LOGIN% * /persistent:no
if errorlevel 1 goto erreur
net use P: \\%SERVER%\Partage /persistent:no >nul 2>&1
net use D: \\%SERVER%\Depot-Vegetale /persistent:no >nul 2>&1
echo.
echo  OK ! Lecteurs :  V: (Prod. Vegetale)   P: (Partage)   D: (Depot-Vegetale)
echo.
goto fin

:erreur
echo.
echo  *** ECHEC. Verifiez identifiant et mot de passe. ***
echo.

:fin
pause
endlocal

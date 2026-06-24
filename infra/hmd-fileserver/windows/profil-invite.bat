@echo off
chcp 65001 >nul
setlocal
REM ============================================================
REM  HMD - Profil INVITE (Ridha, ou acces anonyme)
REM  Acces : Partage + tous les Depot-* uniquement.
REM ============================================================
set SERVER=192.168.1.4

echo ================================================
echo   HMD - Profil INVITE
echo ================================================
echo.
echo Laissez vide pour une connexion anonyme, ou tapez votre
echo identifiant (ex: ridha).
set /p LOGIN=Identifiant :
echo.
echo Nettoyage des connexions existantes...
net use * /delete /y >nul 2>&1
echo Connexion...
if "%LOGIN%"=="" (
  net use P: \\%SERVER%\Partage /persistent:no
) else (
  net use P: \\%SERVER%\Partage /user:%LOGIN% * /persistent:no
)
if errorlevel 1 goto erreur
echo.
echo  OK ! Lecteur P: = Partage commun.
echo  Les depots sont accessibles dans l'explorateur a : \\%SERVER%
echo.
start "" \\%SERVER%
goto fin

:erreur
echo.
echo  *** ECHEC de la connexion. ***
echo.

:fin
pause
endlocal

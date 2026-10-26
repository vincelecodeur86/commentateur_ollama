@echo off
rem Construit dist\Commentateur-C-Setup-<version>.exe
rem Prerequis (machine de construction uniquement) : Python et Inno Setup 6
rem   winget install -e --id JRSoftware.InnoSetup
setlocal
cd /d "%~dp0"

set "ISCC="
for %%P in ("%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe") do (
    if exist %%P set "ISCC=%%~P"
)
if not defined ISCC (
    echo Inno Setup 6 introuvable. Installez-le avec :
    echo   winget install -e --id JRSoftware.InnoSetup
    exit /b 1
)

if not exist commentateur.ico python make_icon.py || exit /b 1
"%ISCC%" commentateur.iss || exit /b 1
echo.
echo Installeur pret dans le dossier dist\

@echo off
chcp 65001 >nul
title Installation - 46Patches

for /f %%a in ('echo prompt $E^| cmd') do set "ESC=%%a"

echo %ESC%[95m
echo   j88D     dD         .d8b.  d8b   db  .d8b.  d8888b.  .o88b. db   db db    db
echo  j8~88    d8'        d8' `8b 888o  88 d8' `8b 88  `8D d8P  Y8 88   88 `8b  d8'
echo j8' 88   d8'         88ooo88 88V8o 88 88ooo88 88oobY' 8P      88ooo88  `8bd8'
echo V88888D d8888b.      88~~~88 88 V8o88 88~~~88 88`8b   8b      88~~~88    88
echo     88  88' `8D      88   88 88  V888 88   88 88 `88. Y8b  d8 88   88    88
echo     VP  `8888P       YP   YP VP   V8P YP   YP 88   YD  `Y88P' YP   YP    YP
echo %ESC%[0m

where python >nul 2>&1
if errorlevel 1 (
    echo Python n'est pas installe.
    pause
    exit /b
)

set "PYTHON_CMD="

where py >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=py"

if not defined PYTHON_CMD (
    where python >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    echo Python n'est pas installe.
    pause
    exit /b
)

echo Installation des dépendances python

cmd /c "%PYTHON_CMD% -m pip install customtkinter psutil"

echo Telechargement de 46patches.pyw...

powershell -NoProfile -ExecutionPolicy Bypass ^
    "Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/PhallBack/46cdn/refs/heads/main/46_updates.pyw' -OutFile '46patches.pyw'"

if exist "46patches.pyw" (
    cmd /c "start %PYTHON_CMD%w 46patches.pyw"
    del 46install_patches.bat
) else (
    echo Erreur lors du telechargement.

    PAUSE
)
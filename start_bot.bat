@echo off
title DnD AI Dungeon Master

:MENU
cls
echo ============================================================
echo   DnD AI Dungeon Master - Startup Menu
echo ============================================================
echo.
echo Select an option:
echo [1] Start Bot ONLY
echo [2] Start Bot + Docker
echo [3] Start Bot + Foundry VTT
echo [4] Start ALL (Bot + Docker + Foundry)
echo [5] Exit
echo.

set /p choice=Enter your choice (1-5): 

if "%choice%"=="1" goto START_BOT
if "%choice%"=="2" goto START_DOCKER
if "%choice%"=="3" goto START_FOUNDRY
if "%choice%"=="4" goto START_ALL
if "%choice%"=="5" exit
goto MENU

:START_DOCKER
echo Starting Docker Desktop...
if exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" (
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
) else (
    echo WARNING: Docker Desktop not found at expected path. Please start it manually.
)
goto START_BOT

:START_FOUNDRY
echo Starting Foundry VTT (Automated Login)...
powershell -ExecutionPolicy Bypass -File scripts\launch_foundry.ps1
goto START_BOT

:START_ALL
echo Starting Docker Desktop...
if exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" (
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
) else (
    echo WARNING: Docker Desktop not found at expected path. Please start it manually.
)
echo Waiting 10 seconds for Docker to initialize...
timeout /t 10 /nobreak

echo Starting Foundry VTT (Automated Login)...
start /wait powershell -ExecutionPolicy Bypass -File scripts\launch_foundry.ps1

goto START_BOT

:START_BOT
echo.
echo ============================================================
echo   DnD AI Dungeon Master - Starting Up
echo ============================================================
echo.

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found.
    echo Run this first:  python -m venv .venv
    echo Then:            .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

if not exist ".env" (
    echo ERROR: .env file not found.
    echo Create a .env file with your DISCORD_BOT_TOKEN and GEMINI_API_KEY.
    pause
    exit /b 1
)

echo Working directory: %cd%
echo Using venv: .venv\Scripts\python.exe
echo.

set PYTHONPATH=%cd%
.venv\Scripts\python orchestration/main.py

echo.
echo ============================================================
echo   Bot has stopped. Press any key to close.
echo ============================================================
pause

@echo off
title DnD AI Dungeon Master
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
.venv\Scripts\python orchestration/bot.py

echo.
echo ============================================================
echo   Bot has stopped. Press any key to close.
echo ============================================================
pause

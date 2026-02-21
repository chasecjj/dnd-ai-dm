@echo off
title DnD AI Dungeon Master
cd /d "%~dp0"

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
echo [5] Pre-Flight Checklist
echo [6] Exit
echo.

set /p choice=Enter your choice (1-6):

if "%choice%"=="1" goto START_BOT
if "%choice%"=="2" goto START_DOCKER
if "%choice%"=="3" goto START_FOUNDRY
if "%choice%"=="4" goto START_ALL
if "%choice%"=="5" goto PREFLIGHT
if "%choice%"=="6" exit
goto MENU

:: ==================================================================
:: PRE-FLIGHT CHECKLIST — verifies everything before session start
:: ==================================================================
:PREFLIGHT
cls
echo ============================================================
echo   PRE-FLIGHT CHECKLIST
echo ============================================================
echo.

set PASS=0
set WARN=0
set FAIL=0

:: --- 1. Virtual environment ---
if exist ".venv\Scripts\python.exe" (
    echo   [OK]  Python venv found
    set /a PASS+=1
) else (
    echo   [FAIL] Python venv missing — run: python -m venv .venv
    set /a FAIL+=1
)

:: --- 2. .env file ---
if exist ".env" (
    echo   [OK]  .env file found
    set /a PASS+=1
) else (
    echo   [FAIL] .env file missing
    set /a FAIL+=1
)

:: --- 3. Discord token ---
findstr /C:"DISCORD_BOT_TOKEN=" .env | findstr /V /C:"DISCORD_BOT_TOKEN=$" | findstr /V /C:"DISCORD_BOT_TOKEN= " >nul 2>&1
if %errorlevel%==0 (
    echo   [OK]  Discord bot token configured
    set /a PASS+=1
) else (
    echo   [FAIL] DISCORD_BOT_TOKEN not set in .env
    set /a FAIL+=1
)

:: --- 4. Gemini API key ---
findstr /C:"GEMINI_API_KEY=" .env | findstr /V /C:"GEMINI_API_KEY=$" | findstr /V /C:"GEMINI_API_KEY= " >nul 2>&1
if %errorlevel%==0 (
    echo   [OK]  Gemini API key configured
    set /a PASS+=1
) else (
    echo   [FAIL] GEMINI_API_KEY not set in .env
    set /a FAIL+=1
)

:: --- 5. Channel IDs ---
findstr /C:"GAME_TABLE_CHANNEL_ID=" .env | findstr /V /C:"GAME_TABLE_CHANNEL_ID=$" >nul 2>&1
if %errorlevel%==0 (
    echo   [OK]  Game Table channel ID configured
    set /a PASS+=1
) else (
    echo   [FAIL] GAME_TABLE_CHANNEL_ID not set in .env
    set /a FAIL+=1
)

findstr /C:"WAR_ROOM_CHANNEL_ID=" .env | findstr /V /C:"WAR_ROOM_CHANNEL_ID=$" >nul 2>&1
if %errorlevel%==0 (
    echo   [OK]  War Room channel ID configured
    set /a PASS+=1
) else (
    echo   [WARN] WAR_ROOM_CHANNEL_ID not set — prep features disabled
    set /a WARN+=1
)

findstr /C:"MODERATOR_LOG_CHANNEL_ID=" .env | findstr /V /C:"MODERATOR_LOG_CHANNEL_ID=$" >nul 2>&1
if %errorlevel%==0 (
    echo   [OK]  Moderator Log channel ID configured
    set /a PASS+=1
) else (
    echo   [WARN] MODERATOR_LOG_CHANNEL_ID not set — errors log locally only
    set /a WARN+=1
)

:: --- 6. Player map ---
findstr /R "PLAYER_MAP=.\+" .env >nul 2>&1
if %errorlevel%==0 (
    echo   [OK]  Player map configured
    set /a PASS+=1
) else (
    echo   [WARN] PLAYER_MAP is empty — characters won't be identified by name
    set /a WARN+=1
)

:: --- 7. Campaign vault ---
if exist "campaign_vault\06 - World State\clock.md" (
    echo   [OK]  Campaign vault linked and populated
    set /a PASS+=1
) else (
    echo   [FAIL] Campaign vault missing or not linked
    set /a FAIL+=1
)

:: --- 8. Party members ---
set PARTY_COUNT=0
if exist "campaign_vault\01 - Party" (
    for %%f in ("campaign_vault\01 - Party\*.md") do set /a PARTY_COUNT+=1
)
if %PARTY_COUNT% GTR 0 (
    echo   [OK]  Party folder has %PARTY_COUNT% character(s)
    set /a PASS+=1
) else (
    echo   [WARN] No characters in Party folder — use /console Register or /import
    set /a WARN+=1
)

:: --- 9. Docker Desktop ---
tasklist /FI "IMAGENAME eq Docker Desktop.exe" 2>nul | findstr /I "Docker" >nul 2>&1
if %errorlevel%==0 (
    echo   [OK]  Docker Desktop is running
    set /a PASS+=1
) else (
    echo   [WARN] Docker Desktop not running — Foundry relay unavailable
    set /a WARN+=1
)

:: --- 10. Relay container ---
docker ps --filter "name=foundryvtt-rest-api-relay" --format "{{.Names}}" 2>nul | findstr "relay" >nul 2>&1
if %errorlevel%==0 (
    echo   [OK]  Foundry relay container is running
    set /a PASS+=1
) else (
    echo   [WARN] Relay container not running — start with: docker compose -f foundryvtt-relay\docker-compose.yml up -d
    set /a WARN+=1
)

:: --- 11. Foundry VTT process ---
tasklist /FI "IMAGENAME eq FoundryVTT.exe" 2>nul | findstr /I "FoundryVTT" >nul 2>&1
if %errorlevel%==0 (
    echo   [OK]  Foundry VTT is running
    set /a PASS+=1
) else (
    echo   [WARN] Foundry VTT not running — live battlemap features unavailable
    set /a WARN+=1
)

:: --- 12. Relay connectivity ---
curl -s -o nul -w "%%{http_code}" http://localhost:3010/api/health 2>nul | findstr "200" >nul 2>&1
if %errorlevel%==0 (
    echo   [OK]  Relay API responding on :3010
    set /a PASS+=1
) else (
    echo   [WARN] Relay API not responding on localhost:3010
    set /a WARN+=1
)

:: --- 13. MongoDB ---
curl -s -o nul -w "%%{http_code}" http://localhost:27017 2>nul | findstr /V "000" >nul 2>&1
if %errorlevel%==0 (
    echo   [OK]  MongoDB responding on :27017
    set /a PASS+=1
) else (
    echo   [WARN] MongoDB not responding — running in vault-only mode
    set /a WARN+=1
)

:: --- Summary ---
echo.
echo ============================================================
echo   RESULTS:  %PASS% passed / %WARN% warnings / %FAIL% failed
echo ============================================================

if %FAIL% GTR 0 (
    echo.
    echo   [FAIL] items must be fixed before starting the bot.
)
if %WARN% GTR 0 (
    echo.
    echo   [WARN] items are optional — the bot degrades gracefully
    echo   without them, but you'll miss features.
)
if %FAIL%==0 if %WARN%==0 (
    echo.
    echo   All systems go! Ready for Session 1.
)

echo.
echo ============================================================
echo   OPTIMAL STARTUP ORDER
echo ============================================================
echo.
echo   1. Docker Desktop          (hosts the Foundry relay)
echo   2. Wait ~15 seconds        (Docker needs time to initialize)
echo   3. Relay container          docker compose -f foundryvtt-relay\docker-compose.yml up -d
echo   4. Foundry VTT              (launch app, unlock your world)
echo   5. MongoDB                  (if using DB-backed state)
echo   6. start_bot.bat [1]        (bot connects to everything in on_ready)
echo.
echo   In Discord after bot is online:
echo   7. /console                 (open the DM Admin Console)
echo   8. Register characters      (Register button, !register, or /import)
echo   9. Map players              (add PLAYER_MAP entries to .env, restart bot)
echo.

pause
goto MENU

:: ==================================================================
:: STARTUP PATHS
:: ==================================================================
:START_DOCKER
echo Starting Docker Desktop...
if exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" (
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
) else (
    echo WARNING: Docker Desktop not found at expected path. Please start it manually.
)
echo Waiting 15 seconds for Docker to initialize...
timeout /t 15 /nobreak
echo Starting Foundry relay container...
docker compose -f foundryvtt-relay\docker-compose.yml up -d 2>nul
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
echo Waiting 15 seconds for Docker to initialize...
timeout /t 15 /nobreak

echo Starting Foundry relay container...
docker compose -f foundryvtt-relay\docker-compose.yml up -d 2>nul

echo Starting Foundry VTT (Automated Login)...
start /wait powershell -ExecutionPolicy Bypass -File scripts\launch_foundry.ps1

goto START_BOT

:START_BOT
echo.
echo ============================================================
echo   DnD AI Dungeon Master - Starting Up
echo ============================================================
echo.

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

@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM ── Locate project root ──
set "ROOT=%~dp0.."
cd /d "%ROOT%"
set "ROOT=%CD%"

echo.
echo ========================================
echo   SiteGuard AI - Construction Site
echo         Safety Monitoring System
echo ========================================
echo.

REM ═══════════════════════════════════════════
REM  1. Environment Check
REM ═══════════════════════════════════════════
echo [1/6] Checking environment...

python --version >nul 2>&1
if errorlevel 1 (
    echo   [FAIL] Python not found. Please install Python 3.8+
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo   %%v

node --version >nul 2>&1
if errorlevel 1 (
    echo   [FAIL] Node.js not found. Please install Node.js 16+
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('node --version 2^>^&1') do echo   Node   %%v

pnpm --version >nul 2>&1
if errorlevel 1 (
    echo   pnpm not found, installing...
    npm install -g pnpm
    if errorlevel 1 (
        echo   [FAIL] pnpm install failed. Please install manually
        pause
        exit /b 1
    )
)
for /f "tokens=*" %%v in ('pnpm --version 2^>^&1') do echo   pnpm   %%v

echo   [OK] Environment check passed

REM ═══════════════════════════════════════════
REM  2. Python Virtual Environment
REM ═══════════════════════════════════════════
echo.
echo [2/6] Setting up Python virtual environment...

if not exist "venv\Scripts\activate.bat" (
    echo   Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo   [FAIL] Failed to create virtual environment
        pause
        exit /b 1
    )
)
call venv\Scripts\activate.bat
echo   Virtual env: %VIRTUAL_ENV%

REM  Upgrade pip (quiet)
python -m pip install --upgrade pip -q 2>nul

echo   [OK] Virtual environment ready

REM ═══════════════════════════════════════════
REM  3. Python Dependencies
REM ═══════════════════════════════════════════
echo.
echo [3/6] Installing Python dependencies...

python -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo   [FAIL] Python dependency install failed
    echo   Please run: pip install -r requirements.txt
    pause
    exit /b 1
)
echo   [OK] Python dependencies installed

REM ═══════════════════════════════════════════
REM  4. Frontend Dependencies
REM ═══════════════════════════════════════════
echo.
echo [4/6] Installing frontend dependencies (pnpm)...

pnpm install --loglevel error 2>nul
if errorlevel 1 (
    pnpm install
    if errorlevel 1 (
        echo   [FAIL] Frontend dependency install failed
        echo   Please run: pnpm install
        pause
        exit /b 1
    )
)
echo   [OK] Frontend dependencies installed

REM ═══════════════════════════════════════════
REM  5. Configuration & Model Check
REM ═══════════════════════════════════════════
echo.
echo [5/6] Checking configuration and model...

REM  .env
if not exist ".env" (
    echo   Creating .env from .env.example...
    copy .env.example .env >nul
    echo   [INFO] .env created. Edit it to customize settings.
) else (
    echo   .env already exists
)

REM  Model files
set "MODEL_COUNT=0"
for %%f in ("data\models\*.pt") do set /a MODEL_COUNT+=1
if %MODEL_COUNT%==0 (
    echo   [WARN] No .pt model files found in data\models\
    echo   Please place a trained model in data\models\
    echo   Or run: python scripts\train.py train
) else (
    echo   Model files: %MODEL_COUNT% .pt file(s)
)

echo   [OK] Configuration check complete

REM ═══════════════════════════════════════════
REM  6. Start Services
REM ═══════════════════════════════════════════
echo.
echo [6/6] Starting services...

REM  Start backend (new window)
start "SiteGuard Backend" /D "%ROOT%" cmd /c "call venv\Scripts\activate.bat && cd apps\server && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

REM  Wait for backend to start
timeout /t 3 /nobreak >nul

REM  Start frontend (new window)
start "SiteGuard Frontend" /D "%ROOT%\apps\web" cmd /c "pnpm dev"

echo.
echo ========================================
echo   System started!
echo.
echo   Frontend:  http://localhost:3000
echo   Backend:   http://localhost:8000
echo   API Docs:  http://localhost:8000/docs
echo ========================================
echo.
echo Press any key to stop all services...
pause >nul

REM ═══════════════════════════════════════════
REM  Stop
REM ═══════════════════════════════════════════
echo.
echo Stopping services...

REM  Close windows by title
taskkill /FI "WINDOWTITLE eq SiteGuard Frontend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq SiteGuard Backend*" /F >nul 2>&1

REM  Ensure port listeners are killed
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000.*LISTENING" 2^>nul') do taskkill /F /PID %%p >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":3000.*LISTENING" 2^>nul') do taskkill /F /PID %%p >nul 2>&1

echo Services stopped
pause

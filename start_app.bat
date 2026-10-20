@echo off
chcp 65001 >nul
title EasyPlan AI Agent - Launcher (Windows)
setlocal enabledelayedexpansion

echo ============================================================================
echo   EASYPLAN AI AGENT - KHOI CHAY HE THONG (BACKEND + FRONTEND)
echo ============================================================================
echo.

cd /d "%~dp0"

:: 1. Kiem tra thu muc backend va frontend
if not exist "backend\app\main.py" (
    echo [LOI] Khong tim thay thu muc backend! Hay chay file sync_github.bat truoc.
    pause
    exit /b 1
)

:: 2. Kiem tra & Khoi tao moi truong Python (.venv) cho Backend
echo [1/4] Kiem tra moi truong Python Backend...
if not exist "backend\.venv\Scripts\python.exe" (
    echo       Dang tao moi truong ao Python ^(backend\.venv^)...
    python -m venv "backend\.venv"
    if errorlevel 1 (
        echo [LOI] Khong the tao .venv. Vui long kiem tra da cai dat Python ^>= 3.10 chua.
        pause
        exit /b 1
    )
    echo       Dang cai dat thu vien Python tu requirements.txt...
    "backend\.venv\Scripts\python.exe" -m pip install --upgrade pip
    "backend\.venv\Scripts\python.exe" -m pip install -r "backend\requirements.txt"
) else (
    echo       Moi truong Python ^(.venv^) da san sang.
)

if not exist "backend\.env" (
    if exist "backend\.env.example" (
        copy /y "backend\.env.example" "backend\.env" >nul
    )
)

:: 3. Kiem tra & Cai dat node_modules cho Frontend
echo [2/4] Kiem tra thu vien Node.js Frontend...
if not exist "frontend\node_modules" (
    echo       Dang cai dat npm packages cho Frontend...
    pushd "frontend"
    call npm install
    popd
) else (
    echo       Thu vien Frontend ^(node_modules^) da san sang.
)

:: 4. Khoi chay Backend (Port 8000) va Frontend (Port 5173)
echo [3/4] Dang khoi chay Backend FastAPI ^(Port 8000^)...
start "EasyPlan Backend - Port 8000" cmd /k "cd /d "%~dp0backend" && .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

timeout /t 2 /nobreak >nul

echo [4/4] Dang khoi chay Frontend React/Vite ^(Port 5173^)...
start "EasyPlan Frontend - Port 5173" cmd /k "cd /d "%~dp0frontend" && npm run dev -- --host 127.0.0.1 --port 5173"

timeout /t 3 /nobreak >nul

echo.
echo ============================================================================
echo   HE THONG DA KHOI CHAY THANH CONG!
echo   - Giao dien Web ^(Frontend^) : http://localhost:5173
echo   - API Docs ^(Swagger UI^)    : http://127.0.0.1:8000/docs
echo ============================================================================
echo Dang mo trinh duyet...
start "" "http://localhost:5173"
echo.
pause

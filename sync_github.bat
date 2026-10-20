@echo off
chcp 65001 >nul
title EasyPlan AI Agent - GitHub Auto Clone & Pull (Windows)
setlocal enabledelayedexpansion

set "REPO_URL=https://github.com/duckyo2007/Probation_Walleye.git"
set "REPO_FOLDER=Probation_Walleye"

echo ============================================================================
echo   EASYPLAN AI AGENT - TU DONG TAI ^& CAP NHAT CODE TU GITHUB
echo   Repository: %REPO_URL%
echo ============================================================================
echo.

cd /d "%~dp0"

:: Kiem tra Git da duoc cai dat chua
where git >nul 2>nul
if errorlevel 1 (
    echo [LOI] May tinh chua cai dat Git! Vui long tai Git tai: https://git-scm.com/
    pause
    exit /b 1
)

:: Truong hop 1: Dang dung ngay trong thu muc Git cua du an
if exist ".git" (
    echo [1/3] Phat hien kho Git hien tai. Dang keo code moi nhat ^(git pull origin main^)...
    git fetch origin main
    git pull origin main
    set "TARGET_DIR=%CD%"
    goto :install_deps
)

:: Truong hop 2: Da co thu muc con Probation_Walleye
if exist "%REPO_FOLDER%\.git" (
    echo [1/3] Phat hien thu muc %REPO_FOLDER%. Dang keo code moi nhat...
    cd /d "%REPO_FOLDER%"
    git fetch origin main
    git pull origin main
    set "TARGET_DIR=%CD%"
    goto :install_deps
)

:: Truong hop 3: Chua co code -> Tu dong git clone ve may
echo [1/3] Chua co du an tren may. Dang tai moi ^(git clone^) tu GitHub...
git clone "%REPO_URL%" "%REPO_FOLDER%"
if errorlevel 1 (
    echo [LOI] Khong the clone repository. Vui long kiem tra ket noi mang!
    pause
    exit /b 1
)
cd /d "%REPO_FOLDER%"
set "TARGET_DIR=%CD%"

:install_deps
echo.
echo [2/3] Dang kiem tra ^& cap nhat thu vien Backend ^(Python^)...
if not exist "backend\.venv\Scripts\python.exe" (
    python -m venv "backend\.venv"
)
if exist "backend\.venv\Scripts\python.exe" (
    "backend\.venv\Scripts\python.exe" -m pip install -r "backend\requirements.txt"
)

echo.
echo [3/3] Dang kiem tra ^& cap nhat thu vien Frontend ^(Node.js^)...
if exist "frontend\package.json" (
    pushd "frontend"
    call npm install
    popd
)

echo.
echo ============================================================================
echo   HOAN TAT CAP NHAT DU AN TAI: %TARGET_DIR%
echo   Ban co the chay file start_app.bat de khoi dong he thong ngay!
echo ============================================================================
echo.
set /p RUN_NOW="Ban co muon khoi chay Ung dung ngay bay gio khong? (Y/N): "
if /i "%RUN_NOW%"=="Y" (
    call "%TARGET_DIR%\start_app.bat"
)
pause

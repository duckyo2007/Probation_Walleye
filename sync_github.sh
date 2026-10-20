#!/usr/bin/env bash
set -e

REPO_URL="https://github.com/duckyo2007/Probation_Walleye.git"
REPO_FOLDER="Probation_Walleye"

echo "============================================================================"
echo "  EASYPLAN AI AGENT - TU DONG TAI & CAP NHAT CODE TU GITHUB (LINUX / MACOS)"
echo "  Repository: $REPO_URL"
echo "============================================================================"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v git &>/dev/null; then
    echo "[LOI] May tinh chua cai dat Git! Vui long cai dat git truoc."
    exit 1
fi

# 1. Kiem tra clone hoac pull
if [ -d ".git" ]; then
    echo "[1/3] Phat hien kho Git hien tai. Dang keo code moi nhat (git pull origin main)..."
    git fetch origin main
    git pull origin main
    TARGET_DIR="$(pwd)"
elif [ -d "$REPO_FOLDER/.git" ]; then
    echo "[1/3] Phat hien thu muc $REPO_FOLDER. Dang keo code moi nhat..."
    cd "$REPO_FOLDER"
    git fetch origin main
    git pull origin main
    TARGET_DIR="$(pwd)"
else
    echo "[1/3] Chua co du an tren may. Dang tai moi (git clone) tu GitHub..."
    git clone "$REPO_URL" "$REPO_FOLDER"
    cd "$REPO_FOLDER"
    TARGET_DIR="$(pwd)"
fi

# Xac dinh lenh python3 hoac python
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi

# 2. Cap nhat thu vien Backend
echo ""
echo "[2/3] Dang kiem tra & cap nhat thu vien Backend (Python)..."
if [ ! -f "backend/.venv/bin/python" ]; then
    $PYTHON_CMD -m venv backend/.venv
fi
backend/.venv/bin/python -m pip install -r backend/requirements.txt

# 3. Cap nhat thu vien Frontend
echo ""
echo "[3/3] Dang kiem tra & cap nhat thu vien Frontend (Node.js)..."
if [ -f "frontend/package.json" ]; then
    (cd frontend && npm install)
fi

chmod +x start_app.sh sync_github.sh 2>/dev/null || true

echo ""
echo "============================================================================"
echo "  HOAN TAT CAP NHAT DU AN TAI: $TARGET_DIR"
echo "  Ban co the chay ./start_app.sh de khoi dong he thong ngay!"
echo "============================================================================"

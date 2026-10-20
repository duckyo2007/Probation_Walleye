#!/usr/bin/env bash
set -e

echo "============================================================================"
echo "  EASYPLAN AI AGENT - KHOI CHAY HE THONG (LINUX / MACOS)"
echo "============================================================================"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f "backend/app/main.py" ]; then
    echo "[LOI] Khong tim thay backend/app/main.py! Hay chay ./sync_github.sh truoc."
    exit 1
fi

# Xac dinh lenh python3 hoac python
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi

# 1. Kiem tra & tao moi truong ao Python (.venv)
echo "[1/4] Kiem tra moi truong Python Backend..."
if [ ! -f "backend/.venv/bin/python" ]; then
    echo "      Dang tao moi truong ao Python (backend/.venv)..."
    $PYTHON_CMD -m venv backend/.venv
    echo "      Dang cai dat thu vien Python tu requirements.txt..."
    backend/.venv/bin/python -m pip install --upgrade pip
    backend/.venv/bin/python -m pip install -r backend/requirements.txt
else
    echo "      Moi truong Python (backend/.venv) da san sang."
fi

if [ ! -f "backend/.env" ] && [ -f "backend/.env.example" ]; then
    cp backend/.env.example backend/.env
fi

# 2. Kiem tra & cai dat node_modules cho Frontend
echo "[2/4] Kiem tra thu vien Node.js Frontend..."
if [ ! -d "frontend/node_modules" ]; then
    echo "      Dang cai dat npm packages cho Frontend..."
    (cd frontend && npm install)
else
    echo "      Thu vien Frontend (node_modules) da san sang."
fi

# Ham don dep tien trinh khi bam Ctrl+C
cleanup() {
    echo ""
    echo "Dang dung Backend va Frontend..."
    [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null || true
    [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

# 3. Khoi chay Backend (Port 8000)
echo "[3/4] Dang khoi chay Backend FastAPI (Port 8000)..."
(cd backend && ./\.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000) &
BACKEND_PID=$!

sleep 2

# 4. Khoi chay Frontend (Port 5173)
echo "[4/4] Dang khoi chay Frontend React/Vite (Port 5173)..."
(cd frontend && npm run dev -- --host 127.0.0.1 --port 5173) &
FRONTEND_PID=$!

sleep 2

echo ""
echo "============================================================================"
echo "  HE THONG DA KHOI CHAY THANH CONG!"
echo "  - Giao dien Web (Frontend) : http://localhost:5173"
echo "  - API Docs (Swagger UI)    : http://127.0.0.1:8000/docs"
echo "  (Nhan Ctrl + C de dung dong thoi ca Backend va Frontend)"
echo "============================================================================"

# Mo trinh duyet tu dong tren macOS hoac Linux
if command -v open &>/dev/null; then
    open "http://localhost:5173" >/dev/null 2>&1 || true
elif command -v xdg-open &>/dev/null; then
    xdg-open "http://localhost:5173" >/dev/null 2>&1 || true
fi

wait

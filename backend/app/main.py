"""Điểm vào của backend. Chạy: uvicorn app.main:app --reload --port 8000"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import config
from app.api.routes import router
from app.services.confirmation import CONFIRMATION_MESSAGE, ConfirmationRequired
from app.services.json_storage import StorageError
from app.services.planner import PlanError

app = FastAPI(title="EasyPlan Backend Gateway", version="0.1.0")

# Cho phép frontend Vite (localhost:5173) gọi backend khi chạy local.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.get_cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}


# ---- Đổi lỗi nghiệp vụ thành HTTP response (403, 400/404, 500) ----
@app.exception_handler(ConfirmationRequired)
async def handle_confirmation_required(request: Request, exc: ConfirmationRequired):
    return JSONResponse(status_code=403, content={"detail": CONFIRMATION_MESSAGE})


@app.exception_handler(PlanError)
async def handle_plan_error(request: Request, exc: PlanError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.exception_handler(StorageError)
async def handle_storage_error(request: Request, exc: StorageError):
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception):
    # Không trả chi tiết lỗi nội bộ cho client.
    return JSONResponse(status_code=500, content={"detail": "Lỗi máy chủ nội bộ"})

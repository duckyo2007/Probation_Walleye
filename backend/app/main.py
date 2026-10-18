import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.config import STATIC_DIR
from app.services.qldt_client import check_and_run_sunday_auto_sync
from app.services.seed_data import ensure_initial_seed_data


async def _sunday_auto_sync_loop() -> None:
    """
    Background loop that checks every 30 minutes if today is Sunday and automatically
    scrapes PTIT QLĐT schedule using the user's saved credentials.
    """
    while True:
        try:
            await asyncio.to_thread(check_and_run_sunday_auto_sync)
        except Exception:
            pass
        await asyncio.sleep(1800)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_initial_seed_data(force_reset=False)
    sync_task = asyncio.create_task(_sunday_auto_sync_loop())
    try:
        yield
    finally:
        sync_task.cancel()


app = FastAPI(
    title="EasyPlan AI Agent API",
    description="Proactive AI Learning Assistant & PTIT QLĐT Schedule Sync Platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(api_router)


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": str(exc.detail)},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    if errors:
        first = errors[0]
        loc = ".".join(str(x) for x in first.get("loc", []))
        msg = first.get("msg", "Validation error")
        detail_msg = f"Validation error at '{loc}': {msg}"
    else:
        detail_msg = "Request validation error"
    return JSONResponse(
        status_code=422,
        content={"detail": detail_msg},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"},
    )


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "EasyPlan AI Agent Backend"}

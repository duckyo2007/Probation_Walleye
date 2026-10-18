import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
SLIDES_DIR = STATIC_DIR / "slides"

DATA_DIR.mkdir(parents=True, exist_ok=True)
SLIDES_DIR.mkdir(parents=True, exist_ok=True)

LESSONS_FILE = DATA_DIR / "lessons.json"
TASKS_FILE = DATA_DIR / "tasks.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
TKB_PTIT_FILE = DATA_DIR / "tkb_ptit.json"
QLDT_FALLBACK_FILE = DATA_DIR / "qldt_fallback_response.json"

# Load .env manually if present so we don't require external dotenv dependency
ENV_FILE = BASE_DIR / ".env"
if ENV_FILE.exists():
    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v

# Default Gemini model per Google Gemini 3.8 SDK specification
GEMINI_MODEL = "gemini-3.8-flash"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
DEFAULT_HOC_KY = int(os.environ.get("QLDT_HOC_KY", "20261"))

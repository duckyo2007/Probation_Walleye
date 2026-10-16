"""Cấu hình chung của backend. Chỉ đọc biến môi trường, không chứa bí mật."""
import os
from pathlib import Path

# Thư mục backend/ (chứa app/, data/, tests/). Tính từ vị trí file này
# nên chạy uvicorn/pytest ở thư mục nào cũng được.
BASE_DIR = Path(__file__).resolve().parent.parent

# Tên các file dữ liệu (nằm trong thư mục data)
LESSONS_FILE = "lessons.json"
TASKS_FILE = "tasks.json"
FALLBACK_FILE = "qldt_fallback_response.json"

POMODORO_MINUTES = 25
INACTIVITY_THRESHOLD_MINUTES = 10  # chỉ nhắc khi không hoạt động từ 10 phút trở lên


def get_data_dir() -> Path:
    """Thư mục chứa file JSON.

    Mặc định là backend/data. Đặt biến EASYPLAN_DATA_DIR để dùng thư mục khác
    (pytest dùng cách này để chạy trên bản sao, không đụng dữ liệu mẫu thật).
    """
    custom = os.environ.get("EASYPLAN_DATA_DIR")
    return Path(custom).resolve() if custom else BASE_DIR / "data"


def get_cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def get_inactivity_cooldown_seconds() -> int:
    """Khoảng cách tối thiểu giữa 2 lần nhắc cho cùng một task."""
    try:
        return int(os.environ.get("INACTIVITY_COOLDOWN_SECONDS", "300"))
    except ValueError:
        return 300

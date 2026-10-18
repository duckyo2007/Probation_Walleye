import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List

from app.config import (
    DEFAULT_HOC_KY,
    LESSONS_FILE,
    SETTINGS_FILE,
    TASKS_FILE,
)

_STORAGE_LOCK = threading.RLock()


def _read_json_file(path: Path, default: Any) -> Any:
    with _STORAGE_LOCK:
        if not path.exists():
            return default
        try:
            text = path.read_text(encoding="utf-8")
            if not text.strip():
                return default
            return json.loads(text)
        except Exception:
            return default


def _write_json_file(path: Path, data: Any) -> None:
    with _STORAGE_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp_path, path)


def load_lessons() -> List[Dict[str, Any]]:
    data = _read_json_file(LESSONS_FILE, [])
    return data if isinstance(data, list) else []


def save_lessons(lessons: List[Dict[str, Any]]) -> None:
    _write_json_file(LESSONS_FILE, lessons)


def load_tasks() -> List[Dict[str, Any]]:
    data = _read_json_file(TASKS_FILE, [])
    return data if isinstance(data, list) else []


def save_tasks(tasks: List[Dict[str, Any]]) -> None:
    _write_json_file(TASKS_FILE, tasks)


def load_settings() -> Dict[str, Any]:
    default_settings: Dict[str, Any] = {
        "qldt_username": os.environ.get("QLDT_USERNAME", ""),
        "qldt_password": os.environ.get("QLDT_PASSWORD", ""),
        "hoc_ky": DEFAULT_HOC_KY,
        "auto_sync_sunday": True,
        "last_sync_at": None,
        "last_sync_source": "fallback_cache",
        "last_sunday_sync_date": None,
        "gemini_api_key": os.environ.get("GEMINI_API_KEY", ""),
        "groq_api_key": os.environ.get("GROQ_API_KEY", ""),
    }
    saved = _read_json_file(SETTINGS_FILE, {})
    if isinstance(saved, dict):
        merged = {**default_settings, **saved}
        # Fall back to env vars if saved keys are empty
        if not merged.get("gemini_api_key") and os.environ.get("GEMINI_API_KEY"):
            merged["gemini_api_key"] = os.environ["GEMINI_API_KEY"]
        if not merged.get("groq_api_key") and os.environ.get("GROQ_API_KEY"):
            merged["groq_api_key"] = os.environ["GROQ_API_KEY"]
        if not merged.get("qldt_username") and os.environ.get("QLDT_USERNAME"):
            merged["qldt_username"] = os.environ["QLDT_USERNAME"]
        if not merged.get("qldt_password") and os.environ.get("QLDT_PASSWORD"):
            merged["qldt_password"] = os.environ["QLDT_PASSWORD"]
        return merged
    return default_settings


def save_settings(updates: Dict[str, Any]) -> Dict[str, Any]:
    current = load_settings()
    for k, v in updates.items():
        if v is not None:
            current[k] = v
    _write_json_file(SETTINGS_FILE, current)
    return current

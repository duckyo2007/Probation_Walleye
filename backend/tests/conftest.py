"""Fixture dùng chung. Mọi test chạy trên BẢN SAO của thư mục data (trong thư mục tạm)."""
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import agent_tools

REAL_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TASK_1 = "TASK_2026-10-15_01"   # trùng với buổi học bù, chưa có gcal_event_id
TASK_2 = "TASK_2026-10-15_02"   # đã có gcal_event_id mẫu


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    target = tmp_path / "data"
    shutil.copytree(REAL_DATA_DIR, target)
    monkeypatch.setenv("EASYPLAN_DATA_DIR", str(target))
    return target


@pytest.fixture
def tasks_path(data_dir):
    return data_dir / "tasks.json"


@pytest.fixture
def client(data_dir):
    agent_tools.reset_reminder_state()
    return TestClient(app)


@pytest.fixture
def gcal_spy(monkeypatch):
    """Thay tool Google Calendar bằng MagicMock để biết nó có bị gọi hay không."""
    spy = MagicMock(name="sync_google_calendar",
                    return_value={"synced": False, "mode": "mock", "results": []})
    monkeypatch.setattr(agent_tools, "sync_google_calendar", spy)
    return spy

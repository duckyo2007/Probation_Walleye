from datetime import date, timedelta

from conftest import TASK_1


def _roadmap_body(**overrides):
    body = {
        "course_code": "CS201",
        "course_name": "Cấu trúc dữ liệu và giải thuật",
        "exam_date": (date.today() + timedelta(days=10)).isoformat(),
        "daily_free_hours": 2,
        "slide_url": "https://example.com/slides/cs201.pdf",
    }
    body.update(overrides)
    return body


# Test 8
def test_roadmap_returns_draft_and_does_not_save(client, tasks_path):
    before = tasks_path.read_bytes()
    res = client.post("/api/roadmap/generate", json=_roadmap_body())
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "draft_generated"
    assert body["saved"] is False
    assert body["summary"]
    assert len(body["suggested_sessions"]) >= 1
    assert all(len(s["subtasks"]) >= 1 for s in body["suggested_sessions"])
    assert tasks_path.read_bytes() == before


def test_roadmap_exam_date_in_the_past_returns_400(client):
    past = (date.today() - timedelta(days=1)).isoformat()
    assert client.post("/api/roadmap/generate", json=_roadmap_body(exam_date=past)).status_code == 400


def test_roadmap_works_without_slide_url(client):
    res = client.post("/api/roadmap/generate", json=_roadmap_body(slide_url=None))
    assert res.status_code == 200
    assert res.json()["document_status"] == "no_document"


def test_tutor_chat_unknown_task_returns_404(client):
    res = client.post("/api/tutor/chat", json={"task_id": "NOPE", "user_message": "xin chào"})
    assert res.status_code == 404


def test_tutor_chat_empty_message_returns_422(client):
    res = client.post("/api/tutor/chat", json={"task_id": TASK_1, "user_message": ""})
    assert res.status_code == 422


def test_inactivity_below_threshold_gives_no_message(client):
    res = client.post("/api/tutor/inactivity-check",
                      json={"task_id": TASK_1, "inactive_minutes": 9, "current_subtask": "Bước 1"})
    assert res.status_code == 200
    assert res.json()["should_remind"] is False
    assert res.json()["message"] is None


def test_inactivity_reminds_at_threshold_then_rate_limits(client):
    body = {"task_id": TASK_1, "inactive_minutes": 10, "current_subtask": "Cài đặt hàm chèn"}
    first = client.post("/api/tutor/inactivity-check", json=body).json()
    assert first["should_remind"] is True
    assert "Cài đặt hàm chèn" in first["message"]

    second = client.post("/api/tutor/inactivity-check", json=body).json()
    assert second["should_remind"] is False
    assert second["skip_reason"] == "rate_limited"

    # Giới hạn tính riêng theo từng task
    other = client.post("/api/tutor/inactivity-check",
                        json={"task_id": "TASK_2026-10-15_02", "inactive_minutes": 12}).json()
    assert other["should_remind"] is True


# Test 10
def test_mock_endpoints_work_without_any_external_api_key(client, monkeypatch):
    for name in ("LLM_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_CALENDAR_CREDENTIALS"):
        monkeypatch.delenv(name, raising=False)

    assert client.post("/api/schedule/sync", json={"force_refresh": False}).status_code == 200
    assert client.post("/api/roadmap/generate", json=_roadmap_body()).status_code == 200
    assert client.get(f"/api/workspace/enter/{TASK_1}").status_code == 200

    chat = client.post("/api/tutor/chat", json={
        "task_id": TASK_1, "user_message": "Cây nhị phân tìm kiếm là gì?",
        "code_snippet": "def insert(node, x):\n    pass", "chat_history": [
            {"role": "user", "content": "chào"}, {"role": "assistant", "content": "chào bạn"}]})
    assert chat.status_code == 200
    assert chat.json()["provider_used"] == "mock"
    assert chat.json()["reply_markdown"]

    inactive = client.post("/api/tutor/inactivity-check",
                           json={"task_id": TASK_1, "inactive_minutes": 10})
    assert inactive.status_code == 200

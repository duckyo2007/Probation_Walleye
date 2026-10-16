import json

from conftest import TASK_1


def _task(tasks_path, task_id):
    data = json.loads(tasks_path.read_text(encoding="utf-8"))
    return next(t for t in data["study_sessions"] if t["task_id"] == task_id)


# Test 1
def test_enter_workspace_returns_existing_task(client):
    res = client.get(f"/api/workspace/enter/{TASK_1}")
    assert res.status_code == 200
    body = res.json()
    assert body["task_info"]["task_id"] == TASK_1
    assert "subtasks" not in body["task_info"]
    assert len(body["checklist"]) == 3
    assert body["document"]["status"] in ("no_document", "not_extracted")


# Test 2
def test_enter_workspace_unknown_task_returns_404(client):
    res = client.get("/api/workspace/enter/TASK_KHONG_TON_TAI")
    assert res.status_code == 404


def test_enter_workspace_without_slide_does_not_pretend_document_was_read(client):
    res = client.get("/api/workspace/enter/TASK_2026-10-16_01")  # slide_url = null
    assert res.json()["document"]["status"] == "no_document"
    assert res.json()["document"]["text"] is None


# Test 9
def test_complete_updates_checklist_and_summary(client, tasks_path):
    checklist = client.get(f"/api/workspace/enter/{TASK_1}").json()["checklist"]
    ids = [s["sub_id"] for s in checklist]
    res = client.post("/api/workspace/complete", json={
        "task_id": TASK_1,
        "pomodoro_completed": 2,
        "completed_subtask_ids": [ids[0], ids[2]],
        "personal_notes": "Ghi chú thử",
    })
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "saved"
    card = body["summary_card"]
    assert card["total_focus_minutes"] == 50
    assert card["pomodoro_result"] == "2/3"
    assert card["completed_tasks_count"] == 2
    assert card["completion_rate_percent"] == 66.7
    assert [s["sub_id"] for s in card["remaining_subtasks"]] == [ids[1]]

    saved = _task(tasks_path, TASK_1)
    assert [s["done"] for s in saved["subtasks"]] == [True, False, True]
    assert saved["pomodoro_completed"] == 2
    assert saved["personal_notes"] == "Ghi chú thử"
    # Không được đổi lịch
    assert (saved["date"], saved["start"], saved["end"]) == ("2026-10-15", "17:00", "18:30")


def test_complete_rejects_negative_pomodoro(client, tasks_path):
    before = tasks_path.read_bytes()
    res = client.post("/api/workspace/complete", json={
        "task_id": TASK_1, "pomodoro_completed": -1, "completed_subtask_ids": [], "personal_notes": ""})
    assert res.status_code == 422
    assert tasks_path.read_bytes() == before


def test_complete_rejects_unknown_subtask_id(client, tasks_path):
    before = tasks_path.read_bytes()
    res = client.post("/api/workspace/complete", json={
        "task_id": TASK_1, "pomodoro_completed": 1, "completed_subtask_ids": ["SUB_KHONG_CO"],
        "personal_notes": ""})
    assert res.status_code == 400
    assert tasks_path.read_bytes() == before


def test_complete_unknown_task_returns_404(client):
    res = client.post("/api/workspace/complete", json={
        "task_id": "TASK_KHONG_TON_TAI", "pomodoro_completed": 1, "completed_subtask_ids": []})
    assert res.status_code == 404

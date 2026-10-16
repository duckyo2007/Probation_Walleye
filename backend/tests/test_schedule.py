import json

import pytest

from conftest import TASK_1, TASK_2

GATE_MESSAGE = "Action requires explicit user confirmation"
VALID_ITEM = {"task_id": TASK_1, "new_date": "2026-10-15", "new_start": "19:00", "new_end": "20:30"}


def _payload(**overrides):
    body = {"user_confirmed": True, "sync_gcal": True, "reschedule_items": [VALID_ITEM]}
    body.update(overrides)
    return body


def _sessions(tasks_path):
    data = json.loads(tasks_path.read_text(encoding="utf-8"))
    return {t["task_id"]: t for t in data["study_sessions"]}


# Test 3
def test_sync_detects_conflict_but_does_not_change_tasks(client, tasks_path):
    before = tasks_path.read_bytes()
    res = client.post("/api/schedule/sync", json={"force_refresh": True})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "success"
    assert body["is_mock"] is True
    assert body["source"] == "qldt_fallback_file"
    assert len(body["lessons"]) > 0 and len(body["tasks"]) > 0
    assert len(body["conflicts"]) == 1
    conflict = body["conflicts"][0]
    assert conflict["task_id"] == TASK_1
    assert conflict["suggested_slot"] == {"date": "2026-10-15", "start": "19:00", "end": "20:30"}
    assert tasks_path.read_bytes() == before   # lịch tự học không bị sửa


# Test 4, 5
@pytest.mark.parametrize("confirm_fields", [{}, {"user_confirmed": False}])
def test_reschedule_without_confirmation_is_rejected(client, tasks_path, gcal_spy, confirm_fields):
    before = tasks_path.read_bytes()
    body = {"sync_gcal": True, "reschedule_items": [VALID_ITEM], **confirm_fields}
    res = client.post("/api/schedule/confirm-reschedule", json=body)
    assert res.status_code == 403
    assert res.json()["detail"] == GATE_MESSAGE
    assert tasks_path.read_bytes() == before
    gcal_spy.assert_not_called()


@pytest.mark.parametrize("not_true", ["true", "yes", 1, None])
def test_reschedule_only_accepts_boolean_true(client, tasks_path, gcal_spy, not_true):
    before = tasks_path.read_bytes()
    res = client.post("/api/schedule/confirm-reschedule", json=_payload(user_confirmed=not_true))
    assert res.status_code == 403
    assert tasks_path.read_bytes() == before
    gcal_spy.assert_not_called()


# Test 6
@pytest.mark.parametrize("bad_items, expected_status", [
    ([{**VALID_ITEM, "task_id": "TASK_KHONG_TON_TAI"}], 404),
    ([{**VALID_ITEM, "new_start": "20:30", "new_end": "19:00"}], 400),
    ([{**VALID_ITEM, "new_start": "19:00", "new_end": "19:00"}], 400),
    ([{**VALID_ITEM, "new_date": "2026-02-30"}], 400),
    ([VALID_ITEM, VALID_ITEM], 400),                                  # task_id bị lặp
    ([VALID_ITEM, {**VALID_ITEM, "task_id": "TASK_KHONG_TON_TAI"}], 404),  # 1 đúng + 1 sai: không ghi gì
    ([{**VALID_ITEM, "new_start": "7pm"}], 422),
    ([], 422),
])
def test_invalid_request_writes_nothing_and_skips_gcal(client, tasks_path, gcal_spy,
                                                       bad_items, expected_status):
    before = tasks_path.read_bytes()
    res = client.post("/api/schedule/confirm-reschedule", json=_payload(reschedule_items=bad_items))
    assert res.status_code == expected_status
    assert tasks_path.read_bytes() == before
    gcal_spy.assert_not_called()


# Test 7
def test_confirmed_reschedule_updates_only_the_right_task(client, tasks_path):
    before = _sessions(tasks_path)
    res = client.post("/api/schedule/confirm-reschedule", json=_payload(sync_gcal=False))
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "rescheduled"
    assert body["gcal_synced"] is False
    assert [t["task_id"] for t in body["updated_tasks"]] == [TASK_1]

    after = _sessions(tasks_path)
    assert (after[TASK_1]["date"], after[TASK_1]["start"], after[TASK_1]["end"]) == (
        "2026-10-15", "19:00", "20:30")
    for task_id in before:
        if task_id != TASK_1:
            assert after[task_id] == before[task_id]


def test_sync_gcal_false_does_not_call_gcal(client, gcal_spy):
    res = client.post("/api/schedule/confirm-reschedule", json=_payload(sync_gcal=False))
    assert res.status_code == 200
    assert res.json()["gcal_mode"] == "skipped"
    gcal_spy.assert_not_called()


def test_confirmed_with_sync_gcal_calls_gcal_once(client, gcal_spy):
    res = client.post("/api/schedule/confirm-reschedule", json=_payload(sync_gcal=True))
    assert res.status_code == 200
    gcal_spy.assert_called_once()


def test_gcal_mock_is_never_reported_as_really_synced(client):
    res = client.post("/api/schedule/confirm-reschedule", json=_payload(sync_gcal=True))
    body = res.json()
    assert body["gcal_synced"] is False
    assert body["gcal_mode"] == "mock"
    assert "mock" in body["message"]


def test_existing_gcal_event_is_updated_not_duplicated(client, tasks_path):
    from app.services import agent_tools
    sessions = _sessions(tasks_path)
    result = agent_tools.sync_google_calendar([sessions[TASK_2], sessions[TASK_1]], user_confirmed=True)
    # Task đã có gcal_event_id -> cập nhật; chưa có -> sẽ tạo. Mock không ghi id giả vào tasks.json.
    assert [r["action"] for r in result["results"]] == ["would_update", "would_create"]
    assert result["synced"] is False
    assert _sessions(tasks_path)[TASK_1]["gcal_event_id"] is None

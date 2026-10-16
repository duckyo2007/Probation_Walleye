import pytest

from app.services import agent_tools, planner
from app.services.confirmation import ConfirmationRequired, require_user_confirmation

ITEM = {"task_id": "T1", "new_date": "2026-10-15", "new_start": "19:00", "new_end": "20:00"}


def test_gate_allows_only_boolean_true():
    require_user_confirmation(True)  # không ném lỗi


@pytest.mark.parametrize("value", [False, None, "true", "yes", 1, 0, [], {}])
def test_gate_rejects_everything_else(value):
    with pytest.raises(ConfirmationRequired):
        require_user_confirmation(value)


def test_gcal_tool_refuses_to_run_without_confirmation():
    with pytest.raises(ConfirmationRequired):
        agent_tools.sync_google_calendar([{"task_id": "T1"}], user_confirmed=False)


def test_apply_reschedule_refuses_without_confirmation_and_changes_nothing():
    data = {"study_sessions": [{"task_id": "T1", "date": "2026-10-14", "start": "08:00", "end": "09:00"}]}
    with pytest.raises(ConfirmationRequired):
        planner.apply_reschedule(data, [ITEM], user_confirmed=False)
    assert data["study_sessions"][0]["date"] == "2026-10-14"


def test_confirmation_is_per_request_not_global(client, tasks_path):
    item = {"task_id": "TASK_2026-10-15_01", "new_date": "2026-10-15", "new_start": "19:00", "new_end": "20:30"}
    ok = client.post("/api/schedule/confirm-reschedule",
                     json={"user_confirmed": True, "reschedule_items": [item]})
    assert ok.status_code == 200
    # Request tiếp theo không có xác nhận vẫn phải bị chặn, dù request trước đã được xác nhận
    denied = client.post("/api/schedule/confirm-reschedule", json={"reschedule_items": [item]})
    assert denied.status_code == 403

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.agent_tools import reset_inactivity_cooldowns
from app.services.json_storage import load_settings, load_tasks, save_settings
from app.services.seed_data import ensure_initial_seed_data

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_state_before_each_test():
    saved_settings = load_settings()
    ensure_initial_seed_data(force_reset=True, demo_tasks=True)
    reset_inactivity_cooldowns()
    yield
    ensure_initial_seed_data(force_reset=True)
    save_settings(saved_settings)


def test_first_time_user_has_no_self_study_tasks():
    ensure_initial_seed_data(force_reset=True)
    data = client.post("/api/schedule/sync", json={"force_refresh": False}).json()
    assert data["tasks"] == []
    assert data["delay_prediction"] is None
    assert len(data["lessons"]) > 0


def test_overdue_tasks_flagged_and_makeup_suggested():
    data = client.post("/api/schedule/sync", json={"force_refresh": False}).json()
    today = data["today"]
    overdue = [t for t in data["tasks"] if t["overdue"]]
    assert overdue, "demo tasks dated before today and not done must be overdue"
    assert all(t["status"] != "done" and t["date"] < today for t in overdue)
    pred = data["delay_prediction"]
    assert pred["is_resolved"] is False
    assert pred["suggested_date"] >= today
    assert pred["overdue_task_ids"]


def test_api_1_schedule_sync_and_read_only_conflict_detection():
    tasks_before = load_tasks()
    resp = client.post("/api/schedule/sync", json={"force_refresh": False})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["source"] in ("live_api", "fallback_cache")
    assert isinstance(data["lessons"], list) and len(data["lessons"]) > 50
    assert isinstance(data["tasks"], list) and len(data["tasks"]) >= 3
    assert data["delay_prediction"]["is_mock"] is True
    assert len(data["conflicts"]) >= 1

    # Verify task_001 conflict is detected
    c0 = next((c for c in data["conflicts"] if c["task_id"] == "task_001"), None)
    assert c0 is not None
    assert c0["old_date"] == "2026-10-15"
    assert c0["old_time"] == "08:00 - 09:30"
    assert c0["new_suggested_time"] in ("16:00 - 17:30", "19:30 - 21:00")

    # Verify read-only: tasks.json was NOT modified by /api/schedule/sync
    tasks_after = load_tasks()
    assert tasks_before == tasks_after


def test_qldt_period_merging_in_lessons():
    resp = client.post("/api/schedule/sync", json={"force_refresh": False})
    lessons = resp.json()["lessons"]
    # On 2026-09-10 (Week 5), INT1359 has consecutive periods merged -> 09:00 to 11:50
    int1359_sep10 = [
        l for l in lessons if l["course_code"] == "INT1359" and l["date"] == "2026-09-10"
    ]
    assert len(int1359_sep10) == 1
    assert int1359_sep10[0]["start"] == "09:00"
    assert int1359_sep10[0]["end"] == "11:50"

    # On 2026-09-12 (Week 5), INT1306 has consecutive periods merged -> 13:00 to 15:50
    int1306_sep12 = [
        l for l in lessons if l["course_code"] == "INT1306" and l["date"] == "2026-09-12"
    ]
    assert len(int1306_sep12) == 1
    assert int1306_sep12[0]["start"] == "13:00"
    assert int1306_sep12[0]["end"] == "15:50"


@pytest.mark.parametrize(
    "invalid_confirm_value",
    [False, None, "true", "True", 1, 0, []],
)
def test_api_2_confirm_reschedule_rejects_unconfirmed_with_403(invalid_confirm_value):
    tasks_before = load_tasks()
    payload = {
        "user_confirmed": invalid_confirm_value,
        "sync_gcal": True,
        "reschedule_items": [
            {
                "task_id": "task_001",
                "new_date": "2026-10-15",
                "new_start": "19:30",
                "new_end": "21:00",
            }
        ],
    }
    resp = client.post("/api/schedule/confirm-reschedule", json=payload)
    assert resp.status_code == 403
    assert resp.json() == {"detail": "Action requires explicit user confirmation"}
    # tasks.json must remain untouched
    assert load_tasks() == tasks_before


def test_api_2_confirm_reschedule_success_and_edge_errors():
    # Valid confirmation
    payload = {
        "user_confirmed": True,
        "sync_gcal": True,
        "reschedule_items": [
            {
                "task_id": "task_001",
                "new_date": "2026-10-15",
                "new_start": "19:30",
                "new_end": "21:00",
            }
        ],
    }
    resp = client.post("/api/schedule/confirm-reschedule", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "updated"
    assert data["gcal_synced"] is True
    assert data["updated_tasks"][0]["start"] == "19:30"
    assert data["updated_tasks"][0]["end"] == "21:00"

    # Non-existent task_id -> 404
    resp_404 = client.post(
        "/api/schedule/confirm-reschedule",
        json={
            "user_confirmed": True,
            "sync_gcal": True,
            "reschedule_items": [
                {
                    "task_id": "task_999_nonexistent",
                    "new_date": "2026-10-15",
                    "new_start": "19:30",
                    "new_end": "21:00",
                }
            ],
        },
    )
    assert resp_404.status_code == 404
    assert "detail" in resp_404.json()

    # Invalid time range (new_end <= new_start) -> 400
    resp_400 = client.post(
        "/api/schedule/confirm-reschedule",
        json={
            "user_confirmed": True,
            "sync_gcal": True,
            "reschedule_items": [
                {
                    "task_id": "task_001",
                    "new_date": "2026-10-15",
                    "new_start": "21:00",
                    "new_end": "19:30",
                }
            ],
        },
    )
    assert resp_400.status_code == 400
    assert "detail" in resp_400.json()


def test_api_3_and_3_1_roadmap_generate_and_confirm_save_gate():
    from app.services.internet_time import fetch_internet_date
    live_today, _ = fetch_internet_date()
    live_today = live_today.isoformat() if hasattr(live_today, "isoformat") else str(live_today)

    gen_resp = client.post(
        "/api/roadmap/generate",
        json={
            "course_code": "INT1306",
            "course_name": "Cấu trúc dữ liệu và giải thuật",
            "exam_date": "2026-11-15",
            "daily_free_hours": 2.0,
            "slide_url": "/static/slides/INT1306_Chuong3_CayNhiPhan.pdf",
        },
    )
    assert gen_resp.status_code == 200
    draft = gen_resp.json()
    assert draft["status"] == "draft_generated"
    sessions = draft["suggested_sessions"]
    # Balanced plan: sessions spread over free days before the exam, no duplicate titles
    assert len(sessions) >= 3
    assert len({s["title"] for s in sessions}) == len(sessions)
    assert all(s["suggested_date"] < "2026-11-15" for s in sessions)
    assert all(s["suggested_date"] >= live_today for s in sessions)

    # Rejects save when user_confirmed is "true" (string) or False
    bad_save = client.post(
        "/api/roadmap/confirm-save",
        json={
            "user_confirmed": "true",
            "course_code": "INT1306",
            "course_name": "Cấu trúc dữ liệu và giải thuật",
            "approved_sessions": [
                {
                    "title": s["title"],
                    "date": s["suggested_date"],
                    "start": s["suggested_start"],
                    "end": s["suggested_end"],
                    "is_flexible": True,
                    "subtasks": s["subtasks"],
                }
                for s in draft["suggested_sessions"]
            ],
        },
    )
    assert bad_save.status_code == 403
    assert bad_save.json() == {"detail": "Action requires explicit user confirmation"}

    # Accepts save when user_confirmed is strictly boolean True
    good_save = client.post(
        "/api/roadmap/confirm-save",
        json={
            "user_confirmed": True,
            "course_code": "INT1306",
            "course_name": "Cấu trúc dữ liệu và giải thuật",
            "approved_sessions": [
                {
                    "title": s["title"],
                    "date": s["suggested_date"],
                    "start": s["suggested_start"],
                    "end": s["suggested_end"],
                    "is_flexible": True,
                    "subtasks": s["subtasks"],
                }
                for s in draft["suggested_sessions"]
            ],
        },
    )
    assert good_save.status_code == 200
    saved_data = good_save.json()
    assert saved_data["status"] == "saved"
    assert len(saved_data["added_task_ids"]) == len(sessions)


def test_api_4_workspace_enter_and_edge_case_2_pdf_extraction():
    resp = client.get("/api/workspace/enter/task_001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ready"
    assert data["task_info"]["task_id"] == "task_001"
    assert len(data["task_info"]["slide_urls"]) == 2
    assert data["document"]["context_loaded"] is True
    assert len(data["document"]["documents"]) == 2
    assert data["document"]["page_count"] == 5
    assert data["document"]["document_status"] == "loaded"
    assert "BST" in data["document"]["extracted_text"]
    assert "STACK" in data["document"]["extracted_text"].upper()

    # Non-existent task -> 404
    resp_404 = client.get("/api/workspace/enter/task_does_not_exist")
    assert resp_404.status_code == 404
    assert "detail" in resp_404.json()


def test_api_5_tutor_chat_and_code_debugging():
    resp = client.post(
        "/api/tutor/chat",
        json={
            "task_id": "task_001",
            "user_message": "Tại sao đoạn code duyệt cây nhị phân của mình lại bị lỗi đệ quy vô tận nhỉ?",
            "code_snippet": "void preOrder(Node* root) {\n    cout << root->data;\n    preOrder(root->left);\n    preOrder(root->right);\n}",
            "chat_history": [],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["provider_used"] in ("gemini-3.8-flash", "groq-fallback")
    assert "nullptr" in data["reply_markdown"] or "NULL" in data["reply_markdown"] or "return" in data["reply_markdown"]


def test_api_6_inactivity_check_cooldown_edge_case_4():
    # First call -> should_remind: True
    r1 = client.post(
        "/api/tutor/inactivity-check",
        json={
            "task_id": "task_001",
            "inactive_minutes": 10,
            "current_subtask": "Code thử thuật toán duyệt cây (Pre-order, In-order)",
        },
    )
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["status"] == "ok"
    assert d1["should_remind"] is True
    assert d1["skip_reason"] is None
    assert d1["retry_after_seconds"] is None
    assert "Code thử thuật toán duyệt cây" in d1["message"]

    # Second immediate call within 300s -> should_remind: False, skip_reason: "rate_limited"
    r2 = client.post(
        "/api/tutor/inactivity-check",
        json={
            "task_id": "task_001",
            "inactive_minutes": 11,
            "current_subtask": "Code thử thuật toán duyệt cây (Pre-order, In-order)",
        },
    )
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["status"] == "ok"
    assert d2["should_remind"] is False
    assert d2["skip_reason"] == "rate_limited"
    assert d2["message"] is None
    assert isinstance(d2["retry_after_seconds"], int) and d2["retry_after_seconds"] > 0


def test_api_7_workspace_complete():
    resp = client.post(
        "/api/workspace/complete",
        json={
            "task_id": "task_001",
            "pomodoro_completed": 2,
            "completed_subtask_ids": ["sub_1", "sub_2"],
            "personal_notes": "Đã hiểu phần duyệt cây, buổi sau cần làm thêm bài tập xóa nút.",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "saved"
    card = data["summary_card"]
    assert card["total_focus_minutes"] == 50
    assert card["pomodoro_result"] == "2 / 2 Pomodoro"
    assert card["completed_tasks_count"] == "2 / 3 Tasks"
    assert card["completion_rate_percent"] == 67
    assert card["remaining_subtasks"] == ["Làm 3 câu hỏi trắc nghiệm cuối bài"]


def test_api_8_flashcards_generation():
    resp = client.post(
        "/api/workspace/flashcards",
        json={"task_id": "task_001", "count": 3},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["task_id"] == "task_001"
    assert len(data["flashcards"]) == 3
    for fc in data["flashcards"]:
        assert "card_id" in fc and "question" in fc and "answer" in fc


def test_settings_endpoints():
    get_res = client.get("/api/settings")
    assert get_res.status_code == 200
    data = get_res.json()
    assert "auto_sync_sunday" in data
    assert data["gemini_model"] == "gemini-3.8-flash"

    update_res = client.post(
        "/api/settings",
        json={"auto_sync_sunday": False, "hoc_ky": 20261},
    )
    assert update_res.status_code == 200
    assert update_res.json()["auto_sync_sunday"] is False


def test_simulate_conflict_and_add_extra_session():
    # 1. Simulate conflict endpoint
    sim_res = client.post("/api/schedule/simulate-conflict")
    assert sim_res.status_code == 200
    sim_data = sim_res.json()
    assert sim_data["status"] == "success"
    assert len(sim_data["conflicts"]) >= 1

    # 2. Add extra session confirmation gate
    bad_res = client.post(
        "/api/schedule/add-extra-session",
        json={
            "user_confirmed": "yes",
            "course_code": "INT1306",
            "course_name": "Cấu trúc dữ liệu",
            "title": "Học bù tối nay",
            "date": "2026-10-18",
            "start": "19:30",
            "end": "21:00",
        },
    )
    assert bad_res.status_code == 403

    good_res = client.post(
        "/api/schedule/add-extra-session",
        json={
            "user_confirmed": True,
            "course_code": "INT1306",
            "course_name": "Cấu trúc dữ liệu",
            "title": "Học bù tối nay",
            "date": "2026-10-18",
            "start": "19:30",
            "end": "21:00",
        },
    )
    assert good_res.status_code == 200
    assert len(good_res.json()["added_task_ids"]) == 1


def test_documents_upload_and_remove():
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Test PDF content upload")
    pdf_bytes = doc.write()
    doc.close()

    up_res = client.post(
        "/api/documents/upload",
        files={"file": ("test_extra_slide.pdf", pdf_bytes, "application/pdf")},
        data={"task_id": "task_001", "append": "true"},
    )
    assert up_res.status_code == 200
    up_data = up_res.json()
    assert up_data["status"] == "uploaded"
    uploaded_url = up_data["slide_url"]

    rm_res = client.post(
        "/api/documents/remove",
        json={"task_id": "task_001", "slide_url": uploaded_url},
    )
    assert rm_res.status_code == 200
    assert rm_res.json()["status"] == "removed"


def test_api_get_today_internet_date():
    resp = client.get("/api/schedule/today")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "today" in data
    # Format should be YYYY-MM-DD
    parts = data["today"].split("-")
    assert len(parts) == 3
    assert len(parts[0]) == 4
    assert len(parts[1]) == 2
    assert len(parts[2]) == 2
    assert "source" in data
    assert "current_week" in data
    assert isinstance(data["current_week"], int)


def test_roadmap_list_and_delete():
    list_res = client.get("/api/roadmap/list")
    assert list_res.status_code == 200
    data = list_res.json()
    assert data["status"] == "ok"
    assert "roadmaps" in data
    assert isinstance(data["roadmaps"], list)
    assert data["total_roadmaps"] == len(data["roadmaps"])
    assert len(data["roadmaps"]) >= 1

    first_rm = data["roadmaps"][0]
    rm_id = first_rm["roadmap_id"]
    assert "course_code" in first_rm
    assert "total_sessions" in first_rm
    assert "completed_sessions" in first_rm
    assert "task_ids" in first_rm

    # Delete the roadmap
    del_res = client.post("/api/roadmap/delete", json={"roadmap_ids": [rm_id]})
    assert del_res.status_code == 200
    del_data = del_res.json()
    assert del_data["status"] == "deleted"
    assert del_data["deleted_count"] == first_rm["total_sessions"]

    # Verify roadmap is gone
    list_after = client.get("/api/roadmap/list").json()
    assert not any(r["roadmap_id"] == rm_id for r in list_after["roadmaps"])



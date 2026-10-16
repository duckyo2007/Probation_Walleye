"""7 endpoint theo API contract. Route chỉ: nhận request -> (kiểm tra Gate) -> gọi service -> trả kết quả."""
from fastapi import APIRouter

from app import config
from app.schemas.requests import (
    CompleteSessionRequest,
    ConfirmRescheduleRequest,
    InactivityRequest,
    RoadmapRequest,
    SyncRequest,
    TutorChatRequest,
)
from app.services import agent_tools, json_storage, planner
from app.services.confirmation import require_user_confirmation

router = APIRouter()


# ---------- API 1 ----------
@router.post("/schedule/sync")
def sync_schedule(req: SyncRequest):
    """Đồng bộ lịch (mock) và ĐỀ XUẤT xử lý xung đột. Không sửa tasks.json."""
    synced = agent_tools.sync_qldt_schedule(req.force_refresh)
    tasks_data = json_storage.read_json(config.TASKS_FILE)
    sessions = tasks_data.get("study_sessions", [])

    conflicts = planner.find_conflicts(synced["lessons"], sessions)
    proposals = agent_tools.resolve_conflicts_and_reschedule(conflicts, synced["lessons"], sessions)
    return {
        "status": "success",
        "source": synced["source"],
        "last_updated": synced["last_updated"],
        "is_mock": synced["is_mock"],
        "lessons": synced["lessons"],
        "tasks": sessions,
        "delay_prediction": tasks_data.get("delay_prediction_mock", {}),
        "conflicts": proposals["conflicts"],
        "note": "Chỉ là đề xuất. Lịch tự học chưa bị thay đổi.",
    }


# ---------- API 2 ----------
@router.post("/schedule/confirm-reschedule")
def confirm_reschedule(req: ConfirmRescheduleRequest):
    """Dời lịch tự học. CHỈ chạy khi user_confirmed là True."""
    # 1) Confirmation Gate - trước mọi thao tác ghi file hoặc gọi Google Calendar.
    require_user_confirmation(req.user_confirmed)

    items = [item.model_dump() for item in req.reschedule_items]

    # 2) Kiểm tra toàn bộ -> sửa -> ghi file tạm rồi thay file chính (update_json lo việc này).
    updated_tasks = json_storage.update_json(
        config.TASKS_FILE,
        lambda tasks_data: planner.apply_reschedule(tasks_data, items, req.user_confirmed),
    )

    # 3) Google Calendar: chỉ gọi sau khi đã xác nhận và đã lưu xong.
    gcal_synced, gcal_mode = False, "skipped"
    if req.sync_gcal:
        gcal = agent_tools.sync_google_calendar(updated_tasks, user_confirmed=req.user_confirmed)
        gcal_synced, gcal_mode = gcal["synced"], gcal["mode"]

    message = "Đã cập nhật lịch tự học."
    if req.sync_gcal and not gcal_synced:
        message += " Google Calendar chưa được tích hợp thật (mock) nên CHƯA đồng bộ."
    return {
        "status": "rescheduled",
        "gcal_synced": gcal_synced,
        "gcal_mode": gcal_mode,  # trường mở rộng: "mock" hoặc "skipped"
        "message": message,
        "updated_tasks": updated_tasks,
    }


# ---------- API 3 ----------
@router.post("/roadmap/generate")
def generate_roadmap(req: RoadmapRequest):
    """Chỉ tạo BẢN NHÁP. Không ghi vào tasks.json."""
    document = agent_tools.extract_document_content(req.slide_url)
    roadmap = agent_tools.generate_study_roadmap(
        req.course_code, req.course_name, req.exam_date, req.daily_free_hours, document
    )
    return {
        "status": "draft_generated",
        "is_mock": roadmap["is_mock"],
        "saved": False,
        "document_status": document["status"],
        "summary": roadmap["summary"],
        "suggested_sessions": roadmap["suggested_sessions"],
        "note": "Bản nháp, chưa được lưu. Việc lưu chính thức cần API riêng (xem mục API mở rộng trong README).",
    }


# ---------- API 4 ----------
@router.get("/workspace/enter/{task_id}")
def enter_workspace(task_id: str):
    tasks_data = json_storage.read_json(config.TASKS_FILE)
    task = planner.get_task(tasks_data, task_id)  # 404 nếu không có
    return {
        "task_info": {k: v for k, v in task.items() if k != "subtasks"},
        "checklist": task.get("subtasks", []),
        "document": agent_tools.extract_document_content(task.get("slide_url")),
    }


# ---------- API 5 ----------
@router.post("/tutor/chat")
def tutor_chat(req: TutorChatRequest):
    tasks_data = json_storage.read_json(config.TASKS_FILE)
    task = planner.get_task(tasks_data, req.task_id)
    history = [m.model_dump() for m in req.chat_history]
    return agent_tools.query_llm_tutor(task, req.user_message, req.code_snippet, history)


# ---------- API 6 ----------
@router.post("/tutor/inactivity-check")
def inactivity_check(req: InactivityRequest):
    tasks_data = json_storage.read_json(config.TASKS_FILE)
    task = planner.get_task(tasks_data, req.task_id)
    result = agent_tools.inactivity_check_trigger(task, req.current_subtask, req.inactive_minutes)
    return {"status": "ok", "is_mock": True, **result}


# ---------- API 7 ----------
@router.post("/workspace/complete")
def complete_workspace(req: CompleteSessionRequest):
    """Người dùng bấm 'Hoàn thành buổi học'. Chỉ ghi pomodoro, checklist, ghi chú, trạng thái."""

    def modify(tasks_data):
        task = planner.get_task(tasks_data, req.task_id)
        return planner.complete_session(
            task, req.pomodoro_completed, req.completed_subtask_ids, req.personal_notes
        )

    summary_card = json_storage.update_json(config.TASKS_FILE, modify)
    return {"status": "saved", "summary_card": summary_card}

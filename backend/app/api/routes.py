import re
from datetime import date
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import SLIDES_DIR
from app.schemas.requests import (
    AddExtraStudySessionRequest,
    ConfirmRescheduleRequest,
    FlashcardGenerateRequest,
    InactivityCheckRequest,
    RemoveTaskDocumentRequest,
    RoadmapConfirmSaveRequest,
    RoadmapDeleteRequest,
    RoadmapGenerateRequest,
    ScheduleSyncRequest,
    SettingsUpdateRequest,
    TutorChatRequest,
    WorkspaceCompleteRequest,
    WorkspaceSaveChatRequest,
)
from app.services.agent_tools import (
    extract_multi_documents_content,
    generate_flashcards_for_task,
    generate_study_roadmap,
    get_task_slide_urls,
    inactivity_check_trigger,
    query_llm_tutor,
    reset_inactivity_cooldowns,
)
from app.services.confirmation import verify_confirmation_gate
from app.services.internet_time import fetch_internet_date
from app.services.json_storage import (
    load_lessons,
    load_settings,
    load_tasks,
    save_lessons,
    save_settings,
    save_tasks,
)
from app.services.planner import (
    annotate_overdue,
    apply_reschedule,
    complete_workspace_session,
    compute_delay_prediction,
    delete_roadmaps,
    get_all_roadmaps,
    resolve_conflicts_and_reschedule,
    save_confirmed_roadmap_sessions,
    save_workspace_chat_history,
)
from app.services.qldt_client import (
    fetch_qldt_schedule,
    get_weeks_metadata,
)
from app.services.seed_data import ensure_initial_seed_data

router = APIRouter(prefix="/api")


@router.get("/schedule/today")
def get_today_endpoint() -> Dict[str, Any]:
    """
    Calls public internet time API to fetch the live date in Vietnam (UTC+7)
    and computes the corresponding semester week.
    """
    live_today, time_source = fetch_internet_date()
    today_iso = live_today.isoformat()
    week_offset = (live_today - date(2026, 8, 10)).days // 7 + 1
    current_week = max(1, min(31, week_offset))
    return {
        "status": "ok",
        "today": today_iso,
        "source": time_source,
        "current_week": current_week,
    }


@router.post("/schedule/sync")
def sync_schedule_endpoint(
    request: ScheduleSyncRequest = ScheduleSyncRequest(),
) -> Dict[str, Any]:
    """
    API 1: `POST /api/schedule/sync`
    Scrapes PTIT QLĐT schedule (or falls back to cached `tkb_ptit.json`),
    runs read-only conflict detection against `tasks.json`, and returns
    the unified dashboard state with live internet date.
    """
    ensure_initial_seed_data(force_reset=False)
    lessons, source, last_updated = fetch_qldt_schedule(
        force_refresh=request.force_refresh,
        username=request.username,
        password=request.password,
        hoc_ky=request.hoc_ky,
    )
    tasks = load_tasks()
    conflicts = resolve_conflicts_and_reschedule(lessons, tasks)
    live_today, time_source = fetch_internet_date()
    today_iso = live_today.isoformat()
    delay_prediction = compute_delay_prediction(tasks, lessons, today_iso)
    tasks = annotate_overdue(tasks, today_iso)
    week_offset = (live_today - date(2026, 8, 10)).days // 7 + 1
    current_week = max(1, min(31, week_offset))

    return {
        "status": "success",
        "source": source,
        "last_updated": last_updated,
        "today": today_iso,
        "today_source": time_source,
        "current_week": current_week,
        "lessons": lessons,
        "tasks": tasks,
        "delay_prediction": delay_prediction,
        "conflicts": conflicts,
        "weeks_metadata": get_weeks_metadata(),
    }


@router.post("/schedule/confirm-reschedule")
def confirm_reschedule_endpoint(
    request: ConfirmRescheduleRequest,
) -> Dict[str, Any]:
    """
    API 2: `POST /api/schedule/confirm-reschedule` (CONFIRMATION GATE)
    Strictly requires `user_confirmed: true` (boolean). Rejects otherwise with HTTP 403.
    """
    verify_confirmation_gate(request.user_confirmed)

    items_dicts = [item.model_dump() for item in request.reschedule_items]
    updated_tasks = apply_reschedule(
        reschedule_items=items_dicts,
    )
    return {
        "status": "updated",
        "message": f"Đã dời {len(updated_tasks)} phiên tự học thành công.",
        "updated_tasks": updated_tasks,
    }


@router.post("/roadmap/generate")
def generate_roadmap_endpoint(
    request: RoadmapGenerateRequest,
) -> Dict[str, Any]:
    """
    API 3: `POST /api/roadmap/generate`
    Reads one or multiple PDF slides via PyMuPDF and proposes conflict-free study sessions before `exam_date`.
    Does NOT write to `tasks.json` until `/api/roadmap/confirm-save` is called.
    """
    return generate_study_roadmap(
        course_code=request.course_code,
        course_name=request.course_name,
        exam_date=request.exam_date,
        daily_free_hours=request.daily_free_hours,
        slide_url=request.slide_url,
        slide_urls=request.slide_urls,
        base_date=request.base_date,
    )


@router.post("/roadmap/confirm-save")
def confirm_save_roadmap_endpoint(
    request: RoadmapConfirmSaveRequest,
) -> Dict[str, Any]:
    """
    API 3.1: `POST /api/roadmap/confirm-save` (CONFIRMATION GATE)
    Strictly requires `user_confirmed: true` (boolean) before saving roadmap sessions to `tasks.json`.
    """
    verify_confirmation_gate(request.user_confirmed)

    sessions_dicts = [s.model_dump() for s in request.approved_sessions]
    added_ids = save_confirmed_roadmap_sessions(
        course_code=request.course_code,
        course_name=request.course_name,
        slide_url=request.slide_url or "/static/slides/INT1306_Chuong3_CayNhiPhan.pdf",
        approved_sessions=sessions_dicts,
        slide_urls=request.slide_urls,
    )
    return {
        "status": "saved",
        "message": f"Đã thêm {len(added_ids)} phiên tự học vào lịch cá nhân.",
        "added_task_ids": added_ids,
    }


@router.get("/roadmap/list")
def list_roadmaps_endpoint() -> Dict[str, Any]:
    """
    Returns list of all active self-study roadmaps with summary statistics.
    """
    ensure_initial_seed_data(force_reset=False)
    roadmaps = get_all_roadmaps()
    return {
        "status": "ok",
        "roadmaps": roadmaps,
        "total_roadmaps": len(roadmaps),
    }


@router.post("/roadmap/delete")
def delete_roadmaps_endpoint(request: RoadmapDeleteRequest) -> Dict[str, Any]:
    """
    Deletes one or multiple roadmaps and their associated self-study sessions.
    """
    result = delete_roadmaps(
        roadmap_ids=request.roadmap_ids,
        task_ids=request.task_ids,
        course_code=request.course_code,
    )
    return result



@router.get("/workspace/enter/{task_id}")
def enter_workspace_endpoint(task_id: str) -> Dict[str, Any]:
    """
    API 4: `GET /api/workspace/enter/{task_id}`
    Loads task details and extracts ALL PDF slides attached to the session via PyMuPDF
    for the 50/50 Deep Working Workspace.
    """
    ensure_initial_seed_data(force_reset=False)
    tasks = load_tasks()
    target = next((t for t in tasks if t.get("task_id") == task_id), None)
    if target is None:
        raise HTTPException(
            status_code=404,
            detail=f"Task ID '{task_id}' not found in tasks.json",
        )

    slide_urls = get_task_slide_urls(target)
    target["slide_urls"] = slide_urls
    if slide_urls and not target.get("slide_url"):
        target["slide_url"] = slide_urls[0]

    doc_info = extract_multi_documents_content(
        slide_urls=slide_urls,
        course_name=target.get("course_name", ""),
    )

    return {
        "status": "ready",
        "task_info": target,
        "document": {
            "slide_url": doc_info["slide_url"],
            "slide_urls": doc_info["slide_urls"],
            "context_loaded": doc_info["context_loaded"],
            "page_count": doc_info["page_count"],
            "document_status": doc_info["document_status"],
            "extracted_text": doc_info["extracted_text"],
            "documents": doc_info["documents"],
        },
    }


@router.post("/tutor/chat")
def tutor_chat_endpoint(request: TutorChatRequest) -> Dict[str, Any]:
    """
    API 5: `POST /api/tutor/chat`
    Answers student questions and debugs code grounded in `<DOCUMENT_DATA>` using Gemini 3.8 Flash + Groq fallback.
    """
    history_dicts = [h.model_dump() for h in request.chat_history]
    return query_llm_tutor(
        task_id=request.task_id,
        user_message=request.user_message,
        code_snippet=request.code_snippet or "",
        chat_history=history_dicts,
        images=request.images,
    )


@router.post("/tutor/inactivity-check")
def tutor_inactivity_check_endpoint(
    request: InactivityCheckRequest,
) -> Dict[str, Any]:
    """
    API 6: `POST /api/tutor/inactivity-check`
    Proactive AI Tutor nudge after 10 minutes of inactivity, with a 300-second cooldown per `task_id`.
    """
    return inactivity_check_trigger(
        task_id=request.task_id,
        inactive_minutes=request.inactive_minutes,
        current_subtask=request.current_subtask,
    )


@router.post("/workspace/complete")
def complete_workspace_endpoint(
    request: WorkspaceCompleteRequest,
) -> Dict[str, Any]:
    """
    API 7: `POST /api/workspace/complete`
    Marks subtasks as done, records Pomodoro focus minutes & personal notes,
    saves chat conversation, and returns the Summary Card.
    """
    summary_card = complete_workspace_session(
        task_id=request.task_id,
        pomodoro_completed=request.pomodoro_completed or 1,
        completed_subtask_ids=request.completed_subtask_ids,
        personal_notes=request.personal_notes or "",
        study_duration_seconds=request.study_duration_seconds,
        chat_history=request.chat_history,
    )
    return {
        "status": "saved",
        "summary_card": summary_card,
    }


@router.post("/workspace/save-chat")
def save_workspace_chat_endpoint(
    request: WorkspaceSaveChatRequest,
) -> Dict[str, Any]:
    """
    API: `POST /api/workspace/save-chat`
    Saves the ongoing chat messages for a workspace task so they can be reviewed anytime.
    """
    return save_workspace_chat_history(
        task_id=request.task_id,
        chat_history=request.chat_history,
    )


@router.post("/workspace/flashcards")
def workspace_flashcards_endpoint(
    request: FlashcardGenerateRequest,
) -> Dict[str, Any]:
    """
    Generates 3-5 review flashcards from the task's PDF slide content.
    """
    return generate_flashcards_for_task(
        task_id=request.task_id,
        count=request.count,
    )


@router.get("/settings")
def get_settings_endpoint() -> Dict[str, Any]:
    """
    Returns saved QLĐT account status, Sunday auto-sync configuration, and LLM key status.
    """
    s = load_settings()
    return {
        "status": "ok",
        "qldt_username": s.get("qldt_username", ""),
        "has_qldt_password": bool(s.get("qldt_password")),
        "hoc_ky": s.get("hoc_ky", 20261),
        "auto_sync_sunday": bool(s.get("auto_sync_sunday", True)),
        "last_sync_at": s.get("last_sync_at"),
        "last_sync_source": s.get("last_sync_source", "fallback_cache"),
        "last_sunday_sync_date": s.get("last_sunday_sync_date"),
        "has_gemini_api_key": bool(s.get("gemini_api_key")),
        "has_groq_api_key": bool(s.get("groq_api_key")),
        "gemini_model": "gemini-3.8-flash",
    }


@router.post("/settings")
def update_settings_endpoint(request: SettingsUpdateRequest) -> Dict[str, Any]:
    """
    Saves QLĐT credentials (1-time setup), Sunday auto-sync toggle, and Gemini/Groq API keys.
    """
    updates: Dict[str, Any] = {}
    if request.qldt_username is not None:
        updates["qldt_username"] = request.qldt_username.strip()
    if request.qldt_password is not None and request.qldt_password.strip():
        updates["qldt_password"] = request.qldt_password.strip()
    if request.hoc_ky is not None:
        updates["hoc_ky"] = int(request.hoc_ky)
    if request.auto_sync_sunday is not None:
        updates["auto_sync_sunday"] = bool(request.auto_sync_sunday)
    if request.gemini_api_key is not None and request.gemini_api_key.strip():
        updates["gemini_api_key"] = request.gemini_api_key.strip()
    if request.groq_api_key is not None and request.groq_api_key.strip():
        updates["groq_api_key"] = request.groq_api_key.strip()

    s = save_settings(updates)
    return {
        "status": "saved",
        "message": "Đã lưu cấu hình tài khoản QLĐT và AI Agent thành công.",
        "qldt_username": s.get("qldt_username", ""),
        "has_qldt_password": bool(s.get("qldt_password")),
        "hoc_ky": s.get("hoc_ky", 20261),
        "auto_sync_sunday": bool(s.get("auto_sync_sunday", True)),
        "has_gemini_api_key": bool(s.get("gemini_api_key")),
        "has_groq_api_key": bool(s.get("groq_api_key")),
    }


@router.post("/documents/upload")
async def upload_pdf_document_endpoint(
    files: Optional[List[UploadFile]] = File(default=None),
    file: Optional[UploadFile] = File(default=None),
    task_id: Optional[str] = Form(default=None),
    append: bool = Form(default=True),
) -> Dict[str, Any]:
    """
    Allows uploading one or MULTIPLE `.pdf` files from the user's computer, saves them to
    `backend/static/slides/`, extracts their text via PyMuPDF, and attaches them to `task_id`
    (appending to `slide_urls` when `append=True` so 1 study session can hold multiple PDFs).
    """
    upload_list: List[UploadFile] = []
    if files:
        upload_list.extend(files)
    if file:
        upload_list.append(file)

    if not upload_list:
        raise HTTPException(status_code=400, detail="No PDF file provided")

    uploaded_urls: List[str] = []
    uploaded_names: List[str] = []

    for up in upload_list:
        raw_name = up.filename or "uploaded_slide.pdf"
        safe_name = re.sub(r"[^a-zA-Z0-9_.\-]", "_", raw_name)
        if not safe_name.lower().endswith(".pdf"):
            safe_name += ".pdf"

        content_bytes = await up.read()
        if not content_bytes:
            continue

        dest_path = SLIDES_DIR / safe_name
        dest_path.write_bytes(content_bytes)
        slide_url = f"/static/slides/{safe_name}"
        if slide_url not in uploaded_urls:
            uploaded_urls.append(slide_url)
            uploaded_names.append(safe_name)

    if not uploaded_urls:
        raise HTTPException(status_code=400, detail="Uploaded PDF file is empty")

    active_urls = list(uploaded_urls)

    if task_id:
        tasks = load_tasks()
        for t in tasks:
            if t.get("task_id") == task_id:
                existing = get_task_slide_urls(t) if append else []
                for u in uploaded_urls:
                    if u not in existing:
                        existing.append(u)
                t["slide_urls"] = existing
                t["slide_url"] = uploaded_urls[-1]
                active_urls = existing
                break
        save_tasks(tasks)

    doc_info = extract_multi_documents_content(active_urls)
    return {
        "status": "uploaded",
        "slide_url": uploaded_urls[-1],
        "slide_urls": active_urls,
        "uploaded_urls": uploaded_urls,
        "filenames": uploaded_names,
        "filename": ", ".join(uploaded_names),
        "document": doc_info,
    }


@router.post("/documents/remove")
def remove_task_document_endpoint(
    request: RemoveTaskDocumentRequest,
) -> Dict[str, Any]:
    """
    Removes a PDF document from a study session's `slide_urls` list and returns the updated document context.
    """
    tasks = load_tasks()
    target = next((t for t in tasks if t.get("task_id") == request.task_id), None)
    if target is None:
        raise HTTPException(
            status_code=404,
            detail=f"Task ID '{request.task_id}' not found in tasks.json",
        )

    current_urls = get_task_slide_urls(target)
    updated_urls = [u for u in current_urls if u != request.slide_url]
    if not updated_urls:
        raise HTTPException(
            status_code=400,
            detail="Mỗi buổi học cần giữ lại ít nhất 1 tài liệu PDF (bạn có thể tải lên file mới trước khi xóa file cuối cùng).",
        )

    target["slide_urls"] = updated_urls
    target["slide_url"] = updated_urls[0]
    save_tasks(tasks)

    doc_info = extract_multi_documents_content(
        slide_urls=updated_urls,
        course_name=target.get("course_name", ""),
    )
    return {
        "status": "removed",
        "task_info": target,
        "document": doc_info,
    }


@router.post("/schedule/simulate-conflict")
def simulate_conflict_endpoint() -> Dict[str, Any]:
    """
    Demo helper: Ensures a conflict exists in Week 10 (`2026-10-15` `08:00 - 09:30`
    between `task_001` and fixed school lesson `INT1306`) so the user can test
    Screen 02 (Conflict Modal & Confirmation Gate) anytime.
    """
    reset_inactivity_cooldowns()
    lessons = load_lessons()
    demo_key = "INT1306_2026-10-15_0700"
    if not any(l.get("key") == demo_key for l in lessons):
        lessons.append(
            {
                "key": demo_key,
                "week": 10,
                "date": "2026-10-15",
                "start": "07:00",
                "end": "09:50",
                "course_code": "INT1306",
                "course_name": "Cấu trúc dữ liệu và giải thuật",
                "teacher": "Bùi Văn Kiên",
                "room": "704-A2-704-A2(HN)",
                "online": False,
                "cancelled": False,
                "makeup": True,
                "slide_url": "/static/slides/INT1306_Chuong3_CayNhiPhan.pdf",
            }
        )
        save_lessons(lessons)

    tasks = load_tasks()
    tasks = [
        t for t in tasks
        if not ("học bù tăng cường" in (t.get("title") or "").lower())
    ]
    found_task_001 = False
    for t in tasks:
        if t.get("task_id") == "task_001":
            t["week"] = 10
            t["date"] = "2026-10-15"
            t["start"] = "08:00"
            t["end"] = "09:30"
            t["status"] = "todo"
            t["is_flexible"] = True
            found_task_001 = True
            break

    if not found_task_001:
        ensure_initial_seed_data(force_reset=True, demo_tasks=True)
        tasks = load_tasks()
    else:
        save_tasks(tasks)

    conflicts = resolve_conflicts_and_reschedule(lessons, tasks)
    today_iso = fetch_internet_date()[0].isoformat()
    delay_prediction = compute_delay_prediction(tasks, lessons, today_iso)
    tasks = annotate_overdue(tasks, today_iso)
    return {
        "status": "success",
        "message": "Đã khôi phục tình huống xung đột lịch học mẫu tại Tuần 10 (Thứ 5, 15/10/2026).",
        "conflicts": conflicts,
        "lessons": lessons,
        "tasks": tasks,
        "delay_prediction": delay_prediction,
    }


@router.post("/schedule/add-extra-session")
def add_extra_study_session_endpoint(
    request: AddExtraStudySessionRequest,
) -> Dict[str, Any]:
    """
    Confirmation-gated action for the Delay Prediction widget (`[Xếp thêm 1 buổi học bù tối nay]`).
    """
    verify_confirmation_gate(request.user_confirmed)
    added_ids = save_confirmed_roadmap_sessions(
        course_code=request.course_code,
        course_name=request.course_name,
        slide_url=request.slide_url,
        slide_urls=request.slide_urls,
        approved_sessions=[
            {
                "title": request.title,
                "date": request.date,
                "start": request.start,
                "end": request.end,
                "is_flexible": True,
                "slide_url": request.slide_url,
                "slide_urls": request.slide_urls,
                "subtasks": [
                    {"sub_id": "sub_1", "content": "Hoàn thành các bài tập còn tồn đọng trong tuần", "done": False},
                    {"sub_id": "sub_2", "content": "Ôn tập nhanh Flashcard chuẩn bị cho hạn nộp bài tập lớn", "done": False},
                ],
            }
        ],
    )
    return {
        "status": "saved",
        "message": "Đã xếp thêm 1 buổi học bù chống trễ hạn vào lịch cá nhân.",
        "added_task_ids": added_ids,
    }

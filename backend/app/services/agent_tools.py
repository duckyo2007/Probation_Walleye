"""Các tool của AI Agent. Tích hợp module đồng bộ QLĐT, xử lý xung đột và Google Calendar."""
import math
import time
from datetime import date, timedelta

from app import config
from app.services import json_storage, planner
from app.services.confirmation import require_user_confirmation
from app.services.sync_qldt_schedule import sync_qldt_schedule as real_sync_qldt
from app.services.conflict_resolver import resolve_conflicts_and_reschedule as real_resolve_conflicts
from app.services.gcal_sync import sync_google_calendar as real_sync_gcal


# ---------------------------------------------------------------- QLĐT
def sync_qldt_schedule(force_refresh: bool = False) -> dict:
    """Đồng bộ thời khóa biểu từ QLĐT sử dụng module sync thực tế (hỗ trợ Live API và Fallback)."""
    result = real_sync_qldt()
    
    return {
        "source": result.get("source"),
        "last_updated": result.get("fetched_at"),
        "lessons": result.get("lessons", []),
        "is_mock": result.get("source") in ["fixture", "cache"],
        "status": result.get("status"),
        "warning": result.get("warning"),
        "changes": result.get("changes")
    }


def resolve_conflicts_and_reschedule(conflicts: list, lessons: list, sessions: list) -> dict:
    """Ủy quyền thuật toán xử lý xung đột và tìm slot trống cho module conflict_resolver."""
    return real_resolve_conflicts(conflicts, lessons, sessions)


# ------------------------------------------------------ Google Calendar
def sync_google_calendar(tasks: list, user_confirmed) -> dict:
    """Ủy quyền đồng bộ Google Calendar cho module gcal_sync."""
    return real_sync_gcal(tasks, user_confirmed)


# ---------------------------------------------------------------- Tài liệu
def extract_document_content(slide_url) -> dict:
    """MOCK: chưa có đọc PDF/OCR, nên không bao giờ trả nội dung giả."""
    if not slide_url:
        return {"status": "no_document", "slide_url": None, "text": None,
                "message": "Task chưa có tài liệu (slide_url trống)."}
    return {"status": "not_extracted", "slide_url": slide_url, "text": None,
            "message": "Có đường dẫn tài liệu nhưng chức năng đọc PDF/OCR chưa được tích hợp "
                       "(mock), nên nội dung chưa được trích xuất."}


_ROADMAP_STEPS = [
    ("Nắm lại tổng quan", ["Đọc lại mục lục và mục tiêu môn học", "Ghi ra 5 khái niệm chính"]),
    ("Đọc lại slide và ghi chú", ["Đọc slide các tuần đã học", "Tóm tắt mỗi tuần trong 3 ý"]),
    ("Làm bài tập và ví dụ", ["Làm lại các bài tập trên lớp", "Đánh dấu bài làm chưa được"]),
    ("Ôn lại phần còn yếu", ["Xem lại các bài đã đánh dấu", "Tự giải thích lại bằng lời của mình"]),
    ("Làm đề thử và rà soát", ["Làm một đề thử có bấm giờ", "Rà lỗi sai và ghi lại cách sửa"]),
]


def generate_study_roadmap(course_code: str, course_name: str, exam_date: str,
                           daily_free_hours: float, document: dict) -> dict:
    """MOCK: sinh lộ trình mẫu theo mẫu cố định, chưa dùng LLM và chưa đọc tài liệu."""
    exam = planner.parse_date(exam_date)
    days_left = (exam - date.today()).days
    if days_left < 1:
        raise planner.PlanError(400, "exam_date phải sau hôm nay")

    n = max(1, min(5, days_left - 1))
    step = max(1, (days_left - 1) // n)
    duration = min(max(int(daily_free_hours * 60), 30), 180)
    start = 19 * 60

    steps = _ROADMAP_STEPS[: n - 1] + [_ROADMAP_STEPS[-1]] if n > 1 else [_ROADMAP_STEPS[-1]]
    sessions = []
    for i, (title, subtasks) in enumerate(steps):
        day = max(exam - timedelta(days=(n - i) * step), date.today())
        sessions.append({
            "title": f"{title} - {course_name}",
            "course_code": course_code,
            "course_name": course_name,
            "date": day.isoformat(),
            "start": planner.to_hhmm(start),
            "end": planner.to_hhmm(start + duration),
            "is_flexible": True,
            "subtasks": [{"sub_id": f"draft_{i + 1}_{j + 1}", "content": text, "done": False}
                         for j, text in enumerate(subtasks)],
        })

    doc_note = ("chưa có tài liệu" if document["status"] == "no_document"
                else "tài liệu chưa được đọc (mock)")
    return {
        "summary": f"Bản nháp {n} buổi ôn tập {course_name} ({course_code}) trước kỳ thi ngày "
                   f"{exam_date}, mỗi buổi khoảng {duration} phút; {doc_note}. "
                   "Đây là kết quả mock theo mẫu cố định.",
        "suggested_sessions": sessions,
        "is_mock": True,
    }


# ---------------------------------------------------------------- Gia sư AI
def query_llm_tutor(task: dict, user_message: str, code_snippet, chat_history: list) -> dict:
    """MOCK: không gọi LLM thật và không cần API key."""
    lines = [
        "*(Phản hồi mock - chưa kết nối LLM thật)*",
        "",
        f"Bạn đang học **{task['title']}** ({task['course_code']}).",
        "",
        f"Câu hỏi của bạn: {user_message}",
        "",
        "Gợi ý chung: chia nhỏ vấn đề, thử một ví dụ đơn giản trước, rồi tự giải thích lại bằng lời của mình.",
    ]
    if code_snippet:
        lines += ["", f"Bạn có gửi kèm đoạn code ({len(code_snippet.splitlines())} dòng); "
                     "bản mock chưa phân tích đoạn code này."]
    return {"status": "success", "provider_used": "mock", "reply_markdown": "\n".join(lines)}


# ------------------------------------------------------- Nhắc học (inactivity)
_last_reminder: dict = {}


def reset_reminder_state() -> None:
    _last_reminder.clear()


def inactivity_check_trigger(task: dict, current_subtask, inactive_minutes: int, now=None) -> dict:
    """MOCK: chỉ nhắc khi inactive_minutes >= ngưỡng, và không quá 1 lần mỗi khoảng cooldown."""
    if inactive_minutes < config.INACTIVITY_THRESHOLD_MINUTES:
        return {"should_remind": False, "skip_reason": "below_threshold",
                "message": None, "retry_after_seconds": None}

    now = time.monotonic() if now is None else now
    cooldown = config.get_inactivity_cooldown_seconds()
    last = _last_reminder.get(task["task_id"])
    if last is not None and now - last < cooldown:
        return {"should_remind": False, "skip_reason": "rate_limited", "message": None,
                "retry_after_sessions": None, "retry_after_seconds": max(1, math.ceil(cooldown - (now - last)))}

    _last_reminder[task["task_id"]] = now
    target = f'bước "{current_subtask}"' if current_subtask else f'buổi học "{task["title"]}"'
    return {
        "should_remind": True,
        "skip_reason": None,
        "message": f"Bạn đã dừng khoảng {inactive_minutes} phút rồi. Mình quay lại {target} nhé? "
                   "Chỉ cần làm một phần nhỏ trong 5 phút thôi.",
        "retry_after_seconds": None,
    }
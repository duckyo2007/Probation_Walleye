<<<<<<< HEAD
"""Các tool của AI Agent. Tích hợp module đồng bộ QLĐT, xử lý xung đột và Google Calendar."""
=======
"""Các tool của AI Agent. HIỆN TẠI TẤT CẢ ĐỀU LÀ MOCK.

Mỗi hàm có input/output rõ ràng; routes chỉ gọi các hàm này. Khi thành viên
khác tích hợp tool thật, chỉ cần thay phần thân hàm, giữ nguyên chữ ký và
dạng dict trả về thì không phải sửa routes.

Mapping API -> tool:
  API 1 /schedule/sync              -> sync_qldt_schedule, resolve_conflicts_and_reschedule (chỉ đề xuất)
  API 2 /schedule/confirm-reschedule -> sync_google_calendar (chỉ sau khi đã xác nhận)
  API 3 /roadmap/generate           -> extract_document_content, generate_study_roadmap
  API 4 /workspace/enter/{task_id}  -> extract_document_content
  API 5 /tutor/chat                 -> query_llm_tutor
  API 6 /tutor/inactivity-check     -> inactivity_check_trigger
  (Nếu tên tool trong contract của nhóm khác, hãy đổi tên hàm ở đây và ghi lại mapping.)
"""
>>>>>>> 7c64ba8e504c34dcf9c1f53235de2acfcf51964c
import math
import time
from datetime import date, timedelta

from app import config
from app.services import json_storage, planner
from app.services.confirmation import require_user_confirmation
<<<<<<< HEAD
from app.services.sync_qldt_schedule import sync_qldt_schedule as real_sync_qldt
from app.services.conflict_resolver import resolve_conflicts_and_reschedule as real_resolve_conflicts
from app.services.gcal_sync import sync_google_calendar as real_sync_gcal
=======
>>>>>>> 7c64ba8e504c34dcf9c1f53235de2acfcf51964c


# ---------------------------------------------------------------- QLĐT
def sync_qldt_schedule(force_refresh: bool = False) -> dict:
<<<<<<< HEAD
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
=======
    """MOCK: chưa kết nối QLĐT thật; `force_refresh` chưa được dùng.

    Đọc qldt_fallback_response.json; nếu không có thì dùng lessons.json.
    Chỉ ĐỌC, không ghi file nào.
    """
    if json_storage.exists(config.FALLBACK_FILE):
        data = json_storage.read_json(config.FALLBACK_FILE)
        return {
            "source": "qldt_fallback_file",
            "last_updated": data.get("last_updated"),
            "lessons": data["lessons"],
            "is_mock": True,
        }
    return {
        "source": "lessons_json_sample",
        "last_updated": None,
        "lessons": json_storage.read_json(config.LESSONS_FILE),
        "is_mock": True,
>>>>>>> 7c64ba8e504c34dcf9c1f53235de2acfcf51964c
    }


def resolve_conflicts_and_reschedule(conflicts: list, lessons: list, sessions: list) -> dict:
<<<<<<< HEAD
    """Ủy quyền thuật toán xử lý xung đột và tìm slot trống cho module conflict_resolver."""
    return real_resolve_conflicts(conflicts, lessons, sessions)
=======
    """MOCK, CHỈ ĐỀ XUẤT: gắn `suggested_slot` cho từng xung đột. KHÔNG sửa lịch nào."""
    proposals = []
    for c in conflicts:
        slot = None
        if c["is_flexible"]:
            duration = planner.to_minutes(c["task_end"]) - planner.to_minutes(c["task_start"])
            slot = planner.suggest_slot(duration, c["date"], planner.to_minutes(c["task_start"]),
                                        lessons, sessions, ignore_task_id=c["task_id"])
        proposals.append({**c, "suggested_slot": slot})
    return {"applied": False, "mode": "mock", "conflicts": proposals}
>>>>>>> 7c64ba8e504c34dcf9c1f53235de2acfcf51964c


# ------------------------------------------------------ Google Calendar
def sync_google_calendar(tasks: list, user_confirmed) -> dict:
<<<<<<< HEAD
    """Ủy quyền đồng bộ Google Calendar cho module gcal_sync."""
    return real_sync_gcal(tasks, user_confirmed)
=======
    """MOCK: chưa gọi Google Calendar thật nên luôn trả synced=False.

    Tự từ chối nếu chưa có xác nhận (không thể gọi tool này khi chưa xác nhận).
    Task đã có gcal_event_id -> "would_update" (cập nhật, không tạo trùng).
    """
    require_user_confirmation(user_confirmed)
    results = []
    for t in tasks:
        event_id = t.get("gcal_event_id")
        results.append({
            "task_id": t["task_id"],
            "action": "would_update" if event_id else "would_create",
            "gcal_event_id": event_id,
        })
    return {"synced": False, "mode": "mock", "results": results}
>>>>>>> 7c64ba8e504c34dcf9c1f53235de2acfcf51964c


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
<<<<<<< HEAD
                     "bản mock chưa phân tích đoạn code này."]
=======
                      "bản mock chưa phân tích đoạn code này."]
>>>>>>> 7c64ba8e504c34dcf9c1f53235de2acfcf51964c
    return {"status": "success", "provider_used": "mock", "reply_markdown": "\n".join(lines)}


# ------------------------------------------------------- Nhắc học (inactivity)
<<<<<<< HEAD
=======
# Mock state trong bộ nhớ, tách theo từng task_id. Giới hạn: mất khi khởi động lại
# server và không dùng chung giữa nhiều worker. Chưa có session bền vững.
>>>>>>> 7c64ba8e504c34dcf9c1f53235de2acfcf51964c
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
<<<<<<< HEAD
                "retry_after_sessions": None, "retry_after_seconds": max(1, math.ceil(cooldown - (now - last)))}
=======
                "retry_after_seconds": max(1, math.ceil(cooldown - (now - last)))}
>>>>>>> 7c64ba8e504c34dcf9c1f53235de2acfcf51964c

    _last_reminder[task["task_id"]] = now
    target = f'bước "{current_subtask}"' if current_subtask else f'buổi học "{task["title"]}"'
    return {
        "should_remind": True,
        "skip_reason": None,
        "message": f"Bạn đã dừng khoảng {inactive_minutes} phút rồi. Mình quay lại {target} nhé? "
                   "Chỉ cần làm một phần nhỏ trong 5 phút thôi.",
        "retry_after_seconds": None,
<<<<<<< HEAD
    }
=======
    }
>>>>>>> 7c64ba8e504c34dcf9c1f53235de2acfcf51964c

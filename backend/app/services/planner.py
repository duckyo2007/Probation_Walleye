"""Logic lịch học bằng Python thuần (không phụ thuộc FastAPI):
phát hiện xung đột, đề xuất khung giờ, dời lịch, tổng kết buổi học.
"""
from datetime import date, datetime, timedelta

from app import config
from app.services.confirmation import require_user_confirmation

DAY_START = 8 * 60    # 08:00 - không đề xuất sớm hơn
DAY_END = 22 * 60     # 22:00 - không đề xuất muộn hơn
SLOT_STEP = 30        # thử từng bước 30 phút
SEARCH_DAYS = 3       # tìm trong ngày gốc và 2 ngày sau


class PlanError(Exception):
    """Lỗi nghiệp vụ kèm mã HTTP (400, 404...). main.py đổi thành response JSON."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


# ---------- Tiện ích ngày giờ ----------
def parse_date(value) -> date:
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        raise PlanError(400, f"Ngày không hợp lệ: {value!r} (cần dạng YYYY-MM-DD)")


def to_minutes(value) -> int:
    try:
        t = datetime.strptime(value, "%H:%M")
    except (ValueError, TypeError):
        raise PlanError(400, f"Giờ không hợp lệ: {value!r} (cần dạng HH:MM)")
    return t.hour * 60 + t.minute


def to_hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _overlap(start_a, end_a, start_b, end_b) -> bool:
    # Hai khoảng chạm nhau (kết thúc 19:00, bắt đầu 19:00) KHÔNG tính là trùng.
    return start_a < end_b and start_b < end_a


def get_task(tasks_data: dict, task_id: str) -> dict:
    for task in tasks_data.get("study_sessions", []):
        if task.get("task_id") == task_id:
            return task
    raise PlanError(404, f"Không tìm thấy task: {task_id}")


# ---------- Xung đột & đề xuất ----------
def find_conflicts(lessons: list, sessions: list) -> list:
    """Buổi tự học (chưa hoàn thành) trùng giờ với buổi học chưa bị hủy."""
    conflicts = []
    for session in sessions:
        if session.get("status") == "completed":
            continue
        s_start, s_end = to_minutes(session["start"]), to_minutes(session["end"])
        for lesson in lessons:
            if lesson.get("cancelled") or lesson["date"] != session["date"]:
                continue
            l_start, l_end = to_minutes(lesson["start"]), to_minutes(lesson["end"])
            if _overlap(s_start, s_end, l_start, l_end):
                conflicts.append({
                    "task_id": session["task_id"],
                    "task_title": session["title"],
                    "course_name": session["course_name"],
                    "date": session["date"],
                    "task_start": session["start"],
                    "task_end": session["end"],
                    "is_flexible": bool(session.get("is_flexible")),
                    "lesson_key": lesson["key"],
                    "lesson_course_name": lesson["course_name"],
                    "lesson_start": lesson["start"],
                    "lesson_end": lesson["end"],
                    "reason": f"Trùng với buổi học {lesson['course_name']} "
                              f"({lesson['start']}–{lesson['end']})",
                })
    return conflicts


def _busy_ranges(day: str, lessons, sessions, ignore_task_id):
    busy = []
    for lesson in lessons:
        if not lesson.get("cancelled") and lesson["date"] == day:
            busy.append((to_minutes(lesson["start"]), to_minutes(lesson["end"])))
    for s in sessions:
        if s["date"] == day and s["task_id"] != ignore_task_id and s.get("status") != "completed":
            busy.append((to_minutes(s["start"]), to_minutes(s["end"])))
    return busy


def suggest_slot(duration, date_str, earliest, lessons, sessions, ignore_task_id=None):
    """Tìm khung giờ trống đầu tiên, bắt đầu từ `earliest` (phút) của ngày gốc.

    Trả về {"date","start","end"} hoặc None nếu không tìm thấy. Chỉ ĐỀ XUẤT, không ghi gì.
    """
    first_day = parse_date(date_str)
    for offset in range(SEARCH_DAYS):
        day = (first_day + timedelta(days=offset)).isoformat()
        busy = _busy_ranges(day, lessons, sessions, ignore_task_id)
        start = max(earliest if offset == 0 else DAY_START, DAY_START)
        start = -(-start // SLOT_STEP) * SLOT_STEP  # làm tròn lên bội số của 30
        while start + duration <= DAY_END:
            if not any(_overlap(start, start + duration, b0, b1) for b0, b1 in busy):
                return {"date": day, "start": to_hhmm(start), "end": to_hhmm(start + duration)}
            start += SLOT_STEP
    return None


# ---------- Dời lịch (CHỈ gọi sau khi đã xác nhận) ----------
def apply_reschedule(tasks_data: dict, items: list, user_confirmed) -> list:
    """Dời lịch các task. Kiểm tra HẾT trước, hợp lệ hết mới sửa (tất cả hoặc không gì).

    Tự kiểm tra xác nhận thêm một lần nữa (lớp bảo vệ thứ hai) phòng khi
    sau này có route khác gọi hàm này mà quên kiểm tra.
    """
    require_user_confirmation(user_confirmed)

    seen = set()
    checked = []
    for item in items:
        task_id = item["task_id"]
        if task_id in seen:
            raise PlanError(400, f"task_id bị lặp trong yêu cầu: {task_id}")
        seen.add(task_id)
        task = get_task(tasks_data, task_id)  # 404 nếu không tồn tại
        new_date = parse_date(item["new_date"]).isoformat()
        start, end = to_minutes(item["new_start"]), to_minutes(item["new_end"])
        if end <= start:
            raise PlanError(400, f"Giờ kết thúc phải sau giờ bắt đầu (task {task_id})")
        checked.append((task, new_date, to_hhmm(start), to_hhmm(end)))

    updated = []
    for task, new_date, new_start, new_end in checked:
        task["date"], task["start"], task["end"] = new_date, new_start, new_end
        updated.append(dict(task))
    return updated


# ---------- Hoàn thành buổi học ----------
def complete_session(task: dict, pomodoro_completed: int, completed_subtask_ids: list,
                     personal_notes: str) -> dict:
    """Ghi tiến độ vào `task` (chỉ pomodoro, checklist, ghi chú, trạng thái) và trả summary_card."""
    if pomodoro_completed < 0:
        raise PlanError(400, "pomodoro_completed không được âm")

    subtasks = task.get("subtasks", [])
    valid_ids = {s["sub_id"] for s in subtasks}
    unknown = [i for i in completed_subtask_ids if i not in valid_ids]
    if unknown:
        raise PlanError(400, "completed_subtask_ids chứa ID không thuộc task này: "
                             + ", ".join(unknown))

    done_ids = set(completed_subtask_ids)
    for s in subtasks:
        s["done"] = s["sub_id"] in done_ids
    task["pomodoro_completed"] = pomodoro_completed
    task["personal_notes"] = personal_notes
    task["status"] = "completed"

    total = len(subtasks)
    done_count = sum(1 for s in subtasks if s["done"])
    return {
        "task_id": task["task_id"],
        "course_name": task["course_name"],
        "title": task["title"],
        "total_focus_minutes": pomodoro_completed * config.POMODORO_MINUTES,
        "pomodoro_result": f"{pomodoro_completed}/{task.get('pomodoro_target', 0)}",
        "completed_tasks_count": done_count,
        "total_subtasks": total,
        "completion_rate_percent": round(done_count / total * 100, 1) if total else 0.0,
        "remaining_subtasks": [
            {"sub_id": s["sub_id"], "content": s["content"]} for s in subtasks if not s["done"]
        ],
    }

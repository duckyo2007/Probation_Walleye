from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException

from app.services.json_storage import load_lessons, load_tasks, save_tasks


def time_to_minutes(t_str: str) -> int:
    try:
        parts = t_str.strip().split(":")
        if len(parts) != 2:
            raise ValueError("Invalid HH:MM")
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError("Out of bounds")
        return h * 60 + m
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid time format '{t_str}'. Expected HH:MM.",
        ) from exc


def minutes_to_time(total_minutes: int) -> str:
    total_minutes = max(0, min(23 * 60 + 59, total_minutes))
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def parse_date_strict(d_str: str) -> date:
    try:
        return datetime.strptime(d_str.strip(), "%Y-%m-%d").date()
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date format '{d_str}'. Expected YYYY-MM-DD.",
        ) from exc


def intervals_overlap(s1: int, e1: int, s2: int, e2: int) -> bool:
    return s1 < e2 and s2 < e1


def find_free_slot_on_or_after(
    target_date_str: str,
    duration_minutes: int,
    lessons: List[Dict[str, Any]],
    tasks: List[Dict[str, Any]],
    exclude_task_id: Optional[str] = None,
) -> Tuple[str, str, str]:
    """
    Finds the best conflict-free slot of `duration_minutes` starting on `target_date_str`
    (preferring 19:30 evening slot first, then 14:00 afternoon, 16:00, 08:00, 20:00).
    Searches up to 7 days ahead if the target day is completely packed.
    """
    base_date = parse_date_strict(target_date_str)
    candidate_starts = [
        19 * 60 + 30,  # 19:30 (Primary evening self-study slot)
        14 * 60,       # 14:00
        16 * 60,       # 16:00
        20 * 60,       # 20:00
        8 * 60,        # 08:00
        9 * 60 + 30,   # 09:30
        18 * 60,       # 18:00
    ]

    for day_offset in range(0, 8):
        curr_date_str = (base_date + timedelta(days=day_offset)).strftime("%Y-%m-%d")
        busy_intervals: List[Tuple[int, int]] = []

        for les in lessons:
            if les.get("cancelled"):
                continue
            if les.get("date") == curr_date_str:
                try:
                    busy_intervals.append(
                        (time_to_minutes(les["start"]), time_to_minutes(les["end"]))
                    )
                except Exception:
                    pass

        for tsk in tasks:
            if tsk.get("task_id") == exclude_task_id:
                continue
            if tsk.get("status") == "done":
                continue
            if tsk.get("date") == curr_date_str:
                try:
                    busy_intervals.append(
                        (time_to_minutes(tsk["start"]), time_to_minutes(tsk["end"]))
                    )
                except Exception:
                    pass

        for start_min in candidate_starts:
            end_min = start_min + duration_minutes
            if end_min > 23 * 60:
                continue
            has_clash = any(
                intervals_overlap(start_min, end_min, b_start, b_end)
                for b_start, b_end in busy_intervals
            )
            if not has_clash:
                return (
                    curr_date_str,
                    minutes_to_time(start_min),
                    minutes_to_time(end_min),
                )

    # Fallback if all candidates are busy
    return target_date_str, "19:30", minutes_to_time(19 * 60 + 30 + duration_minutes)


def resolve_conflicts_and_reschedule(
    lessons: List[Dict[str, Any]],
    tasks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Tool 2 (`resolve_conflicts_and_reschedule`):
    Strictly READ-ONLY. Detects overlaps between fixed school lessons (`lessons.json`)
    and flexible self-study sessions (`tasks.json`), and returns suggested conflict-free
    slots without modifying `tasks.json`.
    """
    conflicts: List[Dict[str, Any]] = []
    # Track virtual placements so multiple conflicting tasks don't get suggested the exact same slot
    virtual_tasks = [dict(t) for t in tasks]

    for idx, task in enumerate(tasks):
        if not task.get("is_flexible", True):
            continue
        if task.get("status") == "done":
            continue

        t_date = str(task.get("date") or "")
        if not t_date:
            continue

        try:
            t_start = time_to_minutes(str(task.get("start") or "08:00"))
            t_end = time_to_minutes(str(task.get("end") or "09:30"))
        except Exception:
            continue

        duration = max(60, t_end - t_start)

        conflicting_lesson: Optional[Dict[str, Any]] = None
        for les in lessons:
            if les.get("cancelled"):
                continue
            if les.get("date") != t_date:
                continue
            try:
                l_start = time_to_minutes(str(les.get("start") or "07:00"))
                l_end = time_to_minutes(str(les.get("end") or "09:50"))
            except Exception:
                continue

            if intervals_overlap(t_start, t_end, l_start, l_end):
                conflicting_lesson = les
                break

        if conflicting_lesson is not None:
            new_date, new_start, new_end = find_free_slot_on_or_after(
                target_date_str=t_date,
                duration_minutes=duration,
                lessons=lessons,
                tasks=virtual_tasks,
                exclude_task_id=task.get("task_id"),
            )
            virtual_tasks[idx]["date"] = new_date
            virtual_tasks[idx]["start"] = new_start
            virtual_tasks[idx]["end"] = new_end

            room_label = conflicting_lesson.get("room") or "Phòng học"
            course_label = conflicting_lesson.get("course_name") or conflicting_lesson.get("course_code")
            conflicts.append(
                {
                    "task_id": task.get("task_id"),
                    "task_title": task.get("title"),
                    "conflict_with": f"{course_label} (Phòng {room_label})",
                    "old_date": t_date,
                    "old_time": f"{task.get('start')} - {task.get('end')}",
                    "new_suggested_date": new_date,
                    "new_suggested_time": f"{new_start} - {new_end}",
                    "reason": (
                        "Trùng lịch học bù mới phát sinh trên QLĐT"
                        if conflicting_lesson.get("makeup")
                        else "Trùng lịch học cố định trên trường (QLĐT)"
                    ),
                }
            )

    return conflicts


def compute_delay_prediction(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Returns the Delay Prediction widget payload (marked `is_mock: True` per Week 1/2 spec).
    """
    todo_tasks = [t for t in tasks if t.get("status") != "done"]
    primary_course = todo_tasks[0].get("course_code", "INT1306") if todo_tasks else "INT1306"
    return {
        "is_mock": True,
        "course_code": primary_course,
        "risk_percent": 78,
        "reason": "Bạn đã lỡ 2 phiên tự học tuần này. Còn 3 ngày nữa đến hạn nộp bài tập lớn.",
        "suggested_action": "Xếp thêm 1 buổi học bù tối nay (19:30 - 21:00)",
    }


def apply_reschedule(
    reschedule_items: List[Dict[str, Any]],
    sync_gcal: bool = True,
) -> List[Dict[str, Any]]:
    """
    Applies user-confirmed rescheduling items to `tasks.json` and updates Google Calendar IDs.
    """
    if not reschedule_items:
        raise HTTPException(
            status_code=400,
            detail="reschedule_items cannot be empty",
        )

    tasks = load_tasks()
    task_map = {t.get("task_id"): t for t in tasks}
    updated_summary: List[Dict[str, Any]] = []

    # Validate all items before writing
    for item in reschedule_items:
        tid = item.get("task_id")
        if tid not in task_map:
            raise HTTPException(
                status_code=404,
                detail=f"Task ID '{tid}' not found in tasks.json",
            )
        new_date = str(item.get("new_date") or "").strip()
        new_start = str(item.get("new_start") or "").strip()
        new_end = str(item.get("new_end") or "").strip()
        parse_date_strict(new_date)
        s_min = time_to_minutes(new_start)
        e_min = time_to_minutes(new_end)
        if e_min <= s_min:
            raise HTTPException(
                status_code=400,
                detail="Invalid time range: new_end must be greater than new_start",
            )

    for item in reschedule_items:
        tid = item["task_id"]
        target = task_map[tid]
        target["date"] = item["new_date"].strip()
        target["start"] = item["new_start"].strip()
        target["end"] = item["new_end"].strip()
        if sync_gcal:
            compact_date = target["date"].replace("-", "")
            compact_start = target["start"].replace(":", "")
            target["gcal_event_id"] = f"gcal_task_{tid}_{compact_date}_{compact_start}"
        updated_summary.append(
            {
                "task_id": tid,
                "date": target["date"],
                "start": target["start"],
                "end": target["end"],
                "status": target.get("status", "todo"),
                "gcal_event_id": target.get("gcal_event_id"),
            }
        )

    save_tasks(tasks)
    return updated_summary


def find_conflict_free_slots_for_roadmap(
    exam_date_str: str,
    daily_free_hours: float,
    num_sessions: int = 3,
    base_date_str: Optional[str] = None,
) -> List[Tuple[str, str, str]]:
    """
    Deterministically finds `num_sessions` conflict-free slots before `exam_date_str`
    using Python time arithmetic (never relying on LLM for date/time math).
    """
    exam_date = parse_date_strict(exam_date_str)
    # Default start date: 2026-10-16 (within PTIT Week 10) or today if earlier than exam_date
    if base_date_str:
        start_date = parse_date_strict(base_date_str)
    else:
        default_anchor = date(2026, 10, 16)
        start_date = default_anchor if default_anchor < exam_date else exam_date - timedelta(days=max(3, num_sessions))

    if exam_date < start_date:
        raise HTTPException(
            status_code=400,
            detail="exam_date must not be in the past relative to the study start date",
        )

    duration_minutes = int(round(max(1.0, min(4.0, daily_free_hours)) * 60))
    lessons = load_lessons()
    tasks = load_tasks()
    virtual_tasks = [dict(t) for t in tasks]

    slots: List[Tuple[str, str, str]] = []
    curr_date = start_date
    for i in range(num_sessions):
        target_str = curr_date.strftime("%Y-%m-%d")
        s_date, s_start, s_end = find_free_slot_on_or_after(
            target_date_str=target_str,
            duration_minutes=duration_minutes,
            lessons=lessons,
            tasks=virtual_tasks,
        )
        slots.append((s_date, s_start, s_end))
        virtual_tasks.append(
            {
                "task_id": f"temp_roadmap_{i}",
                "date": s_date,
                "start": s_start,
                "end": s_end,
                "status": "todo",
            }
        )
        next_day = parse_date_strict(s_date) + timedelta(days=1)
        curr_date = next_day if next_day <= exam_date else parse_date_strict(s_date)

    return slots


def save_confirmed_roadmap_sessions(
    course_code: str,
    course_name: str,
    slide_url: str,
    approved_sessions: List[Dict[str, Any]],
    slide_urls: Optional[List[str]] = None,
) -> List[str]:
    """
    Saves user-confirmed roadmap sessions to `tasks.json` and returns `added_task_ids`.
    """
    if not approved_sessions:
        raise HTTPException(
            status_code=400,
            detail="approved_sessions cannot be empty",
        )

    tasks = load_tasks()
    existing_nums = []
    for t in tasks:
        tid = str(t.get("task_id") or "")
        if tid.startswith("task_") and tid[5:].isdigit():
            existing_nums.append(int(tid[5:]))
    next_num = (max(existing_nums) + 1) if existing_nums else 1

    added_ids: List[str] = []
    for session in approved_sessions:
        s_date = str(session.get("date") or "").strip()
        s_start = str(session.get("start") or "").strip()
        s_end = str(session.get("end") or "").strip()
        parse_date_strict(s_date)
        if time_to_minutes(s_end) <= time_to_minutes(s_start):
            raise HTTPException(
                status_code=400,
                detail="Invalid session time range: end must be greater than start",
            )

        new_tid = f"task_{next_num:03d}"
        next_num += 1

        try:
            week_offset = (parse_date_strict(s_date) - date(2026, 8, 10)).days // 7 + 1
            week_num = max(1, week_offset)
        except Exception:
            week_num = 10

        raw_subtasks = session.get("subtasks") or []
        subtasks = []
        for idx, sub in enumerate(raw_subtasks, start=1):
            if isinstance(sub, dict):
                subtasks.append(
                    {
                        "sub_id": str(sub.get("sub_id") or f"sub_{idx}"),
                        "content": str(sub.get("content") or f"Mục tiêu {idx}"),
                        "done": bool(sub.get("done", False)),
                    }
                )

        if not subtasks:
            subtasks = [
                {"sub_id": "sub_1", "content": f"Đọc lý thuyết cốt lõi {session.get('title')}", "done": False},
                {"sub_id": "sub_2", "content": "Làm bài tập vận dụng & ghi chú câu hỏi", "done": False},
            ]

        compact_date = s_date.replace("-", "")
        compact_start = s_start.replace(":", "")
        primary_slide = str(
            session.get("slide_url")
            or (slide_urls[0] if slide_urls else None)
            or slide_url
            or "/static/slides/INT1306_Chuong3_CayNhiPhan.pdf"
        )
        session_slide_urls = session.get("slide_urls") or slide_urls or [primary_slide]
        # Deduplicate while preserving order
        clean_slide_urls: List[str] = []
        for u in session_slide_urls:
            if u and str(u).strip() and str(u).strip() not in clean_slide_urls:
                clean_slide_urls.append(str(u).strip())
        if not clean_slide_urls:
            clean_slide_urls = [primary_slide]

        task_obj = {
            "task_id": new_tid,
            "week": week_num,
            "date": s_date,
            "start": s_start,
            "end": s_end,
            "course_code": course_code,
            "course_name": course_name,
            "title": str(session.get("title") or f"Tự học {course_name}"),
            "status": "todo",
            "is_flexible": bool(session.get("is_flexible", True)),
            "pomodoro_target": max(1, (time_to_minutes(s_end) - time_to_minutes(s_start)) // 30),
            "pomodoro_Completed": 0,
            "slide_url": clean_slide_urls[0],
            "slide_urls": clean_slide_urls,
            "subtasks": subtasks,
            "personal_notes": "",
            "gcal_event_id": f"gcal_task_{new_tid}_{compact_date}_{compact_start}",
        }
        tasks.append(task_obj)
        added_ids.append(new_tid)

    save_tasks(tasks)
    return added_ids


def complete_workspace_session(
    task_id: str,
    pomodoro_completed: int,
    completed_subtask_ids: List[str],
    personal_notes: str = "",
) -> Dict[str, Any]:
    """
    Tool 7 (`complete_workspace_session`):
    Updates `tasks.json` with completed subtasks, Pomodoro count, and personal notes,
    and returns the summary card matching API Contract 7.
    """
    tasks = load_tasks()
    target: Optional[Dict[str, Any]] = None
    for t in tasks:
        if t.get("task_id") == task_id:
            target = t
            break

    if target is None:
        raise HTTPException(
            status_code=404,
            detail=f"Task ID '{task_id}' not found in tasks.json",
        )

    completed_set = set(completed_subtask_ids or [])
    subtasks = target.get("subtasks") or []
    remaining_subtasks: List[str] = []
    done_count = 0

    for sub in subtasks:
        if sub.get("sub_id") in completed_set or sub.get("done") is True:
            sub["done"] = True
            done_count += 1
        else:
            sub["done"] = False
            remaining_subtasks.append(str(sub.get("content") or ""))

    total_subs = len(subtasks)
    completion_rate = int(round((done_count / total_subs) * 100)) if total_subs > 0 else 100

    pomo_target = int(target.get("pomodoro_target") or 2)
    pomo_done = max(0, int(pomodoro_completed))
    target["pomodoro_Completed"] = pomo_done
    target["personal_notes"] = personal_notes or ""
    target["status"] = "done" if (done_count == total_subs and total_subs > 0) or pomo_done > 0 else "in_progress"

    save_tasks(tasks)

    return {
        "task_title": target.get("title", ""),
        "total_focus_minutes": pomo_done * 25,
        "pomodoro_result": f"{pomo_done} / {pomo_target} Pomodoro",
        "completed_tasks_count": f"{done_count} / {total_subs} Tasks",
        "completion_rate_percent": completion_rate,
        "remaining_subtasks": remaining_subtasks,
        "personal_notes": target["personal_notes"],
    }

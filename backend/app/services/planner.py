import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException

from app.services.internet_time import fetch_internet_date
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


def is_task_overdue(task: Dict[str, Any], today_iso: str) -> bool:
    """A study session is overdue (chậm tiến độ) if not done and its date is before today."""
    return task.get("status") != "done" and (task.get("date") or "") < today_iso


def _is_makeup_task(task: Dict[str, Any]) -> bool:
    title = (task.get("title") or "").lower()
    return "học bù" in title or "chống trễ hạn" in title or "tăng cường" in title


def annotate_overdue(tasks: List[Dict[str, Any]], today_iso: str) -> List[Dict[str, Any]]:
    """Returns task copies with a computed (non-persisted) `overdue` flag."""
    return [{**t, "overdue": is_task_overdue(t, today_iso)} for t in tasks]


def compute_delay_prediction(
    tasks: List[Dict[str, Any]],
    lessons: Optional[List[Dict[str, Any]]] = None,
    today_iso: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Returns the Delay Prediction widget payload (marked `is_mock: True` per Week 1/2 spec),
    now driven by real overdue sessions: not done and date before today.
    Returns None when nothing is overdue (e.g. first-time user with no self-study tasks).
    Suggests a conflict-free makeup slot; marks resolved once an upcoming makeup session exists.
    """
    if today_iso is None:
        today_iso = fetch_internet_date()[0].isoformat()

    overdue = [t for t in tasks if is_task_overdue(t, today_iso)]
    if not overdue:
        return None

    primary_course = overdue[0].get("course_code", "INT1306")
    overdue_ids = [t.get("task_id") for t in overdue]

    has_upcoming_makeup = any(
        _is_makeup_task(t) and t.get("status") != "done" and (t.get("date") or "") >= today_iso
        for t in tasks
    )
    if has_upcoming_makeup:
        return {
            "is_mock": True,
            "course_code": primary_course,
            "risk_percent": 12,
            "is_resolved": True,
            "reason": f"Đã xếp buổi học bù cho {len(overdue)} phiên bị chậm tiến độ. Tiến độ đã an toàn.",
            "suggested_action": None,
            "overdue_task_ids": overdue_ids,
        }

    try:
        s_date, s_start, s_end = find_free_slot_on_or_after(
            today_iso, 90, lessons if lessons is not None else load_lessons(), tasks
        )
    except Exception:
        s_date, s_start, s_end = today_iso, "19:30", "21:00"

    d = parse_date_strict(s_date)
    return {
        "is_mock": True,
        "course_code": primary_course,
        "risk_percent": min(95, 40 + 15 * len(overdue)),
        "is_resolved": False,
        "reason": f"Chậm tiến độ: bạn đã bỏ lỡ {len(overdue)} phiên tự học (chưa hoàn thành mà đã qua ngày).",
        "suggested_action": f"Xếp lịch học bù {d.day:02d}/{d.month:02d} ({s_start} - {s_end})",
        "suggested_date": s_date,
        "suggested_start": s_start,
        "suggested_end": s_end,
        "overdue_task_ids": overdue_ids,
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


DAY_START = 8 * 60          # earliest self-study start
DAY_END = 22 * 60 + 30      # latest self-study end
LESSON_BUFFER = 15          # rest/travel buffer around school lessons
MIN_BLOCK = 45              # shorter gaps are not worth a session
MAX_BLOCK = 120             # longest single session before forcing a break
BREAK_BETWEEN_BLOCKS = 15
SLOT_STEP = 15              # round allocations to 15-minute granularity


def _free_windows(busy: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """Returns free [start, end) windows inside the study day, each >= MIN_BLOCK."""
    merged: List[List[int]] = []
    for s, e in sorted((max(DAY_START, s), min(DAY_END, e)) for s, e in busy):
        if e <= s:
            continue
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    windows: List[Tuple[int, int]] = []
    cursor = DAY_START
    for s, e in merged:
        if s - cursor >= MIN_BLOCK:
            windows.append((cursor, s))
        cursor = max(cursor, e)
    if DAY_END - cursor >= MIN_BLOCK:
        windows.append((cursor, DAY_END))
    return windows


def _window_preference(win: Tuple[int, int]) -> Tuple[int, int]:
    """Prefer evening (19:30), then afternoon (14:00), then morning windows."""
    s, e = win
    for rank, anchor in enumerate((19 * 60 + 30, 14 * 60, 9 * 60)):
        if s <= anchor < e:
            return rank, s
    return 3, s


def _place_minutes(windows: List[Tuple[int, int]], minutes: int) -> List[Tuple[int, int]]:
    """Places `minutes` of study into the day's free windows (preferred windows first)."""
    blocks: List[Tuple[int, int]] = []
    remaining = minutes
    for ws, we in sorted(windows, key=_window_preference):
        cursor = ws
        # Start at the anchor (e.g. 19:30) when the window allows it, otherwise as late/early as fits
        rank, _ = _window_preference((ws, we))
        anchor = (19 * 60 + 30, 14 * 60, 9 * 60, ws)[rank]
        if anchor + min(remaining, MAX_BLOCK) <= we:
            cursor = anchor
        elif we - min(remaining, MAX_BLOCK) >= ws:
            cursor = we - min(remaining, MAX_BLOCK)
        while remaining >= MIN_BLOCK:
            cursor += (-cursor) % SLOT_STEP  # align start to :00/:15/:30/:45
            if we - cursor < MIN_BLOCK:
                break
            # Absorb a small leftover (< MIN_BLOCK) into this block instead of dropping it
            max_len = remaining if remaining - MAX_BLOCK < MIN_BLOCK else MAX_BLOCK
            length = min(remaining, max_len, we - cursor)
            length -= length % SLOT_STEP
            if length < MIN_BLOCK:
                break
            blocks.append((cursor, cursor + length))
            remaining -= length
            cursor += length + BREAK_BETWEEN_BLOCKS
        if remaining < MIN_BLOCK:
            break
    if blocks and 0 < remaining < MIN_BLOCK:
        # Try to extend the last placed block by the leftover minutes
        s, e = blocks[-1]
        if any(ws <= s and e + remaining <= we for ws, we in windows):
            blocks[-1] = (s, e + remaining)
    return sorted(blocks)


def find_conflict_free_slots_for_roadmap(
    exam_date_str: str,
    daily_free_hours: float,
    num_sessions: int = 3,
    base_date_str: Optional[str] = None,
) -> List[Tuple[str, str, str]]:
    """
    Deterministically builds a balanced, conflict-free study plan before `exam_date_str`
    using Python time arithmetic (never relying on LLM for date/time math).

    Algorithm (load balancing / "water-filling"):
      1. Target total study time = `daily_free_hours` x number of study days.
      2. For every day, compute real free capacity (school lessons + buffer and existing
         self-study sessions are blocked), capped at 2x the daily target (max 4h).
      3. Every day gets an equal share; busy days that cannot fit their share push the
         deficit to free days (make-up study), so no free day is left empty.
      4. Each day's minutes are placed into its free windows (evening preferred), split
         into blocks of at most 2h with a 15-minute break.
    `num_sessions` is kept as the minimum number of sessions for backward compatibility.
    """
    exam_date = parse_date_strict(exam_date_str)
    # Query live internet time API to get today's date in Vietnam (UTC+7)
    live_today, time_source = fetch_internet_date()

    if base_date_str:
        requested_start = parse_date_strict(base_date_str)
        # Constrain start_date so it is never earlier than today's live internet date
        start_date = max(requested_start, live_today)
    else:
        start_date = live_today if live_today < exam_date else exam_date - timedelta(days=max(3, num_sessions))

    if exam_date < start_date:
        raise HTTPException(
            status_code=400,
            detail=f"exam_date ({exam_date}) must not be in the past relative to the live study start date ({start_date})",
        )

    lessons = load_lessons()
    tasks = load_tasks()

    last_day = exam_date - timedelta(days=1) if exam_date > start_date else start_date
    days = [
        (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range((last_day - start_date).days + 1)
    ]

    daily_target = int(round(max(0.5, min(8.0, daily_free_hours)) * 60))
    day_cap_limit = min(240, daily_target * 2)

    windows_by_day: Dict[str, List[Tuple[int, int]]] = {}
    capacity: Dict[str, int] = {}
    for d in days:
        busy: List[Tuple[int, int]] = []
        for les in lessons:
            if les.get("cancelled") or les.get("date") != d:
                continue
            try:
                busy.append((time_to_minutes(les["start"]) - LESSON_BUFFER, time_to_minutes(les["end"]) + LESSON_BUFFER))
            except Exception:
                pass
        existing_minutes = 0
        for tsk in tasks:
            if tsk.get("status") == "done" or tsk.get("date") != d:
                continue
            try:
                s, e = time_to_minutes(tsk["start"]), time_to_minutes(tsk["end"])
                busy.append((s - BREAK_BETWEEN_BLOCKS, e + BREAK_BETWEEN_BLOCKS))
                existing_minutes += max(0, e - s)
            except Exception:
                pass
        wins = _free_windows(busy)
        windows_by_day[d] = wins
        free_total = sum(we - ws for ws, we in wins)
        # Existing self-study on that day already counts toward the daily cap
        cap = max(0, min(free_total, day_cap_limit - existing_minutes))
        capacity[d] = cap - cap % SLOT_STEP if cap >= MIN_BLOCK else 0

    available = [d for d in days if capacity[d] > 0]
    if not available:
        raise HTTPException(
            status_code=409,
            detail="Không còn khung giờ trống đủ dài trước ngày thi để xếp buổi tự học.",
        )

    # Water-filling: equal share, busy days' deficit flows to free days
    total_budget = daily_target * len(days)
    alloc: Dict[str, int] = {d: 0 for d in available}
    remaining_days = sorted(available, key=lambda d: capacity[d])
    budget = total_budget
    while remaining_days and budget >= MIN_BLOCK:
        share = budget / len(remaining_days)
        d = remaining_days[0]
        if capacity[d] <= share:
            alloc[d] = capacity[d]          # busy day: take what fits
        else:
            # all remaining days can absorb an equal share
            for rd in remaining_days:
                give = int(share) - int(share) % SLOT_STEP
                alloc[rd] = max(MIN_BLOCK, min(capacity[rd], give))
            break
        budget -= alloc[d]
        remaining_days.pop(0)

    slots: List[Tuple[str, str, str]] = []
    for d in days:
        minutes = alloc.get(d, 0)
        if minutes < MIN_BLOCK:
            continue
        for s, e in _place_minutes(windows_by_day[d], minutes):
            slots.append((d, minutes_to_time(s), minutes_to_time(e)))

    slots.sort()
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

    generated_roadmap_id = f"rm_{course_code}_{uuid.uuid4().hex[:6]}"
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
            "roadmap_id": session.get("roadmap_id") or generated_roadmap_id,
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


def get_all_roadmaps(
    tasks: Optional[List[Dict[str, Any]]] = None,
    today_iso: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Returns grouped roadmap summaries across all self-study tasks in `tasks.json`.
    """
    if tasks is None:
        tasks = load_tasks()
    if today_iso is None:
        live_today, _ = fetch_internet_date()
        today_iso = live_today.isoformat()

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for t in tasks:
        rid = t.get("roadmap_id")
        if not rid:
            cc = t.get("course_code") or "CUSTOM"
            rid = f"rm_{cc}"
        grouped.setdefault(rid, []).append(t)

    roadmaps: List[Dict[str, Any]] = []
    for rid, rtasks in grouped.items():
        if not rtasks:
            continue
        sorted_rtasks = sorted(rtasks, key=lambda x: (x.get("date", ""), x.get("start", "")))
        c_code = sorted_rtasks[0].get("course_code", "")
        c_name = sorted_rtasks[0].get("course_name", "")
        start_date = sorted_rtasks[0].get("date", "")
        end_date = sorted_rtasks[-1].get("date", "")

        all_slides: List[str] = []
        for t in sorted_rtasks:
            urls = t.get("slide_urls") or ([t.get("slide_url")] if t.get("slide_url") else [])
            for u in urls:
                if u and u not in all_slides:
                    all_slides.append(u)

        completed_count = sum(1 for t in sorted_rtasks if t.get("status") == "done")
        overdue_count = sum(
            1 for t in sorted_rtasks if t.get("status") != "done" and (t.get("date") or "") < today_iso
        )
        upcoming_count = sum(
            1 for t in sorted_rtasks if t.get("status") != "done" and (t.get("date") or "") >= today_iso
        )

        roadmaps.append(
            {
                "roadmap_id": rid,
                "course_code": c_code,
                "course_name": c_name,
                "total_sessions": len(sorted_rtasks),
                "completed_sessions": completed_count,
                "upcoming_sessions": upcoming_count,
                "overdue_sessions": overdue_count,
                "start_date": start_date,
                "end_date": end_date,
                "slide_urls": all_slides,
                "task_ids": [t.get("task_id") for t in sorted_rtasks],
            }
        )

    # Sort roadmaps by start_date descending
    roadmaps.sort(key=lambda r: (r.get("start_date") or "", r.get("course_code") or ""), reverse=True)
    return roadmaps


def delete_roadmaps(
    roadmap_ids: Optional[List[str]] = None,
    task_ids: Optional[List[str]] = None,
    course_code: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Deletes roadmap sessions matching given roadmap_ids, task_ids, or course_code from `tasks.json`.
    """
    tasks = load_tasks()
    rid_set = set(roadmap_ids or [])
    tid_set = set(task_ids or [])
    c_code = (course_code or "").strip()

    remaining: List[Dict[str, Any]] = []
    deleted_ids: List[str] = []

    for t in tasks:
        t_id = t.get("task_id")
        t_rid = t.get("roadmap_id") or f"rm_{t.get('course_code')}"
        t_cc = t.get("course_code")

        is_match = False
        if t_rid in rid_set:
            is_match = True
        elif f"rm_{t_cc}" in rid_set or t_cc in rid_set:
            is_match = True
        elif t_id in tid_set:
            is_match = True
        elif c_code and t_cc == c_code:
            is_match = True

        if is_match:
            deleted_ids.append(t_id)
        else:
            remaining.append(t)

    save_tasks(remaining)
    return {
        "status": "deleted",
        "deleted_count": len(deleted_ids),
        "deleted_task_ids": deleted_ids,
        "remaining_count": len(remaining),
        "message": f"Đã xóa thành công {len(deleted_ids)} buổi tự học.",
    }


def complete_workspace_session(
    task_id: str,
    pomodoro_completed: int = 1,
    completed_subtask_ids: Optional[List[str]] = None,
    personal_notes: str = "",
    study_duration_seconds: Optional[int] = None,
    chat_history: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Tool 7 (`complete_workspace_session`):
    Updates `tasks.json` with completed subtasks, actual elapsed study time,
    learning performance evaluation (struggling / excellent / normal), personal notes,
    and chat history conversation for reviewing.
    Returns the summary card matching API Contract 7.
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

    # 1. Planned study duration
    planned_minutes = 60
    s_start = target.get("start")
    s_end = target.get("end")
    if s_start and s_end:
        try:
            diff = time_to_minutes(s_end) - time_to_minutes(s_start)
            if diff > 0:
                planned_minutes = diff
        except Exception:
            pass

    # 2. Actual study time
    pomo_target = int(target.get("pomodoro_target") or 2)
    pomo_done = max(0, int(pomodoro_completed or 1))

    if study_duration_seconds is not None and study_duration_seconds > 0:
        actual_seconds = int(study_duration_seconds)
        actual_minutes = round(actual_seconds / 60, 1)
        total_focus_minutes = max(1, int(round(actual_seconds / 60)))
    else:
        total_focus_minutes = pomo_done * 25
        actual_seconds = total_focus_minutes * 60
        actual_minutes = float(total_focus_minutes)

    def format_study_seconds(sec: int) -> str:
        m = sec // 60
        s = sec % 60
        if m == 0:
            return f"{s} giây"
        if s == 0:
            return f"{m} phút"
        return f"{m} phút {s} giây"

    ratio = round((actual_minutes / planned_minutes) * 100) if planned_minutes > 0 else 100

    # 3. Learning Performance Evaluation
    # - Quá thời gian dự kiến (actual > planned): Phân tích khúc mắc và gợi ý hỗ trợ
    # - Sớm hơn khoảng 75% (actual <= planned * 0.75): Hiểu bài rất tốt
    # - Còn lại: Hoàn thành bình thường / đúng tiến độ
    if actual_minutes > planned_minutes:
        eval_status = "struggling"
        eval_category = "Có thể đang gặp khúc mắc"
        eval_badge = "💡 Cần hỗ trợ / Khúc mắc"
        eval_message = (
            f"Thời gian học của bạn ({format_study_seconds(actual_seconds)}) vượt quá thời gian dự kiến ({planned_minutes} phút). "
            "Có vẻ bạn đang gặp khúc mắc ở một số nội dung khó hoặc bài tập cần nhiều thời gian đào sâu. "
            "Hãy tận dụng AI trợ giảng để gỡ rối các khái niệm khó hoặc ghi lại để trao đổi thêm với giảng viên nhé!"
        )
        eval_tips = [
            "Đặt câu hỏi cho AI trợ giảng hoặc chụp ảnh bài tập cần giải đáp",
            "Chia nhỏ tài liệu bài học và ôn lại từng phần trọng tâm",
            "Dùng tính năng Flashcard để củng cố các định nghĩa quan trọng",
        ]
    elif actual_minutes <= planned_minutes * 0.75:
        eval_status = "excellent"
        eval_category = "Hiểu bài rất tốt"
        eval_badge = "🌟 Hiểu bài rất tốt"
        eval_message = (
            f"Bạn đã hoàn thành phiên học rất nhanh chóng ({format_study_seconds(actual_seconds)} / {planned_minutes} phút dự kiến, đạt ~{ratio}% thời gian). "
            "Tốc độ tiếp thu của bạn rất ấn tượng và bạn nắm vững kiến thức rất tốt!"
        )
        eval_tips = [
            "Tiếp tục duy trì phong độ tập trung xuất sắc này!",
            "Thử sức với các bài tập nâng cao hoặc ôn trước tài liệu buổi sau",
        ]
    else:
        eval_status = "normal"
        eval_category = "Hoàn thành đúng tiến độ"
        eval_badge = "✅ Hoàn thành đúng tiến độ"
        eval_message = (
            f"Bạn đã hoàn thành phiên học với nhịp độ học tập chuẩn xác ({format_study_seconds(actual_seconds)} / {planned_minutes} phút dự kiến). "
            "Bạn duy trì được sự tập trung đều đặn và tiếp thu bài bản toàn bộ mục tiêu!"
        )
        eval_tips = [
            "Duy trì thói quen học tập đều đặn mỗi ngày",
            "Đọc lại các ghi chú cá nhân trước khi bước vào buổi học tiếp theo",
        ]

    evaluation = {
        "status": eval_status,
        "category": eval_category,
        "badge": eval_badge,
        "message": eval_message,
        "actual_minutes": actual_minutes,
        "actual_seconds": actual_seconds,
        "planned_minutes": planned_minutes,
        "ratio_percent": ratio,
        "tips": eval_tips,
    }

    target["pomodoro_Completed"] = pomo_done
    target["actual_study_seconds"] = actual_seconds
    target["actual_study_minutes"] = actual_minutes
    target["planned_study_minutes"] = planned_minutes
    target["evaluation"] = evaluation
    target["personal_notes"] = personal_notes or ""
    if chat_history is not None:
        target["chat_history"] = chat_history
    target["status"] = "done" if (done_count == total_subs and total_subs > 0) or pomo_done > 0 or actual_seconds > 0 else "in_progress"

    save_tasks(tasks)

    return {
        "task_title": target.get("title", ""),
        "total_focus_minutes": total_focus_minutes,
        "study_duration_seconds": actual_seconds,
        "study_duration_formatted": format_study_seconds(actual_seconds),
        "planned_focus_minutes": planned_minutes,
        "evaluation": evaluation,
        "pomodoro_result": f"{pomo_done} / {pomo_target} Pomodoro",
        "completed_tasks_count": f"{done_count} / {total_subs} Tasks",
        "completion_rate_percent": completion_rate,
        "remaining_subtasks": remaining_subtasks,
        "personal_notes": target["personal_notes"],
    }


def save_workspace_chat_history(
    task_id: str,
    chat_history: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Saves or updates the session conversation (chat history) into tasks.json
    so that students can review past conversations at any time.
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

    target["chat_history"] = chat_history
    save_tasks(tasks)
    return {
        "status": "saved",
        "task_id": task_id,
        "messages_count": len(chat_history),
    }

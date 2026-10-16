"""Module thuật toán xử lý xung đột lịch và đề xuất slot trống thay thế."""
from app.services import planner


def resolve_conflicts_and_reschedule(conflicts: list, lessons: list, sessions: list) -> dict:
    """Thuật toán tự động tìm slot trống thay thế cho các lịch bị xung đột với QLĐT."""
    proposals = []
    for c in conflicts:
        slot = None
        # Kiểm tra nếu task có thể dời lịch (flexible)
        if c.get("is_flexible", True):
            start_min = planner.to_minutes(c["task_start"])
            end_min = planner.to_minutes(c["task_end"])
            duration = end_min - start_min
            
            # Gọi hàm gợi ý slot trống từ module planner
            slot = planner.suggest_slot(
                duration=duration,
                target_date=c["date"],
                preferred_start_minute=start_min,
                lessons=lessons,
                sessions=sessions,
                ignore_task_id=c["task_id"]
            )
        
        proposals.append({
            **c,
            "suggested_slot": slot,
            "status": "resolved" if slot else "no_available_slot"
        })
        
    return {
        "applied": False,  # Chỉ đề xuất, chờ người dùng xác nhận
        "mode": "live_algorithm",
        "conflicts": proposals
    }
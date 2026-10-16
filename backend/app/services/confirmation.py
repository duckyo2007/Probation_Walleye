"""Confirmation Gate: chặn các thao tác ghi/dời lịch khi người dùng chưa xác nhận.

Kiểm tra ở SERVER, mỗi request tự mang cờ xác nhận của riêng nó
(không có biến global dùng chung cho mọi người dùng).
"""

CONFIRMATION_MESSAGE = "Action requires explicit user confirmation"

# Danh sách rõ ràng: thao tác nào cần xác nhận, thao tác nào không.
ACTIONS_REQUIRING_CONFIRMATION = {
    "reschedule_tasks": "POST /api/schedule/confirm-reschedule: sửa ngày/giờ trong tasks.json "
                        "và (tuỳ chọn) gọi Google Calendar",
}
ACTIONS_NEVER_WRITING_SCHEDULE = {
    "schedule_sync": "POST /api/schedule/sync: chỉ ĐỀ XUẤT khung giờ mới, không sửa tasks",
    "roadmap_generate": "POST /api/roadmap/generate: chỉ trả bản nháp, không lưu",
}
ACTIONS_TRIGGERED_BY_UI_BUTTON = {
    "workspace_complete": "POST /api/workspace/complete: người dùng bấm 'Hoàn thành buổi học'; "
                          "chỉ ghi pomodoro, checklist, ghi chú, trạng thái (không đổi ngày/giờ)",
}


class ConfirmationRequired(Exception):
    """Ném ra khi chưa có xác nhận hợp lệ. main.py đổi thành HTTP 403."""


def require_user_confirmation(user_confirmed) -> None:
    """Chỉ chấp nhận ĐÚNG giá trị boolean True.

    "true", 1, "yes", None, False... đều bị từ chối.
    """
    if user_confirmed is not True:
        raise ConfirmationRequired(CONFIRMATION_MESSAGE)

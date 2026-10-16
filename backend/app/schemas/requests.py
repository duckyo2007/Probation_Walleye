"""Pydantic schema kiểm tra dữ liệu request. Sai kiểu/định dạng -> FastAPI trả 422."""
from typing import Any, Optional

from pydantic import BaseModel, Field

DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"


class SyncRequest(BaseModel):
    force_refresh: bool = False


class RescheduleItem(BaseModel):
    task_id: str = Field(min_length=1)
    new_date: str = Field(pattern=DATE_PATTERN)
    new_start: str = Field(pattern=TIME_PATTERN)
    new_end: str = Field(pattern=TIME_PATTERN)


class ConfirmRescheduleRequest(BaseModel):
    # Cố ý để kiểu Any và mặc định None: thiếu hoặc sai kiểu phải ra 403
    # (qua Confirmation Gate), không phải 422. Gate chỉ chấp nhận đúng `True`.
    user_confirmed: Any = None
    sync_gcal: bool = False
    reschedule_items: list[RescheduleItem] = Field(min_length=1)


class RoadmapRequest(BaseModel):
    course_code: str = Field(min_length=1)
    course_name: str = Field(min_length=1)
    exam_date: str = Field(pattern=DATE_PATTERN)
    daily_free_hours: float = Field(gt=0, le=12)
    slide_url: Optional[str] = None


class ChatMessage(BaseModel):
    role: str
    content: str


class TutorChatRequest(BaseModel):
    task_id: str = Field(min_length=1)
    user_message: str = Field(min_length=1, max_length=4000)
    code_snippet: Optional[str] = Field(default=None, max_length=10000)
    chat_history: list[ChatMessage] = Field(default_factory=list, max_length=50)


class InactivityRequest(BaseModel):
    task_id: str = Field(min_length=1)
    inactive_minutes: int = Field(ge=0)
    current_subtask: Optional[str] = None


class CompleteSessionRequest(BaseModel):
    task_id: str = Field(min_length=1)
    pomodoro_completed: int = Field(ge=0, le=100)
    completed_subtask_ids: list[str] = Field(default_factory=list)
    personal_notes: str = Field(default="", max_length=5000)

from typing import Any, List, Optional
from pydantic import BaseModel, Field


class ScheduleSyncRequest(BaseModel):
    force_refresh: bool = True
    username: Optional[str] = None
    password: Optional[str] = None
    hoc_ky: Optional[int] = None


class RescheduleItem(BaseModel):
    task_id: str = Field(..., min_length=1)
    new_date: str = Field(..., min_length=8)
    new_start: str = Field(..., min_length=4)
    new_end: str = Field(..., min_length=4)


class ConfirmRescheduleRequest(BaseModel):
    # Kept as Any so non-bool truthy values like "true" or 1 are caught by the 403 Confirmation Gate
    user_confirmed: Any = None
    sync_gcal: bool = True
    reschedule_items: List[RescheduleItem] = Field(default_factory=list)


class RoadmapGenerateRequest(BaseModel):
    course_code: str = Field(..., min_length=1)
    course_name: str = Field(..., min_length=1)
    exam_date: str = Field(..., min_length=8)
    daily_free_hours: float = Field(default=2.0, gt=0, le=16)
    slide_url: str = Field(default="/static/slides/INT1306_Chuong3_CayNhiPhan.pdf")
    slide_urls: Optional[List[str]] = None


class SubtaskItem(BaseModel):
    sub_id: str
    content: str
    done: bool = False


class ApprovedSessionItem(BaseModel):
    title: str = Field(..., min_length=1)
    date: str = Field(..., min_length=8)
    start: str = Field(..., min_length=4)
    end: str = Field(..., min_length=4)
    is_flexible: bool = True
    slide_url: Optional[str] = None
    slide_urls: Optional[List[str]] = None
    subtasks: List[SubtaskItem] = Field(default_factory=list)


class RoadmapConfirmSaveRequest(BaseModel):
    user_confirmed: Any = None
    course_code: str = Field(..., min_length=1)
    course_name: str = Field(..., min_length=1)
    slide_url: Optional[str] = "/static/slides/INT1306_Chuong3_CayNhiPhan.pdf"
    slide_urls: Optional[List[str]] = None
    approved_sessions: List[ApprovedSessionItem] = Field(default_factory=list)


class ChatHistoryItem(BaseModel):
    role: str
    content: str


class TutorChatRequest(BaseModel):
    task_id: str = Field(..., min_length=1)
    user_message: str = Field(..., min_length=1)
    code_snippet: Optional[str] = ""
    chat_history: List[ChatHistoryItem] = Field(default_factory=list)


class InactivityCheckRequest(BaseModel):
    task_id: str = Field(..., min_length=1)
    inactive_minutes: int = Field(default=10, ge=1)
    current_subtask: str = Field(default="Đọc định nghĩa và ôn tập nội dung bài học")


class WorkspaceCompleteRequest(BaseModel):
    task_id: str = Field(..., min_length=1)
    pomodoro_completed: int = Field(default=1, ge=0)
    completed_subtask_ids: List[str] = Field(default_factory=list)
    personal_notes: Optional[str] = ""


class FlashcardGenerateRequest(BaseModel):
    task_id: str = Field(..., min_length=1)
    count: int = Field(default=4, ge=2, le=8)


class SettingsUpdateRequest(BaseModel):
    qldt_username: Optional[str] = None
    qldt_password: Optional[str] = None
    hoc_ky: Optional[int] = None
    auto_sync_sunday: Optional[bool] = None
    gemini_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None


class AddExtraStudySessionRequest(BaseModel):
    user_confirmed: Any = None
    course_code: str = "INT1306"
    course_name: str = "Cấu trúc dữ liệu và giải thuật"
    title: str = "Phiên học bù tăng cường (Chống trễ hạn)"
    date: str = "2026-10-18"
    start: str = "19:30"
    end: str = "21:00"
    slide_url: str = "/static/slides/INT1306_Chuong3_CayNhiPhan.pdf"
    slide_urls: Optional[List[str]] = None


class RemoveTaskDocumentRequest(BaseModel):
    task_id: str = Field(..., min_length=1)
    slide_url: str = Field(..., min_length=1)

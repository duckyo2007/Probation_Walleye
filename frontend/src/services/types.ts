// Kiểu dữ liệu khớp với JSON mà backend trả về.

export interface Lesson {
  key: string;
  week: number;
  date: string;
  start: string;
  end: string;
  course_code: string;
  course_name: string;
  teacher: string;
  room: string;
  online: boolean;
  cancelled: boolean;
  makeup: boolean;
  slide_url: string | null;
  gcal_event_id: string | null;
}

export interface Subtask {
  sub_id: string;
  content: string;
  done: boolean;
}

export interface StudySession {
  task_id: string;
  course_code: string;
  course_name: string;
  title: string;
  date: string;
  start: string;
  end: string;
  status: "pending" | "in_progress" | "completed";
  is_flexible: boolean;
  slide_url: string | null;
  pomodoro_completed: number;
  pomodoro_target: number;
  personal_notes: string;
  subtasks: Subtask[];
  gcal_event_id: string | null;
}

export interface SuggestedSlot {
  date: string;
  start: string;
  end: string;
}

export interface Conflict {
  task_id: string;
  task_title: string;
  course_name: string;
  date: string;
  task_start: string;
  task_end: string;
  is_flexible: boolean;
  lesson_key: string;
  lesson_course_name: string;
  lesson_start: string;
  lesson_end: string;
  reason: string;
  suggested_slot: SuggestedSlot | null;
}

export interface DelayPrediction {
  overall_risk?: string;
  generated_at?: string;
  predictions?: { task_id: string; risk_level: "low" | "medium" | "high"; reason: string }[];
}

export interface SyncResponse {
  status: string;
  source: string;
  last_updated: string | null;
  is_mock: boolean;
  lessons: Lesson[];
  tasks: StudySession[];
  delay_prediction: DelayPrediction;
  conflicts: Conflict[];
  note?: string;
}

export interface RescheduleItem {
  task_id: string;
  new_date: string;
  new_start: string;
  new_end: string;
}

export interface RescheduleResponse {
  status: string;
  gcal_synced: boolean;
  gcal_mode: "mock" | "skipped" | string;
  message: string;
  updated_tasks: StudySession[];
}

export interface RoadmapRequest {
  course_code: string;
  course_name: string;
  exam_date: string;
  daily_free_hours: number;
  slide_url: string | null;
}

export interface DraftSession {
  title: string;
  course_code: string;
  course_name: string;
  date: string;
  start: string;
  end: string;
  is_flexible: boolean;
  subtasks: Subtask[];
}

export interface RoadmapResponse {
  status: string;
  is_mock: boolean;
  saved: boolean;
  document_status: string;
  summary: string;
  suggested_sessions: DraftSession[];
  note: string;
}

export interface DocumentInfo {
  status: "no_document" | "not_extracted" | string;
  slide_url: string | null;
  text: string | null;
  message: string;
}

export interface WorkspaceResponse {
  task_info: Omit<StudySession, "subtasks">;
  checklist: Subtask[];
  document: DocumentInfo;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  status: string;
  provider_used: string;
  reply_markdown: string;
}

export interface InactivityResponse {
  status: string;
  is_mock: boolean;
  should_remind: boolean;
  skip_reason: "below_threshold" | "rate_limited" | null;
  message: string | null;
  retry_after_seconds: number | null;
}

export interface CompleteRequest {
  task_id: string;
  pomodoro_completed: number;
  completed_subtask_ids: string[];
  personal_notes: string;
}

export interface SummaryCardData {
  task_id: string;
  course_name: string;
  title: string;
  total_focus_minutes: number;
  pomodoro_result: string;
  completed_tasks_count: number;
  total_subtasks: number;
  completion_rate_percent: number;
  remaining_subtasks: { sub_id: string; content: string }[];
}

export interface CompleteResponse {
  status: string;
  summary_card: SummaryCardData;
}

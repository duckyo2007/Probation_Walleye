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
  slide_url: string;
  gcal_event_id: string;
}

export interface Subtask {
  sub_id: string;
  content: string;
  done: boolean;
}

export interface StudyTask {
  task_id: string;
  week: number;
  date: string;
  start: string;
  end: string;
  course_code: string;
  course_name: string;
  title: string;
  status: 'todo' | 'in_progress' | 'done';
  is_flexible: boolean;
  pomodoro_target: number;
  pomodoro_Completed: number;
  slide_url: string;
  slide_urls?: string[];
  subtasks: Subtask[];
  personal_notes: string;
  gcal_event_id: string;
}

export interface DelayPrediction {
  is_mock: boolean;
  course_code: string;
  risk_percent: number;
  reason: string;
  suggested_action: string;
}

export interface ConflictItem {
  task_id: string;
  task_title: string;
  conflict_with: string;
  old_date: string;
  old_time: string;
  new_suggested_date: string;
  new_suggested_time: string;
  reason: string;
}

export interface WeekMetadata {
  week: number;
  info: string;
  start_date: string;
  end_date: string;
  lesson_count: number;
}

export interface SyncScheduleResponse {
  status: string;
  source: 'live_api' | 'fallback_cache';
  last_updated: string;
  lessons: Lesson[];
  tasks: StudyTask[];
  delay_prediction: DelayPrediction;
  conflicts: ConflictItem[];
  weeks_metadata?: WeekMetadata[];
}

export interface SuggestedRoadmapSession {
  title: string;
  suggested_date: string;
  suggested_start: string;
  suggested_end: string;
  slide_url?: string;
  slide_urls?: string[];
  subtasks: Subtask[];
}

export interface RoadmapDraftResponse {
  status: string;
  course_code: string;
  course_name?: string;
  slide_url?: string;
  slide_urls?: string[];
  summary: string;
  suggested_sessions: SuggestedRoadmapSession[];
}

export interface SingleDocumentItem {
  slide_url: string;
  filename: string;
  context_loaded: boolean;
  page_count: number;
  document_status: 'loaded' | 'no_document' | 'ocr_fallback';
  extracted_text: string;
}

export interface DocumentContext {
  slide_url: string;
  slide_urls?: string[];
  context_loaded: boolean;
  page_count: number;
  document_status: 'loaded' | 'no_document' | 'ocr_fallback';
  extracted_text: string;
  documents?: SingleDocumentItem[];
}

export interface WorkspaceEnterResponse {
  status: string;
  task_info: StudyTask;
  document: DocumentContext;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  provider?: string;
  isProactive?: boolean;
}

export interface SummaryCard {
  task_title: string;
  total_focus_minutes: number;
  pomodoro_result: string;
  completed_tasks_count: string;
  completion_rate_percent: number;
  remaining_subtasks: string[];
  personal_notes?: string;
}

export interface Flashcard {
  card_id: string;
  question: string;
  answer: string;
  explanation: string;
}

export interface AgentSettings {
  status: string;
  qldt_username: string;
  has_qldt_password: boolean;
  hoc_ky: number;
  auto_sync_sunday: boolean;
  last_sync_at: string | null;
  last_sync_source: string;
  last_sunday_sync_date: string | null;
  has_gemini_api_key: boolean;
  has_groq_api_key: boolean;
  gemini_model: string;
}

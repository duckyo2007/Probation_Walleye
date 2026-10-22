import {
  AgentSettings,
  ConflictItem,
  DelayPrediction,
  DocumentContext,
  Flashcard,
  Lesson,
  RoadmapDeleteResponse,
  RoadmapDraftResponse,
  RoadmapItem,
  RoadmapListResponse,
  StudyTask,
  SummaryCard,
  SyncScheduleResponse,
  WorkspaceEnterResponse,
} from './types';

const API_BASE = import.meta.env.VITE_API_BASE || '';

async function handleJson<T>(res: Response): Promise<T> {
  const data = await res.json().catch(() => ({ detail: `HTTP error ${res.status}` }));
  if (!res.ok) {
    throw new Error(data.detail || `Request failed with status ${res.status}`);
  }
  return data as T;
}

export function getStaticUrl(path: string): string {
  if (!path) return '';
  if (path.startsWith('http://') || path.startsWith('https://')) return path;
  return `${API_BASE}${path.startsWith('/') ? '' : '/'}${path}`;
}

// API 1: POST /api/schedule/sync
export async function syncSchedule(params?: {
  force_refresh?: boolean;
  username?: string;
  password?: string;
  hoc_ky?: number;
}): Promise<SyncScheduleResponse> {
  const res = await fetch(`${API_BASE}/api/schedule/sync`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ force_refresh: true, ...params }),
  });
  return handleJson<SyncScheduleResponse>(res);
}

// API 2: POST /api/schedule/confirm-reschedule (CONFIRMATION GATE)
export async function confirmReschedule(payload: {
  user_confirmed: boolean;
  sync_gcal: boolean;
  reschedule_items: Array<{
    task_id: string;
    new_date: string;
    new_start: string;
    new_end: string;
  }>;
}): Promise<{
  status: string;
  gcal_synced: boolean;
  message: string;
  updated_tasks: Array<{ task_id: string; date: string; start: string; end: string; status: string }>;
}> {
  const res = await fetch(`${API_BASE}/api/schedule/confirm-reschedule`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return handleJson(res);
}

// API 3: POST /api/roadmap/generate
export async function generateRoadmap(payload: {
  course_code: string;
  course_name: string;
  exam_date: string;
  daily_free_hours: number;
  slide_url: string;
  slide_urls?: string[];
  base_date?: string;
}): Promise<RoadmapDraftResponse> {
  const res = await fetch(`${API_BASE}/api/roadmap/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return handleJson<RoadmapDraftResponse>(res);
}

// API 3.1: POST /api/roadmap/confirm-save (CONFIRMATION GATE)
export async function confirmSaveRoadmap(payload: {
  user_confirmed: boolean;
  course_code: string;
  course_name: string;
  slide_url?: string;
  slide_urls?: string[];
  approved_sessions: Array<{
    title: string;
    date: string;
    start: string;
    end: string;
    is_flexible: boolean;
    slide_url?: string;
    slide_urls?: string[];
    subtasks: Array<{ sub_id: string; content: string; done: boolean }>;
  }>;
}): Promise<{ status: string; message: string; added_task_ids: string[] }> {
  const res = await fetch(`${API_BASE}/api/roadmap/confirm-save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return handleJson(res);
}

// API 4: GET /api/workspace/enter/{task_id}
export async function enterWorkspace(taskId: string): Promise<WorkspaceEnterResponse> {
  const res = await fetch(`${API_BASE}/api/workspace/enter/${encodeURIComponent(taskId)}`);
  return handleJson<WorkspaceEnterResponse>(res);
}

// API 5: POST /api/tutor/chat
export async function sendTutorChat(payload: {
  task_id: string;
  user_message: string;
  code_snippet?: string;
  chat_history: Array<{ role: string; content: string }>;
}): Promise<{ status: string; provider_used: string; reply_markdown: string }> {
  const res = await fetch(`${API_BASE}/api/tutor/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return handleJson(res);
}

// API 6: POST /api/tutor/inactivity-check
export async function checkTutorInactivity(payload: {
  task_id: string;
  inactive_minutes: number;
  current_subtask: string;
}): Promise<{
  status: string;
  should_remind: boolean;
  skip_reason: string | null;
  message: string | null;
  current_subtask: string;
  retry_after_seconds: number | null;
}> {
  const res = await fetch(`${API_BASE}/api/tutor/inactivity-check`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return handleJson(res);
}

// API 7: POST /api/workspace/complete
export async function completeWorkspaceSession(payload: {
  task_id: string;
  pomodoro_completed: number;
  completed_subtask_ids: string[];
  personal_notes: string;
}): Promise<{ status: string; summary_card: SummaryCard }> {
  const res = await fetch(`${API_BASE}/api/workspace/complete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return handleJson(res);
}

// Extra endpoints: Flashcards, Multi-PDF Upload & Remove, Settings, Simulate Conflict
export async function fetchFlashcards(taskId: string): Promise<{
  status: string;
  flashcards: Flashcard[];
}> {
  const res = await fetch(`${API_BASE}/api/workspace/flashcards`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task_id: taskId, count: 4 }),
  });
  return handleJson(res);
}

export async function uploadPdfDocuments(
  files: File[] | FileList,
  taskId?: string,
  append: boolean = true
): Promise<{
  status: string;
  slide_url: string;
  slide_urls: string[];
  uploaded_urls: string[];
  filenames: string[];
  filename: string;
  document: DocumentContext;
}> {
  const form = new FormData();
  Array.from(files).forEach((f) => {
    form.append('files', f);
  });
  if (taskId) form.append('task_id', taskId);
  form.append('append', String(append));
  const res = await fetch(`${API_BASE}/api/documents/upload`, {
    method: 'POST',
    body: form,
  });
  return handleJson(res);
}

export async function removeTaskDocument(
  taskId: string,
  slideUrl: string
): Promise<{
  status: string;
  task_info: StudyTask;
  document: DocumentContext;
}> {
  const res = await fetch(`${API_BASE}/api/documents/remove`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task_id: taskId, slide_url: slideUrl }),
  });
  return handleJson(res);
}

export async function getAgentSettings(): Promise<AgentSettings> {
  const res = await fetch(`${API_BASE}/api/settings`);
  return handleJson<AgentSettings>(res);
}

export async function updateAgentSettings(payload: {
  qldt_username?: string;
  qldt_password?: string;
  hoc_ky?: number;
  auto_sync_sunday?: boolean;
  gemini_api_key?: string;
  groq_api_key?: string;
}): Promise<AgentSettings & { message: string }> {
  const res = await fetch(`${API_BASE}/api/settings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return handleJson(res);
}

export async function simulateConflictDemo(): Promise<{
  status: string;
  message: string;
  conflicts: ConflictItem[];
  lessons: Lesson[];
  tasks: StudyTask[];
  delay_prediction?: DelayPrediction;
}> {
  const res = await fetch(`${API_BASE}/api/schedule/simulate-conflict`, {
    method: 'POST',
  });
  return handleJson(res);
}

export async function fetchTodayDate(): Promise<{
  status: string;
  today: string;
  source: string;
  current_week: number;
}> {
  const res = await fetch(`${API_BASE}/api/schedule/today`);
  return handleJson(res);
}

export async function addExtraStudySession(payload: {
  user_confirmed: boolean;
  course_code: string;
  course_name: string;
  title: string;
  date: string;
  start: string;
  end: string;
  slide_url: string;
  slide_urls?: string[];
}): Promise<{ status: string; message: string; added_task_ids: string[] }> {
  const res = await fetch(`${API_BASE}/api/schedule/add-extra-session`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return handleJson(res);
}

// GET /api/roadmap/list
export async function fetchRoadmapsList(): Promise<RoadmapListResponse> {
  const res = await fetch(`${API_BASE}/api/roadmap/list`);
  return handleJson<RoadmapListResponse>(res);
}

// POST /api/roadmap/delete
export async function deleteRoadmaps(payload: {
  roadmap_ids: string[];
  task_ids?: string[];
  course_code?: string;
}): Promise<RoadmapDeleteResponse> {
  const res = await fetch(`${API_BASE}/api/roadmap/delete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return handleJson<RoadmapDeleteResponse>(res);
}

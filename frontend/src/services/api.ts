// Toàn bộ lời gọi backend nằm ở đây. Component không tự gọi fetch.
import type {
  ChatMessage,
  ChatResponse,
  CompleteRequest,
  CompleteResponse,
  InactivityResponse,
  RescheduleItem,
  RescheduleResponse,
  RoadmapRequest,
  RoadmapResponse,
  SyncResponse,
  WorkspaceResponse,
} from "./types";

const API_BASE: string = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";

/** Lỗi từ backend (hoặc không kết nối được). `status` = 0 nghĩa là không có phản hồi. */
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

// FastAPI trả `detail` là chuỗi (403/404/400) hoặc danh sách lỗi (422).
function formatDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d: { loc?: unknown[]; msg?: string }) => `${(d.loc ?? []).slice(1).join(".")}: ${d.msg ?? ""}`)
      .join("; ");
  }
  return "Yêu cầu không hợp lệ";
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch {
    throw new ApiError(0, "Không kết nối được backend. Hãy kiểm tra backend đang chạy ở cổng 8000.");
  }
  if (!res.ok) {
    let message = `Lỗi ${res.status}`;
    try {
      const body = await res.json();
      message = formatDetail(body.detail);
    } catch {
      /* giữ message mặc định */
    }
    throw new ApiError(res.status, message);
  }
  return (await res.json()) as T;
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: "POST", body: JSON.stringify(body) });
}

// API 1: chỉ đọc + đề xuất, không sửa lịch tự học.
export function syncSchedule(forceRefresh: boolean): Promise<SyncResponse> {
  return post("/schedule/sync", { force_refresh: forceRefresh });
}

// API 2: CHỈ gọi hàm này sau khi người dùng bấm "Đồng ý" trong modal xác nhận.
// `user_confirmed: true` chỉ được đặt ở đây, và backend vẫn kiểm tra lại.
export function confirmReschedule(
  items: RescheduleItem[],
  syncGcal: boolean
): Promise<RescheduleResponse> {
  return post("/schedule/confirm-reschedule", {
    user_confirmed: true,
    sync_gcal: syncGcal,
    reschedule_items: items,
  });
}

// API 3: chỉ tạo bản nháp.
export function generateRoadmap(payload: RoadmapRequest): Promise<RoadmapResponse> {
  return post("/roadmap/generate", payload);
}

// API 4
export function enterWorkspace(taskId: string): Promise<WorkspaceResponse> {
  return request(`/workspace/enter/${encodeURIComponent(taskId)}`);
}

// API 5
export function chatWithTutor(
  taskId: string,
  userMessage: string,
  codeSnippet: string | null,
  chatHistory: ChatMessage[]
): Promise<ChatResponse> {
  return post("/tutor/chat", {
    task_id: taskId,
    user_message: userMessage,
    code_snippet: codeSnippet,
    chat_history: chatHistory,
  });
}

// API 6
export function checkInactivity(
  taskId: string,
  inactiveMinutes: number,
  currentSubtask: string | null
): Promise<InactivityResponse> {
  return post("/tutor/inactivity-check", {
    task_id: taskId,
    inactive_minutes: inactiveMinutes,
    current_subtask: currentSubtask,
  });
}

// API 7: chỉ gọi khi người dùng chủ động bấm "Hoàn thành buổi học".
export function completeSession(payload: CompleteRequest): Promise<CompleteResponse> {
  return post("/workspace/complete", payload);
}

/** Chuyển lỗi bất kỳ thành câu tiếng Việt để hiển thị cho người dùng. */
export function errorMessage(e: unknown): string {
  return e instanceof ApiError ? e.message : "Đã xảy ra lỗi không xác định.";
}

# EasyPlan - Web & Backend Gateway

EasyPlan là AI Agent hỗ trợ học sinh, sinh viên lập kế hoạch học tập, theo dõi tiến độ và ôn tập.
Repo này chứa **frontend (React + Vite + TypeScript)** và **backend gateway (Python + FastAPI)**
nối giao diện với các tool của AI Agent.

> **Đây là bản prototype.** Mọi tool (QLĐT, Google Calendar, đọc PDF/OCR, LLM) hiện đều là **mock**.
> Xem mục [Giới hạn của bản mock](#giới-hạn-của-bản-mock).

## Cấu trúc

```
easyplan/
├── frontend/                 # React + Vite + TypeScript
│   └── src/
│       ├── components/       # ConfirmModal, ConflictTable, PomodoroTimer, ChatBox, SummaryCard
│       ├── pages/            # DashboardPage, RoadmapPage, WorkspacePage
│       ├── services/         # api.ts (mọi lời gọi backend), types.ts, format.ts
│       ├── App.tsx, main.tsx, index.css
├── backend/
│   ├── app/
│   │   ├── main.py           # tạo app, CORS, đổi lỗi thành HTTP 403/400/404/500
│   │   ├── config.py         # đường dẫn dữ liệu, hằng số, biến môi trường
│   │   ├── api/routes.py     # 7 endpoint
│   │   ├── schemas/requests.py   # Pydantic kiểm tra request (lỗi -> 422)
│   │   └── services/
│   │       ├── json_storage.py   # NƠI DUY NHẤT đọc/ghi JSON (ghi file tạm rồi thay file chính)
│   │       ├── confirmation.py   # Confirmation Gate
│   │       ├── planner.py        # logic xung đột, đề xuất khung giờ, dời lịch, tổng kết buổi học
│   │       └── agent_tools.py    # các tool mock của AI Agent
│   ├── data/                 # lessons.json, tasks.json, qldt_fallback_response.json (dữ liệu giả lập)
│   ├── tests/                # pytest
│   ├── pytest.ini, requirements.txt, .env.example
├── .gitignore
└── README.md
```

So với cấu trúc ban đầu có thêm: `services/planner.py` (tách logic khỏi routes để dễ test),
`pytest.ini`, và ở frontend `services/types.ts`, `services/format.ts`, `vite-env.d.ts`.

## Yêu cầu

- Python 3.11 trở lên
- Node.js 18 trở lên (kèm npm)

## Chạy backend

```bash
cd backend
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows (PowerShell):
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

- Kiểm tra: mở http://localhost:8000/health (phải thấy `{"status":"ok"}`).
- Trang thử API (Swagger UI): http://localhost:8000/docs
- Không cần file `.env` để chạy. Muốn đổi cấu hình: `cp .env.example .env` rồi chạy
  `uvicorn app.main:app --reload --port 8000 --env-file .env`.

## Chạy frontend

Mở terminal thứ hai:

```bash
cd frontend
npm install
npm run dev
```

Mở http://localhost:5173. Frontend gọi backend ở `http://localhost:8000/api`
(đổi bằng biến `VITE_API_BASE_URL`, xem `frontend/.env.example`).
Kiểm tra build: `npm run build`.

## Chạy tests

```bash
cd backend
pytest
```

Test chạy trên **bản sao** thư mục `data` (trong thư mục tạm), không làm đổi dữ liệu mẫu thật.

## Danh sách API

Tất cả có tiền tố `/api`.

| # | Method và đường dẫn | Chức năng | Có ghi file không |
|---|---|---|---|
| 1 | `POST /schedule/sync` | Lấy lịch (mock), phát hiện xung đột, **đề xuất** khung giờ mới | Không |
| 2 | `POST /schedule/confirm-reschedule` | Dời lịch tự học, tùy chọn gọi Google Calendar (mock) | Có, **chỉ khi `user_confirmed` là `true`** |
| 3 | `POST /roadmap/generate` | Tạo **bản nháp** lộ trình ôn thi | Không |
| 4 | `GET /workspace/enter/{task_id}` | Lấy task, checklist, trạng thái tài liệu | Không |
| 5 | `POST /tutor/chat` | Hỏi gia sư AI (mock) | Không |
| 6 | `POST /tutor/inactivity-check` | Nhắc học khi không hoạt động từ 10 phút, có giới hạn tần suất | Không |
| 7 | `POST /workspace/complete` | Lưu pomodoro, checklist, ghi chú; trả `summary_card` | Có, chỉ các trường tiến độ |

Mã lỗi: `400` dữ liệu sai nội dung (giờ kết thúc không sau giờ bắt đầu, ngày không tồn tại, ID subtask lạ...),
`403` chưa xác nhận, `404` không thấy task, `422` sai kiểu/định dạng (Pydantic), `500` lỗi máy chủ hoặc file dữ liệu hỏng.
Lỗi luôn có dạng `{"detail": "..."}`.

## Confirmation Gate

Logic nằm ở `backend/app/services/confirmation.py`, kiểm tra **ở server**:

- `POST /schedule/confirm-reschedule` chỉ chạy khi `user_confirmed` là boolean `true`. Thiếu, `false`,
  `"true"`, `1`... đều bị từ chối: **HTTP 403**, `{"detail": "Action requires explicit user confirmation"}`.
- Việc kiểm tra diễn ra **trước** mọi thao tác ghi file và trước khi gọi Google Calendar.
  Hàm dời lịch (`planner.apply_reschedule`) và tool Google Calendar còn tự kiểm tra thêm một lần nữa.
- Cờ xác nhận nằm trong từng request, không có biến global dùng chung.
- Dời lịch là "tất cả hoặc không gì": nếu một mục sai thì không mục nào được ghi.
- API 1 và API 3 chỉ đề xuất/tạo nháp, không sửa lịch. API 7 chỉ ghi tiến độ (không đổi ngày/giờ).
- Frontend chỉ gửi `user_confirmed: true` khi người dùng bấm **Đồng ý** trong modal; bấm **Hủy** không gửi gì.

### Tự thử Confirmation Gate

Cách dễ nhất: mở http://localhost:8000/docs, chọn `POST /api/schedule/confirm-reschedule`, bấm *Try it out*.
Hoặc dùng curl (macOS/Linux/Git Bash):

```bash
# 1) Thiếu user_confirmed -> phải ra HTTP 403
curl -i -X POST http://localhost:8000/api/schedule/confirm-reschedule \
  -H "Content-Type: application/json" \
  -d '{"sync_gcal": true, "reschedule_items": [{"task_id": "TASK_2026-10-15_01", "new_date": "2026-10-15", "new_start": "19:00", "new_end": "20:30"}]}'

# 2) user_confirmed = true -> HTTP 200, tasks.json được cập nhật
curl -i -X POST http://localhost:8000/api/schedule/confirm-reschedule \
  -H "Content-Type: application/json" \
  -d '{"user_confirmed": true, "sync_gcal": true, "reschedule_items": [{"task_id": "TASK_2026-10-15_01", "new_date": "2026-10-15", "new_start": "19:00", "new_end": "20:30"}]}'
```

Sau khi thử xong, đưa dữ liệu mẫu về như cũ: `git checkout backend/data/tasks.json`.

Trên giao diện: vào trang *Lịch học* -> bấm **Cập nhật lịch** -> bảng xung đột -> **Dời lịch theo đề xuất** -> **Hủy**
(không có request nào được gửi, xem tab Network của trình duyệt) hoặc **Đồng ý**.

## Mapping tool của AI Agent

Các tool nằm ở `backend/app/services/agent_tools.py` (mock, có input/output rõ ràng để thay bằng bản thật
mà không phải sửa routes). Nếu tên trong API contract của nhóm khác, đổi tên hàm tại đó và ghi lại ở bảng này.

| API | Tool |
|---|---|
| 1 `/schedule/sync` | `sync_qldt_schedule`, `resolve_conflicts_and_reschedule` (chỉ đề xuất) |
| 2 `/schedule/confirm-reschedule` | `sync_google_calendar` (chỉ gọi sau khi đã xác nhận) |
| 3 `/roadmap/generate` | `extract_document_content`, `generate_study_roadmap` |
| 4 `/workspace/enter/{task_id}` | `extract_document_content` |
| 5 `/tutor/chat` | `query_llm_tutor` |
| 6 `/tutor/inactivity-check` | `inactivity_check_trigger` |

## Giới hạn của bản mock

- **QLĐT**: không kết nối thật. API 1 đọc `data/qldt_fallback_response.json` và trả `source: "qldt_fallback_file"`, `is_mock: true`.
- **Google Calendar**: không gọi thật. Kết quả luôn `gcal_synced: false`, `gcal_mode: "mock"`; message nói rõ là mock.
  Task đã có `gcal_event_id` được tính là "cập nhật", không tạo trùng; mock không ghi ID giả vào `tasks.json`.
- **Đọc PDF/OCR**: chưa có. Task có `slide_url` trả `document.status = "not_extracted"`, không có `slide_url` trả `"no_document"`.
  Không bao giờ giả vờ đã đọc tài liệu.
- **LLM gia sư**: trả lời mẫu cố định (`provider_used: "mock"`), không cần API key và không đọc code đính kèm.
- **Lộ trình ôn thi**: sinh theo mẫu cố định, chưa dùng LLM, chưa dựa vào nội dung tài liệu.
- **Nhắc học (API 6)**: trạng thái "đã nhắc lúc nào" lưu **trong bộ nhớ**, theo từng `task_id`. Mất khi khởi động lại server
  và không dùng chung giữa nhiều worker. Chờ tối thiểu 300 giây giữa 2 lần nhắc (đổi bằng `INACTIVITY_COOLDOWN_SECONDS`).
- **Lưu trữ**: file JSON, chỉ phù hợp prototype một người dùng. Chưa có đăng nhập; khóa ghi file chỉ có tác dụng trong một tiến trình.
- Chat hiển thị `reply_markdown` dạng văn bản thường (chưa render Markdown).

## Điểm cần thống nhất với nhóm

Chưa có file API contract gốc nên một số chi tiết do phía backend tự chọn. Hãy đối chiếu và sửa nếu khác:

- `completed_subtask_ids` (API 7) là **danh sách đầy đủ** các subtask đã tick lúc bấm hoàn thành; subtask không có trong danh sách sẽ thành `done = false`.
- `completed_tasks_count` = số subtask đã hoàn thành trong buổi học; `pomodoro_result` dạng chuỗi `"2/3"` (đã xong/mục tiêu);
  `total_focus_minutes` = số pomodoro x 25 phút. Task chuyển sang `status = "completed"`.
- Trường **thêm** so với mô tả: API 1 có `is_mock`, `note`; API 2 có `gcal_mode`; API 3 có `is_mock`, `saved`, `document_status`, `note`;
  API 6 trả `should_remind`, `skip_reason`, `message`, `retry_after_seconds`; summary_card có thêm `total_subtasks`. Đây là trường bổ sung, không bỏ trường nào.
- Khung giờ đề xuất (API 1) tìm theo bước 30 phút trong 08:00-22:00, bắt đầu từ giờ gốc của task, thử tối đa 3 ngày; chỉ áp dụng cho task `is_flexible = true`.

## API mở rộng được đề xuất (chưa cài, chưa thuộc contract)

API 3 chỉ trả bản nháp nên hiện **chưa có cách lưu lộ trình**. Đề xuất bổ sung:

`POST /api/roadmap/confirm-save` nhận `{"user_confirmed": true, "sessions": [...]}`, đi qua Confirmation Gate như API 2
rồi mới ghi các buổi vào `study_sessions` trong `tasks.json`. Hãy thống nhất với nhóm trước khi thêm.

## Commit và push lên GitHub

```bash
cd easyplan
git init                         # bỏ qua nếu đã có repo
git status                       # kiểm tra: KHÔNG thấy .env, node_modules, .venv
git add .
git commit -m "Add EasyPlan web platform and backend gateway prototype"
git branch -M main
git remote add origin <URL-repo-của-nhóm>
git push -u origin main
```

Trước khi `git add`, nhớ đưa `backend/data/tasks.json` về trạng thái mẫu nếu bạn đã thử dời lịch/hoàn thành buổi học.

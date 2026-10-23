# 🚀 Hướng dẫn Triển khai (Deployment Guide) — EasyPlan AI Agent

Tài liệu này hướng dẫn chi tiết cách triển khai hệ thống **EasyPlan AI Agent** (Backend **FastAPI** + Frontend **React/Vite**) lên các môi trường Production phổ biến.

---

## 1. Biến Môi trường Cần chuẩn bị (Environment Variables)

### Đối với Backend (`backend/.env`)
| Tên biến | Bắt buộc | Mô tả | Giá trị mặc định / Ví dụ |
| :--- | :---: | :--- | :--- |
| `GEMINI_API_KEY` | Khuyên dùng | API Key của Google AI Studio để sử dụng model `gemini-3.8-flash` | `AIzaSy...` *(Có thể nhập trực tiếp trên Web UI)* |
| `GROQ_API_KEY` | Tùy chọn | API Key của Groq Cloud để làm Fallback (`llama-3.3-70b-versatile`) | `gsk_...` *(Có thể nhập trực tiếp trên Web UI)* |
| `QLDT_USERNAME` | Tùy chọn | Mã sinh viên PTIT để tự động cào lịch | `B25DCCN...` *(Có thể nhập 1 lần trên Web UI)* |
| `QLDT_PASSWORD` | Tùy chọn | Mật khẩu cổng QLĐT PTIT | `...` *(Có thể nhập 1 lần trên Web UI)* |
| `QLDT_HOC_KY` | Tùy chọn | Mã học kỳ trên cổng QLĐT PTIT | `20261` |

> **Lưu ý**: Ngay cả khi bạn chưa cấu hình biến môi trường trên server, người dùng vẫn có thể bấm nút **⚙️ Tài khoản QLĐT & API Key** ngay trên giao diện Web để nhập và lưu trực tiếp!

### Đối với Frontend (`frontend/.env.production`)
| Tên biến | Bắt buộc | Mô tả | Ví dụ |
| :--- | :---: | :--- | :--- |
| `VITE_API_BASE` | Khi tách tên miền | URL trỏ tới Backend FastAPI khi deploy tách rời Frontend và Backend | `https://easyplan-backend.onrender.com` |

---

## 2. Phương án 0: Chạy Tự động trên Máy Local / Máy Demo bằng Script 1-Click

Nếu bạn triển khai nhanh trên máy tính thuyết trình (Demo Day) chạy **Windows**, **macOS** hoặc **Linux**:

1. **Tự động tải / cập nhật code mới nhất từ GitHub**:
   - **Windows**: Chạy `sync_github.bat`
   - **Linux / macOS**: Chạy `./sync_github.sh`
2. **Tự động bật cả Backend (`Port 8000`) + Frontend (`Port 5173`) & mở trình duyệt**:
   - **Windows**: Chạy `start_app.bat`
   - **Linux / macOS**: Chạy `./start_app.sh`

---

## 3. Phương án 1: Deploy bằng Docker & Docker Compose (Khuyên dùng cho VPS / Máy chủ riêng)

Dự án đã được cấu hình sẵn [`docker-compose.yml`](./docker-compose.yml), [`backend/Dockerfile`](./backend/Dockerfile) và [`frontend/Dockerfile`](./frontend/Dockerfile).

### Các bước thực hiện:
1. Clone repository về máy chủ:
   ```bash
   git clone https://github.com/duckyo2007/Probation_Walleye.git
   cd Probation_Walleye
   ```
2. Tạo file `backend/.env` (tùy chọn):
   ```bash
   cp backend/.env.example backend/.env
   ```
3. Khởi chạy toàn bộ hệ thống bằng Docker Compose:
   ```bash
   docker compose up -d --build
   ```
4. Kiểm tra trạng thái container:
   ```bash
   docker compose ps
   ```
   - Giao diện Web Frontend: `http://<IP-May-Chu>:5173`
   - API Backend & Swagger Docs: `http://<IP-May-Chu>:8000/docs`

---

## 3. Phương án 2: Deploy Cloud Miễn phí (Backend trên Render/Railway + Frontend trên Vercel)

### Bước A: Deploy Backend lên Render.com (hoặc Railway.app)
1. Đăng nhập [Render.com](https://render.com) $\rightarrow$ Chọn **New +** $\rightarrow$ **Web Service**.
2. Kết nối tới GitHub repository: `https://github.com/duckyo2007/Probation_Walleye`.
3. Thiết lập cấu hình dịch vụ:
   - **Name**: `easyplan-ai-backend`
   - **Root Directory**: `backend`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Trong mục **Environment Variables**, thêm:
   - `GEMINI_API_KEY`: *(Key của bạn)*
   - `GROQ_API_KEY`: *(Key của bạn, nếu có)*
   - `PYTHON_VERSION`: `3.12.0`
5. Bấm **Create Web Service**. Sau khi deploy xong, sao chép đường dẫn Backend (ví dụ: `https://easyplan-ai-backend.onrender.com`).

### Bước B: Deploy Frontend lên Vercel (hoặc Netlify)
1. Đăng nhập [Vercel.com](https://vercel.com) $\rightarrow$ **Add New Project** $\rightarrow$ Chọn repository `Probation_Walleye`.
2. Thiết lập cấu hình:
   - **Framework Preset**: `Vite`
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
3. Trong mục **Environment Variables**, thêm:
   - `VITE_API_BASE` = `https://easyplan-ai-backend.onrender.com` *(không có dấu `/` ở cuối)*
4. Bấm **Deploy**. Vercel sẽ cung cấp tên miền HTTPS cho ứng dụng của bạn!

---

## 4. Phương án 3: Deploy Trực tiếp trên VPS Ubuntu (Systemd + Nginx)

### 1. Chạy Backend với Systemd
```bash
cd /var/www/Probation_Walleye/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```
*(Lưu ý: Dùng `--workers 1` để bộ nhớ đệm `_INACTIVITY_LAST_SENT` và khóa ghi file JSON hoạt động đồng nhất trên cùng một tiến trình).*

### 2. Build Frontend Tĩnh & Cấu hình Nginx
```bash
cd /var/www/Probation_Walleye/frontend
npm install
npm run build
```

Cấu hình Nginx (`/etc/nginx/sites-available/easyplan`):
```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Phục vụ giao diện React đã build
    root /var/www/Probation_Walleye/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # Chuyển tiếp các request API và file PDF sang FastAPI Backend
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        client_max_body_size 50M;
    }

    location /static/ {
        proxy_pass http://127.0.0.1:8000/static/;
        proxy_set_header Host $host;
    }
}
```

---

## 5. Checklist Kiểm thử Sau khi Deploy (Post-Deployment Smoke Test)

1. **Kiểm tra Health Check**: Truy cập `GET /health` $\rightarrow$ Trả về `{"status": "ok", "service": "EasyPlan AI Agent Backend"}`.
2. **Kiểm tra Đồng bộ QLĐT**: Bấm **🔄 Đồng bộ lịch QLĐT** trên thanh Header $\rightarrow$ Lưới lịch hiển thị đầy đủ các môn học từ `lessons.json` và các phiên tự học từ `tasks.json`.
3. **Kiểm tra Confirmation Gate**: Bấm **⚠️ Tạo xung đột mẫu** $\rightarrow$ Modal cảnh báo xung đột bật lên $\rightarrow$ Bấm **✓ Đồng ý dời lịch** $\rightarrow$ Phiên học được dời sang khung giờ trống thành công.
4. **Kiểm tra Phòng học 50/50 & Nhiều File PDF**: Bấm **VÀO TỰ HỌC NGAY →** $\rightarrow$ Kiểm tra chuyển đổi giữa 2 tab PDF mặc định, tải thêm file PDF mới và đặt câu hỏi cho **AI Trợ giảng (`gemini-3.8-flash`)**.

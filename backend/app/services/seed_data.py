import json
from typing import Any, Dict, List
import fitz  # PyMuPDF

from app.config import (
    LESSONS_FILE,
    QLDT_FALLBACK_FILE,
    SLIDES_DIR,
    TASKS_FILE,
    TKB_PTIT_FILE,
)
from app.services.json_storage import save_lessons, save_tasks
from app.services.qldt_client import parse_qldt_payload_to_lessons


SLIDE_CONTENTS: Dict[str, List[Dict[str, str]]] = {
    "INT1306_Chuong3_CayNhiPhan.pdf": [
        {
            "title": "CHUONG 3: CAY NHI PHAN & CAY NHI PHAN TIM KIEM (BST)",
            "body": (
                "Mon hoc: Cau truc du lieu va giai thuat (INT1306) - PTIT\n\n"
                "1. Dinh nghia Cay nhi phan (Binary Tree):\n"
                "- Cay nhi phan la cau truc du lieu phan cap, trong do moi nut (Node) co toi da 2 nut con: "
                "nut con trai (left child) va nut con phai (right child).\n"
                "- Cau truc Node trong C++:\n"
                "  struct Node {\n"
                "      int data;\n"
                "      Node* left;\n"
                "      Node* right;\n"
                "  };\n\n"
                "2. Tinh chat Cay nhi phan tim kiem (Binary Search Tree - BST):\n"
                "- Moi nut thuoc cay con ben trai co gia tri NHO HON nut goc (left->data < root->data).\n"
                "- Moi nut thuoc cay con ben phai co gia tri LON HON nut goc (right->data > root->data).\n"
                "- Hai cay con trai va phai cung phai la cay nhi phan tim kiem."
            ),
        },
        {
            "title": "CAC PHEP DUYET CAY NHI PHAN (TREE TRAVERSALS)",
            "body": (
                "Ba phep duyet cay de quy kinh dien (Do phuc tap O(n)):\n\n"
                "1. Duyet Tien thu tu - Pre-order (Node - Left - Right):\n"
                "   void preOrder(Node* root) {\n"
                "       if (root == nullptr) return; // BẮT BUỘC: Điều kiện dừng đệ quy!\n"
                "       cout << root->data << ' ';\n"
                "       preOrder(root->left);\n"
                "       preOrder(root->right);\n"
                "   }\n\n"
                "2. Duyet Trung thu tu - In-order (Left - Node - Right):\n"
                "- Tren cay BST, phep duyet In-order se in ra cac phan tu theo thu tu TANG DAN.\n\n"
                "3. Duyet Hau thu tu - Post-order (Left - Right - Node):\n"
                "- Ung dung: Tinh chieu cao cay, giai phong bo nho (delete tree)."
            ),
        },
        {
            "title": "TIM KIEM, THEM NUT VA XOA NUT TRONG BST",
            "body": (
                "1. Tim kiem (Search) & Them nut (Insert):\n"
                "- Do phuc tap trung binh: O(log n) khi cay can bang.\n"
                "- Truong hop xau nhat (cay suy bien thanh danh sach lien ket): O(n).\n\n"
                "2. Xoa mot nut (Delete Node) trong BST gom 3 truong hop:\n"
                "- TH1: Nut can xoa la nut la (khong co con) -> Giai phong truc tiep.\n"
                "- TH2: Nut can xoa co 1 cay con -> Noi cha cua nut do voi nut con duy nhat.\n"
                "- TH3: Nut can xoa co du 2 con -> Tim nut the mang la phan tu NHO NHAT ben cay con phai "
                "(In-order Successor), chep gia tri vao nut can xoa roi xoa de quy nut the mang."
            ),
        },
    ],
    "INT1306_BaiTap_ThucHanh_CayNhiPhan.pdf": [
        {
            "title": "TAI LIEU 2: KHU DE QUY DUYET CAY BANG NGAN XEP (STACK)",
            "body": (
                "Mon hoc: Cau truc du lieu va giai thuat (INT1306) - Bai tap & Nang cao\n\n"
                "1. Tai sao dung Stack thay cho De quy?\n"
                "- Ban chat cua de quy la su dung Call Stack cua he thong. Khi cay qua sau (suy bien O(n)), "
                "de quy co nguy co tran bo nho ngan xep (Stack Overflow).\n"
                "- Ta hoan toan co the dung std::stack<Node*> tường minh trên Heap de khu de quy.\n\n"
                "2. Code Duyet Pre-order (NLR) bang Stack (Khong de quy):\n"
                "   void preOrderIterative(Node* root) {\n"
                "       if (root == nullptr) return;\n"
                "       stack<Node*> st;\n"
                "       st.push(root);\n"
                "       while (!st.empty()) {\n"
                "           Node* curr = st.top(); st.pop();\n"
                "           cout << curr->data << ' ';\n"
                "           // Day con PHAI truoc, con TRAI sau de con TRAI duoc lay ra truoc (LIFO)\n"
                "           if (curr->right) st.push(curr->right);\n"
                "           if (curr->left)  st.push(curr->left);\n"
                "       }\n"
                "   }"
            ),
        },
        {
            "title": "DUYET IN-ORDER BANG STACK & BAI TAP TU LUYEN",
            "body": (
                "3. Code Duyet In-order (LNR) bang Stack:\n"
                "   void inOrderIterative(Node* root) {\n"
                "       stack<Node*> st;\n"
                "       Node* curr = root;\n"
                "       while (curr != nullptr || !st.empty()) {\n"
                "           while (curr != nullptr) {\n"
                "               st.push(curr);\n"
                "               curr = curr->left; // Di het ve nhanh trai\n"
                "           }\n"
                "           curr = st.top(); st.pop();\n"
                "           cout << curr->data << ' '; // Tham nut\n"
                "           curr = curr->right; // Chuyen sang nhanh phai\n"
                "       }\n"
                "   }\n\n"
                "4. Bai tap thuc hanh:\n"
                "- Bai 1: Dem so nut la (leaf nodes) tren BST bang Queue (BFS) hoac Stack (DFS).\n"
                "- Bai 2: Kiem tra mot cay nhi phan co phai la BST hop le hay khong."
            ),
        },
    ],
    "INT1359_ToanRoiRac2.pdf": [
        {
            "title": "TOAN ROI RAC 2 (INT1359) - LY THUYET DO THI",
            "body": (
                "Giang vien: Nguyen Thi Kieu Linh - Hoc vien Cong nghe Buu chinh Vien thong (PTIT)\n\n"
                "1. Bieu dien do thi tren may tinh:\n"
                "- Ma tran ke (Adjacency Matrix): Mang 2 chieu A[n][n], ton O(n^2) bo nho.\n"
                "- Danh sach ke (Adjacency List): Vector cac danh sach, toi uu O(V + E) cho do thi thua.\n"
                "- Danh sach canh (Edge List): Dung trong thuat toan Kruskal tim cay khung nho nhat.\n\n"
                "2. Thuat toan duyet do thi:\n"
                "- DFS (Depth First Search): Su dung Stack hoac De quy, do phuc tap O(V + E).\n"
                "- BFS (Breadth First Search): Su dung Queue, tim duong di ngan nhat theo so canh."
            ),
        },
        {
            "title": "DO THI EULER, HAMILTON & DUONG DI NGAN NHAT",
            "body": (
                "1. Chu trinh Euler & Duong di Euler:\n"
                "- Do thi vo huong lien thong G co chu trinh Euler <=> Moi dinh cua G deu co BAC CHAN.\n"
                "- Do thi vo huong lien thong G co duong di Euler <=> G co dung 0 hoac 2 dinh bac le.\n\n"
                "2. Thuat toan Dijkstra:\n"
                "- Tim duong di ngan nhat tu 1 dinh nguon s den moi dinh khac tren do thi trong so KHONG AM.\n"
                "- Su dung Priority Queue (Min-Heap) dat do phuc tap O((V + E) log V)."
            ),
        },
    ],
    "ELE1309_DienTuSo.pdf": [
        {
            "title": "DIEN TU SO (ELE1309) - DAI SO BOOLE & BIA KARNAUGH",
            "body": (
                "Giang vien: Nguyen Trung Hieu - PTIT\n\n"
                "1. Cac cong logic co ban: AND, OR, NOT, NAND, NOR, XOR, XNOR.\n"
                "- NAND va NOR la hai he cong logic day du (Universal Gates).\n\n"
                "2. Toi thieu hoa ham Boole bang Bia Karnaugh (K-Map):\n"
                "- Nhom cac o ke nhau chua gia tri 1 theo luy thua cua 2 (1, 2, 4, 8, 16 o).\n"
                "- Loai bo cac bien thay doi trang thai trong cung mot nhom.\n"
                "- Thiet ke mach to hop: Bo cong (Adder), Bo giai ma (Decoder), Multiplexer (MUX)."
            ),
        },
    ],
    "BAS1269_XacSuatThongKe.pdf": [
        {
            "title": "XAC SUAT THONG KE (BAS1269) - BIEN NGAU NHIEN & PHAN PHOI",
            "body": (
                "Giang vien: Nguyen Thi Trang - PTIT\n\n"
                "1. Cong thuc Xac suat day du va Cong thuc Bayes:\n"
                "- P(A) = Sum(P(H_i) * P(A | H_i))\n"
                "- P(H_k | A) = [P(H_k) * P(A | H_k)] / P(A)\n\n"
                "2. Ky vong E(X) va Phuong sai V(X):\n"
                "- Ky vong E(X) dac trung cho gia tri trung binh.\n"
                "- Phuong sai V(X) = E(X^2) - [E(X)]^2 do muc do phan tan quang ky vong.\n"
                "- Cac phan phoi quan trong: Nhi thuc B(n, p), Poisson P(lambda), Chuan N(mu, sigma^2)."
            ),
        },
    ],
    "BAS1152_CNXHKH.pdf": [
        {
            "title": "CHU NGHIA XA HOI KHOA HOC (BAS1152) - ON TAP TRONG TAM",
            "body": (
                "Giang vien: Dao Thi Huong - PTIT\n\n"
                "1. Su menh lich su cua giai cap cong nhan:\n"
                "- Dieu kien khach quan va nhan to chu quan quy dinh su menh lich su.\n"
                "2. Thoi ky qua do len Chu nghia xa hoi tai Viet Nam:\n"
                "- Dac diem, thach thuc va phuong huong xay dung nha nuoc phap quyen XHCN."
            ),
        },
    ],
    "SKD1101_KyNangThuyetTrinh.pdf": [
        {
            "title": "KY NANG THUYET TRINH (SKD1101) - CAU TRUC BAI PITCH",
            "body": (
                "Giang vien: Hoang Thi Thu Ha - PTIT\n\n"
                "1. Cau truc 3 phan: Mo dau gay an tuong (Hook) - Noi dung cot loi (3 luan diem) - Ket luan keu goi hanh dong (Call to Action).\n"
                "2. Ngon ngu co the (Body Language), giao tiep mat (Eye Contact) va kiem soat giong noi."
            ),
        },
    ],
    "BAS1158_TiengAnhCourse2.pdf": [
        {
            "title": "TIENG ANH COURSE 2 (BAS1158) - ACADEMIC COMMUNICATION",
            "body": (
                "Giang vien: Le Thi Hong Hanh - PTIT\n\n"
                "1. Grammar Focus: Relative Clauses, Conditionals (Types 1, 2, 3), Passive Voice in Technical Writing.\n"
                "2. Vocabulary: Information Technology, Telecommunications, and Data Analysis terminology."
            ),
        },
    ],
}


def ensure_sample_pdfs() -> None:
    """Generates sample PDF slides in `backend/static/slides/` using PyMuPDF (`fitz`)."""
    SLIDES_DIR.mkdir(parents=True, exist_ok=True)
    for filename, pages in SLIDE_CONTENTS.items():
        target_path = SLIDES_DIR / filename
        if target_path.exists() and target_path.stat().st_size > 500:
            continue
        doc = fitz.open()
        for idx, p_data in enumerate(pages, start=1):
            page = doc.new_page(width=595, height=842)
            page.draw_rect(
                fitz.Rect(36, 36, 559, 92),
                color=(0.31, 0.27, 0.90),
                fill=(0.93, 0.94, 1.0),
            )
            page.insert_text(
                fitz.Point(48, 60),
                f"EasyPlan PTIT Slide - Trang {idx}/{len(pages)}",
                fontsize=10,
                color=(0.31, 0.27, 0.90),
            )
            page.insert_text(
                fitz.Point(48, 80),
                p_data["title"],
                fontsize=13,
                color=(0.1, 0.1, 0.25),
            )
            page.insert_textbox(
                fitz.Rect(48, 115, 547, 790),
                p_data["body"],
                fontsize=11.5,
                color=(0.15, 0.15, 0.15),
            )
        doc.save(str(target_path))
        doc.close()

    scanned_pdf = SLIDES_DIR / "Scanned_Image_Only_Demo.pdf"
    if not scanned_pdf.exists():
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        page.draw_rect(
            fitz.Rect(50, 50, 545, 792),
            color=(0.4, 0.4, 0.4),
            fill=(0.95, 0.95, 0.95),
        )
        doc.save(str(scanned_pdf))
        doc.close()


def build_default_lessons() -> List[Dict[str, Any]]:
    source_file = TKB_PTIT_FILE if TKB_PTIT_FILE.exists() else QLDT_FALLBACK_FILE
    lessons: List[Dict[str, Any]] = []
    if source_file.exists():
        raw = json.loads(source_file.read_text(encoding="utf-8"))
        lessons = parse_qldt_payload_to_lessons(raw)

    demo_key = "INT1306_2026-10-15_0700"
    if not any(l.get("key") == demo_key for l in lessons):
        lessons.append(
            {
                "key": demo_key,
                "week": 10,
                "date": "2026-10-15",
                "start": "07:00",
                "end": "09:50",
                "course_code": "INT1306",
                "course_name": "Cấu trúc dữ liệu và giải thuật",
                "teacher": "Bùi Văn Kiên",
                "room": "704-A2-704-A2(HN)",
                "online": False,
                "cancelled": False,
                "makeup": True,
                "slide_url": "/static/slides/INT1306_Chuong3_CayNhiPhan.pdf",
                "gcal_event_id": "gcal_evt_INT1306_20261015_0700",
            }
        )

    lessons.sort(key=lambda x: (x["date"], x["start"], x["course_code"]))
    return lessons


def build_default_tasks() -> List[Dict[str, Any]]:
    """
    Builds initial `tasks.json`, supporting multiple PDF documents per study session (`slide_urls`)
    while keeping `slide_url` for backward compatibility with single-URL contracts.
    """
    return [
        {
            "task_id": "task_001",
            "week": 10,
            "date": "2026-10-15",
            "start": "08:00",
            "end": "09:30",
            "course_code": "INT1306",
            "course_name": "Cấu trúc dữ liệu và giải thuật",
            "title": "Tự học: Cây nhị phân & Duyệt cây",
            "status": "todo",
            "is_flexible": True,
            "pomodoro_target": 2,
            "pomodoro_Completed": 0,
            "slide_url": "/static/slides/INT1306_Chuong3_CayNhiPhan.pdf",
            "slide_urls": [
                "/static/slides/INT1306_Chuong3_CayNhiPhan.pdf",
                "/static/slides/INT1306_BaiTap_ThucHanh_CayNhiPhan.pdf",
            ],
            "subtasks": [
                {
                    "sub_id": "sub_1",
                    "content": "Đọc định nghĩa Cây nhị phân tìm kiếm (BST)",
                    "done": True,
                },
                {
                    "sub_id": "sub_2",
                    "content": "Code thử thuật toán duyệt cây (Pre-order, In-order)",
                    "done": False,
                },
                {
                    "sub_id": "sub_3",
                    "content": "Làm 3 câu hỏi trắc nghiệm cuối bài",
                    "done": False,
                },
            ],
            "personal_notes": "",
            "gcal_event_id": "gcal_task_001",
        },
        {
            "task_id": "task_002",
            "week": 10,
            "date": "2026-10-18",
            "start": "19:30",
            "end": "21:00",
            "course_code": "INT1359",
            "course_name": "Toán rời rạc 2",
            "title": "Tự học: Duyệt đồ thị DFS/BFS & Chu trình Euler",
            "status": "todo",
            "is_flexible": True,
            "pomodoro_target": 2,
            "pomodoro_Completed": 0,
            "slide_url": "/static/slides/INT1359_ToanRoiRac2.pdf",
            "slide_urls": [
                "/static/slides/INT1359_ToanRoiRac2.pdf",
            ],
            "subtasks": [
                {
                    "sub_id": "sub_1",
                    "content": "So sánh ma trận kề và danh sách kề trên đồ thị thưa",
                    "done": False,
                },
                {
                    "sub_id": "sub_2",
                    "content": "Cài đặt thuật toán DFS đệ quy và BFS dùng hàng đợi Queue",
                    "done": False,
                },
                {
                    "sub_id": "sub_3",
                    "content": "Chứng minh điều kiện bậc chẵn của chu trình Euler",
                    "done": False,
                },
            ],
            "personal_notes": "",
            "gcal_event_id": "gcal_task_002",
        },
        {
            "task_id": "task_003",
            "week": 10,
            "date": "2026-10-17",
            "start": "19:30",
            "end": "21:00",
            "course_code": "ELE1309",
            "course_name": "Điện tử số",
            "title": "Tự học: Tối thiểu hóa hàm Boole bằng Bìa Karnaugh",
            "status": "todo",
            "is_flexible": True,
            "pomodoro_target": 2,
            "pomodoro_Completed": 0,
            "slide_url": "/static/slides/ELE1309_DienTuSo.pdf",
            "slide_urls": [
                "/static/slides/ELE1309_DienTuSo.pdf",
            ],
            "subtasks": [
                {
                    "sub_id": "sub_1",
                    "content": "Ôn tập định lý De Morgan và các cổng NAND/NOR",
                    "done": False,
                },
                {
                    "sub_id": "sub_2",
                    "content": "Rút gọn 3 bài tập hàm Boole 4 biến bằng Bìa Karnaugh",
                    "done": False,
                },
            ],
            "personal_notes": "",
            "gcal_event_id": "gcal_task_003",
        },
        {
            "task_id": "task_004",
            "week": 10,
            "date": "2026-10-13",
            "start": "19:30",
            "end": "20:30",
            "course_code": "BAS1269",
            "course_name": "Xác suất thống kê",
            "title": "Ôn tập: Công thức xác suất đầy đủ và Công thức Bayes",
            "status": "done",
            "is_flexible": True,
            "pomodoro_target": 2,
            "pomodoro_Completed": 2,
            "slide_url": "/static/slides/BAS1269_XacSuatThongKe.pdf",
            "slide_urls": [
                "/static/slides/BAS1269_XacSuatThongKe.pdf",
            ],
            "subtasks": [
                {
                    "sub_id": "sub_1",
                    "content": "Nắm vững hệ đầy đủ các biến cố H1, H2, ..., Hn",
                    "done": True,
                },
                {
                    "sub_id": "sub_2",
                    "content": "Giải 4 bài tập áp dụng công thức Bayes trong slide",
                    "done": True,
                },
            ],
            "personal_notes": "Đã làm chắc dạng bài công thức Bayes.",
            "gcal_event_id": "gcal_task_004",
        },
    ]


def ensure_initial_seed_data(force_reset: bool = False, demo_tasks: bool = False) -> Dict[str, int]:
    """
    Seeds lessons and tasks. First-time users start with NO self-study tasks (only school
    lessons); pass `demo_tasks=True` (tests / demo helpers) to seed the sample sessions.
    """
    ensure_sample_pdfs()
    if force_reset or not LESSONS_FILE.exists():
        lessons = build_default_lessons()
        save_lessons(lessons)
    else:
        lessons = json.loads(LESSONS_FILE.read_text(encoding="utf-8"))

    if force_reset or not TASKS_FILE.exists():
        tasks = build_default_tasks() if demo_tasks else []
        save_tasks(tasks)
    else:
        tasks = json.loads(TASKS_FILE.read_text(encoding="utf-8"))
        # Upgrade any existing task that doesn't have slide_urls yet
        changed = False
        for t in tasks:
            if "slide_urls" not in t or not isinstance(t["slide_urls"], list) or not t["slide_urls"]:
                s_url = t.get("slide_url") or "/static/slides/INT1306_Chuong3_CayNhiPhan.pdf"
                if t.get("task_id") == "task_001" and s_url == "/static/slides/INT1306_Chuong3_CayNhiPhan.pdf":
                    t["slide_urls"] = [
                        "/static/slides/INT1306_Chuong3_CayNhiPhan.pdf",
                        "/static/slides/INT1306_BaiTap_ThucHanh_CayNhiPhan.pdf",
                    ]
                else:
                    t["slide_urls"] = [s_url]
                changed = True
        if changed:
            save_tasks(tasks)

    return {
        "lessons_count": len(lessons),
        "tasks_count": len(tasks),
    }

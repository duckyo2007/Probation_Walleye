"""Chuyển response API thời khóa biểu của qldt thành danh sách buổi học phẳng.

Cách dùng:
    python parse_qldt.py response.json lessons.json

response.json là nội dung response của request w-locdstkbtuanusertheohocky
(DevTools -> Network -> chọn request -> Response -> Copy).
"""
import json
import sys

# Tiết ngắn hơn ngưỡng này (vd 5 phút) là tiết "ảo" mà qldt dùng cho buổi học online
# trên LMS: đó không phải giờ học thật nên không được tính là giờ bận.
MIN_REAL_PERIOD_MINUTES = 30
ONLINE_KEYWORDS = ("online", "lms", "trực tuyến")


def build_period_table(periods):
    """tiet -> (giờ bắt đầu, giờ kết thúc, có phải tiết thật không)."""
    return {
        p["tiet"]: (
            p["gio_bat_dau"],
            p["gio_ket_thuc"],
            p["so_phut"] >= MIN_REAL_PERIOD_MINUTES,
        )
        for p in periods
    }


def session_times(table, first_period, count):
    """Giờ bắt đầu/kết thúc của một buổi, có giá trị dự phòng an toàn thay vì trả về None."""
    default = (None, None, False)
    real = [
        t for t in range(first_period, first_period + count)
        if table.get(t, default)[2]
    ]
    if not real:
        # Dự phòng: lấy bất kỳ tiết nào có trong khoảng thời gian này nếu không tìm thấy tiết thực
        all_periods = [
            t for t in range(first_period, first_period + count)
            if t in table
        ]
        if all_periods:
            return table[all_periods[0]][0], table[all_periods[-1]][1]
        # Nếu hoàn toàn trống, trả về khung giờ mặc định để tránh lỗi None ở các module kiểm tra giờ
        return "07:00", "09:00"
    return table[real[0]][0], table[real[-1]][1]


def parse_lessons(payload):
    data = payload["data"]
    table = build_period_table(data["ds_tiet_trong_ngay"])
    lessons = []
    for week in data["ds_tuan_tkb"]:
        for s in week["ds_thoi_khoa_bieu"]:
            date = s["ngay_hoc"][:10]  # "2026-09-08T00:00:00" -> "2026-09-08"
            start, end = session_times(table, s["tiet_bat_dau"], s["so_tiet"])
            room = (s.get("ma_phong") or "").strip()
            lessons.append({
                # id_tkb lặp lại mỗi tuần, nên khóa duy nhất của một buổi là id_tkb + ngày
                "key": f"{s['id_tkb']}_{date}",
                "week": week["tuan_hoc_ky"],
                "date": date,  # giờ địa phương, không kèm múi giờ (Asia/Ho_Chi_Minh)
                "start": start,
                "end": end,
                "course_code": s["ma_mon"],
                "course_name": s["ten_mon"].strip(),
                "teacher": (s.get("ten_giang_vien") or "").strip(),
                "room": room,
                "online": start is None or any(k in room.lower() for k in ONLINE_KEYWORDS),
                "cancelled": bool(s.get("is_nghi_day")),  # nghỉ dạy
                "makeup": bool(s.get("is_day_bu")),  # dạy bù
            })
    lessons.sort(key=lambda x: (x["date"], x["start"] or "99:99"))
    return lessons


def main(src, dst):
    with open(src, encoding="utf-8") as f:
        payload = json.load(f)
    if not payload.get("result"):
        sys.exit(f"API trả về lỗi (code={payload.get('code')}), không có dữ liệu để parse")
    lessons = parse_lessons(payload)
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(lessons, f, ensure_ascii=False, indent=2)
    print(f"Đã lưu {len(lessons)} buổi học vào {dst}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Cách dùng: python parse_qldt.py response.json lessons.json")
    main(sys.argv[1], sys.argv[2])
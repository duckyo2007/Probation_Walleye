"""Tool sync_qldt_schedule: lấy thời khóa biểu từ QLĐT và lưu thành lessons.json.

Nguồn dữ liệu, theo thứ tự ưu tiên:
  1. live     gọi API QLĐT bằng request trong curl.txt
  2. cache    lessons.json của lần đồng bộ thành công gần nhất
  3. fixture  file qldt_sample_response.json (dữ liệu mẫu đã thay thông tin cá nhân)
"""
import argparse
import json
import os
from datetime import datetime

from app.services.check_api import is_ok, load_curl, parse_json, send
from app.services.parse_qldt import parse_lessons

HERE = os.path.dirname(os.path.abspath(__file__))
CURL_FILE = os.path.join(HERE, "curl.txt")
LESSONS_FILE = os.path.join(HERE, "lessons.json")
FIXTURE_FILE = os.path.join(HERE, "qldt_sample_response.json")
SNAPSHOT_DIR = os.path.join(HERE, "snapshots")


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _write_json(path, data, **kwargs):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, **kwargs)


def _fetch_live(curl_file):
    """Trả về (payload, None) nếu thành công, hoặc (None, lý do lỗi)."""
    try:
        req = load_curl(curl_file)
    except SystemExit as e:  # load_curl báo lỗi bằng sys.exit(thông báo)
        return None, f"Không đọc được {os.path.basename(curl_file)}: {e}"
    status, text, _ = send(req, req["headers"], timeout=20)
    if status is None:
        return None, "Không kết nối được tới QLĐT (lỗi mạng hoặc QLĐT đang sập)."
    if status in (401, 403):
        return None, (f"Phiên đăng nhập QLĐT đã hết hạn (HTTP {status}). "
                      "Copy lại cURL mới vào curl.txt.")
    if status != 200:
        return None, f"QLĐT trả về HTTP {status}."
    if not is_ok(status, text):
        return None, "QLĐT trả về nội dung không hợp lệ (result khác true)."
    return parse_json(text), None


def _parse(payload):
    """Parse response thành danh sách buổi học; ném ValueError nếu cấu trúc khác dự kiến."""
    try:
        return parse_lessons(payload)
    except (KeyError, TypeError, AttributeError) as e:
        raise ValueError(f"Cấu trúc response khác dự kiến (lỗi ở trường {e}), "
                         "có thể QLĐT đã đổi API.") from e


def diff_lessons(old, new):
    """So hai danh sách buổi học theo key: buổi mới, buổi bị bỏ, buổi bị sửa."""
    o = {x["key"]: x for x in old}
    n = {x["key"]: x for x in new}
    return {
        "added": sorted(n.keys() - o.keys()),
        "removed": sorted(o.keys() - n.keys()),
        "changed": sorted(k for k in n.keys() & o.keys() if n[k] != o[k]),
    }


def _result(status, source, fetched_at, warning, lessons, changes=None):
    return {"status": status, "source": source, "fetched_at": fetched_at,
            "warning": warning, "lessons": lessons, "changes": changes}


def sync_qldt_schedule(curl_file=CURL_FILE, lessons_file=LESSONS_FILE,
                       fixture_file=FIXTURE_FILE, snapshot_dir=SNAPSHOT_DIR, offline=False):
    reason = "Chế độ offline, không gọi QLĐT." if offline else None
    old = _read_json(lessons_file)

    # 1. Dữ liệu mới từ QLĐT
    if not offline:
        payload, reason = _fetch_live(curl_file)
        lessons = None
        if payload is not None:
            try:
                lessons = _parse(payload)
            except ValueError as e:
                reason = str(e)
        if lessons is not None:
            now = datetime.now()
            os.makedirs(snapshot_dir, exist_ok=True)  # giữ bản response gốc để debug
            _write_json(os.path.join(snapshot_dir, now.strftime("response_%Y%m%d_%H%M%S.json")),
                        payload, separators=(",", ":"))
            _write_json(lessons_file, lessons, indent=2)
            changes = diff_lessons(old, lessons) if old is not None else None
            return _result("ok", "live", now.isoformat(timespec="seconds"), None, lessons, changes)

    # 2. Bản đồng bộ thành công gần nhất
    if old is not None:
        fetched = datetime.fromtimestamp(os.path.getmtime(lessons_file))
        return _result("fallback", "cache", fetched.isoformat(timespec="seconds"), reason, old)

    # 3. File dữ liệu mẫu
    sample = _read_json(fixture_file)
    if sample is not None:
        try:
            return _result("fallback", "fixture", None, reason, _parse(sample))
        except ValueError as e:
            reason = f"{reason} File dự phòng cũng lỗi: {e}"
    return _result("error", None, None, f"{reason} Không có dữ liệu dự phòng.", [])


def main():
    ap = argparse.ArgumentParser(description="Đồng bộ thời khóa biểu từ QLĐT")
    ap.add_argument("--offline", action="store_true",
                    help="bỏ qua QLĐT, dùng bản gần nhất hoặc file dự phòng")
    args = ap.parse_args()
    r = sync_qldt_schedule(offline=args.offline)
    print(f"status={r['status']} | nguồn={r['source']} | {len(r['lessons'])} buổi học | "
          f"dữ liệu lúc {r['fetched_at'] or 'không rõ (dữ liệu mẫu)'}")
    if r["warning"]:
        print("Cảnh báo:", r["warning"])
    if r["changes"] is not None:
        c = r["changes"]
        print(f"So với lần trước: {len(c['added'])} buổi mới, "
              f"{len(c['removed'])} buổi bị bỏ, {len(c['changed'])} buổi bị sửa")


if __name__ == "__main__":
    main()
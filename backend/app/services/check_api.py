"""Kiểm tra gọi API qldt ngoài trình duyệt (không cần cài thêm thư viện nào).

Chuẩn bị: trong DevTools -> Network, chuột phải request cần thử ->
Copy -> "Copy as cURL (bash)", dán vào file curl.txt cùng thư mục với script này.

Cách dùng:
    python check_api.py                       gọi lại request trong curl.txt
    python check_api.py login_curl.txt        dùng file cURL khác
    python check_api.py --save response.json  lưu nội dung trả về
    python check_api.py --minimize            tìm header tối thiểu phải gửi
    python check_api.py --watch 15            gọi lại mỗi 15 phút đến khi lỗi (đo token sống bao lâu)

Script không in token hay mật khẩu ra màn hình, nhưng file cURL thì có chứa chúng:
đừng đẩy file đó lên GitHub hay gửi cho người khác.
"""
import argparse
import ast
import base64
import gzip
import json
import re
import shlex
import sys
import time
import urllib.error
import urllib.request
import zlib
from datetime import datetime
from urllib.parse import urlsplit

LOG_FILE = "check_log.txt"
# Những header để thư viện tự đặt, gửi lại nguyên văn dễ gây lỗi
SKIP_HEADERS = {"content-length", "host", "connection", "accept-encoding"}
# Cờ curl đi kèm một giá trị mà script không dùng: bỏ qua cả giá trị đó
FLAGS_WITH_VALUE = {"-o", "--output", "-m", "--max-time", "--connect-timeout",
                    "-x", "--proxy", "-w", "--write-out", "--retry", "-u", "--user"}
JWT_RE = re.compile(r"eyJ[\w-]+\.[\w-]+\.[\w-]+")


# ---------- đọc lệnh cURL ----------

def _ansi_c(match):
    """Chrome viết chuỗi có ký tự đặc biệt dạng $'...': đổi về chuỗi thường."""
    try:
        return shlex.quote(ast.literal_eval("'" + match.group(1) + "'"))
    except (ValueError, SyntaxError):
        return shlex.quote(match.group(1))


def load_curl(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            text = f.read()
    except FileNotFoundError:
        sys.exit(f"Không tìm thấy file {path} trong thư mục hiện tại.")
    if '^"' in text or re.search(r"\^\s*$", text, re.M):
        sys.exit('File này có vẻ copy kiểu cmd. Hãy copy lại bằng "Copy as cURL (bash)".')
    text = re.sub(r"\\\r?\n", " ", text)  # nối các dòng bị ngắt bằng dấu \
    text = re.sub(r"\$'((?:[^'\\]|\\.)*)'", _ansi_c, text)
    try:
        args = shlex.split(text)
    except ValueError as e:
        sys.exit(f"Không đọc được lệnh curl ({e}). Thử copy lại cả lệnh.")
    if not args or not args[0].lower().startswith("curl"):
        sys.exit("File phải bắt đầu bằng lệnh curl.")

    url, method, data, headers = None, None, None, {}
    i = 1
    while i < len(args):
        a = args[i]
        if a in ("-H", "--header"):
            i += 1
            name, _, value = args[i].partition(":")
            if name.strip():
                headers[name.strip().lower()] = value.strip()
        elif a in ("-X", "--request"):
            i += 1
            method = args[i].upper()
        elif a in ("-d", "--data", "--data-raw", "--data-binary", "--data-ascii"):
            i += 1
            data = args[i]
        elif a in ("-b", "--cookie"):
            i += 1
            headers["cookie"] = args[i]
        elif a in ("-A", "--user-agent"):
            i += 1
            headers["user-agent"] = args[i]
        elif a in ("-e", "--referer"):
            i += 1
            headers["referer"] = args[i]
        elif a in FLAGS_WITH_VALUE:
            i += 1
        elif a.startswith("-"):
            pass  # cờ không có giá trị (--compressed, -s, -L ...)
        else:
            url = a
        i += 1
    if not url:
        sys.exit("Không tìm thấy URL trong lệnh curl.")
    return {"url": url, "method": method or ("POST" if data is not None else "GET"),
            "data": data, "headers": headers}


# ---------- gửi request ----------

def send(req, headers, timeout=30):
    """Gửi request. Trả về (mã HTTP, nội dung, số ms); mã HTTP là None nếu không kết nối được."""
    sent = {k: v for k, v in headers.items() if k not in SKIP_HEADERS}
    body = req["data"].encode("utf-8") if req["data"] is not None else None
    request = urllib.request.Request(req["url"], data=body, headers=sent, method=req["method"])
    start = time.time()
    try:
        resp = urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as e:
        resp = e  # 4xx/5xx vẫn có nội dung để đọc
    except (urllib.error.URLError, OSError) as e:
        return None, f"Không kết nối được: {e}", int((time.time() - start) * 1000)
    raw = resp.read()
    ms = int((time.time() - start) * 1000)
    encoding = (resp.headers.get("Content-Encoding") or "").lower()
    try:
        if encoding == "gzip":
            raw = gzip.decompress(raw)
        elif encoding == "deflate":
            raw = zlib.decompress(raw)
    except (OSError, zlib.error):
        pass
    return resp.getcode(), raw.decode("utf-8", errors="replace"), ms


def parse_json(text):
    try:
        return json.loads(text)
    except ValueError:
        return None


def is_ok(status, text):
    j = parse_json(text)
    return status == 200 and isinstance(j, dict) and j.get("result") is True


# ---------- đọc hạn của token (JWT) ----------

def fmt_time(ts):
    return datetime.fromtimestamp(ts).strftime("%d/%m %H:%M")


def jwt_info(token):
    try:
        part = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
    except (ValueError, IndexError):
        return None
    if not isinstance(claims, dict):
        return None
    info = []
    if isinstance(claims.get("iat"), (int, float)):
        info.append("cấp lúc " + fmt_time(claims["iat"]))
    exp = claims.get("exp")
    if isinstance(exp, (int, float)):
        left = int((exp - time.time()) / 60)
        state = f"còn {left} phút" if left >= 0 else "ĐÃ HẾT HẠN"
        info.append(f"hết hạn {fmt_time(exp)} ({state})")
    else:
        info.append("không có thời hạn (exp) trong token")
    return ", ".join(info)


def walk_strings(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk_strings(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:50]):
            yield from walk_strings(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield path, obj


def report_jwts(req, j):
    for name, value in req["headers"].items():
        for token in JWT_RE.findall(value):
            info = jwt_info(token)
            if info:
                print(f"Token trong request (header {name}): {info}")
    if j is not None:
        for path, value in walk_strings(j):
            for token in JWT_RE.findall(value):
                info = jwt_info(token)
                if info:
                    print(f"Token trong response ({path}): {info}")


# ---------- in kết quả và ghi log ----------

def summarize(req, status, text, ms):
    parts = urlsplit(req["url"])
    print(f"{req['method']} {parts.netloc}{parts.path}")  # không in phần ?query vì có thể chứa token
    if status is None:
        print(text)
        return
    print(f"HTTP {status} | {ms} ms | {len(text)} ký tự")
    j = parse_json(text)
    if j is None:
        print("Nội dung không phải JSON, 200 ký tự đầu:", text[:200].replace("\n", " "))
        return
    if isinstance(j, dict):
        print("Khóa cấp 1:", ", ".join(j.keys()))
        data = j.get("data")
        if isinstance(data, dict):
            print("Khóa trong data:", ", ".join(list(data.keys())[:15]))
            weeks = data.get("ds_tuan_tkb")
            if isinstance(weeks, list):
                sessions = sum(len(w.get("ds_thoi_khoa_bieu", [])) for w in weeks)
                print(f"Lịch: {len(weeks)} tuần, {sessions} buổi học")
        if "result" in j:
            verdict = "THÀNH CÔNG" if is_ok(status, text) else "THẤT BẠI"
            print(f"result={j['result']}, code={j.get('code')} => {verdict}")
        else:
            print("Không có trường result: mở file lưu bằng --save để tự đọc nội dung.")
        for key in ("message", "msg", "error", "detail"):
            if isinstance(j.get(key), str):
                print(f"{key}: {j[key][:200]}")
    report_jwts(req, j)


def log_line(status, text, ms):
    j = parse_json(text)
    result = j.get("result") if isinstance(j, dict) else None
    verdict = "OK" if is_ok(status, text) else "LỖI"
    return f"HTTP {status} | result={result} | {ms} ms | {verdict}"


def log(line):
    stamp = datetime.now().strftime("%d/%m %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{stamp} | {line}\n")


# ---------- các chế độ ----------

def minimize(req, delay=1.5):
    """Thử bỏ từng header một, giữ lại những header bỏ đi thì request hỏng."""
    keep = dict(req["headers"])
    status, text, _ = send(req, keep)
    if not is_ok(status, text):
        sys.exit("Request gốc chưa thành công nên không thể rút gọn. "
                 "Chạy lại không có --minimize để xem lỗi.")
    print("Đang thử bỏ từng header (mỗi lần cách nhau vài giây)...")
    for name in [n for n in keep if n not in SKIP_HEADERS]:
        time.sleep(delay)
        trial = {k: v for k, v in keep.items() if k != name}
        status, text, _ = send(req, trial)
        needed = not is_ok(status, text)
        print(f"  {'CẦN    ' if needed else 'bỏ được'}  {name}")
        if not needed:
            keep = trial
    final = [k for k in keep if k not in SKIP_HEADERS]
    print("\nHeader tối thiểu:", ", ".join(final) if final else "(không cần header nào)")


def watch(req, interval):
    """Gọi lại đều đặn đến khi lỗi để biết token sống được bao lâu."""
    first = time.time()
    calls = 0
    print(f"Đang theo dõi, nhấn Ctrl+C để dừng. Kết quả ghi vào {LOG_FILE}")
    while True:
        status, text, ms = send(req, req["headers"])
        calls += 1
        line = log_line(status, text, ms)
        log(line)
        print(datetime.now().strftime("%H:%M:%S"), line)
        if not is_ok(status, text):
            minutes = int((time.time() - first) / 60)
            print(f"Bắt đầu lỗi sau khoảng {minutes} phút kể từ lần gọi đầu ({calls} lần gọi).")
            return
        time.sleep(interval)


def main():
    ap = argparse.ArgumentParser(description="Kiểm tra gọi API qldt ngoài trình duyệt")
    ap.add_argument("file", nargs="?", default="curl.txt",
                    help="file chứa lệnh cURL (mặc định curl.txt)")
    ap.add_argument("--save", metavar="FILE", help="lưu nội dung trả về vào file")
    ap.add_argument("--minimize", action="store_true", help="tìm header tối thiểu phải gửi")
    ap.add_argument("--watch", type=float, metavar="PHÚT",
                    help="gọi lại mỗi N phút (tối thiểu 1) đến khi lỗi")
    args = ap.parse_args()

    req = load_curl(args.file)
    if args.minimize:
        return minimize(req)
    if args.watch:
        return watch(req, max(args.watch, 1) * 60)

    status, text, ms = send(req, req["headers"])
    summarize(req, status, text, ms)
    log(log_line(status, text, ms))
    if args.save and status is not None:
        with open(args.save, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Đã lưu nội dung trả về vào {args.save}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nĐã dừng.")
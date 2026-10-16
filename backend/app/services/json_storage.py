"""Module DUY NHẤT được đọc/ghi file JSON. Các route không tự mở file.

Ghi file an toàn: ghi ra file tạm cùng thư mục rồi os.replace() sang file chính.
Nếu lỗi giữa chừng thì file chính vẫn nguyên vẹn.
"""
import json
import os
import tempfile
import threading
from typing import Any, Callable

from app import config


class StorageError(Exception):
    """Không đọc/ghi được dữ liệu (file thiếu, JSON hỏng, lỗi ổ đĩa)."""


# Khóa để 2 request không ghi chồng lên nhau trong cùng một tiến trình.
_lock = threading.RLock()


def _path(filename: str):
    return config.get_data_dir() / filename


def exists(filename: str) -> bool:
    return _path(filename).is_file()


def read_json(filename: str) -> Any:
    path = _path(filename)
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as e:
        raise StorageError(f"Không tìm thấy file dữ liệu: {filename}") from e
    except json.JSONDecodeError as e:
        raise StorageError(f"File dữ liệu không phải JSON hợp lệ: {filename}") from e
    except OSError as e:
        raise StorageError(f"Không đọc được file dữ liệu: {filename}") from e


def _write_atomic(filename: str, data: Any) -> None:
    path = _path(filename)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=filename + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)  # bước "đổi tên" là nguyên tử
    except Exception as e:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        raise StorageError(f"Không ghi được file dữ liệu: {filename}") from e


def write_json(filename: str, data: Any) -> None:
    with _lock:
        _write_atomic(filename, data)


def update_json(filename: str, modify: Callable[[Any], Any]) -> Any:
    """Đọc file -> gọi modify(data) -> ghi lại. Trả về kết quả của modify.

    Nếu modify ném lỗi (ví dụ dữ liệu không hợp lệ) thì KHÔNG ghi gì cả.
    """
    with _lock:
        data = read_json(filename)
        result = modify(data)
        _write_atomic(filename, data)
        return result

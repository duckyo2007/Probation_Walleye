import base64
import json
import urllib.parse
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import requests

from app.config import DEFAULT_HOC_KY, QLDT_FALLBACK_FILE, TKB_PTIT_FILE
from app.services.json_storage import (
    load_lessons,
    load_settings,
    save_lessons,
    save_settings,
)

BASE_URL = "https://qldt.ptit.edu.vn"
LOGIN_URL = f"{BASE_URL}/api/pn-signin"
SCHEDULE_URL = f"{BASE_URL}/api/sch/w-locdstkbtuanusertheohocky"

DEFAULT_UA_HEADER = (
    "706675655469506568414e6b54573634526973436b673d3d"
)

# Default PTIT period schedule fallback
DEFAULT_PERIOD_TIMES: Dict[int, Tuple[str, str]] = {
    1: ("07:00", "07:50"),
    2: ("08:00", "08:50"),
    3: ("09:00", "09:50"),
    4: ("10:00", "10:50"),
    5: ("11:00", "11:50"),
    6: ("12:00", "12:50"),
    7: ("13:00", "13:50"),
    8: ("14:00", "14:50"),
    9: ("15:00", "15:50"),
    10: ("16:00", "16:50"),
    11: ("17:00", "17:50"),
    12: ("18:00", "18:50"),
    13: ("19:00", "19:50"),
    14: ("20:00", "20:50"),
}

COURSE_SLIDE_MAP: Dict[str, str] = {
    "INT1306": "/static/slides/INT1306_Chuong3_CayNhiPhan.pdf",
    "INT1359": "/static/slides/INT1359_ToanRoiRac2.pdf",
    "ELE1309": "/static/slides/ELE1309_DienTuSo.pdf",
    "BAS1269": "/static/slides/BAS1269_XacSuatThongKe.pdf",
    "BAS1152": "/static/slides/BAS1152_CNXHKH.pdf",
    "SKD1101": "/static/slides/SKD1101_KyNangThuyetTrinh.pdf",
    "BAS1158": "/static/slides/BAS1158_TiengAnhCourse2.pdf",
}


def login_qldt(username: str, password: str, timeout: int = 5) -> str:
    """
    Authenticates against PTIT QLĐT API (`test.py` logic) and returns Bearer access_token.
    """
    payload_str = json.dumps(
        {
            "username": username,
            "password": password,
            "uri": f"{BASE_URL}/#/home",
        }
    )
    code_b64 = base64.b64encode(payload_str.encode("utf-8")).decode("utf-8")
    params = {
        "code": code_b64,
        "gopage": "",
        "mgr": "1",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": f"{BASE_URL}/",
    }
    response = requests.get(
        LOGIN_URL,
        params=params,
        headers=headers,
        allow_redirects=False,
        timeout=timeout,
    )
    if response.status_code == 302 and "Location" in response.headers:
        location_url = response.headers["Location"]
        if "CurrUser=" in location_url:
            curr_user_encoded = location_url.split("CurrUser=")[1].split("&")[0]
            curr_user_b64 = urllib.parse.unquote(curr_user_encoded)
            padding = 4 - (len(curr_user_b64) % 4)
            if padding != 4:
                curr_user_b64 += "=" * padding
            user_data_str = base64.b64decode(curr_user_b64).decode("utf-8")
            user_data = json.loads(user_data_str)
            token = user_data.get("access_token")
            if token:
                return token
    raise RuntimeError(f"QLĐT login failed (HTTP {response.status_code})")


def fetch_schedule_qldt(
    access_token: str,
    hoc_ky: int = DEFAULT_HOC_KY,
    timeout: int = 5,
) -> Dict[str, Any]:
    """
    Fetches full semester weekly schedule from PTIT QLĐT API (`test.py` logic).
    """
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "ua": DEFAULT_UA_HEADER,
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/",
    }
    payload = {
        "filter": {
            "hoc_ky": hoc_ky,
            "ten_hoc_ky": "",
        },
        "additional": {
            "paging": {
                "limit": 500,
                "page": 1,
            },
            "ordering": [
                {
                    "name": None,
                    "order_type": None,
                }
            ],
        },
    }
    response = requests.post(
        SCHEDULE_URL,
        headers=headers,
        json=payload,
        timeout=timeout,
    )
    if response.status_code == 200:
        data = response.json()
        if isinstance(data, dict) and data.get("data"):
            return data
    raise RuntimeError(f"QLĐT schedule fetch failed (HTTP {response.status_code})")


def get_slide_for_course(course_code: str) -> str:
    return COURSE_SLIDE_MAP.get(
        course_code,
        "/static/slides/INT1306_Chuong3_CayNhiPhan.pdf",
    )


def parse_qldt_payload_to_lessons(raw_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Transforms raw QLĐT response (`tkb_ptit.json`) into flat `lessons.json` format,
    automatically merging consecutive periods (`tiet_bat_dau` + `so_tiet`) of the same
    course and room on the same day.
    """
    data_obj = raw_payload.get("data") or {}
    period_map: Dict[int, Tuple[str, str]] = dict(DEFAULT_PERIOD_TIMES)

    for p in data_obj.get("ds_tiet_trong_ngay") or []:
        tiet_num = p.get("tiet")
        start_str = p.get("gio_bat_dau")
        end_str = p.get("gio_ket_thuc")
        if isinstance(tiet_num, int) and start_str and end_str:
            period_map[tiet_num] = (str(start_str), str(end_str))

    weeks = data_obj.get("ds_tuan_tkb") or []
    merged_lessons: List[Dict[str, Any]] = []

    for week_item in weeks:
        week_num = int(week_item.get("tuan_hoc_ky") or 1)
        raw_items = week_item.get("ds_thoi_khoa_bieu") or []
        if not raw_items:
            continue

        # Sort by date, course, room, starting period so consecutive blocks can be merged cleanly
        sorted_items = sorted(
            raw_items,
            key=lambda x: (
                str(x.get("ngay_hoc") or "")[:10],
                str(x.get("ma_mon") or ""),
                str(x.get("ma_phong") or ""),
                int(x.get("tiet_bat_dau") or 1),
            ),
        )

        grouped: List[Dict[str, Any]] = []
        for item in sorted_items:
            date_str = str(item.get("ngay_hoc") or "")[:10]
            if not date_str:
                continue
            course_code = str(item.get("ma_mon") or "UNKNOWN").strip()
            course_name = str(item.get("ten_mon") or course_code).strip()
            teacher = str(item.get("ten_giang_vien") or "Giảng viên PTIT").strip()
            room = str(item.get("ma_phong") or "Phòng học").strip()
            tiet_start = int(item.get("tiet_bat_dau") or 1)
            so_tiet = max(1, int(item.get("so_tiet") or 1))
            tiet_end = tiet_start + so_tiet - 1
            cancelled = bool(item.get("is_nghi_day", False))
            makeup = bool(item.get("is_day_bu", False))
            online = "ONLINE" in room.upper() or "ZOOM" in room.upper() or "TEAMS" in room.upper()

            if grouped:
                prev = grouped[-1]
                if (
                    prev["date"] == date_str
                    and prev["course_code"] == course_code
                    and prev["room"] == room
                    and prev["cancelled"] == cancelled
                    and prev["_tiet_end"] + 1 == tiet_start
                ):
                    prev["_tiet_end"] = max(prev["_tiet_end"], tiet_end)
                    if not prev["teacher"] and teacher:
                        prev["teacher"] = teacher
                    continue

            grouped.append(
                {
                    "week": week_num,
                    "date": date_str,
                    "_tiet_start": tiet_start,
                    "_tiet_end": tiet_end,
                    "course_code": course_code,
                    "course_name": course_name,
                    "teacher": teacher,
                    "room": room,
                    "online": online,
                    "cancelled": cancelled,
                    "makeup": makeup,
                }
            )

        for g in grouped:
            t_start = g.pop("_tiet_start")
            t_end = g.pop("_tiet_end")
            start_time = period_map.get(t_start, ("07:00", "07:50"))[0]
            end_time = period_map.get(t_end, ("11:50", "11:50"))[1]
            c_code = g["course_code"]
            d_str = g["date"]
            start_compact = start_time.replace(":", "")
            date_compact = d_str.replace("-", "")

            lesson_obj = {
                "key": f"{c_code}_{d_str}_{start_compact}",
                "week": g["week"],
                "date": d_str,
                "start": start_time,
                "end": end_time,
                "course_code": c_code,
                "course_name": g["course_name"],
                "teacher": g["teacher"],
                "room": g["room"],
                "online": g["online"],
                "cancelled": g["cancelled"],
                "makeup": g["makeup"],
                "slide_url": get_slide_for_course(c_code),
                "gcal_event_id": f"gcal_evt_{c_code}_{date_compact}_{start_compact}",
            }
            merged_lessons.append(lesson_obj)

    merged_lessons.sort(key=lambda x: (x["date"], x["start"], x["course_code"]))
    return merged_lessons


def get_weeks_metadata() -> List[Dict[str, Any]]:
    """
    Returns metadata for all semester weeks from `tkb_ptit.json` so the frontend
    can let the user browse any week in the semester.
    """
    source_path = TKB_PTIT_FILE if TKB_PTIT_FILE.exists() else QLDT_FALLBACK_FILE
    if not source_path.exists():
        return []
    try:
        raw = json.loads(source_path.read_text(encoding="utf-8"))
        weeks = (raw.get("data") or {}).get("ds_tuan_tkb") or []
        result = []
        for w in weeks:
            result.append(
                {
                    "week": int(w.get("tuan_hoc_ky") or 1),
                    "info": str(w.get("thong_tin_tuan") or ""),
                    "start_date": str(w.get("ngay_bat_dau") or ""),
                    "end_date": str(w.get("ngay_ket_thuc") or ""),
                    "lesson_count": len(w.get("ds_thoi_khoa_bieu") or []),
                }
            )
        return result
    except Exception:
        return []


def fetch_qldt_schedule(
    force_refresh: bool = True,
    username: Optional[str] = None,
    password: Optional[str] = None,
    hoc_ky: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], str, str]:
    """
    Tool 1 (`fetch_qldt_schedule`):
    - Saves user credentials if provided (1-time setup).
    - Attempts real QLĐT API scrape if `force_refresh` is True and credentials exist.
    - Falls back to `tkb_ptit.json` / `qldt_fallback_response.json` if QLĐT API fails or credentials are not configured.
    - Preserves any custom/makeup lessons injected for demo/conflict testing if using fallback cache.
    Returns `(lessons, source, last_updated_hhmm)`.
    """
    settings = load_settings()
    if username is not None and username.strip():
        settings["qldt_username"] = username.strip()
    if password is not None and password.strip():
        settings["qldt_password"] = password.strip()
    if hoc_ky is not None:
        settings["hoc_ky"] = int(hoc_ky)

    eff_user = settings.get("qldt_username", "").strip()
    eff_pass = settings.get("qldt_password", "").strip()
    eff_hoc_ky = int(settings.get("hoc_ky") or DEFAULT_HOC_KY)
    now_hhmm = datetime.now().strftime("%H:%M")

    # 1. Try Live QLĐT API if force_refresh and credentials are provided
    if force_refresh and eff_user and eff_pass:
        try:
            token = login_qldt(eff_user, eff_pass, timeout=10)
            raw_data = fetch_schedule_qldt(token, hoc_ky=eff_hoc_ky, timeout=10)
            TKB_PTIT_FILE.write_text(
                json.dumps(raw_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            QLDT_FALLBACK_FILE.write_text(
                json.dumps(raw_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            lessons = parse_qldt_payload_to_lessons(raw_data)
            save_lessons(lessons)
            save_settings(
                {
                    "qldt_username": eff_user,
                    "qldt_password": eff_pass,
                    "hoc_ky": eff_hoc_ky,
                    "last_sync_at": datetime.now().isoformat(),
                    "last_sync_source": "live_api",
                }
            )
            return lessons, "live_api", now_hhmm
        except Exception:
            # Graceful fallback to cached tkb_ptit.json / lessons.json
            pass

    # 2. Fallback to existing lessons.json (if already populated) or parse from tkb_ptit.json
    existing_lessons = load_lessons()
    if existing_lessons:
        save_settings(
            {
                "qldt_username": eff_user,
                "qldt_password": eff_pass,
                "hoc_ky": eff_hoc_ky,
                "last_sync_at": datetime.now().isoformat(),
                "last_sync_source": "fallback_cache",
            }
        )
        return existing_lessons, "fallback_cache", now_hhmm

    fallback_file = TKB_PTIT_FILE if TKB_PTIT_FILE.exists() else QLDT_FALLBACK_FILE
    if fallback_file.exists():
        raw_fallback = json.loads(fallback_file.read_text(encoding="utf-8"))
        lessons = parse_qldt_payload_to_lessons(raw_fallback)
        save_lessons(lessons)
        save_settings(
            {
                "qldt_username": eff_user,
                "qldt_password": eff_pass,
                "hoc_ky": eff_hoc_ky,
                "last_sync_at": datetime.now().isoformat(),
                "last_sync_source": "fallback_cache",
            }
        )
        return lessons, "fallback_cache", now_hhmm

    return [], "fallback_cache", now_hhmm


def check_and_run_sunday_auto_sync() -> Optional[Dict[str, Any]]:
    """
    Runs automatically in the background scheduler.
    If today is Sunday (weekday == 6) and `auto_sync_sunday` is True,
    scrapes QLĐT once for the day.
    """
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    settings = load_settings()
    if not settings.get("auto_sync_sunday", True):
        return None
    if now.weekday() == 6 and settings.get("last_sunday_sync_date") != today_str:
        lessons, source, updated_at = fetch_qldt_schedule(force_refresh=True)
        save_settings({"last_sunday_sync_date": today_str})
        return {
            "synced_date": today_str,
            "source": source,
            "updated_at": updated_at,
            "lesson_count": len(lessons),
        }
    return None

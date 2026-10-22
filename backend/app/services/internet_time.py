import email.utils
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Tuple
import requests

_CACHED_INTERNET_DATE: Optional[Tuple[date, float, str]] = None
CACHE_TTL_SECONDS = 300  # 5 minutes


def fetch_internet_date(timeout: float = 3.0) -> Tuple[date, str]:
    """
    Calls a public internet time API to fetch the current live date in Vietnam (UTC+7).
    Fallback hierarchy:
      1. https://timeapi.io/api/time/current/zone?timeZone=Asia/Ho_Chi_Minh
      2. HTTP Date header from https://www.google.com (adjusted to UTC+7)
      3. System local datetime (datetime.now().date())
    """
    global _CACHED_INTERNET_DATE
    import time
    now_ts = time.time()
    if _CACHED_INTERNET_DATE and (now_ts - _CACHED_INTERNET_DATE[1] < CACHE_TTL_SECONDS):
        return _CACHED_INTERNET_DATE[0], _CACHED_INTERNET_DATE[2]

    # 1. Primary: timeapi.io
    try:
        resp = requests.get(
            "https://timeapi.io/api/time/current/zone?timeZone=Asia/Ho_Chi_Minh",
            timeout=timeout,
        )
        if resp.status_code == 200:
            data = resp.json()
            y, m, d = int(data["year"]), int(data["month"]), int(data["day"])
            res_date = date(y, m, d)
            _CACHED_INTERNET_DATE = (res_date, now_ts, "timeapi.io (Live Internet)")
            return res_date, "timeapi.io (Live Internet)"
    except Exception:
        pass

    # 2. Secondary: Google HTTP Date Header (+7h for VN)
    try:
        head_resp = requests.head("https://www.google.com", timeout=timeout)
        date_hdr = head_resp.headers.get("Date")
        if date_hdr:
            parsed_dt = email.utils.parsedate_to_datetime(date_hdr)
            # convert to UTC+7
            vn_dt = parsed_dt.astimezone(timezone(timedelta(hours=7)))
            res_date = vn_dt.date()
            _CACHED_INTERNET_DATE = (res_date, now_ts, "google.com Date Header (Live Internet)")
            return res_date, "google.com Date Header (Live Internet)"
    except Exception:
        pass

    # 3. Fallback: local system date
    res_date = datetime.now().date()
    _CACHED_INTERNET_DATE = (res_date, now_ts, "system_clock")
    return res_date, "system_clock"


if __name__ == "__main__":
    d, src = fetch_internet_date()
    print(f"Fetched Internet Date: {d.isoformat()} from {src}")

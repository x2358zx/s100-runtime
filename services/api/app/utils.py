import hashlib
from datetime import datetime
from dateutil import parser as dtparser, tz

TPE = tz.gettz("Asia/Taipei")

def parse_time(s: str):
    s = (s or "").strip()
    if not s:
        return None
    s2 = s.replace('/', '-')  # 2025/9/12-9:57 -> 2025-9-12-9:57
    try:
        # 若像 YYYY-MM-DD-HH:MM(:SS)? 就從「最後一個 -」切成 日期 與 時間
        if ' ' not in s2 and ':' in s2 and s2.count('-') >= 3:
            date_part, time_part = s2.rsplit('-', 1)  # ← 這裡用 rsplit
            if time_part.count(':') == 1:
                time_part += ":00"
            s_fmt = f"{date_part} {time_part}"
        else:
            s_fmt = s2
        dt = dtparser.parse(s_fmt, yearfirst=True, dayfirst=False)
        # 一律視為台北時間，最後回傳「去掉 tzinfo 的本地時間」
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TPE)
        dt = dt.astimezone(TPE).replace(tzinfo=None)
        return dt
    except Exception:
        return None

def sha1(s: str) -> str:
    return hashlib.sha1(s.encode('utf-8', errors='ignore')).hexdigest()

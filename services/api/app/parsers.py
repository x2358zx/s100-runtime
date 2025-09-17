import re
from typing import Dict, Any, Tuple, Optional, List

def parse_keyvals(line: str) -> Dict[str,str]:
    parts = [p.strip() for p in line.strip().split(',') if p.strip()]
    kv = {}
    for p in parts:
        if '=' in p:
            k,v = p.split('=',1)
            kv[k.strip()] = v.strip()
    return kv

def split_project(project_raw: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    if not project_raw or '_' not in project_raw:
        return project_raw, None
    a,b = project_raw.split('_',1)
    return a, b

_site_re = re.compile(r'^s(\d+)$', re.IGNORECASE)
_eng_prefix_re = re.compile(r'^ENG(?:-([A-Za-z0-9]+))?-', re.IGNORECASE)

def parse_logname(logname_raw: Optional[str]) -> Dict[str, Optional[str]]:
    # returns dict of sample_no, voltage, test_item, temp, category, accessory, site, eng_flag, eng_tag
    out = {
        "sample_no": None, "voltage": None, "test_item": None, "temp": None,
        "category": None, "accessory": None, "site": None,
        "eng_flag": 0, "eng_tag": None
    }
    if not logname_raw:
        return out
    s = logname_raw.strip()

    # Detect ENG prefix
    m = _eng_prefix_re.match(s)
    if m:
        out["eng_flag"] = 1
        out["eng_tag"] = (m.group(1) or "").strip() or None
        s = s[m.end():]  # remove prefix

    toks = [t for t in s.split('_') if t]
    if not toks:
        return out

    # Site is typically the last token like s1~s4
    if toks and _site_re.match(toks[-1]):
        out["site"] = toks[-1]
        toks = toks[:-1]

    # Assign by position when available (best-effort)
    # expected: sample, voltage, test_item, temp, category, accessory
    fields = ["sample_no", "voltage", "test_item", "temp", "category", "accessory"]
    for i, name in enumerate(fields):
        out[name] = toks[i] if i < len(toks) else None

    # Normalize weird temps (e.g., '-40C', '25C', '3P41V' belongs to voltage/test_item; we do not enforce here)
    return out

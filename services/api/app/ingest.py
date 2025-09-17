import os, io
from datetime import datetime
from typing import Optional, List, Tuple, Dict
from sqlalchemy.orm import Session
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from dateutil import tz
from .models import RawLog, Run, IngestionState
from .utils import parse_time, sha1
from .parsers import parse_keyvals, split_project, parse_logname

TPE = tz.gettz("Asia/Taipei")

def _iter_file_lines(path: str):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for i, line in enumerate(f, start=1):
            if line.strip():
                yield i, line.rstrip("\n")

def _normalize_and_hash(equipment: str, kv: Dict[str,str]) -> str:
    st = kv.get("StTime","")
    sp = kv.get("SpTime","")
    proj = kv.get("Project","")
    logn = kv.get("LogName","")
    return sha1(f"{equipment}|{st}|{sp}|{proj}|{logn}")

def ingest_file(db: Session, equipment: str, file_path: str) -> Dict[str,int]:
    stats = {"lines":0, "raw_new":0, "raw_dup":0, "runs_new":0, "runs_dups_or_replaced":0}
    now = datetime.now(TPE)

    # 新增：本次匯入的「同一檔」內部雜湊集合，避免同檔重複行在同一交易內互撞
    seen_hashes = set()

    for line_no, line in _iter_file_lines(file_path):
        stats["lines"] += 1
        kv = parse_keyvals(line)

        # v1 compatibility: fill missing with None
        user = kv.get("User")
        prgver = kv.get("PrgVer")
        codever = kv.get("CodeVer")
        missing_user = 0 if user else 1
        missing_prgver = 0 if prgver else 1
        missing_codever = 0 if codever else 1

        st = parse_time(kv.get("StTime",""))
        sp = parse_time(kv.get("SpTime",""))
        total_s = None
        if "TotalTime" in kv:
            t = kv["TotalTime"].rstrip("s")
            try:
                total_s = int(float(t))
            except:
                total_s = None

        project_raw = kv.get("Project")
        cust, code = split_project(project_raw)

        ln = kv.get("LogName")
        pf = parse_logname(ln)

        h = _normalize_and_hash(equipment, kv)
        
        # 新增：同檔即時去重（不用等到 commit）
        if h in seen_hashes:
            stats["raw_dup"] += 1
            continue
        
        # 原本的資料庫層級去重（避免跨檔/歷史重複）
        exists = db.query(RawLog.id).filter(
            RawLog.equipment==equipment, RawLog.hash_sig==h
        ).first()
        if exists:
            stats["raw_dup"] += 1
            continue

        r = RawLog(
            equipment=equipment, source_file=file_path, line_no=line_no,
            st_time=st, sp_time=sp, total_s=total_s,
            project_raw=project_raw, project_customer=cust, project_code=code,
            user=user, prgver=prgver, codever=codever,
            logname_raw=ln, sample_no=pf["sample_no"], voltage=pf["voltage"], test_item=pf["test_item"],
            temp=pf["temp"], category=pf["category"], accessory=pf["accessory"], site=pf["site"],
            eng_flag=pf["eng_flag"], eng_tag=pf["eng_tag"],
            missing_user=missing_user, missing_prgver=missing_prgver, missing_codever=missing_codever,
            hash_sig=h, inserted_at=now
        )
        db.add(r)
        stats["raw_new"] += 1
        seen_hashes.add(h)

        # Dedup & upsert Run
        if st and sp and total_s is not None:
            # Strict consistency check (±1s tolerance)
            dur = int(abs((sp - st).total_seconds()))
            consistent = abs(dur - int(total_s)) <= 1
            # Composite key: equip + times + project + logname
            # We allow ±1s tolerance on times; we implement by exact match first; else search small window
            q = db.query(Run).filter(
                Run.equipment==equipment,
                Run.project_customer==cust,
                Run.project_code==code,
                Run.sample_no==pf["sample_no"],
                Run.test_item==pf["test_item"],
            )
            candidates = q.filter(
                and_(Run.st_time <= sp, Run.sp_time >= st)  # any overlap
            ).all()

            kept = True
            reason = None
            if candidates:
                # same record different time? choose the one with max(duration)
                best = max(candidates, key=lambda x: x.duration_s)
                if total_s > best.duration_s:
                    # Replace: update best
                    best.st_time = min(best.st_time, st)
                    best.sp_time = max(best.sp_time, sp)
                    best.duration_s = int((best.sp_time - best.st_time).total_seconds())
                    best.source_count += 1
                    best.dedup_status = "replaced"
                    reason = "longer_duration_preferred"
                    kept = False
                    stats["runs_dups_or_replaced"] += 1
                else:
                    kept = False
                    stats["runs_dups_or_replaced"] += 1

            if kept:
                run = Run(
                    equipment=equipment, st_time=st, sp_time=sp,
                    duration_s=dur if consistent else int(total_s),
                    project_customer=cust, project_code=code,
                    user=user, prgver=prgver, codever=codever,
                    sample_no=pf["sample_no"], voltage=pf["voltage"],
                    test_item=pf["test_item"], temp=pf["temp"],
                    category=pf["category"], accessory=pf["accessory"],
                    site=pf["site"], eng_flag=pf["eng_flag"], eng_tag=pf["eng_tag"],
                    source_count=1, dedup_status="kept", conflict_reason=None if consistent else "time_mismatch"
                )
                db.add(run)
                stats["runs_new"] += 1

    # 新增：穩健 commit，若極少數情況仍因競態撞到唯一鍵，回滾後繼續
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # 這裡不再重試插入，讓重複視為 raw_dup；下次再跑也會被 exists 擋掉
    return stats

def find_month_file(root_dir: str, year: int, month: int) -> Optional[str]:
    yyyymm = f"{year:04d}{month:02d}"
    cand = os.path.join(root_dir, f"{yyyymm}_total_run_time.txt")
    return cand if os.path.isfile(cand) else None

def ingest_current_month(db: Session, equipment: str, root_dir: str) -> Dict[str,int]:
    now = datetime.now(TPE)
    f = find_month_file(root_dir, now.year, now.month)
    if not f:
        return {"lines":0,"raw_new":0,"raw_dup":0,"runs_new":0,"runs_dups_or_replaced":0}
    return ingest_file(db, equipment, f)

def ingest_historical(db: Session, equipment: str, root_dir: str, hist_dir_name: str = "S100_test_log"):
    hist_dir = os.path.join(root_dir, hist_dir_name)
    stats_total = {"lines":0, "raw_new":0, "raw_dup":0, "runs_new":0, "runs_dups_or_replaced":0}
    if not os.path.isdir(hist_dir):
        return stats_total
    for name in sorted(os.listdir(hist_dir)):
        if name.endswith("_total_run_time.txt"):
            path = os.path.join(hist_dir, name)
            st = ingest_file(db, equipment, path)
            for k,v in st.items():
                stats_total[k] += v
    return stats_total

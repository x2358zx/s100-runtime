from datetime import datetime, timedelta
from typing import List, Tuple
from .models import Run, DailyMetrics
from sqlalchemy.orm import Session

def merge_intervals(intervals: List[Tuple[datetime, datetime]]) -> List[Tuple[datetime, datetime]]:
    if not intervals:
        return []
    intervals = sorted(intervals, key=lambda x: x[0])
    merged = [intervals[0]]
    for cur in intervals[1:]:
        last = merged[-1]
        if cur[0] <= last[1]:
            merged[-1] = (last[0], max(last[1], cur[1]))
        else:
            merged.append(cur)
    return merged

def compute_daily_metrics(db: Session, day: datetime, equipment: str):
    # Day boundaries in local tz (assume already localized at 00:00)
    start = day
    end = day + timedelta(days=1)

    runs = (
        db.query(Run)
          .filter(Run.equipment == equipment, Run.st_time < end, Run.sp_time > start)
          .all()
    )
    # Clip to day window
    intervals = []
    for r in runs:
        a = max(r.st_time, start)
        b = min(r.sp_time, end)
        if a < b:
            intervals.append((a,b))

    merged = merge_intervals(intervals)
    busy_s = sum(int((b-a).total_seconds()) for a,b in merged)
    util = (busy_s / 86400.0) * 100.0
    dm = DailyMetrics(
        equipment=equipment, day=start, busy_time_s=busy_s,
        utilization_24h_pct=util, records_count=len(runs)
    )
    # Upsert-like: delete existing for (equipment, day) then add
    db.query(DailyMetrics).filter(DailyMetrics.equipment==equipment, DailyMetrics.day==start).delete()
    db.add(dm)
    db.commit()
    return dm

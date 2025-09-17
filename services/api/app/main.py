from fastapi import FastAPI, Depends, Query, Header, Response
from sqlalchemy.orm import Session
from sqlalchemy import text as sqltext
from datetime import datetime, timedelta
import pandas as pd
import os
from .db import engine, SessionLocal, Base
from .config import settings
from .models import RawLog, Run, DailyMetrics
from .schemas import IngestStats
from .ingest import ingest_current_month, ingest_historical
from .metrics import compute_daily_metrics
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dateutil import tz

app = FastAPI(title="S100 Log Analytics API", version="1.0.0")
TPE = tz.gettz(settings.TZ)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def auth_ok(x_token: str | None) -> bool:
    if not settings.API_TOKEN:
        return True
    return x_token == settings.API_TOKEN

@app.on_event("startup")
def startup():
    # create tables
    Base.metadata.create_all(bind=engine)
    # schedule nightly job 23:00 TPE
    sched = BackgroundScheduler(timezone=settings.TZ)
    def nightly():
        with SessionLocal() as db:
            for equip, root in [("s100-1", settings.LOG_ROOT_S100_1), ("s100-2", settings.LOG_ROOT_S100_2)]:
                ingest_current_month(db, equip, root)
            # 昨天 00:00（naive, local）
            y = datetime.now(TPE).replace(hour=0, minute=0, second=0, microsecond=0).replace(tzinfo=None) - timedelta(days=1)
            for equip in ["s100-1","s100-2"]:
                compute_daily_metrics(db, y, equip)

    sched.add_job(nightly, CronTrigger(hour=23, minute=0))
    sched.start()
    app.state.scheduler = sched

@app.on_event("shutdown")
def shutdown():
    sched = getattr(app.state, "scheduler", None)
    if sched:
        sched.shutdown(wait=False)

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/ingest/current", response_model=IngestStats)
def ingest_current(x_token: str | None = Header(None), db: Session = Depends(get_db)):
    if not auth_ok(x_token):
        return Response(status_code=401)
    s1 = ingest_current_month(db, "s100-1", settings.LOG_ROOT_S100_1)
    s2 = ingest_current_month(db, "s100-2", settings.LOG_ROOT_S100_2)
    # compute today metrics so far
    today = datetime.now(TPE).replace(hour=0, minute=0, second=0, microsecond=0).replace(tzinfo=None)
    for equip in ["s100-1","s100-2"]:
        compute_daily_metrics(db, today, equip)

    # merge stats
    out = {k: s1.get(k,0)+s2.get(k,0) for k in s1}
    return out

@app.post("/ingest/historical", response_model=IngestStats)
def ingest_hist(x_token: str | None = Header(None), db: Session = Depends(get_db)):
    if not auth_ok(x_token):
        return Response(status_code=401)
    s1 = ingest_historical(db, "s100-1", settings.LOG_ROOT_S100_1, settings.HIST_DIR_NAME)
    s2 = ingest_historical(db, "s100-2", settings.LOG_ROOT_S100_2, settings.HIST_DIR_NAME)
    out = {k: s1.get(k,0)+s2.get(k,0) for k in s1}
    return out

@app.get("/metrics/daily")
def metrics_daily(equipment: str = Query("s100-1"), start: str = Query(None), end: str = Query(None), db: Session = Depends(get_db)):
    q = db.query(DailyMetrics).filter(DailyMetrics.equipment==equipment)
    if start:
        q = q.filter(DailyMetrics.day >= start)
    if end:
        q = q.filter(DailyMetrics.day < end)
    rows = q.order_by(DailyMetrics.day.asc()).all()
    return [{
        "day": r.day.isoformat(),
        "busy_time_s": r.busy_time_s,
        "utilization_24h_pct": r.utilization_24h_pct,
        "records_count": r.records_count
    } for r in rows]

@app.get("/reports/records.csv")
def export_records_csv(equipment: str = Query(None), start: str = Query(None), end: str = Query(None), db: Session = Depends(get_db)):
    q = db.query(Run)
    if equipment:
        q = q.filter(Run.equipment==equipment)
    if start:
        q = q.filter(Run.st_time >= start)
    if end:
        q = q.filter(Run.sp_time < end)
    runs = q.all()
    df = pd.DataFrame([{
        "equipment": r.equipment,
        "st_time": r.st_time,
        "sp_time": r.sp_time,
        "duration_s": r.duration_s,
        "customer": r.project_customer,
        "project_code": r.project_code,
        "user": r.user, "prgver": r.prgver, "codever": r.codever,
        "sample_no": r.sample_no, "voltage": r.voltage, "test_item": r.test_item,
        "temp": r.temp, "category": r.category, "accessory": r.accessory, "site": r.site,
        "eng_flag": r.eng_flag, "eng_tag": r.eng_tag
    } for r in runs])
    path = "/exports/records.csv"
    df.to_csv(path, index=False)
    return Response(open(path, "rb").read(), media_type="text/csv", headers={
        "Content-Disposition": "attachment; filename=records.csv"
    })

@app.get("/reports/records.xlsx")
def export_records_xlsx(equipment: str = Query(None), start: str = Query(None), end: str = Query(None), db: Session = Depends(get_db)):
    q = db.query(Run)
    if equipment:
        q = q.filter(Run.equipment==equipment)
    if start:
        q = q.filter(Run.st_time >= start)
    if end:
        q = q.filter(Run.sp_time < end)
    runs = q.all()
    df = pd.DataFrame([{
        "equipment": r.equipment,
        "st_time": r.st_time,
        "sp_time": r.sp_time,
        "duration_s": r.duration_s,
        "customer": r.project_customer,
        "project_code": r.project_code,
        "user": r.user, "prgver": r.prgver, "codever": r.codever,
        "sample_no": r.sample_no, "voltage": r.voltage, "test_item": r.test_item,
        "temp": r.temp, "category": r.category, "accessory": r.accessory, "site": r.site,
        "eng_flag": r.eng_flag, "eng_tag": r.eng_tag
    } for r in runs])
    path = "/exports/records.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="records")
    return Response(open(path, "rb").read(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={
        "Content-Disposition": "attachment; filename=records.xlsx"
    })

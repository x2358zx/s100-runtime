from sqlalchemy import Column, Integer, String, BigInteger, DateTime, Boolean, UniqueConstraint, Index, Float
from sqlalchemy.dialects.mysql import TINYINT
from .db import Base

class RawLog(Base):
    __tablename__ = "raw_logs"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    equipment = Column(String(32), nullable=False)
    source_file = Column(String(512), nullable=False)
    line_no = Column(Integer, nullable=False)
    st_time = Column(DateTime, nullable=True)
    sp_time = Column(DateTime, nullable=True)
    total_s = Column(Integer, nullable=True)

    project_raw = Column(String(255), nullable=True)
    project_customer = Column(String(128), nullable=True)
    project_code = Column(String(128), nullable=True)

    user = Column(String(64), nullable=True)
    prgver = Column(String(64), nullable=True)
    codever = Column(String(64), nullable=True)

    logname_raw = Column(String(512), nullable=True)
    sample_no = Column(String(64), nullable=True)
    voltage = Column(String(64), nullable=True)
    test_item = Column(String(64), nullable=True)
    temp = Column(String(64), nullable=True)
    category = Column(String(64), nullable=True)
    accessory = Column(String(64), nullable=True)
    site = Column(String(16), nullable=True)

    eng_flag = Column(TINYINT, default=0)
    eng_tag = Column(String(64), nullable=True)

    missing_user = Column(TINYINT, default=0)
    missing_prgver = Column(TINYINT, default=0)
    missing_codever = Column(TINYINT, default=0)

    hash_sig = Column(String(64), nullable=False)  # sha1
    inserted_at = Column(DateTime, nullable=False)
    __table_args__ = (
        UniqueConstraint("equipment","hash_sig", name="uq_equipment_hash"),
        Index("idx_time_equipment", "equipment", "st_time", "sp_time"),
    )

class Run(Base):
    __tablename__ = "runs"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    equipment = Column(String(32), nullable=False)
    st_time = Column(DateTime, nullable=False)
    sp_time = Column(DateTime, nullable=False)
    duration_s = Column(Integer, nullable=False)
    project_customer = Column(String(128), nullable=True)
    project_code = Column(String(128), nullable=True)
    user = Column(String(64), nullable=True)
    prgver = Column(String(64), nullable=True)
    codever = Column(String(64), nullable=True)
    sample_no = Column(String(64), nullable=True)
    voltage = Column(String(64), nullable=True)
    test_item = Column(String(64), nullable=True)
    temp = Column(String(64), nullable=True)
    category = Column(String(64), nullable=True)
    accessory = Column(String(64), nullable=True)
    site = Column(String(16), nullable=True)
    eng_flag = Column(TINYINT, default=0)
    eng_tag = Column(String(64), nullable=True)
    source_count = Column(Integer, default=1)
    dedup_status = Column(String(32), default="kept")  # kept | replaced | dropped
    conflict_reason = Column(String(255), nullable=True)
    __table_args__ = (
        Index("idx_runs_time_equipment", "equipment", "st_time", "sp_time"),
    )

class IngestionState(Base):
    __tablename__ = "ingestion_state"
    id = Column(Integer, primary_key=True, autoincrement=True)
    equipment = Column(String(32), nullable=False)
    source_file = Column(String(512), nullable=False)
    last_ingested_at = Column(DateTime, nullable=False)
    note = Column(String(255), nullable=True)
    __table_args__ = (
        UniqueConstraint("equipment","source_file", name="uq_ingest_file"),
    )

class DailyMetrics(Base):
    __tablename__ = "metrics_daily"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    equipment = Column(String(32), nullable=False)
    day = Column(DateTime, nullable=False)  # date at 00:00
    busy_time_s = Column(Integer, nullable=False)
    utilization_24h_pct = Column(Float, nullable=False)
    records_count = Column(Integer, nullable=False)
    __table_args__ = (
        UniqueConstraint("equipment","day", name="uq_daily_equipment_day"),
        Index("idx_metrics_day_equipment", "equipment", "day"),
    )

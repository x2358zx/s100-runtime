import os
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text as sqltext
from datetime import datetime, timedelta
import plotly.express as px

st.set_page_config(page_title="S100 稼動率儀表板", layout="wide")

DB_HOST = os.getenv("DB_HOST","localhost")
DB_PORT = int(os.getenv("DB_PORT","3306"))
DB_NAME = os.getenv("DB_NAME","s100logs")
DB_USER = os.getenv("DB_USER","app")
DB_PASS = os.getenv("DB_PASS","app123")

engine = create_engine(f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4")

st.sidebar.header("篩選條件")
st.sidebar.markdown("---")
st.sidebar.header("管理動作")
api_host = os.getenv("API_HOST", "api")  # Docker 內可用服務名稱
api_port = int(os.getenv("API_PORT", "8000"))
if st.sidebar.button("匯入當月最新資料"):
    import requests
    try:
        r = requests.post(f"http://{api_host}:{api_port}/ingest/current", timeout=300)
        st.sidebar.success(f"已觸發：{r.status_code} {r.text[:200]}")
    except Exception as e:
        st.sidebar.error(f"觸發失敗：{e}")
if st.sidebar.button("一鍵跑完所有歷史資料"):
    import requests
    try:
        r = requests.post(f"http://{api_host}:{api_port}/ingest/historical", timeout=1800)
        st.sidebar.success(f"已觸發：{r.status_code} {r.text[:200]}")
    except Exception as e:
        st.sidebar.error(f"觸發失敗：{e}")

equipment = st.sidebar.selectbox("設備", ["s100-1","s100-2","(全部)"], index=0)
today = datetime.now().date()
start_date = st.sidebar.date_input("起始日", today.replace(day=1))
end_date = st.sidebar.date_input("結束日", today)

def load_records():
    q = "SELECT * FROM runs WHERE 1=1"
    params = {}
    if equipment in ("s100-1","s100-2"):
        q += " AND equipment=:eq"
        params["eq"] = equipment
    q += " AND st_time>=:st AND sp_time<:ed"
    params["st"] = f"{start_date} 00:00:00"
    params["ed"] = f"{end_date} 23:59:59"
    return pd.read_sql(sqltext(q), engine, params=params)

def load_daily():
    q = "SELECT * FROM metrics_daily WHERE day>=:st AND day<:ed"
    params = {"st": f"{start_date} 00:00:00", "ed": f"{end_date} 23:59:59"}
    if equipment in ("s100-1","s100-2"):
        q += " AND equipment=:eq"
        params["eq"] = equipment
    return pd.read_sql(sqltext(q), engine, params=params)

st.title("S100 稼動率儀表板")

tabs = st.tabs(["總覽", "專案/樣品分析", "ENG vs 正式", "資料品質"])

with tabs[0]:
    dm = load_daily()
    if dm.empty:
        st.info("沒有資料，請先觸發一次匯入或等候每日 23:00 排程。")
    else:
        fig = px.line(dm.sort_values("day"), x="day", y="utilization_24h_pct", color="equipment", markers=True)
        st.plotly_chart(fig, use_container_width=True)
        st.metric("平均稼動率(%)", f"{dm['utilization_24h_pct'].mean():.2f}")
        st.metric("總忙碌時間(小時)", f"{dm['busy_time_s'].sum()/3600:.1f}")

with tabs[1]:
    df = load_records()
    if df.empty:
        st.info("無資料")
    else:
        # --- 相容處理：若是從 API 匯出的 CSV 讀入時欄位叫 'customer'，改名成 project_customer ---
        if "project_customer" not in df.columns and "customer" in df.columns:
            df = df.rename(columns={"customer": "project_customer"})

        # --- 這裡用 runs 表的正式欄位名稱 project_customer / project_code ---
        grp_cols = ["equipment", "project_customer", "project_code"]
        by_proj = df.groupby(grp_cols, dropna=False)["duration_s"].sum().reset_index()
        by_proj["duration_hr"] = by_proj["duration_s"] / 3600.0

        st.subheader("各專案測試時數")
        st.dataframe(by_proj.sort_values("duration_s", ascending=False))

        fig2 = px.bar(by_proj, x="project_code", y="duration_hr", color="equipment")
        st.plotly_chart(fig2, use_container_width=True)

        st.download_button(
            "下載目前篩選的記錄 (CSV)",
            df.to_csv(index=False).encode("utf-8"),
            "records_filtered.csv",
            "text/csv",
        )

with tabs[2]:
    df = load_records()
    if df.empty:
        st.info("無資料")
    else:
        df["type"] = df["eng_flag"].apply(lambda x: "ENG" if x==1 else "正式")
        by_type = df.groupby(["equipment","type"])["duration_s"].sum().reset_index()
        by_type["hr"] = by_type["duration_s"]/3600.0
        st.subheader("ENG vs 正式 測試時數")
        st.dataframe(by_type)
        fig3 = px.bar(by_type, x="type", y="hr", color="equipment", barmode="group")
        st.plotly_chart(fig3, use_container_width=True)

with tabs[3]:
    df = load_records()
    if df.empty:
        st.info("無資料")
    else:
        # 相容：有時從 CSV 讀可能是 'customer'，統一改名
        if "project_customer" not in df.columns and "customer" in df.columns:
            df = df.rename(columns={"customer": "project_customer"})

        # ---- 缺漏統計（不要對 Series 做 int(...)）----
        missing_user = df["user"].fillna("").eq("").sum() if "user" in df.columns else 0
        missing_prgver = df["prgver"].fillna("").eq("").sum() if "prgver" in df.columns else 0
        missing_codever = df["codever"].fillna("").eq("").sum() if "codever" in df.columns else 0

        missing = pd.DataFrame({
            "missing_user(筆)":   [missing_user],
            "missing_prgver(筆)": [missing_prgver],
            "missing_codever(筆)":[missing_codever],
        })
        st.write("欄位缺漏統計")
        st.dataframe(missing)

        # ---- 其他品質指標（可選）----
        zero_dur = df["duration_s"].fillna(0).eq(0).sum() if "duration_s" in df.columns else 0
        mismatch = df["conflict_reason"].fillna("").eq("time_mismatch").sum() if "conflict_reason" in df.columns else 0
        st.write(f"0 秒筆數：{zero_dur}，時間不一致筆數：{mismatch}")

        st.write("原始記錄（前 300 筆，按起始時間排序）")
        cols_for_view = sorted(df.columns)  # 方便檢查有哪些欄位
        st.dataframe(df.sort_values("st_time").head(300)[cols_for_view])


st.caption("※ 稼動率=每日合併後的忙碌時段總長 / 24h。若同時間多筆重疊只計一次，避免因ENG重複記錄而膨脹。")

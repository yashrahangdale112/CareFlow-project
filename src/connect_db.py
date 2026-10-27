"""
CareFlow - database connector.
Change the CONFIG block (or set the env vars) and the same file talks to
MySQL 8, PostgreSQL 13+ or a local SQLite file.

    python src/connect_db.py                 # sqlite demo (no server needed)
    python src/connect_db.py --engine mysql  # needs a running MySQL
"""
from __future__ import annotations
import argparse, os, sqlite3, sys
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]

CONFIG = {
    # ---------- MySQL ----------
    "mysql":    "mysql+pymysql://careflow:careflow@localhost:3306/careflow?charset=utf8mb4",
    # ---------- PostgreSQL ----------
    "postgres": "postgresql+psycopg2://postgres:postgres@localhost:5432/careflow",
    # ---------- SQLite (used for the offline demo) ----------
    "sqlite":   f"sqlite:///{ROOT/'careflow_demo.sqlite'}",
}

def get_engine(which: str = "sqlite"):
    url = os.getenv("CAREFLOW_DB_URL", CONFIG[which])
    eng = create_engine(url, future=True)
    print(f"[connect_db] engine = {which}")
    return eng

def build_sqlite(eng) -> None:
    """Create the star schema in SQLite and load the CSVs (offline demo)."""
    ev = pd.read_csv(ROOT / "data/raw/event_log.csv")
    ca = pd.read_csv(ROOT / "data/raw/case_attributes.csv")
    with eng.begin() as c:
        c.execute(text("DROP TABLE IF EXISTS fact_event"))
        c.execute(text("DROP TABLE IF EXISTS fact_case"))
        c.execute(text("""CREATE TABLE fact_case(case_id TEXT PRIMARY KEY, patient_id TEXT,
            triage_level INT, admission_type TEXT, pathway TEXT, los_hours REAL,
            total_cost_inr REAL, n_events INT, is_long_stay INT)"""))
        c.execute(text("""CREATE TABLE fact_event(event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id TEXT, event_index INT, activity TEXT, event_timestamp TEXT, resource TEXT,
            department TEXT, wait_minutes REAL, service_minutes REAL, cost_inr REAL, is_rework INT)"""))
    ca2 = ca.assign(is_long_stay=(ca["los_hours"] > 24).astype(int))
    case_cols = ["case_id","patient_id","triage_level","admission_type","pathway",
                 "los_hours","total_cost_inr","n_events","is_long_stay"]
    ca2[case_cols].to_sql("fact_case", eng, if_exists="append", index=False)
    ev = ev.assign(event_index=ev.groupby("case_id").cumcount(),
                   is_rework=(ev.groupby("case_id")["activity"].shift(1)==ev["activity"]).astype(int))
    event_cols = ["case_id","event_index","activity","timestamp","resource","department",
                  "wait_minutes","service_minutes","cost_inr","is_rework"]
    ev[event_cols].rename(columns={"timestamp":"event_timestamp"}).to_sql(
        "fact_event", eng, if_exists="append", index=False)
    print(f"[connect_db] loaded {len(ca2):,} cases / {len(ev):,} events")

KPI = {
 "Q1_overall_KPI": """SELECT COUNT(*) cases, SUM(is_long_stay) long_stay,
        ROUND(AVG(los_hours),2) avg_los_h, ROUND(SUM(total_cost_inr),0) total_cost_inr FROM fact_case""",
 "Q2_bottlenecks": """SELECT activity, COUNT(*) occurrences, ROUND(AVG(wait_minutes),1) avg_wait_min,
        ROUND(AVG(service_minutes),1) avg_service_min FROM fact_event
        GROUP BY activity ORDER BY avg_wait_min DESC""",
 "Q3_department_cost": """SELECT department, COUNT(*) events, ROUND(SUM(cost_inr),0) total_cost_inr
        FROM fact_event GROUP BY department ORDER BY total_cost_inr DESC""",
 "Q4_dfg_edges": """SELECT activity source_activity, next_activity, COUNT(*) edge_count FROM
        (SELECT case_id, event_index, activity, LEAD(activity) OVER
          (PARTITION BY case_id ORDER BY event_index) next_activity FROM fact_event)
        WHERE next_activity IS NOT NULL GROUP BY activity, next_activity
        HAVING COUNT(*) >= 3 ORDER BY edge_count DESC LIMIT 10""",
}

def run_kpis(eng) -> dict:
    out = {}
    for name, q in KPI.items():
        df = pd.read_sql(text(q), eng)
        out[name] = df
        print(f"\n--- {name} ---")
        print(df.head(10).to_string(index=False))
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="sqlite", choices=["sqlite", "mysql", "postgres", "auto"])
    a = ap.parse_args()
    eng = get_engine(a.engine)
    if a.engine in ("sqlite", "auto"):
        build_sqlite(eng)
    res = run_kpis(eng)
    outdir = ROOT / "outputs/reports"; outdir.mkdir(parents=True, exist_ok=True)
    for k, v in res.items():
        v.to_csv(outdir / f"sql_{k}.csv", index=False)
    print(f"\n[connect_db] KPI csv files -> {outdir}")

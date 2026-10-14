"""
CareFlow - STEP 2a  Data cleaning, with a before/after audit trail.
Run: python src/clean_data.py
"""
from pathlib import Path
import json, pandas as pd, numpy as np

ROOT = Path(__file__).resolve().parents[1]
raw  = pd.read_csv(ROOT / "data/raw/event_log.csv")
log, before = [], len(raw)

# 1. standard names
raw.columns = [c.strip().lower() for c in raw.columns]
log.append(f"normalise column names -> {list(raw.columns)}")

# 2. types
raw["timestamp"] = pd.to_datetime(raw["timestamp"], errors="coerce")
for c in ["wait_minutes", "service_minutes", "cost_inr"]:
    raw[c] = pd.to_numeric(raw[c], errors="coerce")
log.append("timestamp -> datetime, numeric columns cast")

# 3. drop rows with no case / activity / timestamp (can't be mined)
n = len(raw); raw = raw.dropna(subset=["case_id", "activity", "timestamp"])
log.append(f"drop rows missing case_id/activity/timestamp: {n-len(raw)}")

# 4. remove EXACT duplicate events (same case + activity + timestamp)
n = len(raw)
raw = raw.drop_duplicates(subset=["case_id", "activity", "timestamp"], keep="first")
log.append(f"remove duplicate events: {n-len(raw)}")

# 5. fill missing resource / department instead of losing the event
raw["resource"]   = raw["resource"].fillna("UNKNOWN").str.strip().str.upper()
raw["department"] = raw["department"].fillna("Unassigned").str.strip()
log.append("blank resource -> 'UNKNOWN', blank department -> 'Unassigned'")

# 6. negative / absurd values -> 0 or clip
raw.loc[raw["wait_minutes"] < 0, "wait_minutes"] = 0
raw.loc[raw["service_minutes"] <= 0, "service_minutes"] = np.nan
raw["service_minutes"] = raw["service_minutes"].fillna(raw["service_minutes"].median())
raw.loc[raw["cost_inr"] < 0, "cost_inr"] = 0
log.append("clamp negative waits/costs, impute non-positive service time with median")

# 7. sort -> event_index, gap, rework flag
raw = raw.sort_values(["case_id", "timestamp"]).reset_index(drop=True)
raw["event_index"]  = raw.groupby("case_id").cumcount()
raw["prev_ts"]      = raw.groupby("case_id")["timestamp"].shift(1)
raw["gap_minutes"]  = ((raw["timestamp"] - raw["prev_ts"]).dt.total_seconds() / 60).fillna(0)
raw["is_rework"]    = (raw.groupby("case_id")["activity"].shift(1) == raw["activity"]).astype(int)
log.append("derive event_index, gap_minutes, is_rework")

# 8. drop cases that are too short / too long to be meaningful
sizes = raw.groupby("case_id").size()
keep  = sizes[(sizes >= 3) & (sizes <= 200)].index
n = raw["case_id"].nunique(); raw = raw[raw["case_id"].isin(keep)]
log.append(f"drop cases with <3 or >200 events: {n - raw['case_id'].nunique()} cases")

out = ROOT / "data/processed/event_log_clean.csv"; out.parent.mkdir(parents=True, exist_ok=True)
raw.to_csv(out, index=False)
report = {"rows_before": before, "rows_after": int(len(raw)),
          "cases": int(raw["case_id"].nunique()), "activities": int(raw["activity"].nunique()),
          "duplicates_removed": int(before - len(raw)), "steps": log}
(ROOT / "outputs/reports/cleaning_audit.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2)[:1200])
print(f"\ncleaned log -> {out}")

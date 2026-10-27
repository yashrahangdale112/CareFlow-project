"""
CareFlow - Step 2: data import, cleaning and validation.

Reads the raw event log + case attributes, fixes data-quality problems,
engineers process-mining features (waiting time, throughput time, variant,
rework flag, shift) and writes one analysis-ready file.

Usage
-----
    python src/preprocess.py
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils import ensure_dirs, get_logger, load_config, path_of, save_json  # noqa: E402

LOG = get_logger("careflow.preprocess")


def load_raw(cfg: dict) -> tuple:
    df = pd.read_csv(path_of(cfg, "raw_events"))
    cases = pd.read_csv(path_of(cfg, "raw_cases"))
    return df, cases


def clean(df: pd.DataFrame, cases: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    p = cfg["preprocessing"]
    report = {"rows_in": int(len(df)), "cases_in": int(df["case_id"].nunique())}

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    bad_ts = int(df["timestamp"].isna().sum())
    df = df.dropna(subset=["timestamp", "case_id", "activity"])

    before = len(df)
    df = df.drop_duplicates(subset=["case_id", "activity", "timestamp"], keep="first")
    report["duplicates_removed"] = int(before - len(df))
    report["bad_timestamps_removed"] = bad_ts
    report["missing_resource_filled"] = int(df["resource"].isna().sum())
    df["resource"] = df["resource"].fillna("UNASSIGNED")

    for col in ("wait_minutes", "service_minutes", "cost_inr"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
            df.loc[df[col] < 0, col] = 0.0

    df = df.sort_values(["case_id", "timestamp", "activity"]).reset_index(drop=True)

    lengths = df.groupby("case_id").size()
    keep = lengths[(lengths >= p["min_case_length"]) &
                   (lengths <= p["max_case_length"])].index
    report["cases_removed_by_length"] = int(len(lengths) - len(keep))
    df = df[df["case_id"].isin(keep)].copy()
    cases = cases[cases["case_id"].isin(keep)].copy().drop_duplicates("case_id")

    # ---------------- feature engineering ----------------
    df["prev_timestamp"] = df.groupby("case_id")["timestamp"].shift(1)
    df["gap_minutes"] = ((df["timestamp"] - df["prev_timestamp"])
                         .dt.total_seconds() / 60.0)
    df["gap_minutes"] = df["gap_minutes"].fillna(0.0).clip(lower=0)

    g = df.groupby("case_id")
    df["event_index"] = g.cumcount()
    df["case_size"] = g["activity"].transform("size")
    df["trace_start"] = g["timestamp"].transform("min")
    df["elapsed_hours"] = (df["timestamp"] - df["trace_start"]).dt.total_seconds() / 3600.0
    df["activity_repeat"] = g["activity"].transform(lambda s: s.duplicated(keep=False))
    df["is_rework"] = df["activity_repeat"].astype(int)

    df["hour"] = df["timestamp"].dt.hour
    df["weekday"] = df["timestamp"].dt.day_name()
    df["is_weekend"] = df["timestamp"].dt.dayofweek.isin([5, 6]).astype(int)
    df["shift"] = pd.cut(df["hour"], bins=[-1, 5, 13, 21, 23],
                         labels=["Night", "Morning", "Evening", "Late Night"]).astype(str)
    df["month"] = df["timestamp"].dt.to_period("M").astype(str)

    variants = (df.sort_values("timestamp")
                  .groupby("case_id")["activity"]
                  .apply(lambda s: " -> ".join(s)))
    df["variant"] = df["case_id"].map(variants)

    merged = df.merge(cases, on="case_id", how="left", suffixes=("", "_case"))
    merged["department"] = merged["department"].fillna("Unknown")
    merged["gender"] = merged["gender"].fillna("Unknown")
    merged["triage_level"] = merged["triage_level"].fillna(3).astype(int)

    report["rows_out"] = int(len(merged))
    report["cases_out"] = int(merged["case_id"].nunique())
    report["activities_out"] = int(merged["activity"].nunique())
    report["resources_out"] = int(merged["resource"].nunique())
    report["variants_out"] = int(merged["variant"].nunique())
    report["date_min"] = str(merged["timestamp"].min())
    report["date_max"] = str(merged["timestamp"].max())
    return merged, report


def main() -> None:
    app = argparse.ArgumentParser()
    app.add_argument("--config", default="config/config.yaml")
    args = app.parse_args()

    cfg = load_config(args.config)
    ensure_dirs(cfg)

    df, cases = load_raw(cfg)
    LOG.info("raw events=%d raw cases=%d", len(df), len(cases))

    clean_df, report = clean(df, cases, cfg)
    os.makedirs(os.path.dirname(path_of(cfg, "processed")), exist_ok=True)
    clean_df.to_csv(path_of(cfg, "processed"), index=False)

    save_json(report, os.path.join(path_of(cfg, "reports"), "preprocessing_report.json"))
    LOG.info("clean events=%d cases=%d variants=%d",
             report["rows_out"], report["cases_out"], report["variants_out"])
    LOG.info("saved -> %s", path_of(cfg, "processed"))


if __name__ == "__main__":
    main()

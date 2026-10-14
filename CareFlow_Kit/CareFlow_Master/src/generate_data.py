"""
CareFlow - Step 1: clinical event-log generator.

Creates a realistic hospital care-pathway event log so that the whole
process-mining pipeline can be demonstrated end-to-end.

Outputs
-------
data/raw/event_log.csv         one row per *event* (case_id, activity, timestamp, ...)
data/raw/case_attributes.csv   one row per *case* (age, gender, triage, LOS, pathway)
Usage
-----
    python src/generate_data.py
    python src/generate_data.py --cases 3000 --seed 7
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np  # type: ignore[reportMissingImports]
import pandas as pd  # type: ignore[reportMissingModuleSource]

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils import ensure_dirs, get_logger, load_config, path_of  # noqa: E402

LOG = get_logger("careflow.generate_data")

# --------------------------------------------------------------------------
# Care pathway definitions
# department, mean service time (minutes), mean waiting time (minutes)
# --------------------------------------------------------------------------
BASE_ACTIVITIES = {
    "Registration":            ("Front Desk",        12,  8),
    "Triage":                  ("Emergency",         15, 10),
    "Emergency Assessment":    ("Emergency",         35, 15),
    "Lab Test":                ("Laboratory",        50, 40),
    "Radiology":               ("Radiology",         45, 35),
    "Specialist Consultation": ("Outpatient",        30, 25),
    "Diagnosis Confirmed":     ("Outpatient",        15, 10),
    "Medication Prescribed":   ("Pharmacy",          25, 15),
    "Admission":               ("Ward",              40, 20),
    "Surgery":                 ("Operation Theatre",210, 60),
    "ICU Transfer":            ("ICU",               70, 30),
    "Observation":             ("Ward",             150, 45),
    "Physiotherapy":           ("Rehabilitation",    50, 20),
    "Discharge Planning":      ("Ward",              35, 20),
    "Discharge":               ("Front Desk",        20, 10),
}

RESOURCES = {
    "Front Desk":        ["REC-01", "REC-02", "REC-03"],
    "Emergency":         ["DR-EM-01", "DR-EM-02", "NUR-EM-01", "NUR-EM-02"],
    "Laboratory":        ["LAB-TECH-01", "LAB-TECH-02"],
    "Radiology":         ["RAD-TECH-01", "RAD-TECH-02"],
    "Outpatient":        ["DR-OP-01", "DR-OP-02", "DR-OP-03"],
    "Pharmacy":          ["PHARM-01", "PHARM-02"],
    "Ward":              ["NUR-WD-01", "NUR-WD-02", "NUR-WD-03"],
    "Operation Theatre": ["SUR-01", "SUR-02", "OT-NUR-01"],
    "ICU":               ["DR-ICU-01", "NUR-ICU-01", "NUR-ICU-02"],
    "Rehabilitation":    ["PHYSIO-01", "PHYSIO-02"],
}

# cost per service minute (INR) used to build a synthetic billing column
DEPT_RATE = {
    "Front Desk": 15, "Emergency": 45, "Laboratory": 30, "Radiology": 55,
    "Outpatient": 40, "Pharmacy": 20, "Ward": 35, "Operation Theatre": 120,
    "ICU": 95, "Rehabilitation": 30,
}

PATHWAYS = {
    "P1_Outpatient_Standard": {
        "weight": 0.35, "wait_factor": 1.0, "admission_type": "Outpatient",
        "triage": (3, 5),
        "activities": [
            "Registration", "Triage", "Specialist Consultation", "Lab Test",
            "Diagnosis Confirmed", "Medication Prescribed", "Discharge",
        ],
        "rework": {"Lab Test": 0.15},
    },
    "P2_Emergency_Surgical": {
        "weight": 0.25, "wait_factor": 1.4, "admission_type": "Emergency",
        "triage": (1, 3),
        "activities": [
            "Registration", "Triage", "Emergency Assessment", "Lab Test",
            "Radiology", "Diagnosis Confirmed", "Admission", "Surgery",
            "Observation", "Physiotherapy", "Discharge Planning", "Discharge",
        ],
        "rework": {"Radiology": 0.20, "Surgery": 0.05},
    },
    "P3_Chronic_Followup": {
        "weight": 0.25, "wait_factor": 0.8, "admission_type": "Day Care",
        "triage": (4, 5),
        "activities": [
            "Registration", "Specialist Consultation", "Lab Test",
            "Medication Prescribed", "Physiotherapy", "Discharge Planning",
            "Discharge",
        ],
        "rework": {"Lab Test": 0.30, "Physiotherapy": 0.20},
    },
    "P4_ICU_Escalation": {
        "weight": 0.15, "wait_factor": 1.8, "admission_type": "Emergency",
        "triage": (1, 2),
        "activities": [
            "Registration", "Triage", "Emergency Assessment", "Lab Test",
            "ICU Transfer", "Observation", "Radiology", "Diagnosis Confirmed",
            "Medication Prescribed", "Discharge Planning", "Discharge",
        ],
        "rework": {"ICU Transfer": 0.10, "Radiology": 0.15},
    },
}


def _log_normal(mean_minutes: float, rng: np.random.Generator, spread: float = 0.45) -> float:
    """Positive, right-skewed duration (looks like real hospital data)."""
    if mean_minutes <= 0:
        return 0.0
    mu = np.log(mean_minutes) - 0.5 * spread ** 2
    return float(max(1.0, rng.lognormal(mean=mu, sigma=spread)))


def _business_hour(rng: np.random.Generator) -> int:
    """Most events happen between 08:00 and 20:00."""
    hours = np.arange(24)
    weights = np.array([0.5, 0.4, 0.4, 0.5, 0.8, 1.2, 2.0, 3.0, 5.0, 6.0,
                        6.0, 5.5, 5.0, 5.0, 4.5, 4.0, 3.5, 3.0, 2.5, 2.0,
                        1.5, 1.2, 1.0, 0.7])
    return int(rng.choice(hours, p=weights / weights.sum()))


def generate(n_cases: int, seed: int, start: str, end: str,
             dup_rate: float, missing_rate: float, cfg) -> tuple:
    rng = np.random.default_rng(seed)
    names = list(PATHWAYS.keys())
    weights = np.array([PATHWAYS[n]["weight"] for n in names])
    weights = weights / weights.sum()

    t_start = pd.Timestamp(start).to_pydatetime()
    t_end = pd.Timestamp(end).to_pydatetime()
    span_days = max((t_end - t_start).days, 1)

    events, cases = [], []

    for i in range(1, n_cases + 1):
        case_id = f"CASE-{i:05d}"
        pathway_name = str(rng.choice(names, p=weights))
        pw = PATHWAYS[pathway_name]

        age = int(np.clip(rng.normal(56, 16), 1, 97))
        gender = str(rng.choice(["Male", "Female"], p=[0.54, 0.46]))
        triage_lo, triage_hi = pw["triage"]
        triage_level = int(rng.integers(triage_lo, triage_hi + 1))
        admission_type = pw["admission_type"]

        day = int(rng.integers(0, span_days))
        stamp = (pd.Timestamp(t_start) + pd.Timedelta(days=day)).replace(
            hour=_business_hour(rng), minute=int(rng.integers(0, 60)), second=0, microsecond=0
        ).to_pydatetime()

        activities = list(pw["activities"])
        prev_activity = None
        for act in activities:
            dept, svc_mean, wait_mean = BASE_ACTIVITIES[act]

            # waiting time before the activity (scaled by pathway pressure)
            wait = _log_normal(wait_mean * pw["wait_factor"], rng, spread=0.75)
            if prev_activity is None:
                wait = 0.0
            stamp = stamp + pd.Timedelta(minutes=wait)

            service = _log_normal(svc_mean, rng, spread=0.40)
            cost = round(service * DEPT_RATE[dept] * float(rng.normal(1.0, 0.08)), 2)
            resource = str(rng.choice(RESOURCES[dept]))

            events.append({
                "case_id": case_id,
                "activity": act,
                "timestamp": stamp,
                "resource": resource,
                "department": dept,
                "wait_minutes": round(wait, 2),
                "service_minutes": round(service, 2),
                "cost_inr": cost,
            })
            stamp = stamp + pd.Timedelta(minutes=service)

            # rework loop: the same step is repeated (very common in hospitals)
            if act in pw["rework"] and rng.random() < pw["rework"][act]:
                dept2, svc_mean2, wait_mean2 = BASE_ACTIVITIES[act]
                wait2 = _log_normal(wait_mean2 * pw["wait_factor"], rng, spread=0.75)
                stamp = stamp + pd.Timedelta(minutes=wait2)
                service2 = _log_normal(svc_mean2, rng, spread=0.40)
                events.append({
                    "case_id": case_id,
                    "activity": act,
                    "timestamp": stamp,
                    "resource": str(rng.choice(RESOURCES[dept2])),
                    "department": dept2,
                    "wait_minutes": round(wait2, 2),
                    "service_minutes": round(service2, 2),
                    "cost_inr": round(service2 * DEPT_RATE[dept2], 2),
                })
                stamp = stamp + pd.Timedelta(minutes=service2)

            prev_activity = act

        case_events = [e for e in events if e["case_id"] == case_id]
        first = min(e["timestamp"] for e in case_events)
        last = max(e["timestamp"] for e in case_events)
        los_hours = round((last - first).total_seconds() / 3600.0, 2)
        total_cost = round(sum(e["cost_inr"] for e in case_events), 2)

        cases.append({
            "case_id": case_id,
            "patient_id": f"PAT-{1000 + i}",
            "age": age,
            "gender": gender,
            "triage_level": triage_level,
            "admission_type": admission_type,
            "pathway": pathway_name,
            "los_hours": los_hours,
            "total_cost_inr": total_cost,
            "n_events": len(case_events),
        })

    df_events = pd.DataFrame(events).sort_values(
        ["case_id", "timestamp"]).reset_index(drop=True)
    df_cases = pd.DataFrame(cases)

    # ---- inject realistic data-quality problems (cleaned in the next step) ----
    if missing_rate > 0:
        idx = rng.choice(df_events.index, size=int(len(df_events) * missing_rate),
                         replace=False)
        df_events.loc[idx, "resource"] = np.nan
    if dup_rate > 0:
        dup_idx = rng.choice(df_events.index, size=int(len(df_events) * dup_rate),
                             replace=False)
        df_events = pd.concat([df_events, df_events.loc[dup_idx]], ignore_index=True)
        df_events = df_events.sort_values(
            ["case_id", "timestamp"]).reset_index(drop=True)

    os.makedirs(os.path.dirname(path_of(cfg, "raw_events")), exist_ok=True)
    df_events.to_csv(path_of(cfg, "raw_events"), index=False)
    df_cases.to_csv(path_of(cfg, "raw_cases"), index=False)

    LOG.info("events=%d  cases=%d  activities=%d  variants(approx)=%d",
             len(df_events), df_cases["case_id"].nunique(),
             df_events["activity"].nunique(), df_cases["pathway"].nunique())
    return df_events, df_cases


def main() -> None:
    app = argparse.ArgumentParser(description="CareFlow synthetic event-log generator")
    app.add_argument("--config", default="config/config.yaml")
    app.add_argument("--cases", type=int, default=None)
    app.add_argument("--seed", type=int, default=None)
    args = app.parse_args()

    cfg = load_config(args.config)
    ensure_dirs(cfg)
    g = cfg["data_generation"]
    generate(
        n_cases=args.cases or g["n_cases"],
        seed=args.seed or g["seed"],
        start=g["start_date"],
        end=g["end_date"],
        dup_rate=g["duplicate_event_rate"],
        missing_rate=g["missing_resource_rate"],
        cfg=cfg,
    )


if __name__ == "__main__":
    main()

"""
CareFlow - one-click pipeline runner.

    python run_all.py              # full pipeline
    python run_all.py --skip-ml    # everything except the ML stage

Stages
------
 1. generate_data.py     -> raw event log
 2. preprocess.py        -> cleaned, feature-engineered log
 3. discover_models.py   -> DFG, variants, process model
 4. analyze_insights.py  -> KPIs, bottlenecks, business insights
 5. conformance.py       -> fitness / deviation analysis
 6. ml_model.py          -> long-stay prediction + evaluation
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

STAGES = [
    ("Step 1 - Generate clinical event log", "generate_data.py"),
    ("Step 2 - Clean & engineer features", "preprocess.py"),
    ("Step 3 - Process discovery", "discover_models.py"),
    ("Step 4 - Insights & visualisation", "analyze_insights.py"),
    ("Step 5 - Conformance checking", "conformance.py"),
    ("Step 6 - Machine-learning model", "ml_model.py"),
]


def run(script: str) -> None:
    cmd = [sys.executable, str(SRC / script)]
    print(f"\n$ {' '.join(cmd)}", flush=True)
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        raise SystemExit(f"[FAILED] {script} exited with code {r.returncode}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-ml", action="store_true")
    ap.add_argument("--skip-data", action="store_true",
                    help="reuse an existing data/raw event log")
    args = ap.parse_args()

    t0 = time.time()
    print("=" * 74)
    print(" CareFlow - Clinical Pathway Process Mining  |  full pipeline")
    print("=" * 74)

    for i, (label, script) in enumerate(STAGES):
        if args.skip_data and script == "generate_data.py":
            print(f"\n[skip] {label}")
            continue
        if args.skip_ml and script == "ml_model.py":
            print(f"\n[skip] {label}")
            continue
        print(f"\n>>> {label}")
        run(script)

    print("\n" + "=" * 74)
    print(f" Pipeline finished in {time.time() - t0:.1f} s")
    print(" Charts  -> outputs/figures/")
    print(" Reports -> outputs/reports/")
    print(" Model   -> outputs/models/")
    print(" Dashboard:  streamlit run dashboard/app.py")
    print("=" * 74)


if __name__ == "__main__":
    main()

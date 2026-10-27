"""CareFlow - optional official process mining with pm4py.
    pip install -r requirements-optional.txt
    python src/pm4py_discovery.py --miner inductive
"""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

def main(miner: str, csv: str) -> None:
    import pm4py
    df = pd.read_csv(ROOT / csv)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.rename(columns={"case_id": "case:concept:name", "activity": "concept:name",
                            "timestamp": "time:timestamp", "resource": "org:resource"})
    log = pm4py.format_dataframe(df, case_id="case:concept:name",
                                 activity_key="concept:name", timestamp_key="time:timestamp")
    print(f"events={len(log)} cases={log['case:concept:name'].nunique()}")
    if miner == "inductive":
        net, im, fm = pm4py.discover_petri_net_inductive(log)
    elif miner == "heuristics":
        net, im, fm = pm4py.discover_petri_net_heuristics(log)
    else:
        net, im, fm = pm4py.discover_petri_net_alpha(log)
    fit = pm4py.fitness_token_based_replay(log, net, im, fm)
    print("fitness:", fit)
    p = ROOT / "outputs/figures/pm4py_petrinet.png"
    try: pm4py.save_vis_petri_net(net, im, fm, str(p)); print("figure ->", p)
    except Exception as e: print("image export needs Graphviz:", e)
    print("variants:", pm4py.get_variants(log).__len__() if hasattr(pm4py.get_variants(log),'__len__') else 'n/a')

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--miner", default="inductive", choices=["inductive", "heuristics", "alpha"])
    ap.add_argument("--csv", default="data/processed/event_log_clean.csv")
    a = ap.parse_args(); main(a.miner, a.csv)

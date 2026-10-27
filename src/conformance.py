"""
CareFlow - Step 5: conformance checking (token-based replay).

Compares every real patient journey (case) against the discovered process
model (the DFG) and reports fitness, deviations and the non-conforming cases.

Outputs
-------
outputs/reports/conformance_report.json
outputs/reports/conformance_by_variant.csv
outputs/figures/conformance_fitness.png
outputs/figures/deviation_types.png

Usage
-----
    python src/conformance.py
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
import pandas as pd                      # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils import (ensure_dirs, get_logger, load_config, path_of,  # noqa: E402
                       save_figure, save_json)

LOG = get_logger("careflow.conformance")
plt.rcParams.update({"font.size": 9.5, "axes.grid": True, "grid.alpha": 0.28})


def build_model_edges(df: pd.DataFrame, min_count: int) -> set:
    d = df.sort_values(["case_id", "timestamp"])
    d["next_activity"] = d.groupby("case_id")["activity"].shift(-1)
    e = d.dropna(subset=["next_activity"])
    counts = e.groupby(["activity", "next_activity"]).size()
    return {edge for edge, c in counts.items() if c >= min_count}


def token_replay_case(trace: list, allowed: set) -> dict:
    """
    Simple token-based replay against a DFG.
      produced  = number of transitions that fired
      consumed  = tokens taken from the model
      missing   = transitions allowed by the model but never observed
      remaining = model tokens left at the end of the trace
      fitness   = 0.5*(1 - missing/consumed) + 0.5*(1 - remaining/produced)
    """
    produced = len(trace) - 1
    consumed = 0
    deviations = []

    for i in range(len(trace) - 1):
        edge = (trace[i], trace[i + 1])
        if edge in allowed:
            consumed += 1
        else:
            deviations.append({
                "position": i,
                "from": trace[i], "to": trace[i + 1],
                "type": "missing_token" if i else "unexpected_start",
            })

    if produced == 0:
        return {"fitness": 1.0, "produced": 0, "consumed": 0,
                "missing": 0, "remaining": 0, "deviations": deviations,
                "conforming": True}

    missing = produced - consumed
    remaining = max(0, consumed - produced)
    fitness = 0.5 * (1 - missing / produced) + 0.5 * (1 - remaining / max(produced, 1))
    fitness = float(min(max(fitness, 0.0), 1.0))
    return {"fitness": fitness, "produced": produced, "consumed": consumed,
            "missing": missing, "remaining": remaining,
            "deviations": deviations, "conforming": missing == 0}


def main() -> None:
    app = argparse.ArgumentParser()
    app.add_argument("--config", default="config/config.yaml")
    args = app.parse_args()

    cfg = load_config(args.config)
    ensure_dirs(cfg)
    min_count = cfg["conformance"]["min_edge_count"]

    df = pd.read_csv(path_of(cfg, "processed"), parse_dates=["timestamp"])
    allowed = build_model_edges(df, min_count)

    traces = (df.sort_values(["case_id", "timestamp"])
                .groupby("case_id")["activity"].apply(list))

    results, all_dev = [], Counter()
    for case_id, trace in traces.items():
        r = token_replay_case(trace, allowed)
        for dev in r["deviations"]:
            all_dev[f"{dev['from']} -> {dev['to']}"] += 1
        results.append({
            "case_id": case_id, "trace_length": len(trace),
            "fitness": round(r["fitness"], 4),
            "missing_tokens": r["missing"],
            "conforming": int(r["conforming"]),
            "variant": " -> ".join(trace),
        })

    res = pd.DataFrame(results)
    res.to_csv(os.path.join(path_of(cfg, "reports"), "conformance_by_case.csv"), index=False)

    by_variant = (res.groupby("variant")
                     .agg(cases=("case_id", "size"),
                          avg_fitness=("fitness", "mean"),
                          conforming_cases=("conforming", "sum"))
                     .reset_index()
                     .sort_values("cases", ascending=False).round(4))
    by_variant.to_csv(os.path.join(path_of(cfg, "reports"),
                                   "conformance_by_variant.csv"), index=False)

    avg_fit = float(res["fitness"].mean())
    perfect = float((res["fitness"] == 1.0).mean() * 100)
    conforming = float(res["conforming"].mean() * 100)

    report = {
        "model": "DFG (directly-follows graph)",
        "min_edge_count": min_count,
        "cases_checked": int(len(res)),
        "model_edges": int(len(allowed)),
        "average_fitness": round(avg_fit, 4),
        "perfectly_fitting_cases_pct": round(perfect, 2),
        "fully_conforming_cases_pct": round(conforming, 2),
        "cases_with_deviations": int((res["conforming"] == 0).sum()),
        "worst_cases": res.nsmallest(10, "fitness")[
            ["case_id", "fitness", "trace_length"]].to_dict("records"),
        "top_deviations": all_dev.most_common(10),
    }
    save_json(report, os.path.join(path_of(cfg, "reports"), "conformance_report.json"))

    # ---- figures ----
    plt.figure(figsize=(10.5, 5.4))
    plt.hist(res["fitness"], bins=22, color="#5AD8A6", edgecolor="#00595A")
    plt.axvline(avg_fit, color="#E8684A", ls="--", lw=2, label=f"Average = {avg_fit:.3f}")
    plt.title("Conformance fitness distribution (token-based replay)",
              fontsize=13, fontweight="bold")
    plt.xlabel("Fitness score (1.0 = perfectly follows the model)")
    plt.ylabel("Number of cases"); plt.legend()
    save_figure(plt.gcf(), cfg, "conformance_fitness.png"); plt.close()

    top = pd.Series(dict(all_dev.most_common(10))).sort_values()
    plt.figure(figsize=(11.5, 6))
    labels = [t[:46] for t in top.index]
    bars = plt.barh(labels, top.values, color="#FF9D4D", edgecolor="#8A4A00")
    plt.bar_label(bars, fontsize=8)
    plt.title("Most frequent deviations from the expected care pathway",
              fontsize=13, fontweight="bold")
    plt.xlabel("Occurrences")
    save_figure(plt.gcf(), cfg, "deviation_types.png"); plt.close()

    LOG.info("cases=%d fitness=%.4f conforming=%.1f%%", len(res), avg_fit, conforming)


if __name__ == "__main__":
    main()

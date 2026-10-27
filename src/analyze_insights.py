"""
CareFlow - Step 4: descriptive analytics, bottleneck detection and insights.

Outputs
-------
outputs/figures/kpi_los_distribution.png
outputs/figures/case_volume_trend.png
outputs/figures/bottleneck_waiting.png
outputs/figures/cost_by_department.png
outputs/figures/resource_workload.png
outputs/figures/hourly_heatmap.png
outputs/figures/pathway_comparison.png
outputs/reports/insights.json
outputs/reports/insights_summary.md

Usage
-----
    python src/analyze_insights.py
"""
from __future__ import annotations

import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
import numpy as np                       # noqa: E402
import pandas as pd                      # noqa: E402
import seaborn as sns                    # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils import (ensure_dirs, get_logger, load_config, path_of,  # noqa: E402
                       save_figure, save_json)

LOG = get_logger("careflow.insights")
PALETTE = ["#5B8FF9", "#5AD8A6", "#F6BD16", "#E8684A", "#6DC8EC",
           "#9270CA", "#FF9D4D", "#269A99", "#FF99C3", "#5D7092"]
plt.rcParams.update({"font.size": 9.5, "axes.grid": True,
                     "grid.alpha": 0.28, "axes.axisbelow": True})


def _bar(series, title, xlabel, ylabel, cfg, fname, color="#5B8FF9", rotate=False):
    plt.figure(figsize=(11, 6))
    labels = [str(i)[:34] for i in series.index]
    bars = plt.bar(labels, series.values, color=color, edgecolor="#1B3B6F", linewidth=0.6)
    plt.bar_label(bars, fmt="%.1f", fontsize=8)
    plt.title(title, fontsize=13, fontweight="bold")
    plt.xlabel(xlabel); plt.ylabel(ylabel)
    if rotate:
        plt.xticks(rotation=35, ha="right")
    return save_figure(plt.gcf(), cfg, fname)


def analyse(df: pd.DataFrame, cfg: dict) -> dict:
    threshold = cfg["ml"]["los_threshold_hours"]
    cases = df.drop_duplicates("case_id")
    rep = os.path.join(path_of(cfg, "reports"))
    insights = {}

    # ---------- 1. LOS distribution ----------
    plt.figure(figsize=(11, 5.5))
    sns.histplot(cases["los_hours"], bins=45, kde=True, color="#5B8FF9")
    plt.axvline(threshold, color="#E8684A", ls="--", lw=2,
                label=f"Long-stay threshold = {threshold} h")
    plt.axvline(cases["los_hours"].median(), color="#5AD8A6", ls=":", lw=2,
                label=f"Median = {cases['los_hours'].median():.1f} h")
    plt.title("Length-of-stay distribution across patient journeys",
              fontsize=13, fontweight="bold")
    plt.xlabel("Length of stay (hours)"); plt.ylabel("Number of cases")
    plt.legend()
    save_figure(plt.gcf(), cfg, "kpi_los_distribution.png"); plt.close()

    insights["los_mean_hours"] = round(float(cases["los_hours"].mean()), 2)
    insights["los_median_hours"] = round(float(cases["los_hours"].median()), 2)
    insights["los_p90_hours"] = round(float(cases["los_hours"].quantile(0.90)), 2)
    insights["long_stay_cases"] = int((cases["los_hours"] > threshold).sum())
    insights["long_stay_share_pct"] = round(
        float((cases["los_hours"] > threshold).mean() * 100), 2)

    # ---------- 2. case volume trend ----------
    vol = df.groupby("month")["case_id"].nunique()
    plt.figure(figsize=(11, 5.5))
    plt.plot(vol.index, vol.values, marker="o", lw=2.2, color="#5B8FF9")
    for x, y in zip(vol.index, vol.values):
        plt.annotate(str(y), (x, y), textcoords="offset points", xytext=(0, 7),
                     ha="center", fontsize=8.5)
    plt.title("Monthly patient case volume", fontsize=13, fontweight="bold")
    plt.xlabel("Month"); plt.ylabel("Cases")
    save_figure(plt.gcf(), cfg, "case_volume_trend.png"); plt.close()
    insights["monthly_case_volume"] = {str(k): int(v) for k, v in vol.items()}

    # ---------- 3. bottlenecks: longest waiting ----------
    wait = (df.groupby("activity")["gap_minutes"].mean()
              .sort_values(ascending=False).head(12))
    _bar(wait, "Top process bottlenecks - average waiting time before each step",
         "Care activity", "Average wait (minutes)", cfg, "bottleneck_waiting.png",
         color="#E8684A", rotate=True)
    insights["top_bottleneck"] = str(wait.index[0])
    insights["top_bottleneck_wait_min"] = round(float(wait.iloc[0]), 2)
    insights["total_wait_minutes"] = round(float(df["gap_minutes"].sum()), 1)

    # ---------- 4. cost by department ----------
    cost = df.groupby("department")["cost_inr"].sum().sort_values(ascending=False)
    _bar(cost, "Total treatment cost by department (INR)",
         "Department", "Total cost (INR)", cfg, "cost_by_department.png",
         color="#5AD8A6", rotate=True)
    insights["total_cost_inr"] = round(float(cost.sum()), 2)
    insights["costliest_department"] = str(cost.index[0])
    insights["avg_cost_per_case_inr"] = round(
        float(df.groupby("case_id")["cost_inr"].sum().mean()), 2)

    # ---------- 5. resource workload ----------
    load = df.groupby("resource").size().sort_values(ascending=False).head(15)
    _bar(load, "Resource workload - most involved clinical staff",
         "Resource", "Events handled", cfg, "resource_workload.png",
         color="#9270CA", rotate=True)
    insights["busiest_resource"] = str(load.index[0])
    insights["busiest_resource_events"] = int(load.iloc[0])

    # ---------- 6. hourly heatmap ----------
    hd = (df.assign(wd=df["timestamp"].dt.day_name())
            .pivot_table(index="wd", columns="hour", values="case_id",
                         aggfunc="count").reindex(
        ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]))
    plt.figure(figsize=(14, 4.6))
    sns.heatmap(hd, cmap="YlOrRd", linewidths=0.35, cbar_kws={"label": "Events"})
    plt.title("Hospital load heatmap - events by weekday and hour",
              fontsize=13, fontweight="bold")
    plt.xlabel("Hour of day"); plt.ylabel("")
    save_figure(plt.gcf(), cfg, "hourly_heatmap.png"); plt.close()
    peak_hour = int(hd.sum().idxmax())
    insights["peak_load_hour"] = peak_hour
    insights["peak_load_day"] = str(hd.sum(axis=1).idxmax())

    # ---------- 7. pathway comparison ----------
    pw = df.drop_duplicates("case_id").groupby("pathway").agg(
        cases=("case_id", "size"),
        avg_los=("los_hours", "mean"),
        avg_cost=("total_cost_inr", "mean")).round(2).sort_values("avg_los")
    fig, ax1 = plt.subplots(figsize=(11.5, 5.8))
    x = np.arange(len(pw))
    b = ax1.bar(x - 0.2, pw["avg_los"], 0.4, label="Avg LOS (h)",
                color="#5B8FF9", edgecolor="#1B3B6F")
    ax1.bar_label(b, fmt="%.1f", fontsize=8)
    ax2 = ax1.twinx()
    b2 = ax2.bar(x + 0.2, pw["avg_cost"], 0.4, label="Avg cost (INR)",
                 color="#F6BD16", edgecolor="#8A6100")
    ax2.bar_label(b2, fmt="%.0f", fontsize=8)
    ax1.set_xticks(x)
    ax1.set_xticklabels([p.split("_", 1)[1] for p in pw.index], rotation=15, ha="right")
    ax1.set_ylabel("Average length of stay (hours)")
    ax2.set_ylabel("Average cost per case (INR)")
    ax1.set_title("Care-pathway comparison - length of stay vs cost",
                  fontsize=13, fontweight="bold")
    ax1.legend(loc="upper left"); ax2.legend(loc="upper right")
    save_figure(plt.gcf(), cfg, "pathway_comparison.png"); plt.close()
    insights["pathways"] = pw.reset_index().to_dict("records")

    json_path = os.path.join(rep, "insights.json")
    save_json(insights, json_path)
    return insights


def write_markdown(insights: dict, cfg: dict) -> str:
    lines = [
        "# CareFlow - Key Findings (auto-generated)", "",
        f"- Total cases analysed: **{insights.get('cases', 'n/a')}**",
        f"- Mean length of stay: **{insights['los_mean_hours']} hours** "
        f"(median {insights['los_median_hours']} h, P90 {insights['los_p90_hours']} h)",
        f"- Long-stay cases (>24 h): **{insights['long_stay_cases']} "
        f"({insights['long_stay_share_pct']}%)**",
        f"- Biggest bottleneck: **{insights['top_bottleneck']}** "
        f"({insights['top_bottleneck_wait_min']} min average wait)",
        f"- Costliest department: **{insights['costliest_department']}** "
        f"(total INR {insights['total_cost_inr']:,.0f})",
        f"- Average cost per case: **INR {insights['avg_cost_per_case_inr']:,.0f}**",
        f"- Busiest resource: **{insights['busiest_resource']}** "
        f"({insights['busiest_resource_events']} events)",
        f"- Peak hospital load: **{insights['peak_load_day']} around "
        f"{insights['peak_load_hour']:02d}:00**", "",
        "## Recommended actions", "",
        "1. Add a second lab sample-collection slot in the morning peak to cut "
        "the waiting time before `Lab Test`.",
        "2. Introduce a fast-track discharge desk so `Discharge Planning` does not "
        "queue behind routine ward rounds.",
        "3. Review the long-stay pathway variants and set up an early-warning flag "
        "for patients predicted as `>24 h` by the ML model.",
        "4. Rebalance nurse rosters towards the peak load window and the busiest unit.",
    ]
    md = "\n".join(lines)
    out = os.path.join(path_of(cfg, "reports"), "insights_summary.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(md)
    return md


def main() -> None:
    app = argparse.ArgumentParser()
    app.add_argument("--config", default="config/config.yaml")
    args = app.parse_args()
    cfg = load_config(args.config)
    ensure_dirs(cfg)

    df = pd.read_csv(path_of(cfg, "processed"), parse_dates=["timestamp"])
    insights = analyse(df, cfg)
    insights["cases"] = int(df["case_id"].nunique())
    save_json(insights, os.path.join(path_of(cfg, "reports"), "insights.json"))
    write_markdown(insights, cfg)
    LOG.info("total cases=%d cost=INR %.0f bottleneck=%s",
             insights["cases"], insights["total_cost_inr"], insights["top_bottleneck"])


if __name__ == "__main__":
    main()

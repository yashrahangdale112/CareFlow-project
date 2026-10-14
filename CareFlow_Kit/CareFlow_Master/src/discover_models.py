"""
CareFlow - Step 3: process discovery.

Builds the Directly-Follows Graph (DFG), the top process variants and - when
pm4py is installed - the official Inductive Miner / Heuristics Miner models.

Outputs
-------
outputs/figures/dfg_careflow.png
outputs/figures/variants_top10.png
outputs/reports/variants.csv
outputs/reports/dfg_edges.csv
outputs/models/petri_net_inductive.png   (only with pm4py + graphviz)

Usage
-----
    python src/discover_models.py --miner inductive
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
import networkx as nx                    # noqa: E402
import pandas as pd                      # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils import (ensure_dirs, get_logger, load_config, path_of,  # noqa: E402
                       save_figure, save_json)

LOG = get_logger("careflow.discover")

try:                                     # optional dependency
    import pm4py                          # noqa: F401
    HAVE_PM4PY = True
except Exception:                         # pragma: no cover
    HAVE_PM4PY = False
    LOG.warning("pm4py not installed - using the built-in pandas/networkx engine")


# --------------------------------------------------------------------------
# pure-pandas process mining engine (always available)
# --------------------------------------------------------------------------
def build_dfg(df: pd.DataFrame) -> pd.DataFrame:
    d = df.sort_values(["case_id", "timestamp"])
    d["next_activity"] = d.groupby("case_id")["activity"].shift(-1)
    edges = d.dropna(subset=["next_activity"])
    counts = (edges.groupby(["activity", "next_activity"])
                   .size().reset_index(name="count")
                   .sort_values("count", ascending=False))
    counts.columns = ["source", "target", "count"]
    return counts.reset_index(drop=True)


def variant_table(df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    d = df.sort_values(["case_id", "timestamp"])
    seq = d.groupby("case_id")["activity"].apply(lambda s: " -> ".join(s))
    counts = seq.value_counts()
    tbl = pd.DataFrame({"variant": counts.index, "case_count": counts.values})
    tbl["share_pct"] = (tbl["case_count"] / tbl["case_count"].sum() * 100).round(2)
    return tbl.head(top_n)


def activity_stats(df: pd.DataFrame) -> pd.DataFrame:
    st = (df.groupby("activity")
            .agg(events=("activity", "size"),
                 avg_service_min=("service_minutes", "mean"),
                 avg_wait_min=("gap_minutes", "mean"),
                 total_cost_inr=("cost_inr", "sum"))
            .reset_index())
    st = st.round(2).sort_values("events", ascending=False)
    return st


def draw_dfg(edges: pd.DataFrame, df: pd.DataFrame, cfg: dict,
             min_count: int = 3, max_edges: int = 45) -> str:
    e = edges[edges["count"] >= min_count].head(max_edges)
    G = nx.DiGraph()
    for _, r in e.iterrows():
        G.add_edge(r["source"], r["target"], weight=int(r["count"]))

    freq = df["activity"].value_counts()
    plt.figure(figsize=(15, 10))
    pos = nx.spring_layout(G, k=1.35, seed=42, iterations=250)
    sizes = [400 + 130 * freq.get(n, 1) ** 0.6 for n in G.nodes()]
    nx.draw_networkx_nodes(G, pos, node_size=sizes, node_color="#5B8FF9",
                           edgecolors="#1B3B6F", linewidths=1.2)
    nx.draw_networkx_edges(G, pos, edge_color="#9FB4CC", width=1.3,
                           arrows=True, arrowsize=14, connectionstyle="arc3,rad=0.08")
    nx.draw_networkx_labels(G, pos, font_size=7.5, font_color="#0B1B2B")
    ax = plt.gca()
    for (u, v, d) in G.edges(data=True):
        x = (pos[u][0] + pos[v][0]) / 2
        y = (pos[u][1] + pos[v][1]) / 2
        ax.text(x, y, str(d["weight"]), fontsize=6, color="#D64545",
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.75))
    ax.set_title("CareFlow - Directly-Follows Graph (clinical care pathway)\n"
                 f"nodes = activities, edge labels = how often the step follows",
                 fontsize=13, fontweight="bold")
    ax.axis("off")
    out = save_figure(plt.gcf(), cfg, "dfg_careflow.png")
    plt.close()
    return out


def draw_variants(tbl: pd.DataFrame, cfg: dict) -> str:
    d = tbl.iloc[::-1]
    labels = [f"V{i+1}: " + (v[:60] + "..." if len(v) > 60 else v)
              for i, v in enumerate(d["variant"])]
    plt.figure(figsize=(13, 7))
    bars = plt.barh(labels, d["case_count"], color="#36CFC9", edgecolor="#00595A")
    plt.bar_label(bars, labels=[f"{c} ({s}%)" for c, s in
                                zip(d["case_count"], d["share_pct"])], fontsize=8.5)
    plt.xlabel("Number of patient journeys (cases)")
    plt.title("Top 10 clinical pathway variants", fontsize=13, fontweight="bold")
    plt.xlim(0, d["case_count"].max() * 1.25)
    out = save_figure(plt.gcf(), cfg, "variants_top10.png")
    plt.close()
    return out


# --------------------------------------------------------------------------
# optional: pm4py official algorithms
# --------------------------------------------------------------------------
def pm4py_models(df: pd.DataFrame, cfg: dict, miner: str) -> dict:
    result = {"pm4py_available": True, "miner": miner}
    if not HAVE_PM4PY:
        result["pm4py_available"] = False
        return result

    import pm4py
    log = pm4py.format_dataframe(
        df[["case_id", "activity", "timestamp"]].copy(),
        case_id="case_id", activity_key="activity", timestamp_key="timestamp")

    try:
        if miner == "inductive":
            net, im, fm = pm4py.discover_petri_net_inductive(
                log, noise_threshold=cfg["discovery"]["noise_threshold"])
        elif miner == "heuristics":
            net, im, fm = pm4py.discover_petri_net_heuristics(log)
        elif miner == "alpha":
            net, im, fm = pm4py.discover_petri_net_alpha(log)
        else:
            net, im, fm = None, None, None
        result["model"] = f"{miner}_petri_net"
        if net is not None:
            result["places"] = len(net.places)
            result["transitions"] = len(net.transitions)
            try:
                png = os.path.join(path_of(cfg, "models"),
                                   f"petri_net_{miner}.png")
                pm4py.save_vis_petri_net(net, im, fm, png)
                result["png"] = png
            except Exception as exc:
                LOG.warning("Petri-net image skipped (Graphviz missing?): %s", exc)
    except Exception as exc:
        LOG.warning("pm4py %s miner failed: %s", miner, exc)
        result["error"] = str(exc)

    try:
        dfg, sa, ea = pm4py.discover_dfg(log)
        result["pm4py_dfg_edges"] = len(dfg)
    except Exception:
        pass
    return result


def main() -> None:
    app = argparse.ArgumentParser()
    app.add_argument("--config", default="config/config.yaml")
    app.add_argument("--miner", default=None,
                     choices=["inductive", "heuristics", "alpha", "dfg"])
    args = app.parse_args()

    cfg = load_config(args.config)
    ensure_dirs(cfg)
    miner = args.miner or cfg["discovery"]["miner"]

    df = pd.read_csv(path_of(cfg, "processed"), parse_dates=["timestamp"])
    LOG.info("events=%d cases=%d", len(df), df["case_id"].nunique())

    edges = build_dfg(df)
    edges.to_csv(os.path.join(path_of(cfg, "reports"), "dfg_edges.csv"), index=False)

    variants = variant_table(df, cfg["discovery"]["top_variants"])
    variants.to_csv(os.path.join(path_of(cfg, "reports"), "variants.csv"), index=False)

    stats = activity_stats(df)
    stats.to_csv(os.path.join(path_of(cfg, "reports"), "activity_stats.csv"), index=False)

    draw_dfg(edges, df, cfg, min_count=cfg["conformance"]["min_edge_count"])
    draw_variants(variants, cfg)

    summary = {
        "cases": int(df["case_id"].nunique()),
        "events": int(len(df)),
        "activities": int(df["activity"].nunique()),
        "dfg_edges": int(len(edges)),
        "unique_variants": int(df["variant"].nunique()),
        "top_variant_share_pct": float(variants.iloc[0]["share_pct"]),
        "top_5_variant_share_pct": float(variants.head(5)["share_pct"].sum()),
        "start_activities": Counter(
            df.sort_values("timestamp").groupby("case_id")["activity"].first()).most_common(5),
        "end_activities": Counter(
            df.sort_values("timestamp").groupby("case_id")["activity"].last()).most_common(5),
    }
    summary.update(pm4py_models(df, cfg, miner))
    save_json(summary, os.path.join(path_of(cfg, "reports"), "discovery_summary.json"))

    LOG.info("variants=%d top_variant_share=%.1f%% dfg_edges=%d",
             summary["unique_variants"], summary["top_variant_share_pct"],
             summary["dfg_edges"])
    LOG.info("pm4py available = %s", summary["pm4py_available"])


if __name__ == "__main__":
    main()

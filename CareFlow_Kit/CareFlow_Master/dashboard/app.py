"""
CareFlow - Step 7: interactive Streamlit dashboard.

Run
---
    streamlit run dashboard/app.py

Reads the processed event log + the artefacts written by the other pipeline
steps and shows KPIs, charts, the discovered process model and the ML results.
"""
from __future__ import annotations

import json
import os
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

st.set_page_config(page_title="CareFlow Analytics", page_icon="🏥", layout="wide")

PROC = os.path.join(ROOT, "data", "processed", "event_log_clean.csv")
FIG = os.path.join(ROOT, "outputs", "figures")
REP = os.path.join(ROOT, "outputs", "reports")


@st.cache_data(show_spinner=False)
def load_data() -> pd.DataFrame:
    df = pd.read_csv(PROC, parse_dates=["timestamp"])
    return df


def read_json(name: str) -> dict:
    p = os.path.join(REP, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def img(name: str, caption: str = "") -> None:
    p = os.path.join(FIG, name)
    if os.path.exists(p):
        st.image(p, caption=caption, use_container_width=True)
    else:
        st.info(f"Run the pipeline first - `{name}` not found.")


# --------------------------------------------------------------------------
st.title("🏥 CareFlow Analytics")
st.caption("Clinical Pathway Process Mining · Infotact Solutions · "
           "Data Associate L1 Internship Project")

if not os.path.exists(PROC):
    st.error("Processed data not found. Run the pipeline first:\n\n"
             "```bash\npython run_all.py\n```")
    st.stop()

df = load_data()
disc = read_json("discovery_summary.json")
conf = read_json("conformance_report.json")
ml = read_json("model_metrics.json")
ins = read_json("insights.json")

# ---------------- sidebar filters ----------------
st.sidebar.header("🔎 Filters")
pathways = st.sidebar.multiselect("Care pathway", sorted(df["pathway"].dropna().unique()),
                                  default=sorted(df["pathway"].dropna().unique()))
depts = st.sidebar.multiselect("Department", sorted(df["department"].unique()),
                               default=sorted(df["department"].unique()))
lo, hi = st.sidebar.slider("Length of stay (hours)",
                           0, int(df["los_hours"].max()) + 1, (0, int(df["los_hours"].max()) + 1))
triage = st.sidebar.multiselect("Triage level", sorted(df["triage_level"].unique()),
                                default=sorted(df["triage_level"].unique()))

f = df[df["pathway"].isin(pathways) & df["department"].isin(depts)
       & df["triage_level"].isin(triage)
       & df["los_hours"].between(lo, hi)]
if f.empty:
    st.warning("No data for the selected filters.")
    st.stop()

# ---------------- KPI cards ----------------
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Patient cases", f"{f['case_id'].nunique():,}")
k2.metric("Total events", f"{len(f):,}")
k3.metric("Avg length of stay", f"{f.drop_duplicates('case_id')['los_hours'].mean():.1f} h")
k4.metric("Avg cost / case", f"₹{f.groupby('case_id')['cost_inr'].sum().mean():,.0f}")
k5.metric("Avg conformance fitness", f"{conf.get('average_fitness', 0):.3f}")

st.divider()

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📊 Overview", "🔀 Process discovery", "✅ Conformance", "🤖 ML model", "📁 Data"])

with tab1:
    c1, c2 = st.columns(2)
    with c1:
        fig = px.histogram(f.drop_duplicates("case_id"), x="los_hours", nbins=45,
                           title="Length-of-stay distribution",
                           labels={"los_hours": "Length of stay (hours)"},
                           color_discrete_sequence=["#5B8FF9"])
        fig.add_vline(x=24, line_dash="dash", line_color="#E8684A",
                      annotation_text="Long-stay threshold")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        vol = f.groupby("month")["case_id"].nunique().reset_index()
        fig = px.line(vol, x="month", y="case_id", markers=True,
                      title="Monthly case volume",
                      labels={"case_id": "Cases", "month": "Month"},
                      color_discrete_sequence=["#5AD8A6"])
        st.plotly_chart(fig, use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        wait = (f.groupby("activity")["gap_minutes"].mean().sort_values()
                 .tail(12).reset_index())
        fig = px.bar(wait, x="gap_minutes", y="activity", orientation="h",
                     title="Top bottlenecks - average waiting time",
                     labels={"gap_minutes": "Avg wait (min)", "activity": ""},
                     color="gap_minutes", color_continuous_scale="Reds")
        st.plotly_chart(fig, use_container_width=True)
    with c4:
        cost = f.groupby("department")["cost_inr"].sum().reset_index()
        fig = px.treemap(cost, path=["department"], values="cost_inr",
                         title="Cost distribution by department",
                         color="cost_inr", color_continuous_scale="Teal")
        st.plotly_chart(fig, use_container_width=True)

    c5, c6 = st.columns(2)
    with c5:
        load = f.groupby("resource").size().sort_values().tail(15).reset_index(name="events")
        fig = px.bar(load, x="events", y="resource", orientation="h",
                     title="Resource workload", color="events",
                     color_continuous_scale="Purples")
        st.plotly_chart(fig, use_container_width=True)
    with c6:
        pw = f.drop_duplicates("case_id").groupby("pathway").agg(
            avg_los=("los_hours", "mean"), cases=("case_id", "size")).reset_index()
        fig = px.scatter(pw, x="pathway", y="avg_los", size="cases",
                         title="Average LOS by care pathway", color="pathway")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("💡 Key insights")
    if ins:
        st.markdown(
            f"- Mean length of stay **{ins.get('los_mean_hours')} h** "
            f"(median {ins.get('los_median_hours')} h)\n"
            f"- Long-stay cases **{ins.get('long_stay_cases')} "
            f"({ins.get('long_stay_share_pct')}%)**\n"
            f"- Biggest bottleneck **{ins.get('top_bottleneck')}** "
            f"({ins.get('top_bottleneck_wait_min')} min)\n"
            f"- Costliest department **{ins.get('costliest_department')}** "
            f"(₹{ins.get('total_cost_inr', 0):,.0f} total)\n"
            f"- Peak load **{ins.get('peak_load_day')} "
            f"{ins.get('peak_load_hour')}:00**")
        st.info(open(os.path.join(REP, "insights_summary.md"), encoding="utf-8").read())

with tab2:
    st.subheader("Discovered process model (Directly-Follows Graph)")
    img("dfg_careflow.png", "Every edge = a step that follows another step in real cases")
    img("variants_top10.png", "The most common clinical pathway variants")
    if disc:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Cases", f"{disc.get('cases', 0):,}")
        c2.metric("Activities", disc.get("activities", 0))
        c3.metric("DFG edges", disc.get("dfg_edges", 0))
        c4.metric("Unique variants", disc.get("unique_variants", 0))
        st.json(disc, expanded=False)

with tab3:
    st.subheader("Conformance checking - real cases vs. the model")
    c1, c2, c3 = st.columns(3)
    c1.metric("Average fitness", conf.get("average_fitness", "n/a"))
    c2.metric("Fully conforming cases", f"{conf.get('fully_conforming_cases_pct', 0)}%")
    c3.metric("Cases with deviations", f"{conf.get('cases_with_deviations', 0):,}")
    img("conformance_fitness.png")
    img("deviation_types.png")
    if os.path.exists(os.path.join(REP, "conformance_by_variant.csv")):
        st.dataframe(pd.read_csv(os.path.join(REP, "conformance_by_variant.csv")).head(25),
                     use_container_width=True)

with tab4:
    st.subheader("Long-stay prediction model")
    if ml:
        st.write(f"**Best model:** `{ml.get('best_model')}` · "
                 f"Long-stay rate in data: {ml.get('long_stay_rate_pct')}%")
        st.dataframe(pd.DataFrame(ml["all_models"]).T, use_container_width=True)
    img("model_roc.png")
    img("model_confusion_matrix.png")
    img("feature_importance.png")
    if os.path.exists(os.path.join(REP, "feature_importance.csv")):
        st.dataframe(pd.read_csv(os.path.join(REP, "feature_importance.csv")).head(20),
                     use_container_width=True)

with tab5:
    st.subheader("Processed event log")
    st.caption(f"{len(f):,} events · {f['case_id'].nunique():,} cases · "
               f"{f['activity'].nunique()} activities")
    st.dataframe(f.head(300), use_container_width=True)
    st.download_button("⬇️ Download filtered CSV",
                       f.to_csv(index=False).encode("utf-8"),
                       "careflow_filtered.csv", "text/csv")

st.divider()
st.caption("CareFlow · Clinical Pathway Process Mining · built by Yash Rahangdale")

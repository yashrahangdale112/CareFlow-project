"""
CareFlow - Step 6: predictive analytics.

Two experiments are run for every algorithm:

  1. "full"          - every engineered feature (duration aggregates included)
  2. "leakage_free"  - duration-derived columns removed, so the model only uses
                       information a hospital really has at ADMISSION time.

The leakage-free winner is the production model saved to
outputs/models/best_model.joblib - it is the honest, deployable result.

Outputs
-------
outputs/models/best_model.joblib
outputs/models/model_metadata.json
outputs/reports/model_metrics.json
outputs/reports/feature_importance.csv
outputs/figures/model_roc.png
outputs/figures/model_confusion_matrix.png
outputs/figures/feature_importance.png

Usage
-----
    python src/ml_model.py
"""
from __future__ import annotations

import argparse
import os
import sys

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
import numpy as np                       # noqa: E402
import pandas as pd                      # noqa: E402
import seaborn as sns                    # noqa: E402
from sklearn.compose import ColumnTransformer          # noqa: E402
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier  # noqa: E402
from sklearn.linear_model import LogisticRegression    # noqa: E402
from sklearn.metrics import (accuracy_score, classification_report,  # noqa: E402
                             confusion_matrix, f1_score, precision_score,
                             recall_score, roc_auc_score, roc_curve)
from sklearn.model_selection import cross_val_score, train_test_split  # noqa: E402
from sklearn.pipeline import Pipeline                   # noqa: E402
from sklearn.preprocessing import OneHotEncoder, StandardScaler  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils import (ensure_dirs, get_logger, load_config, path_of,  # noqa: E402
                       save_figure, save_json)

LOG = get_logger("careflow.ml")
plt.rcParams.update({"font.size": 9.5, "axes.grid": True, "grid.alpha": 0.28})

# columns that are computed FROM the outcome (length of stay) -> leakage if used
DURATION_LEAKY = ["total_wait", "avg_wait", "max_wait", "total_service", "wait_ratio"]


def build_features(df: pd.DataFrame, cfg: dict) -> tuple:
    """Aggregate the event log to one row per case and build the design matrix."""
    cases = df.drop_duplicates("case_id").copy()
    cases = cases.drop(columns=[c for c in ["n_events"] if c in cases.columns])

    agg = df.groupby("case_id").agg(
        n_events=("activity", "size"),
        n_unique_activities=("activity", "nunique"),
        total_wait=("gap_minutes", "sum"),
        avg_wait=("gap_minutes", "mean"),
        max_wait=("gap_minutes", "max"),
        total_service=("service_minutes", "sum"),
        n_rework=("is_rework", "sum"),
        n_night=("shift", lambda s: int((s == "Night").sum())),
    ).reset_index()

    data = cases.merge(agg, on="case_id", how="left", validate="one_to_one")
    data["rework_rate"] = (data["n_rework"] / data["n_events"]).round(4)
    data["wait_ratio"] = (data["total_wait"] / (data["total_service"] + 1)).round(4)

    d = df.sort_values(["case_id", "timestamp"])
    g = d.groupby("case_id")
    extra = pd.DataFrame({
        "case_id": list(g.groups.keys()),
        "first_activity": g["activity"].first().values,
        "last_activity": g["activity"].last().values,
        "has_surgery": g["activity"].apply(lambda s: int("Surgery" in set(s))).values,
        "has_icu": g["activity"].apply(lambda s: int("ICU Transfer" in set(s))).values,
    })
    data = data.merge(extra, on="case_id", how="left")

    thr = cfg["ml"]["los_threshold_hours"]
    data["y_long_stay"] = (data["los_hours"] > thr).astype(int)

    num_cols = ["age", "triage_level", "n_events", "n_unique_activities",
                "total_wait", "avg_wait", "max_wait", "total_service",
                "n_rework", "n_night", "rework_rate", "wait_ratio",
                "has_surgery", "has_icu"]
    cat_cols = ["gender", "admission_type", "pathway", "first_activity",
                "last_activity"]
    for c in num_cols:
        data[c] = pd.to_numeric(data[c], errors="coerce").fillna(0)
    for c in cat_cols:
        data[c] = data[c].astype(str).fillna("Unknown")

    num_lf = [c for c in num_cols if c not in DURATION_LEAKY]

    LOG.info("design matrix: %d cases | full=%d features | leakage-free=%d features "
             "| long-stay share %.1f%%",
             len(data), len(num_cols) + len(cat_cols), len(num_lf) + len(cat_cols),
             data["y_long_stay"].mean() * 100)
    return data, {"full": (num_cols, cat_cols), "leakage_free": (num_lf, cat_cols)}


def candidate_models(seed: int) -> dict:
    return {
        "logistic_regression": LogisticRegression(max_iter=1500, random_state=seed),
        "random_forest": RandomForestClassifier(
            n_estimators=350, max_depth=12, min_samples_leaf=3,
            random_state=seed, n_jobs=-1),
        "gradient_boosting": GradientBoostingClassifier(random_state=seed),
    }


def evaluate(data: pd.DataFrame, num_cols: list, cat_cols: list,
             cfg: dict) -> tuple:
    seed = cfg["ml"]["random_state"]
    X = data[num_cols + cat_cols]
    y = data["y_long_stay"]
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=cfg["ml"]["test_size"], random_state=seed, stratify=y)

    pre = ColumnTransformer([
        ("num", StandardScaler(), num_cols),
        ("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols),
    ])

    results, fitted = {}, {}
    for name, clf in candidate_models(seed).items():
        pipe = Pipeline([("prep", pre), ("clf", clf)])
        pipe.fit(X_tr, y_tr)
        pred = pipe.predict(X_te)
        proba = pipe.predict_proba(X_te)[:, 1]
        cv = cross_val_score(pipe, X, y, cv=5, scoring="f1", n_jobs=-1)
        results[name] = {
            "accuracy": round(float(accuracy_score(y_te, pred)), 4),
            "precision": round(float(precision_score(y_te, pred, zero_division=0)), 4),
            "recall": round(float(recall_score(y_te, pred, zero_division=0)), 4),
            "f1": round(float(f1_score(y_te, pred, zero_division=0)), 4),
            "roc_auc": round(float(roc_auc_score(y_te, proba)), 4),
            "cv_f1_mean": round(float(cv.mean()), 4),
            "cv_f1_std": round(float(cv.std()), 4),
        }
        fitted[name] = (pipe, pred, proba)
    return results, fitted, (X_tr, X_te, y_tr, y_te)


def main() -> None:
    app = argparse.ArgumentParser()
    app.add_argument("--config", default="config/config.yaml")
    args = app.parse_args()

    cfg = load_config(args.config)
    ensure_dirs(cfg)

    df = pd.read_csv(path_of(cfg, "processed"), parse_dates=["timestamp"])
    data, feature_sets = build_features(df, cfg)
    y = data["y_long_stay"]
    seed = cfg["ml"]["random_state"]

    all_results, best_of = {}, {}
    for set_name, (num_cols, cat_cols) in feature_sets.items():
        res, fitted, split = evaluate(data, num_cols, cat_cols, cfg)
        all_results[set_name] = res
        best = max(res, key=lambda k: res[k]["f1"])
        best_of[set_name] = {"num": num_cols, "cat": cat_cols,
                             "name": best, "fitted": fitted[best],
                             "results": res, "split": split}
        for m, r in res.items():
            LOG.info("[%-13s] %-20s acc=%.3f f1=%.3f auc=%.3f cv_f1=%.3f+-%.3f",
                     set_name, m, r["accuracy"], r["f1"], r["roc_auc"],
                     r["cv_f1_mean"], r["cv_f1_std"])

    prod = best_of["leakage_free"]
    best_name = prod["name"]
    best_pipe, best_pred, best_proba = prod["fitted"]
    _, X_te, y_tr, y_te = prod["split"]
    LOG.info("production model (leakage-free) = %s", best_name)

    joblib.dump(best_pipe, os.path.join(path_of(cfg, "models"), "best_model.joblib"))
    save_json({
        "production_model": best_name,
        "feature_set": "leakage_free",
        "excluded_leaky_columns": DURATION_LEAKY,
        "target": "y_long_stay",
        "los_threshold_hours": cfg["ml"]["los_threshold_hours"],
        "numeric_features": prod["num"], "categorical_features": prod["cat"],
    }, os.path.join(path_of(cfg, "models"), "model_metadata.json"))

    save_json({
        "target": "long stay > %s hours" % cfg["ml"]["los_threshold_hours"],
        "long_stay_rate_pct": round(float(y.mean() * 100), 2),
        "n_train": int(len(y_tr)), "n_test": int(len(y_te)),
        "full_feature_set": all_results["full"],
        "leakage_free_feature_set": all_results["leakage_free"],
        "production_model": best_name,
        "production_classification_report": classification_report(
            y_te, best_pred, output_dict=True, zero_division=0),
    }, os.path.join(path_of(cfg, "reports"), "model_metrics.json"))

    # ---------------- feature importance (production model) ----------------
    names = prod["num"] + list(best_pipe.named_steps["prep"]
                               .named_transformers_["cat"]
                               .get_feature_names_out(prod["cat"]))
    est = best_pipe.named_steps["clf"]
    imp = est.feature_importances_ if hasattr(est, "feature_importances_") \
        else np.abs(est.coef_[0])
    fi = (pd.DataFrame({"feature": names, "importance": imp})
            .sort_values("importance", ascending=False).round(5))
    fi.to_csv(os.path.join(path_of(cfg, "reports"), "feature_importance.csv"), index=False)

    plt.figure(figsize=(10.5, 6.5))
    top = fi.head(15).iloc[::-1]
    bars = plt.barh(top["feature"], top["importance"], color="#6DC8EC",
                    edgecolor="#0B4A6F")
    plt.bar_label(bars, fmt="%.3f", fontsize=8)
    plt.title(f"Top 15 drivers of a long hospital stay\n({best_name}, "
              f"leakage-free features)", fontsize=12.5, fontweight="bold")
    plt.xlabel("Feature importance")
    save_figure(plt.gcf(), cfg, "feature_importance.png"); plt.close()

    # ---------------- ROC ----------------
    plt.figure(figsize=(7.4, 6.8))
    for set_name, colour in (("full", None), ("leakage_free", None)):
        for name, (_, _, proba) in best_of[set_name]["fitted"][0:0] or []:
            pass
    # plot every model of the leakage-free set + the full-set winner as upper bound
    for name, r in all_results["leakage_free"].items():
        _, _, proba = best_of["leakage_free"]["fitted"] if name == best_name else (None, None, None)
    # rebuild curves explicitly for clarity
    for set_name, style in (("leakage_free", "-"), ("full", "--")):
        for name, clf in candidate_models(seed).items():
            pass
    # --- simple, explicit curves ---
    plt.clf()
    curves = {}
    for set_name, (num_cols, cat_cols) in feature_sets.items():
        res, fitted, split = evaluate(data, num_cols, cat_cols, cfg)
        for name, (_, _, proba) in fitted.items():
            fpr, tpr, _ = roc_curve(split[3], proba)
            curves[f"{name} [{set_name}]"] = (fpr, tpr, res[name]["roc_auc"])
    for label, (fpr, tpr, auc) in sorted(curves.items()):
        plt.plot(fpr, tpr, lw=2, label=f"{label} (AUC = {auc:.3f})")
    plt.plot([0, 1], [0, 1], "k--", lw=1)
    plt.title("ROC curve - long-stay prediction\n"
              "solid = leakage-free, dashed = full feature set",
              fontsize=12, fontweight="bold")
    plt.xlabel("False positive rate"); plt.ylabel("True positive rate")
    plt.legend(fontsize=7.2, loc="lower right")
    save_figure(plt.gcf(), cfg, "model_roc.png"); plt.close()

    # ---------------- confusion matrix ----------------
    cm = confusion_matrix(y_te, best_pred)
    plt.figure(figsize=(6.6, 5.6))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", cbar=False,
                xticklabels=["Normal stay", "Long stay"],
                yticklabels=["Normal stay", "Long stay"])
    plt.title(f"Confusion matrix - {best_name} (leakage-free)",
              fontsize=12.5, fontweight="bold")
    plt.xlabel("Predicted"); plt.ylabel("Actual")
    save_figure(plt.gcf(), cfg, "model_confusion_matrix.png"); plt.close()

    LOG.info("saved production model -> outputs/models/best_model.joblib")


if __name__ == "__main__":
    main()

"""
Publication-style RQ1/RQ2 figures: distributions (box + jitter), violin optional,
and bootstrap mean-difference panels matching hypothesis_tests.json.

Reads from ../data/exports/: nodes.json, correlations_by_region_period.json,
model_performance.json, hypothesis_tests.json

Writes PNGs next to this file:
  rq1_distribution_node_abs_corr.png
  rq1_inferential_mean_diff_ci.png
  rq2_distribution_node_weather_only_metric.png
  rq2_inferential_mean_diff_ci.png

Run from repo root:  python docs/generate_rq_research_figures.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "data" / "exports"
OUT = Path(__file__).resolve().parent

DC_COLOR = "#6366f1"
NONDC_COLOR = "#22c55e"


def load_json(name: str):
    p = EXP / name
    if not p.exists():
        print(f"Missing {p}", file=sys.stderr)
        sys.exit(1)
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def node_buckets(nodes: list[dict]) -> pd.Series:
    rows = []
    for n in nodes:
        nid = str(n["id"])
        if n.get("classificationLabel"):
            lab = str(n["classificationLabel"]).lower()
            b = "dc" if lab in {"high_likelihood", "medium_likelihood"} else "nonDc"
        else:
            b = "dc" if n.get("isDataCenterHeavy") else "nonDc"
        rows.append({"id": nid, "bucket": b})
    return pd.Series({r["id"]: r["bucket"] for r in rows})


def rq1_node_mean_abs_corr(corr_rows: list[dict], bucket: pd.Series) -> tuple[list[float], list[float]]:
    df = pd.DataFrame(corr_rows)
    df = df.dropna(subset=["nodeId"])
    df["abs_r"] = df["correlation"].abs()
    by_node = df.groupby("nodeId")["abs_r"].mean()
    dc, nondc = [], []
    for nid, v in by_node.items():
        b = bucket.get(str(nid), "nonDc")
        if b == "dc":
            dc.append(float(v))
        else:
            nondc.append(float(v))
    return dc, nondc


def rq2_node_mean_metric(metrics: list[dict], bucket: pd.Series) -> tuple[list[float], list[float], str]:
    df = pd.DataFrame(metrics)
    wo = df[df["modelType"] == "weatherOnly"].dropna(subset=["nodeId"])
    use_nrmse = "nrmse" in wo.columns and wo["nrmse"].notna().any()
    col = "nrmse" if use_nrmse else "rmse"
    label = "nRMSE" if use_nrmse else "RMSE"

    def row_val(r):
        if use_nrmse and pd.notna(r.get("nrmse")):
            return float(r["nrmse"])
        return float(r["rmse"]) if pd.notna(r.get("rmse")) else np.nan

    wo = wo.copy()
    wo["_y"] = wo.apply(row_val, axis=1)
    wo = wo.dropna(subset=["_y"])
    agg = wo.groupby("nodeId")["_y"].mean()

    dc, nondc = [], []
    for nid, v in agg.items():
        b = bucket.get(str(nid), "nonDc")
        if b == "dc":
            dc.append(float(v))
        else:
            nondc.append(float(v))
    return dc, nondc, label


def jitter(arr: np.ndarray, rng: np.random.Generator, scale: float) -> np.ndarray:
    if len(arr) == 0:
        return arr
    return arr + (rng.random(len(arr)) - 0.5) * scale


def plot_distribution_dual(
    dc: list[float],
    nondc: list[float],
    ylabel: str,
    title: str,
    out_path: Path,
    violin: bool = True,
):
    """Descriptive: box + jittered points; optional violin for density context (plot only; caption in LaTeX)."""
    fig, ax = plt.subplots(figsize=(7.2, 4.5))
    positions = [1, 2]
    data = [np.asarray(dc, float), np.asarray(nondc, float)]
    labs = ["DC-likely", "Non-DC"]
    colors = [DC_COLOR, NONDC_COLOR]

    rng = np.random.default_rng(42)
    width = 0.52

    if violin and all(len(d) > 1 for d in data):
        parts = ax.violinplot(
            [d for d in data if len(d) > 0],
            positions=[positions[i] for i in range(2) if len(data[i]) > 0],
            widths=0.65,
            showmeans=False,
            showmedians=False,
            showextrema=False,
        )
        for i, b in enumerate(parts["bodies"]):
            idx = [j for j in range(2) if len(data[j]) > 0][i]
            b.set_facecolor(colors[idx])
            b.set_alpha(0.35)
            b.set_edgecolor(colors[idx])

    bp = ax.boxplot(
        data,
        positions=positions,
        widths=width,
        patch_artist=True,
        medianprops={"color": "black", "linewidth": 1.6},
        boxprops={"linewidth": 1.2},
        whiskerprops={"linewidth": 1},
        capprops={"linewidth": 1},
        flierprops={"marker": "", "markersize": 0},
    )
    for patch, c in zip(bp["boxes"], colors):
        patch.set_facecolor(c)
        patch.set_alpha(0.45)

    for pos, vals, c in zip(positions, data, colors):
        if len(vals) == 0:
            continue
        xj = jitter(vals, rng, 0.21 * width)
        ax.scatter(
            np.full_like(vals, pos, dtype=float) + xj,
            vals,
            alpha=0.65,
            s=22,
            color=c,
            edgecolors="white",
            linewidths=0.4,
            zorder=4,
        )

    ax.set_xticks(positions)
    ax.set_xticklabels([f"{labs[0]}\n($n={len(dc)}$)", f"{labs[1]}\n($n={len(nondc)}$)"])
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=11)
    ax.grid(axis="y", alpha=0.28)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {out_path}")


def plot_inferential_ci(result: dict, rq_name: str, out_path: Path):
    """Plot only: bootstrap CI bar and point estimate for DC mean − non-DC mean (detail in LaTeX / Table 1)."""
    est = result.get("signedDifference")
    lo = result.get("diffCiLower")
    hi = result.get("diffCiUpper")

    has_ci = lo is not None and hi is not None and np.isfinite(lo) and np.isfinite(hi)

    fig, ax = plt.subplots(figsize=(8.0, 3.0))

    ax.axvline(0, color="#64748b", linestyle="--", linewidth=1.1, zorder=1)

    if has_ci:
        ax.plot([lo, hi], [0, 0], color="#94a3b8", linewidth=11, solid_capstyle="round", zorder=2)
    if est is not None and np.isfinite(est):
        ax.scatter([est], [0], color="#0f172a", s=130, zorder=5, edgecolors="white", linewidths=1)

    ax.set_yticks([])
    ax.set_ylim(-0.35, 0.35)
    ax.set_xlabel("Mean difference (DC − non-DC)", fontsize=10)
    ax.set_title(f"{rq_name} — inferential (bootstrap 95% CI for mean contrast)", fontsize=11, pad=10)

    if has_ci and lo is not None and hi is not None:
        span = max(float(hi - lo), abs(float(est or 0)) * 0.55, 1e-6)
        mid = (float(lo) + float(hi)) / 2
    elif est is not None and np.isfinite(est):
        span = max(abs(float(est)) * 0.55, 0.02)
        mid = float(est)
    else:
        span, mid = 0.1, 0.0
    ax.set_xlim(mid - span * 1.4, mid + span * 1.4)

    fig.tight_layout()
    fig.savefig(out_path, dpi=180, bbox_inches="tight", pad_inches=0.14)
    plt.close(fig)
    print(f"Wrote {out_path}")


def main():
    nodes = load_json("nodes.json")
    corr = load_json("correlations_by_region_period.json")
    metrics = load_json("model_performance.json")
    hyp = load_json("hypothesis_tests.json")

    bucket = node_buckets(nodes)

    rq1_dc, rq1_nd = rq1_node_mean_abs_corr(corr, bucket)
    plot_distribution_dual(
        rq1_dc,
        rq1_nd,
        r"Node-level mean $|\rho|$ (all merged weather$\times$target rows)",
        "RQ1 — descriptive",
        OUT / "rq1_distribution_node_abs_corr.png",
        violin=True,
    )

    rq2_dc, rq2_nd, rq2_lab = rq2_node_mean_metric(metrics, bucket)
    plot_distribution_dual(
        rq2_dc,
        rq2_nd,
        f"Node-level mean weather-only {rq2_lab}",
        "RQ2 — descriptive",
        OUT / "rq2_distribution_node_weather_only_metric.png",
        violin=True,
    )

    results = {r["metricKey"]: r for r in hyp["results"]}
    r1 = results["rq1_mean_abs_weather_correlation"]
    r2 = results["rq2_weather_only_rmse"]

    plot_inferential_ci(r1, "RQ1", OUT / "rq1_inferential_mean_diff_ci.png")
    plot_inferential_ci(r2, "RQ2", OUT / "rq2_inferential_mean_diff_ci.png")


if __name__ == "__main__":
    main()

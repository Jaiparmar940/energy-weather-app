"""
Regenerate correlation figures for the Part 4 report from pipeline exports.

Reads:  ../data/exports/correlations_by_region_period.json
Writes: docs/avg_corr_by_bucket_over_time.png
         docs/heavy_vs_nonheavy_shift.png

Run from repo root:
  python docs/generate_report_figures.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CORR_PATH = ROOT / "data" / "exports" / "correlations_by_region_period.json"
OUT_DIR = Path(__file__).resolve().parent


def sem(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) <= 1:
        return 0.0
    return float(np.std(x, ddof=1) / np.sqrt(len(x)))


def load_corr() -> pd.DataFrame:
    if not CORR_PATH.exists():
        print(f"Missing {CORR_PATH}; run build_analysis_exports first.", file=sys.stderr)
        sys.exit(1)
    with CORR_PATH.open(encoding="utf-8") as f:
        rows = json.load(f)
    return pd.DataFrame(rows)


def figure_avg_corr_by_bucket_over_time(df: pd.DataFrame) -> None:
    """Year on x-axis; mean Pearson r (LMP target) by DC vs non-DC bucket with SEM ribbon."""
    d = df[df["target"] == "lmp"].copy()
    d = d[d["isDataCenterHeavyBucket"].isin(["dc", "nonDc"])]
    d["bucket"] = d["isDataCenterHeavyBucket"].map({"dc": "DC-likely", "nonDc": "Non-DC"})

    agg = (
        d.groupby(["year", "bucket"], as_index=False)
        .agg(mean_r=("correlation", "mean"), n=("correlation", "count"))
    )
    # SEM within each year×bucket cell (across node×variable observations)
    sems = (
        d.groupby(["year", "bucket"])["correlation"]
        .apply(lambda s: sem(s.values))
        .reset_index(name="sem")
    )
    agg = agg.merge(sems, on=["year", "bucket"]).sort_values(["year", "bucket"])

    fig, ax = plt.subplots(figsize=(8, 4.5))
    years = sorted(agg["year"].unique())
    colors = {"DC-likely": "#6366f1", "Non-DC": "#22c55e"}
    for bucket in ["DC-likely", "Non-DC"]:
        sub = agg[agg["bucket"] == bucket].set_index("year").reindex(years)
        y = sub["mean_r"].values
        e = sub["sem"].fillna(0).values
        ax.plot(years, y, marker="o", label=bucket, color=colors[bucket])
        ax.fill_between(years, y - e, y + e, alpha=0.18, color=colors[bucket])

    ax.set_xlabel("Year")
    ax.set_ylabel(r"Mean Pearson $r$ (weather vs.\ day-ahead LMP)")
    ax.set_title("Mean weather--LMP correlation by bucket over time")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    out = OUT_DIR / "avg_corr_by_bucket_over_time.png"
    fig.savefig(out, dpi=160)
    plt.close(fig)
    print(f"Wrote {out}")


def figure_heavy_vs_nonheavy_shift(df: pd.DataFrame) -> None:
    """Bar chart: mean shift (recentAI aggregate minus earlyAI aggregate) per weather variable."""
    d = df[df["target"] == "lmp"].copy()
    d = d[d["isDataCenterHeavyBucket"].isin(["dc", "nonDc"])]
    variables = sorted(d["variable"].unique())

    shifts = {"dc": [], "nonDc": [], "dc_err": [], "nonDc_err": []}
    for var in variables:
        for bucket in ["dc", "nonDc"]:
            sub = d[(d["variable"] == var) & (d["isDataCenterHeavyBucket"] == bucket)]
            early = sub[sub["period"] == "earlyAI"]["correlation"].values
            recent = sub[sub["period"] == "recentAI"]["correlation"].values
            m_e = np.nanmean(early) if len(early) else np.nan
            m_r = np.nanmean(recent) if len(recent) else np.nan
            shift = m_r - m_e if np.isfinite(m_e) and np.isfinite(m_r) else np.nan
            se = np.sqrt(sem(early) ** 2 + sem(recent) ** 2) if len(early) and len(recent) else 0.0
            shifts[bucket].append(shift)
            shifts[f"{bucket}_err"].append(se)

    x = np.arange(len(variables))
    w = 0.36
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.bar(x - w / 2, shifts["dc"], width=w, yerr=shifts["dc_err"], label="DC-likely", color="#6366f1", capsize=3)
    ax.bar(x + w / 2, shifts["nonDc"], width=w, yerr=shifts["nonDc_err"], label="Non-DC", color="#22c55e", capsize=3)
    ax.axhline(0, color="#64748b", lw=1)
    ax.set_xticks(x)
    ax.set_xticklabels(variables, rotation=25, ha="right")
    ax.set_ylabel(r"$\Delta r$: mean(recentAI) $-$ mean(earlyAI)")
    ax.set_title("Shift in weather--LMP correlation between periods (by bucket)")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    out = OUT_DIR / "heavy_vs_nonheavy_shift.png"
    fig.savefig(out, dpi=160)
    plt.close(fig)
    print(f"Wrote {out}")


def main():
    df = load_corr()
    figure_avg_corr_by_bucket_over_time(df)
    figure_heavy_vs_nonheavy_shift(df)


if __name__ == "__main__":
    main()

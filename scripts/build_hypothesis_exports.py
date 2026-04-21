import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
EXPORTS_DIR = ROOT / "data" / "exports"


@dataclass
class InferenceConfig:
    min_group_n_for_inference: int = 5
    min_total_n_for_inference: int = 15
    min_group_n_for_permutation: int = 8
    min_group_n_for_bootstrap: int = 5
    permutation_count: int = 3000
    bootstrap_iterations: int = 5000
    random_seed: int = 42
    alpha: float = 0.05
    severe_imbalance_ratio: float = 3.0


def _read_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def _mean(vals: np.ndarray) -> float:
    return float(np.mean(vals)) if len(vals) else 0.0


def _safe_std(vals: np.ndarray) -> float | None:
    if len(vals) < 2:
        return None
    return float(np.std(vals, ddof=1))


def _safe_iqr(vals: np.ndarray) -> float | None:
    if len(vals) < 2:
        return None
    q1 = np.percentile(vals, 25)
    q3 = np.percentile(vals, 75)
    return float(q3 - q1)


def _relative_diff_pct(dc_mean: float, non_dc_mean: float) -> float | None:
    if non_dc_mean == 0:
        return None
    return float(((dc_mean - non_dc_mean) / abs(non_dc_mean)) * 100.0)


def _cohens_d(dc_vals: np.ndarray, non_dc_vals: np.ndarray) -> float | None:
    if len(dc_vals) < 2 or len(non_dc_vals) < 2:
        return None
    dc_std = np.std(dc_vals, ddof=1)
    non_std = np.std(non_dc_vals, ddof=1)
    pooled_num = ((len(dc_vals) - 1) * dc_std**2) + ((len(non_dc_vals) - 1) * non_std**2)
    pooled_den = len(dc_vals) + len(non_dc_vals) - 2
    if pooled_den <= 0:
        return None
    pooled = np.sqrt(pooled_num / pooled_den)
    if pooled == 0:
        return None
    return float((_mean(dc_vals) - _mean(non_dc_vals)) / pooled)


def _bootstrap_ci(
    rng: np.random.Generator,
    dc_vals: np.ndarray,
    non_dc_vals: np.ndarray,
    iterations: int,
) -> tuple[float | None, float | None]:
    if len(dc_vals) == 0 or len(non_dc_vals) == 0:
        return None, None
    diffs = np.empty(iterations, dtype=float)
    for i in range(iterations):
        dc_sample = rng.choice(dc_vals, size=len(dc_vals), replace=True)
        non_sample = rng.choice(non_dc_vals, size=len(non_dc_vals), replace=True)
        diffs[i] = float(np.mean(dc_sample) - np.mean(non_sample))
    return float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))


def _permutation_p_value(
    rng: np.random.Generator,
    dc_vals: np.ndarray,
    non_dc_vals: np.ndarray,
    permutations: int,
) -> float:
    observed = abs(float(np.mean(dc_vals) - np.mean(non_dc_vals)))
    pooled = np.concatenate([dc_vals, non_dc_vals]).copy()
    n_dc = len(dc_vals)
    extreme = 0
    # We permute group labels across node-level observations under H0 of exchangeability.
    for _ in range(permutations):
        rng.shuffle(pooled)
        a = pooled[:n_dc]
        b = pooled[n_dc:]
        diff = abs(float(np.mean(a) - np.mean(b)))
        if diff >= observed:
            extreme += 1
    return float((extreme + 1) / (permutations + 1))


def _build_metric_entry(
    config: InferenceConfig,
    rng: np.random.Generator,
    metric_key: str,
    metric_label: str,
    question: str,
    dc_vals: list[float],
    non_dc_vals: list[float],
    notes: list[str],
) -> dict:
    dc_arr = np.asarray(dc_vals, dtype=float)
    non_arr = np.asarray(non_dc_vals, dtype=float)

    n_dc = int(len(dc_arr))
    n_non = int(len(non_arr))
    n_total = n_dc + n_non

    dc_mean = _mean(dc_arr)
    non_mean = _mean(non_arr)
    signed_diff = dc_mean - non_mean
    abs_diff = abs(signed_diff)

    warnings: list[str] = []
    warnings.extend(notes)

    inference_eligible = (
        n_dc >= config.min_group_n_for_inference
        and n_non >= config.min_group_n_for_inference
        and n_total >= config.min_total_n_for_inference
    )
    permutation_eligible = (
        inference_eligible
        and n_dc >= config.min_group_n_for_permutation
        and n_non >= config.min_group_n_for_permutation
    )
    bootstrap_eligible = (
        n_dc >= config.min_group_n_for_bootstrap and n_non >= config.min_group_n_for_bootstrap
    )

    if not inference_eligible:
        warnings.append("Group sample size below minimum threshold for inferential testing.")

    if n_dc == 0 or n_non == 0:
        warnings.append("One comparison group has zero observations.")

    imbalance_ratio = float(max(n_dc, n_non) / max(1, min(n_dc, n_non)))
    if min(n_dc, n_non) > 0 and imbalance_ratio >= config.severe_imbalance_ratio:
        warnings.append(
            "Severe group-size imbalance; interpret inferential results with caution."
        )

    diff_ci_lower, diff_ci_upper = (None, None)
    if bootstrap_eligible:
        diff_ci_lower, diff_ci_upper = _bootstrap_ci(
            rng, dc_arr, non_arr, config.bootstrap_iterations
        )
    else:
        warnings.append("Bootstrap CI unavailable due to small group size.")

    p_value = None
    if permutation_eligible:
        p_value = _permutation_p_value(rng, dc_arr, non_arr, config.permutation_count)
    elif inference_eligible:
        warnings.append("Permutation test unavailable: group sizes below permutation threshold.")

    effect_size = _cohens_d(dc_arr, non_arr)
    if effect_size is None:
        warnings.append("Standardized effect size unavailable (insufficient variance or sample size).")

    if not inference_eligible:
        result_label = "Descriptive only"
    elif p_value is None:
        result_label = "Inference limited"
    elif p_value < config.alpha:
        result_label = "Statistically significant difference"
    else:
        result_label = "No statistically significant difference"

    return {
        "metricKey": metric_key,
        "metricLabel": metric_label,
        "question": question,
        "dcMean": dc_mean,
        "nonDcMean": non_mean,
        "absoluteDifference": abs_diff,
        "signedDifference": signed_diff,
        "relativeDifferencePct": _relative_diff_pct(dc_mean, non_mean),
        "dcMedian": float(np.median(dc_arr)) if n_dc else None,
        "nonDcMedian": float(np.median(non_arr)) if n_non else None,
        "dcStd": _safe_std(dc_arr),
        "nonDcStd": _safe_std(non_arr),
        "dcIqr": _safe_iqr(dc_arr),
        "nonDcIqr": _safe_iqr(non_arr),
        "nDc": n_dc,
        "nNonDc": n_non,
        "diffCiLower": diff_ci_lower,
        "diffCiUpper": diff_ci_upper,
        "bootstrapIterations": config.bootstrap_iterations if bootstrap_eligible else 0,
        "standardizedEffectSize": effect_size,
        "effectSizeLabel": "Cohen_d" if effect_size is not None else "Unavailable",
        "pValue": p_value,
        "testType": "two-sided permutation",
        "permutationCount": config.permutation_count if permutation_eligible else 0,
        "inferenceEligible": inference_eligible,
        "testEligible": permutation_eligible,
        "significantAt05": (p_value < config.alpha) if p_value is not None else None,
        "resultLabel": result_label,
        "warnings": warnings,
    }


def build_rq1_values(correlations: pd.DataFrame, nodes: pd.DataFrame) -> tuple[list[float], list[float], list[str]]:
    notes = [
        "RQ1 uses node-level mean absolute weather correlation as a descriptive comparison.",
        "Correlation magnitude does not establish causality or temporal mechanism by itself.",
    ]
    node_bucket = nodes.set_index("id")["bucket"]
    by_node = correlations.groupby("nodeId")["correlation"].apply(
        lambda s: float(np.mean(np.abs(s.values)))
    )
    dc_vals: list[float] = []
    non_dc_vals: list[float] = []
    for node_id, value in by_node.items():
        bucket = node_bucket.get(str(node_id), "nonDc")
        if bucket == "dc":
            dc_vals.append(float(value))
        else:
            non_dc_vals.append(float(value))
    if len(dc_vals) <= 1:
        notes.append("Insufficient DC node count for robust inferential RQ1 comparison.")
    return dc_vals, non_dc_vals, notes


def build_rq2_values(model_metrics: pd.DataFrame) -> tuple[list[float], list[float], list[str]]:
    notes = [
        "RQ2 compares out-of-sample weather-only RMSE across node-level model-performance observations.",
    ]
    weather_only = model_metrics[model_metrics["modelType"] == "weatherOnly"].copy()
    dc = weather_only[weather_only["isDataCenterHeavyBucket"] == "dc"]
    non = weather_only[weather_only["isDataCenterHeavyBucket"] == "nonDc"]
    # Prefer normalized metric for scale fairness when available.
    if "nrmse" in weather_only.columns and weather_only["nrmse"].notna().any():
        metric_col = "nrmse"
        notes.append("RQ2 uses normalized RMSE (nRMSE) for cross-node scale comparability.")
    else:
        metric_col = "rmse"
        notes.append("nRMSE unavailable for some rows; raw RMSE comparison used.")
    return (
        dc[metric_col].dropna().astype(float).tolist(),
        non[metric_col].dropna().astype(float).tolist(),
        notes,
    )


def main():
    config = InferenceConfig()
    rng = np.random.default_rng(config.random_seed)

    nodes_path = EXPORTS_DIR / "nodes.json"
    corr_path = EXPORTS_DIR / "correlations_by_region_period.json"
    model_path = EXPORTS_DIR / "model_performance.json"
    out_path = EXPORTS_DIR / "hypothesis_tests.json"

    if not nodes_path.exists() or not corr_path.exists() or not model_path.exists():
        raise FileNotFoundError("Required exports missing. Run metadata/correlation/model scripts first.")

    nodes = pd.read_json(nodes_path)
    correlations = pd.read_json(corr_path)
    model_metrics = pd.read_json(model_path)

    nodes["id"] = nodes["id"].astype(str)
    if "classificationLabel" in nodes.columns:
        nodes["bucket"] = nodes["classificationLabel"].map(
            lambda x: "dc" if str(x).lower() in {"high_likelihood", "medium_likelihood"} else "nonDc"
        )
    else:
        nodes["bucket"] = nodes["isDataCenterHeavy"].map(lambda x: "dc" if bool(x) else "nonDc")

    rq1_dc, rq1_non, rq1_notes = build_rq1_values(correlations, nodes)
    rq2_dc, rq2_non, rq2_notes = build_rq2_values(model_metrics)

    entries = [
        _build_metric_entry(
            config=config,
            rng=rng,
            metric_key="rq1_mean_abs_weather_correlation",
            metric_label="Mean |weather correlation| per node",
            question="RQ1",
            dc_vals=rq1_dc,
            non_dc_vals=rq1_non,
            notes=rq1_notes,
        ),
        _build_metric_entry(
            config=config,
            rng=rng,
            metric_key="rq2_weather_only_rmse",
            metric_label="Weather-only error metric",
            question="RQ2",
            dc_vals=rq2_dc,
            non_dc_vals=rq2_non,
            notes=rq2_notes,
        ),
    ]

    payload = {
        "metadata": {
            "alpha": config.alpha,
            "minGroupNForInference": config.min_group_n_for_inference,
            "minTotalNForInference": config.min_total_n_for_inference,
            "minGroupNForPermutation": config.min_group_n_for_permutation,
            "minGroupNForBootstrap": config.min_group_n_for_bootstrap,
            "permutationCount": config.permutation_count,
            "bootstrapIterations": config.bootstrap_iterations,
            "randomSeed": config.random_seed,
        },
        "results": entries,
    }
    _write_json(out_path, payload)
    print(f"Wrote {len(entries)} hypothesis test entries to {out_path}")


if __name__ == "__main__":
    main()


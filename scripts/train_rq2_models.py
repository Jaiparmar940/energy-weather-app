import argparse
import json
import math
import os
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Lasso, LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from pandas.errors import DtypeWarning

from build_analysis_exports import (
    cooling_degree_hours,
    heating_degree_hours,
    infer_period,
    parse_noaa_dew_c,
    parse_noaa_precip_mm_from_aa1,
    parse_noaa_slp_hpa,
    parse_noaa_tmp_c,
    parse_noaa_wind_speed_ms,
    relative_humidity_pct,
)


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DATA = ROOT / "data" / "exports"


def resolve_data_root() -> Path:
    env = os.environ.get("PJM_DATA_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    return ROOT / "data" / "pjm data"


DATA_ROOT = resolve_data_root()


def _write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def parse_args():
    ap = argparse.ArgumentParser(description="Train weather-heavy RQ2 models and export metrics JSON.")
    ap.add_argument("--years", type=int, nargs="+", default=[2021, 2022, 2023, 2024, 2025])
    ap.add_argument("--base-c", type=float, default=18.0)
    ap.add_argument("--limit-nodes", type=int, default=20)
    ap.add_argument("--test-start-year", type=int, default=2024)
    ap.add_argument("--max-da-files-per-year", type=int, default=30)
    ap.add_argument("--balanced-dc", action="store_true", help="Mix DC-heavy and non-DC-heavy nodes.")
    ap.add_argument("--dc-ratio", type=float, default=0.5, help="Target DC-heavy ratio when --balanced-dc is set.")
    ap.add_argument("--prefer-dc-heavy", action="store_true", help="Sort nodes to prioritize DC-heavy records.")
    ap.add_argument("--output", default=str(PUBLIC_DATA / "model_performance.json"))
    return ap.parse_args()


def build_models():
    # Six models provide an expanded suite with both linear and nonlinear behavior.
    return {
        "LinearRegression": Pipeline(
            [("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler()), ("model", LinearRegression())]
        ),
        "Ridge": Pipeline(
            [("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler()), ("model", Ridge(alpha=1.0))]
        ),
        "Lasso": Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                ("model", Lasso(alpha=0.001, max_iter=5000)),
            ]
        ),
        "RandomForest": Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("model", RandomForestRegressor(n_estimators=90, random_state=42, n_jobs=-1)),
            ]
        ),
        "GradientBoosting": Pipeline(
            [("imputer", SimpleImputer(strategy="median")), ("model", GradientBoostingRegressor(random_state=42))]
        ),
        "ExtraTrees": Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("model", ExtraTreesRegressor(n_estimators=100, random_state=42, n_jobs=-1)),
            ]
        ),
    }


def to_utc_ept(col: pd.Series) -> pd.Series:
    ts = pd.to_datetime(col, errors="coerce")
    ts = ts.dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT")
    return ts.dt.tz_convert("UTC")


def load_weather_for_station(station_id: str, years: list[int], base_c: float) -> pd.DataFrame:
    frames = []
    weather_dir = ROOT / "data" / "noaa_isd_global_hourly" / str(station_id)
    for year in years:
        weather_csv = weather_dir / f"{station_id}_{year}.csv"
        if not weather_csv.exists():
            continue
        w = pd.read_csv(
            weather_csv,
            low_memory=False,
            usecols=lambda c: c in {"DATE", "TMP", "DEW", "SLP", "WND", "AA1"},
        )
        if "DATE" not in w.columns or "TMP" not in w.columns:
            continue
        w["timestamp"] = pd.to_datetime(w["DATE"], errors="coerce")
        w["timestamp"] = w["timestamp"].dt.tz_localize("UTC", nonexistent="NaT", ambiguous="NaT")
        w["temp_c"] = w["TMP"].map(parse_noaa_tmp_c)
        w["dew_c"] = w["DEW"].map(parse_noaa_dew_c) if "DEW" in w.columns else np.nan
        w["slp_hpa"] = w["SLP"].map(parse_noaa_slp_hpa) if "SLP" in w.columns else np.nan
        w["wind_ms"] = w["WND"].map(parse_noaa_wind_speed_ms) if "WND" in w.columns else np.nan
        w["precip_mm"] = w["AA1"].map(parse_noaa_precip_mm_from_aa1) if "AA1" in w.columns else np.nan
        w = w.dropna(subset=["timestamp", "temp_c"]).copy()
        w["cdh"] = w["temp_c"].map(lambda t: cooling_degree_hours(t, base_c=base_c))
        w["hdh"] = w["temp_c"].map(lambda t: heating_degree_hours(t, base_c=base_c))
        w["rh_pct"] = w.apply(
            lambda r: relative_humidity_pct(r["temp_c"], r["dew_c"]) if pd.notna(r["dew_c"]) else np.nan,
            axis=1,
        )
        frames.append(
            w[["timestamp", "temp_c", "dew_c", "rh_pct", "wind_ms", "slp_hpa", "precip_mm", "cdh", "hdh"]]
        )
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
    return out


def load_lmp_for_node(node_id: int, years: list[int], max_da_files_per_year: int) -> pd.DataFrame:
    da_dir = DATA_ROOT / "pjm_da_full_system_parquet"
    frames = []
    for year in years:
        files = sorted(da_dir.glob(f"da_lmp_*{year}*.parquet"))[:max_da_files_per_year]
        for file in files:
            df = pd.read_parquet(file, columns=["datetime_beginning_utc", "pnode_id", "total_lmp_da", "zone"])
            df = df[df["pnode_id"] == node_id]
            if df.empty:
                continue
            df["timestamp"] = pd.to_datetime(df["datetime_beginning_utc"], errors="coerce")
            df["timestamp"] = df["timestamp"].dt.tz_localize("UTC", nonexistent="NaT", ambiguous="NaT")
            df = df.dropna(subset=["timestamp", "total_lmp_da"])
            frames.append(df[["timestamp", "total_lmp_da", "zone"]])
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).sort_values("timestamp")


def load_forecast_for_zone(zone: str, years: list[int]) -> pd.DataFrame:
    load_dir = DATA_ROOT / "pjm_load_yearly_clean"
    frames = []
    zone_norm = str(zone).strip().upper()
    for year in years:
        path = load_dir / f"pjm_load_forecast_{year}_clean.parquet"
        if not path.exists():
            continue
        df = pd.read_parquet(path, columns=["forecast_area", "forecast_hour_beginning_ept", "forecast_load_mw"])
        area = df["forecast_area"].astype(str).str.strip().str.upper()
        df = df[area == zone_norm]
        if df.empty:
            continue
        df["timestamp"] = to_utc_ept(df["forecast_hour_beginning_ept"])
        df = df.dropna(subset=["timestamp", "forecast_load_mw"])
        frames.append(df[["timestamp", "forecast_load_mw"]])
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).sort_values("timestamp")


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["hour"] = out["timestamp"].dt.hour
    out["month"] = out["timestamp"].dt.month
    out["day_of_week"] = out["timestamp"].dt.dayofweek
    out["period"] = out["timestamp"].map(infer_period)
    out["year"] = out["timestamp"].dt.year
    return out


def metrics_row(y_true: np.ndarray, y_pred: np.ndarray) -> tuple[float, float, float]:
    rmse = float(math.sqrt(mean_squared_error(y_true, y_pred)))
    mae = float(mean_absolute_error(y_true, y_pred))
    r2 = float(r2_score(y_true, y_pred))
    return rmse, mae, r2


def evaluate_for_target(
    df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str,
    model_type: str,
    node_id: str,
    region_id: str,
    bucket: str,
    test_start_year: int,
) -> list[dict]:
    rows: list[dict] = []
    train = df[df["year"] < test_start_year].copy()
    test = df[df["year"] >= test_start_year].copy()
    if len(train) < 200 or len(test) < 100:
        return rows

    available_cols = [c for c in feature_cols if c in train.columns and train[c].notna().any()]
    if len(available_cols) < 3:
        return rows
    X_train = train[available_cols]
    y_train = train[target_col]
    X_test = test[available_cols]
    y_test = test[target_col]

    for model_name, model in build_models().items():
        model.fit(X_train, y_train)
        pred = model.predict(X_test)
        eval_df = test[["period"]].copy()
        eval_df["y_true"] = y_test.values
        eval_df["y_pred"] = pred
        for period, grp in eval_df.groupby("period"):
            if len(grp) < 24:
                continue
            rmse, mae, r2 = metrics_row(grp["y_true"].to_numpy(), grp["y_pred"].to_numpy())
            target_mean = float(np.mean(grp["y_true"].to_numpy()))
            nrmse = (rmse / abs(target_mean)) if abs(target_mean) > 1e-9 else None
            rows.append(
                {
                    "nodeId": node_id,
                    "regionId": region_id,
                    "period": period,
                    "isDataCenterHeavyBucket": bucket,
                    "modelType": model_type,
                    "modelName": model_name,
                    "target": "lmp" if target_col == "total_lmp_da" else "load",
                    "split": "test",
                    "nSamples": int(len(grp)),
                    "targetMean": target_mean,
                    "rmse": rmse,
                    "nrmse": nrmse,
                    "mae": mae,
                    "r2": r2,
                }
            )
    return rows


def main():
    warnings.filterwarnings("ignore", category=DtypeWarning)
    warnings.filterwarnings("ignore", category=UserWarning, module="sklearn.impute")
    warnings.filterwarnings("ignore", category=FutureWarning)
    args = parse_args()
    nodes_path = PUBLIC_DATA / "nodes.json"
    station_map_path = ROOT / "data" / "node_to_isd_station.json"
    if not nodes_path.exists():
        raise FileNotFoundError(f"Missing {nodes_path}. Run scripts/export_pjm_metadata.py first.")
    if not station_map_path.exists():
        raise FileNotFoundError(f"Missing {station_map_path}. Run scripts/noaa_isd_pull.py first.")

    nodes = pd.read_json(nodes_path).copy()
    nodes["id"] = nodes["id"].astype(str)
    if args.balanced_dc and args.limit_nodes > 0:
        dc_nodes = nodes[nodes.get("isDataCenterHeavy") == True].sort_values(by=["regionId", "id"]).copy()
        non_dc_nodes = nodes[nodes.get("isDataCenterHeavy") != True].sort_values(by=["regionId", "id"]).copy()
        ratio = max(0.0, min(1.0, float(args.dc_ratio)))
        dc_target = int(round(args.limit_nodes * ratio))
        non_dc_target = args.limit_nodes - dc_target
        nodes = pd.concat([dc_nodes.head(dc_target), non_dc_nodes.head(non_dc_target)], ignore_index=True)
    else:
        if args.prefer_dc_heavy:
            nodes = nodes.sort_values(by=["isDataCenterHeavy", "regionId", "id"], ascending=[False, True, True]).copy()
        nodes = nodes.head(args.limit_nodes).copy()
    station_map = pd.read_json(station_map_path)
    station_map["nodeId"] = station_map["nodeId"].astype(str)
    station_map = station_map.set_index("nodeId")

    all_rows: list[dict] = []
    weather_cols = ["temp_c", "dew_c", "rh_pct", "wind_ms", "slp_hpa", "precip_mm", "cdh", "hdh"]
    time_cols = ["hour", "month", "day_of_week"]
    for _, node in nodes.iterrows():
        node_id = str(node["id"])
        if node_id not in station_map.index:
            continue
        station = station_map.loc[node_id]
        station_id = station.get("fileId") or station.get("stationId")
        if not station_id:
            continue
        region_id = str(node["regionId"])
        label = str(node.get("classificationLabel") or "").strip().lower()
        if label in {"high_likelihood", "medium_likelihood"}:
            bucket = "dc"
        else:
            bucket = "dc" if bool(node.get("isDataCenterHeavy", False)) else "nonDc"

        weather = load_weather_for_station(str(station_id), args.years, args.base_c)
        if weather.empty:
            continue
        lmp = load_lmp_for_node(int(node_id), args.years, args.max_da_files_per_year)
        load = load_forecast_for_zone(region_id, args.years)
        if lmp.empty and load.empty:
            continue

        base = weather.sort_values("timestamp")
        if not lmp.empty:
            base = pd.merge_asof(
                base,
                lmp[["timestamp", "total_lmp_da"]].sort_values("timestamp"),
                on="timestamp",
                direction="nearest",
                tolerance=pd.Timedelta("30min"),
            )
        if not load.empty:
            base = pd.merge_asof(
                base,
                load.sort_values("timestamp"),
                on="timestamp",
                direction="nearest",
                tolerance=pd.Timedelta("30min"),
            )
        base = add_time_features(base).dropna(subset=["timestamp"]).copy()

        base["is_dc"] = 1 if bucket == "dc" else 0
        base["cdh_x_dc"] = base["cdh"] * base["is_dc"]
        base["hdh_x_dc"] = base["hdh"] * base["is_dc"]

        weather_only = weather_cols + time_cols
        weather_plus_dc = weather_only + ["is_dc", "cdh_x_dc", "hdh_x_dc"]

        if "total_lmp_da" in base.columns:
            lmp_df = base.dropna(subset=["total_lmp_da"]).copy()
            all_rows.extend(
                evaluate_for_target(
                    lmp_df, weather_only, "total_lmp_da", "weatherOnly", node_id, region_id, bucket, args.test_start_year
                )
            )
            all_rows.extend(
                evaluate_for_target(
                    lmp_df, weather_plus_dc, "total_lmp_da", "weatherPlusDc", node_id, region_id, bucket, args.test_start_year
                )
            )
        if "forecast_load_mw" in base.columns:
            load_df = base.dropna(subset=["forecast_load_mw"]).copy()
            all_rows.extend(
                evaluate_for_target(
                    load_df, weather_only, "forecast_load_mw", "weatherOnly", node_id, region_id, bucket, args.test_start_year
                )
            )
            all_rows.extend(
                evaluate_for_target(
                    load_df, weather_plus_dc, "forecast_load_mw", "weatherPlusDc", node_id, region_id, bucket, args.test_start_year
                )
            )

    out = Path(args.output)
    _write_json(out, all_rows)
    print(f"Wrote {len(all_rows)} model metric rows to {out}")


if __name__ == "__main__":
    main()

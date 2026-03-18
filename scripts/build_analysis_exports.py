import json
import math
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = Path(r"C:\Users\Jaipa\OneDrive\Desktop\GridIntelligence-1\Data")

PUBLIC_DATA = ROOT / "public" / "data"


def _read_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def parse_noaa_tmp_c(x: str) -> float | None:
    # global-hourly TMP is like "+0123,1" (tenths of °C, quality code after comma)
    # docs: https://www.ncei.noaa.gov/data/global-hourly/doc/isd-format-document.pdf
    if not isinstance(x, str):
        return None
    if "," not in x:
        return None
    val, _qc = x.split(",", 1)
    val = val.strip()
    if val in {"+9999", "9999", "-9999"}:
        return None
    try:
        return int(val) / 10.0
    except Exception:
        return None


def parse_noaa_dew_c(x: str) -> float | None:
    # DEW uses same encoding as TMP: "+0123,1" (tenths of °C)
    return parse_noaa_tmp_c(x)


def parse_noaa_slp_hpa(x: str) -> float | None:
    # SLP like "10132,1" (tenths of hPa) or "99999,9" missing
    if not isinstance(x, str) or "," not in x:
        return None
    val, _qc = x.split(",", 1)
    val = val.strip()
    if val in {"99999", "+99999", "-99999"}:
        return None
    try:
        return int(val) / 10.0
    except Exception:
        return None


def parse_noaa_wind_speed_ms(x: str) -> float | None:
    # WND like "ddd,ss,fff,qq" where fff is wind speed in m/s * 10
    # Example: "180,1,N,0010,1" is also seen in some exports; handle robustly by taking 4th field if present.
    if not isinstance(x, str):
        return None
    parts = x.split(",")
    if len(parts) < 4:
        return None
    spd = parts[3].strip()
    if spd in {"9999", "+9999", "-9999"}:
        return None
    try:
        return int(spd) / 10.0
    except Exception:
        return None


def parse_noaa_precip_mm_from_aa1(x: str) -> float | None:
    # AA1 like "01,0000,1,99" (period hours, depth mm * 10, qc, trace)
    if not isinstance(x, str):
        return None
    parts = x.split(",")
    if len(parts) < 2:
        return None
    depth = parts[1].strip()
    if depth in {"9999", "+9999", "-9999"}:
        return None
    try:
        return int(depth) / 10.0
    except Exception:
        return None


def relative_humidity_pct(temp_c: float, dew_c: float) -> float | None:
    # Magnus formula approximation
    try:
        a = 17.625
        b = 243.04
        es = math.exp((a * temp_c) / (b + temp_c))
        e = math.exp((a * dew_c) / (b + dew_c))
        rh = 100.0 * (e / es)
        return max(0.0, min(100.0, rh))
    except Exception:
        return None


def cooling_degree_hours(temp_c: float, base_c: float = 18.0) -> float:
    return max(0.0, temp_c - base_c)


def heating_degree_hours(temp_c: float, base_c: float = 18.0) -> float:
    return max(0.0, base_c - temp_c)


def infer_period(ts: pd.Timestamp) -> str:
    y = ts.year
    if y <= 2017:
        return "preAI"
    if y <= 2021:
        return "earlyAI"
    return "recentAI"


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--append", action="store_true", help="Append/merge into existing export JSON instead of overwriting")
    ap.add_argument("--limit-nodes", type=int, default=10)
    ap.add_argument("--max-points", type=int, default=20000)
    ap.add_argument("--base-c", type=float, default=18.0)
    ap.add_argument("--prefer-dc-heavy", action="store_true", help="Prioritize nodes where isDataCenterHeavy=true")
    ap.add_argument("--dc-only", action="store_true", help="Only compute correlations for DC-heavy nodes")
    args = ap.parse_args()

    nodes_path = PUBLIC_DATA / "nodes.json"
    if not nodes_path.exists():
        raise FileNotFoundError(f"Missing {nodes_path}. Run scripts/export_pjm_metadata.py first.")

    station_map_path = ROOT / "data" / "node_to_isd_station.json"
    if not station_map_path.exists():
        raise FileNotFoundError(
            f"Missing {station_map_path}. Run scripts/noaa_isd_pull.py first."
        )

    nodes = pd.read_json(nodes_path)
    nodes["id"] = nodes["id"].astype(str)
    if args.dc_only:
        nodes = nodes[nodes.get("isDataCenterHeavy") == True].copy()
    if args.prefer_dc_heavy:
        nodes = nodes.sort_values(
            by=["isDataCenterHeavy", "regionId", "id"], ascending=[False, True, True]
        ).copy()
    nodes = nodes.head(args.limit_nodes).copy()
    station_map = pd.read_json(station_map_path)
    station_map["nodeId"] = station_map["nodeId"].astype(str)
    station_map = station_map.set_index("nodeId")

    # Load PJM DA LMP for the chosen year (all parquet files; we’ll sample rows to keep it light).
    da_dir = DATA_ROOT / "pjm_da_full_system_parquet"
    da_files = sorted(da_dir.glob(f"da_lmp_*{args.year}*.parquet"))
    if not da_files:
        raise FileNotFoundError(f"No DA LMP parquet files found for year={args.year} in {da_dir}")

    all_corr_rows: list[dict] = []
    all_case_studies: dict[str, list[dict]] = {}

    for _, node in nodes.iterrows():
        node_id = str(node["id"])
        if node_id not in station_map.index:
            continue
        station_id = station_map.loc[node_id].get("fileId") or station_map.loc[node_id]["stationId"]

        # Read weather CSVs for this station/year.
        weather_dir = ROOT / "data" / "noaa_isd_global_hourly" / str(station_id)
        weather_csv = weather_dir / f"{station_id}_{args.year}.csv"
        if not weather_csv.exists():
            continue

        # Some stations/years won't include every optional column (e.g., AA1). Load flexibly.
        w = pd.read_csv(weather_csv)
        for required in ["DATE", "TMP"]:
            if required not in w.columns:
                raise ValueError(f"Missing required NOAA column {required} in {weather_csv}")
        # NOAA global-hourly DATE is UTC (ISO-like). Parse and localize to UTC.
        w["timestamp"] = pd.to_datetime(w["DATE"], errors="coerce")
        w["timestamp"] = w["timestamp"].dt.tz_localize("UTC", nonexistent="NaT", ambiguous="NaT")
        w["temp_c"] = w["TMP"].map(parse_noaa_tmp_c)
        w["dew_c"] = w["DEW"].map(parse_noaa_dew_c) if "DEW" in w.columns else None
        w["slp_hpa"] = w["SLP"].map(parse_noaa_slp_hpa) if "SLP" in w.columns else None
        w["wind_ms"] = w["WND"].map(parse_noaa_wind_speed_ms) if "WND" in w.columns else None
        w["precip_mm"] = w["AA1"].map(parse_noaa_precip_mm_from_aa1) if "AA1" in w.columns else None
        w = w.dropna(subset=["timestamp", "temp_c"]).copy()
        w["cdh"] = w["temp_c"].map(lambda t: cooling_degree_hours(t, base_c=args.base_c))
        w["hdh"] = w["temp_c"].map(lambda t: heating_degree_hours(t, base_c=args.base_c))
        w["rh_pct"] = w.apply(
            lambda r: relative_humidity_pct(r["temp_c"], r["dew_c"])
            if pd.notna(r["dew_c"])
            else None,
            axis=1,
        )
        w = w[
            [
                "timestamp",
                "temp_c",
                "dew_c",
                "rh_pct",
                "wind_ms",
                "slp_hpa",
                "precip_mm",
                "cdh",
                "hdh",
            ]
        ]

        # Load PJM DA LMP rows for this pnode across all files in year; sample to keep runtime down.
        pnode_id_int = int(node_id)
        lmp_frames = []
        for f in da_files:
            df = pd.read_parquet(f, engine="pyarrow", columns=["datetime_beginning_utc", "pnode_id", "total_lmp_da", "zone"])
            df = df[df["pnode_id"] == pnode_id_int]
            if df.empty:
                continue
            # PJM parquet field is labeled *_utc but stored as a string without tz info.
            # Parse as naive then localize to UTC to align with NOAA timestamps.
            df["timestamp"] = pd.to_datetime(df["datetime_beginning_utc"], errors="coerce")
            df["timestamp"] = df["timestamp"].dt.tz_localize("UTC", nonexistent="NaT", ambiguous="NaT")
            df = df.dropna(subset=["timestamp"])
            lmp_frames.append(df[["timestamp", "total_lmp_da", "zone"]])
        if not lmp_frames:
            continue
        lmp = pd.concat(lmp_frames, ignore_index=True)
        lmp = lmp.dropna(subset=["total_lmp_da"])
        lmp = lmp.sort_values("timestamp")

        # Join on timestamp (hourly).
        joined = pd.merge_asof(
            lmp.sort_values("timestamp"),
            w.sort_values("timestamp"),
            on="timestamp",
            direction="nearest",
            tolerance=pd.Timedelta("30min"),
        ).dropna(subset=["temp_c"])

        if joined.empty:
            continue

        # Compute simple correlations (weather vs LMP) for CDH/HDH/temp.
        def corr(a: pd.Series, b: pd.Series) -> float:
            if len(a) < 10:
                return float("nan")
            return float(a.corr(b))

        zone = str(joined["zone"].iloc[0]) if "zone" in joined.columns else str(node["regionId"])
        period = infer_period(pd.Timestamp(args.year, 1, 1))

        corr_vars: list[tuple[str, pd.Series]] = [
            ("TEMP_C", joined["temp_c"]),
            ("DEW_C", joined["dew_c"]),
            ("RH_PCT", joined["rh_pct"]),
            ("WIND_MS", joined["wind_ms"]),
            ("SLP_HPA", joined["slp_hpa"]),
            ("PRECIP_MM", joined["precip_mm"]),
            ("CDH", joined["cdh"]),
            ("HDH", joined["hdh"]),
        ]
        for var, s in corr_vars:
            if var in {"DEW_C", "RH_PCT", "WIND_MS", "SLP_HPA", "PRECIP_MM"}:
                if s.isna().all():
                    continue
            c = corr(s, joined["total_lmp_da"])
            if math.isnan(c):
                continue
            all_corr_rows.append(
                {
                    "nodeId": node_id,
                    "regionId": zone,
                    "period": period,
                    "year": int(args.year),
                    "variable": var,
                    "target": "lmp",
                    "correlation": c,
                    "isDataCenterHeavyBucket": "all",
                }
            )

        # Case study export for this node.
        pts = joined.head(500)[
            [
                "timestamp",
                "total_lmp_da",
                "temp_c",
                "dew_c",
                "rh_pct",
                "wind_ms",
                "slp_hpa",
                "precip_mm",
                "cdh",
                "hdh",
            ]
        ].copy()
        points = [
            {
                "timestamp": ts.isoformat(),
                "load": float(lmpv),
                "lmp": float(lmpv),
                "temperature": float(tc),
                "dewpoint_c": float(dew) if pd.notna(dew) else None,
                "rh_pct": float(rh) if pd.notna(rh) else None,
                "wind_ms": float(ws) if pd.notna(ws) else None,
                "slp_hpa": float(slp) if pd.notna(slp) else None,
                "precip_mm": float(pr) if pd.notna(pr) else None,
                "cdh": float(cdh),
                "hdh": float(hdh),
            }
            for ts, lmpv, tc, dew, rh, ws, slp, pr, cdh, hdh in zip(
                pts["timestamp"],
                pts["total_lmp_da"],
                pts["temp_c"],
                pts["dew_c"],
                pts["rh_pct"],
                pts["wind_ms"],
                pts["slp_hpa"],
                pts["precip_mm"],
                pts["cdh"],
                pts["hdh"],
            )
        ]
        all_case_studies[node_id] = [
            {"nodeId": node_id, "period": period, "points": points},
        ]

        if len(all_corr_rows) >= args.max_points:
            break

    # Write correlation summary and case studies.
    out_corr = PUBLIC_DATA / "correlations_by_region_period.json"
    if args.append and out_corr.exists():
        existing = _read_json(out_corr)
        # Merge by (nodeId, regionId, year, variable, target, bucket)
        index = {}
        for r in existing:
            key = (
                str(r.get("nodeId") or ""),
                str(r.get("regionId") or ""),
                int(r.get("year") or 0),
                str(r.get("variable") or ""),
                str(r.get("target") or ""),
                str(r.get("isDataCenterHeavyBucket") or ""),
            )
            index[key] = r
        for r in all_corr_rows:
            key = (
                str(r.get("nodeId") or ""),
                str(r.get("regionId") or ""),
                int(r.get("year") or 0),
                str(r.get("variable") or ""),
                str(r.get("target") or ""),
                str(r.get("isDataCenterHeavyBucket") or ""),
            )
            index[key] = r
        merged = list(index.values())
        merged.sort(key=lambda r: (r.get("year", 0), r.get("regionId", ""), r.get("nodeId", ""), r.get("variable", "")))
        _write_json(out_corr, merged)
    else:
        _write_json(out_corr, all_corr_rows)
    for node_id, series in all_case_studies.items():
        _write_json(PUBLIC_DATA / "case_studies" / f"{node_id}.json", series)

    # Model metrics are still an offline ML step; export an empty list for now.
    if not (PUBLIC_DATA / "model_performance.json").exists():
        _write_json(PUBLIC_DATA / "model_performance.json", [])

    print(f"Wrote {len(all_corr_rows)} correlation rows to {PUBLIC_DATA / 'correlations_by_region_period.json'}")
    print(f"Wrote {len(all_case_studies)} case studies to {PUBLIC_DATA / 'case_studies'}")


if __name__ == "__main__":
    main()


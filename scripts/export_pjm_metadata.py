import json
import os
from pathlib import Path

import pandas as pd
from dc_region_scoring import assign_data_center_likelihood, default_pjm_scoring_config


ROOT = Path(__file__).resolve().parents[1]
def resolve_data_root() -> Path:
    """
    Where the raw PJM dataset lives.

    Default:
      <repo>/data/pjm data

    Override:
      PJM_DATA_ROOT=/path/to/pjm_data
    """

    env = os.environ.get("PJM_DATA_ROOT")
    if env:
        return Path(env).expanduser().resolve()

    # Repo-relative default so we don't hardcode machine-specific paths.
    return ROOT / "data" / "pjm data"


DATA_ROOT = resolve_data_root()

FEATURE_DATA = DATA_ROOT / "feature_data"

OUT_DIR = ROOT / "data" / "exports"
CASE_STUDIES_DIR = OUT_DIR / "case_studies"


def _load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def main():
    import argparse

    ap = argparse.ArgumentParser(description="Export PJM metadata with explainable DC-likelihood scoring.")
    ap.add_argument(
        "--node-attributes-csv",
        default="",
        help="Optional CSV with node attributes: node_id,zone,state,county,city,latitude,longitude",
    )
    args = ap.parse_args()

    lmp_node_index = _load_json(FEATURE_DATA / "lmp_node_index.json")
    zone_mapping = _load_json(FEATURE_DATA / "zone_mapping.json")
    coords = _load_json(FEATURE_DATA / "ehv_node_coordinates.json")

    zones = [z for z in lmp_node_index.get("zones", []) if z and z != "nan"]

    nodes: list[dict] = []
    by_zone = lmp_node_index.get("by_zone", {})
    for zone, zone_obj in by_zone.items():
        if zone not in zones:
            continue
        by_type = zone_obj.get("by_type", {})
        for node_type, node_list in by_type.items():
            for n in node_list:
                pnode_id = str(n.get("pnode_id"))
                coord = coords.get(pnode_id) or {}
                lat = coord.get("lat")
                lon = coord.get("lon")
                if lat is None or lon is None:
                    continue
                # The coordinate source was derived from a best-effort geocode; filter to contiguous US-ish bounds
                # to avoid obviously bad matches (e.g., overseas towns with same name).
                lat_f = float(lat)
                lon_f = float(lon)
                if not (24.0 <= lat_f <= 50.0 and -125.0 <= lon_f <= -66.0):
                    continue
                nodes.append(
                    {
                        "node_id": pnode_id,
                        "name": n.get("pnode_name") or pnode_id,
                        "zone": zone,
                        "regionId": zone,
                        "subregion": node_type,
                        "state": None,
                        "county": None,
                        "city": None,
                        "lat": lat_f,
                        "lon": lon_f,
                    }
                )

    nodes_df = pd.DataFrame(nodes)
    if args.node_attributes_csv:
        attrs = pd.read_csv(args.node_attributes_csv)
        rename_map = {
            "node_id": "node_id",
            "zone": "zone",
            "state": "state",
            "county": "county",
            "city": "city",
            "latitude": "lat",
            "longitude": "lon",
        }
        cols = [c for c in rename_map if c in attrs.columns]
        attrs = attrs[cols].rename(columns=rename_map).copy()
        attrs["node_id"] = attrs["node_id"].astype(str)
        nodes_df = nodes_df.merge(attrs, on="node_id", how="left", suffixes=("", "_attr"))
        for c in ["zone", "state", "county", "city", "lat", "lon"]:
            attr_col = f"{c}_attr"
            if attr_col in nodes_df.columns:
                nodes_df[c] = nodes_df[attr_col].combine_first(nodes_df[c])
                nodes_df = nodes_df.drop(columns=[attr_col])

    scored_df = assign_data_center_likelihood(nodes_df, default_pjm_scoring_config())
    scored_df["isDataCenterHeavy"] = scored_df["classification_label"].isin(
        ["high_likelihood", "medium_likelihood"]
    )

    # Region-level summary from node-level scores.
    region_agg = (
        scored_df.groupby("regionId")
        .agg(
            avgLikelihood=("data_center_likelihood_score", "mean"),
            avgConfidence=("confidence_score", "mean"),
            highCount=("classification_label", lambda s: int((s == "high_likelihood").sum())),
            mediumCount=("classification_label", lambda s: int((s == "medium_likelihood").sum())),
            totalNodes=("classification_label", "count"),
        )
        .reset_index()
    )
    region_agg["isDataCenterHeavy"] = (region_agg["highCount"] + region_agg["mediumCount"]) >= (
        0.35 * region_agg["totalNodes"]
    )
    region_agg = region_agg.set_index("regionId")
    regions = []
    for zone in zones:
        row = region_agg.loc[zone] if zone in region_agg.index else None
        regions.append(
            {
                "id": zone,
                "name": f"PJM Zone {zone}",
                "iso": "PJM",
                "isDataCenterHeavy": bool(row["isDataCenterHeavy"]) if row is not None else False,
                "avgLikelihood": round(float(row["avgLikelihood"]), 4) if row is not None else 0.0,
                "avgConfidence": round(float(row["avgConfidence"]), 4) if row is not None else 0.0,
            }
        )

    nodes_out = []
    for _, r in scored_df.iterrows():
        nodes_out.append(
            {
                "id": str(r["node_id"]),
                "name": r.get("name"),
                "regionId": r.get("regionId"),
                "subregion": r.get("subregion"),
                "state": r.get("state"),
                "county": r.get("county"),
                "city": r.get("city"),
                "lat": float(r["lat"]) if pd.notna(r.get("lat")) else None,
                "lon": float(r["lon"]) if pd.notna(r.get("lon")) else None,
                "isDataCenterHeavy": bool(r.get("isDataCenterHeavy")),
                "dataCenterLikelihoodScore": float(r.get("data_center_likelihood_score", 0.0)),
                "confidenceScore": float(r.get("confidence_score", 0.0)),
                "classificationLabel": r.get("classification_label"),
                "matchedRegion": r.get("matched_region"),
                "reasonCodes": r.get("reason_codes") or [],
                "intermediateFeatures": r.get("intermediate_features") or {},
            }
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(OUT_DIR / "regions.json", regions)
    _write_json(OUT_DIR / "nodes.json", nodes_out)
    _write_json(
        OUT_DIR / "node_dc_scoring_debug.json",
        [
            {
                "node_id": str(r["node_id"]),
                "zone": r.get("regionId"),
                "data_center_likelihood_score": float(r.get("data_center_likelihood_score", 0.0)),
                "confidence_score": float(r.get("confidence_score", 0.0)),
                "classification_label": r.get("classification_label"),
                "reason_codes": r.get("reason_codes") or [],
                "matched_region": r.get("matched_region"),
                "intermediate_features": r.get("intermediate_features") or {},
            }
            for _, r in scored_df.iterrows()
        ],
    )

    # Export a minimal case-study for one node (first node) to validate end-to-end loading.
    # This uses Day-Ahead LMP parquet (hourly) as a stand-in for "usage signal" if load isn't present.
    da_dir = DATA_ROOT / "pjm_da_full_system_parquet"
    da_files = sorted(da_dir.glob("*.parquet"))
    if da_files and nodes_out:
        sample_node_id = int(nodes_out[0]["id"])
        df = pd.read_parquet(da_files[0], engine="pyarrow")
        df = df[df["pnode_id"] == sample_node_id].copy()
        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["datetime_beginning_ept"])
            df = df.sort_values("timestamp")
            points = [
                {
                    "timestamp": ts.isoformat(),
                    "load": float(lmp),  # using LMP as placeholder signal for now
                    "lmp": float(lmp),
                }
                for ts, lmp in zip(df["timestamp"].head(200), df["total_lmp_da"].head(200))
            ]
            series = [
                {
                    "nodeId": str(sample_node_id),
                    "period": "recentAI",
                    "points": points,
                }
            ]
            _write_json(CASE_STUDIES_DIR / f"{sample_node_id}.json", series)

    # Keep existing zone_mapping accessible for downstream scripts.
    _write_json(OUT_DIR / "zone_mapping.json", zone_mapping)


if __name__ == "__main__":
    main()


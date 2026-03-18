import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = Path(r"C:\Users\Jaipa\OneDrive\Desktop\GridIntelligence-1\Data")

FEATURE_DATA = DATA_ROOT / "feature_data"

OUT_DIR = ROOT / "public" / "data"
CASE_STUDIES_DIR = OUT_DIR / "case_studies"


def _load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def main():
    lmp_node_index = _load_json(FEATURE_DATA / "lmp_node_index.json")
    zone_mapping = _load_json(FEATURE_DATA / "zone_mapping.json")
    coords = _load_json(FEATURE_DATA / "ehv_node_coordinates.json")

    zones = [z for z in lmp_node_index.get("zones", []) if z and z != "nan"]

    # Very rough heuristic: treat DOM (Northern Virginia) + APS as more DC-heavy by default.
    # You can override in post-processing or by supplying your own mapping file later.
    dc_heavy_zones = {"DOM", "APS"}

    regions = [
        {
            "id": zone,
            "name": f"PJM Zone {zone}",
            "iso": "PJM",
            "isDataCenterHeavy": zone in dc_heavy_zones,
        }
        for zone in zones
    ]

    nodes = []
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
                        "id": pnode_id,
                        "name": n.get("pnode_name") or pnode_id,
                        "regionId": zone,
                        "subregion": node_type,
                        "lat": lat_f,
                        "lon": lon_f,
                        "isDataCenterHeavy": zone in dc_heavy_zones,
                    }
                )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(OUT_DIR / "regions.json", regions)
    _write_json(OUT_DIR / "nodes.json", nodes)

    # Export a minimal case-study for one node (first node) to validate end-to-end loading.
    # This uses Day-Ahead LMP parquet (hourly) as a stand-in for "usage signal" if load isn't present.
    da_dir = DATA_ROOT / "pjm_da_full_system_parquet"
    da_files = sorted(da_dir.glob("*.parquet"))
    if da_files and nodes:
        sample_node_id = int(nodes[0]["id"])
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


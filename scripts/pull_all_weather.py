import json
import math
import re
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DATA = ROOT / "data" / "exports"

GRID_DATA = Path(r"C:\Users\Jaipa\OneDrive\Desktop\GridIntelligence-1\Data")

ISD_HISTORY_URL = "https://www.ncei.noaa.gov/pub/data/noaa/isd-history.csv"
GLOBAL_HOURLY_BASE = "https://www.ncei.noaa.gov/data/global-hourly/access"


@dataclass(frozen=True)
class Station:
    usaf: str
    wban: str
    name: str
    lat: float
    lon: float

    @property
    def file_id(self) -> str:
        # NCEI /access/{year}/ uses concatenated filename, no dash.
        return f"{self.usaf}{self.wban}"

    @property
    def station_id(self) -> str:
        return f"{self.usaf}-{self.wban}"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p = math.pi / 180.0
    dlat = (lat2 - lat1) * p
    dlon = (lon2 - lon1) * p
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin(dlon / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(a))


def detect_energy_years() -> list[int]:
    years: set[int] = set()

    for folder, pattern in [
        (GRID_DATA / "pjm_da_full_system_parquet", "da_lmp_*_to_*.parquet"),
        (GRID_DATA / "pjm_load_yearly_clean", "pjm_load_forecast_*_clean.parquet"),
    ]:
        if not folder.exists():
            continue
        for p in folder.glob(pattern):
            m = re.search(r"(\d{4})", p.name)
            if m:
                years.add(int(m.group(1)))

    return sorted(years)


def load_nodes() -> pd.DataFrame:
    nodes_path = PUBLIC_DATA / "nodes.json"
    if not nodes_path.exists():
        raise FileNotFoundError(f"Missing {nodes_path}. Run scripts/export_pjm_metadata.py first.")
    nodes = pd.read_json(nodes_path)
    nodes["id"] = nodes["id"].astype(str)
    return nodes


def load_isd_history() -> pd.DataFrame:
    cache = ROOT / ".cache" / "isd-history.csv"
    cache.parent.mkdir(parents=True, exist_ok=True)
    if not cache.exists():
        print("Downloading isd-history.csv …")
        r = requests.get(ISD_HISTORY_URL, timeout=60)
        r.raise_for_status()
        cache.write_bytes(r.content)

    df = pd.read_csv(cache)
    df = df.rename(
        columns={
            "USAF": "usaf",
            "WBAN": "wban",
            "STATION NAME": "name",
            "LAT": "lat",
            "LON": "lon",
            "CTRY": "ctry",
        }
    )
    df = df.dropna(subset=["usaf", "wban", "lat", "lon", "ctry"])
    df["usaf"] = df["usaf"].astype(str).str.strip()
    df["wban"] = df["wban"].astype(str).str.strip()
    df.loc[df["usaf"].str.fullmatch(r"\d+"), "usaf"] = (
        df.loc[df["usaf"].str.fullmatch(r"\d+"), "usaf"].str.zfill(6)
    )
    df.loc[df["wban"].str.fullmatch(r"\d+"), "wban"] = (
        df.loc[df["wban"].str.fullmatch(r"\d+"), "wban"].str.zfill(5)
    )
    return df


def candidates_for_node(
    stations: pd.DataFrame, lat: float, lon: float, max_km: float, top_k: int
) -> list[Station]:
    tmp = stations.copy()
    tmp["__dist_km"] = tmp.apply(
        lambda r: haversine_km(lat, lon, float(r["lat"]), float(r["lon"])), axis=1
    )
    tmp = tmp[tmp["__dist_km"] <= max_km].nsmallest(top_k, "__dist_km")
    out: list[Station] = []
    for _, r in tmp.iterrows():
        out.append(
            Station(
                usaf=str(r["usaf"]),
                wban=str(r["wban"]),
                name=str(r.get("name", "")),
                lat=float(r["lat"]),
                lon=float(r["lon"]),
            )
        )
    return out


def url_for(file_id: str, year: int) -> str:
    return f"{GLOBAL_HOURLY_BASE}/{year}/{file_id}.csv"


def head_ok(file_id: str, year: int) -> bool:
    # HEAD would be ideal, but GET is more reliably supported; keep it quick.
    try:
        r = requests.get(url_for(file_id, year), timeout=20)
        return r.status_code == 200
    except Exception:
        return False


def download(file_id: str, year: int, out_dir: Path) -> str:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{file_id}_{year}.csv"
    if out_path.exists():
        return "exists"
    r = requests.get(url_for(file_id, year), timeout=120)
    if r.status_code == 404:
        return "404"
    r.raise_for_status()
    out_path.write_bytes(r.content)
    return "downloaded"


def load_existing_mapping(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
        out = {}
        for r in rows:
            node_id = str(r.get("nodeId", ""))
            if node_id:
                out[node_id] = r
        return out
    except Exception:
        return {}


def save_mapping(path: Path, mapping: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(mapping.values())
    rows.sort(key=lambda r: (r.get("nodeId", ""), r.get("stationName", "")))
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--max-km", type=float, default=120.0)
    ap.add_argument("--ctry", default="US")
    ap.add_argument("--max-stations", type=int, default=6)
    ap.add_argument("--limit-nodes", type=int, default=0, help="0 = no limit")
    ap.add_argument("--prefer-dc-heavy", action="store_true")
    ap.add_argument("--dc-only", action="store_true")
    ap.add_argument("--sleep-ms", type=int, default=0, help="Throttle between downloads (ms)")
    args = ap.parse_args()

    years = detect_energy_years()
    if not years:
        raise RuntimeError("Could not detect any energy years in GridIntelligence-1/Data.")
    print(f"Energy years detected: {years}")

    nodes = load_nodes()
    if args.dc_only:
        nodes = nodes[nodes.get("isDataCenterHeavy") == True].copy()
    if args.prefer_dc_heavy:
        nodes = nodes.sort_values(
            by=["isDataCenterHeavy", "regionId", "id"], ascending=[False, True, True]
        ).copy()
    if args.limit_nodes and args.limit_nodes > 0:
        nodes = nodes.head(args.limit_nodes).copy()

    print(f"Nodes considered: {len(nodes)}")

    stations = load_isd_history()
    stations = stations[stations["ctry"] == args.ctry].copy()
    print(f"Stations in catalog for ctry={args.ctry}: {len(stations)}")

    out_base = ROOT / "data" / "noaa_isd_global_hourly"
    mapping_path = ROOT / "data" / "node_to_isd_station.json"
    mapping = load_existing_mapping(mapping_path)

    counts = {
        "mapped_reused": 0,
        "mapped_new": 0,
        "downloaded": 0,
        "exists": 0,
        "404": 0,
        "nodes_failed": 0,
    }

    started = time.time()

    for i, n in enumerate(nodes.itertuples(index=False), start=1):
        node_id = str(getattr(n, "id"))
        lat = float(getattr(n, "lat"))
        lon = float(getattr(n, "lon"))
        region_id = str(getattr(n, "regionId"))
        is_dc = bool(getattr(n, "isDataCenterHeavy"))

        print(f"\n[{i}/{len(nodes)}] node={node_id} zone={region_id} dc={is_dc}")

        entry = mapping.get(node_id)
        chosen = None

        # Reuse existing mapping if it still has files available for at least one year.
        if entry and entry.get("fileId"):
            fid = str(entry["fileId"])
            if any(head_ok(fid, y) for y in years):
                chosen = fid
                counts["mapped_reused"] += 1
                print(f"  mapping: reused {fid} ({entry.get('stationName','')})")

        if chosen is None:
            candidates = candidates_for_node(stations, lat, lon, args.max_km, top_k=args.max_stations)
            if not candidates:
                counts["nodes_failed"] += 1
                print("  mapping: no nearby stations found")
                continue

            for cand in candidates:
                if any(head_ok(cand.file_id, y) for y in years):
                    chosen = cand.file_id
                    mapping[node_id] = {
                        "nodeId": node_id,
                        "regionId": region_id,
                        "isDataCenterHeavy": is_dc,
                        "stationId": cand.station_id,
                        "fileId": cand.file_id,
                        "stationName": cand.name,
                        "stationLat": cand.lat,
                        "stationLon": cand.lon,
                    }
                    counts["mapped_new"] += 1
                    print(f"  mapping: picked {cand.file_id} ({cand.name})")
                    break

        if chosen is None:
            counts["nodes_failed"] += 1
            print("  mapping: failed to find any station with available files")
            continue

        # Download missing years.
        for y in years:
            status = download(chosen, y, out_base / chosen)
            counts[status] += 1
            if status == "downloaded":
                print(f"  {y}: downloaded")
            elif status == "exists":
                # keep quieter
                pass
            elif status == "404":
                print(f"  {y}: 404 (no file)")
            if args.sleep_ms and status == "downloaded":
                time.sleep(args.sleep_ms / 1000.0)

        # Persist mapping incrementally so progress isn’t lost.
        if i % 10 == 0:
            save_mapping(mapping_path, mapping)
            elapsed = int(time.time() - started)
            print(f"\nProgress checkpoint @ {i} nodes, elapsed {elapsed}s")
            print("Counts:", counts)

    save_mapping(mapping_path, mapping)
    elapsed = int(time.time() - started)
    print("\nDone.")
    print(f"Elapsed: {elapsed}s")
    print("Counts:", counts)
    print(f"Mapping written: {mapping_path}")
    print(f"Weather files under: {out_base}")


if __name__ == "__main__":
    main()


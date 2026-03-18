import math
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DATA = ROOT / "public" / "data"

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
    def station_id(self) -> str:
        # global-hourly uses USAF-WBAN (WBAN can be 99999)
        return f"{self.usaf}-{self.wban}"

    @property
    def file_id(self) -> str:
        # In the NCEI /access/{year}/ directory, filenames are concatenated (no dash).
        return f"{self.usaf}{self.wban}"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p = math.pi / 180
    dlat = (lat2 - lat1) * p
    dlon = (lon2 - lon1) * p
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin(dlon / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(a))


def load_nodes() -> pd.DataFrame:
    nodes_path = PUBLIC_DATA / "nodes.json"
    if not nodes_path.exists():
        raise FileNotFoundError(
            f"Missing {nodes_path}. Run scripts/export_pjm_metadata.py first."
        )
    return pd.read_json(nodes_path)


def load_isd_history() -> pd.DataFrame:
    cache = ROOT / ".cache" / "isd-history.csv"
    cache.parent.mkdir(parents=True, exist_ok=True)
    if not cache.exists():
        r = requests.get(ISD_HISTORY_URL, timeout=60)
        r.raise_for_status()
        cache.write_bytes(r.content)
    df = pd.read_csv(cache)
    # Normalize columns we need
    df = df.rename(
        columns={
            "USAF": "usaf",
            "WBAN": "wban",
            "STATION NAME": "name",
            "LAT": "lat",
            "LON": "lon",
            "BEGIN": "begin",
            "END": "end",
            "CTRY": "ctry",
            "STATE": "state",
        }
    )
    df = df.dropna(subset=["usaf", "wban", "lat", "lon"])
    # USAF can include alphanumeric IDs (e.g. 'A00002'); keep as string and pad numeric-only IDs.
    df["usaf"] = df["usaf"].astype(str).str.strip()
    df["wban"] = df["wban"].astype(str).str.strip()
    df.loc[df["usaf"].str.fullmatch(r"\d+"), "usaf"] = (
        df.loc[df["usaf"].str.fullmatch(r"\d+"), "usaf"].str.zfill(6)
    )
    df.loc[df["wban"].str.fullmatch(r"\d+"), "wban"] = (
        df.loc[df["wban"].str.fullmatch(r"\d+"), "wban"].str.zfill(5)
    )
    return df


def candidate_stations_for_point(
    stations_df: pd.DataFrame, lat: float, lon: float, max_km: float, top_k: int = 25
) -> list[Station]:
    tmp = stations_df.copy()
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


def file_available(file_id: str, year: int) -> bool:
    url = f"{GLOBAL_HOURLY_BASE}/{year}/{file_id}.csv"
    try:
        r = requests.get(url, timeout=30)
        return r.status_code == 200
    except Exception:
        return False


def download_global_hourly_csv(file_id: str, year: int, out_dir: Path) -> Path | None:
    url = f"{GLOBAL_HOURLY_BASE}/{year}/{file_id}.csv"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{file_id}_{year}.csv"
    if out_path.exists():
        return out_path
    r = requests.get(url, timeout=120)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    out_path.write_bytes(r.content)
    return out_path


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--years", nargs="+", type=int, required=True)
    ap.add_argument("--max-km", type=float, default=50.0)
    ap.add_argument("--ctry", default="US")
    ap.add_argument("--limit-nodes", type=int, default=30)
    ap.add_argument("--max-stations", type=int, default=10, help="Max nearby stations to probe per node")
    ap.add_argument(
        "--prefer-dc-heavy",
        action="store_true",
        help="Prioritize nodes marked isDataCenterHeavy=true in public/data/nodes.json",
    )
    ap.add_argument(
        "--dc-only",
        action="store_true",
        help="Only pull weather for nodes marked isDataCenterHeavy=true in public/data/nodes.json",
    )
    args = ap.parse_args()

    nodes = load_nodes()
    nodes["id"] = nodes["id"].astype(str)
    stations = load_isd_history()
    stations = stations[stations["ctry"] == args.ctry].copy()

    if args.dc_only:
        nodes = nodes[nodes.get("isDataCenterHeavy") == True].copy()

    if args.prefer_dc_heavy:
        nodes = nodes.sort_values(
            by=["isDataCenterHeavy", "regionId", "id"], ascending=[False, True, True]
        ).copy()

    # To keep the pull manageable, limit to first N nodes (after sorting/filtering).
    nodes = nodes.head(args.limit_nodes).copy()

    mappings = []
    out_base = ROOT / "data" / "noaa_isd_global_hourly"

    for _, n in nodes.iterrows():
        candidates = candidate_stations_for_point(
            stations, float(n["lat"]), float(n["lon"]), args.max_km, top_k=max(5, args.max_stations)
        )
        station = None
        for cand in candidates:
            if any(file_available(cand.file_id, y) for y in args.years):
                station = cand
                break
        if station is None:
            continue
        mappings.append(
            {
                "nodeId": str(n["id"]),
                "stationId": station.station_id,
                "fileId": station.file_id,
                "stationName": station.name,
                "stationLat": station.lat,
                "stationLon": station.lon,
            }
        )

        for y in args.years:
            download_global_hourly_csv(station.file_id, y, out_base / station.file_id)

    mappings_path = ROOT / "data" / "node_to_isd_station.json"
    mappings_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(mappings).drop_duplicates(subset=["nodeId"]).to_json(
        mappings_path, orient="records", indent=2
    )
    print(f"Wrote station mappings: {mappings_path}")
    print(f"Downloaded CSVs under: {out_base}")


if __name__ == "__main__":
    main()


"""
Explainable PJM data-center-region likelihood scoring.

This module estimates whether a PJM node belongs to a data-center-heavy region.
It is a conservative, auditable heuristic system (not a ground-truth detector).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from math import asin, cos, radians, sin, sqrt
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class RegionDefinition:
    name: str
    tier: int
    zones: list[str] = field(default_factory=list)
    states: list[str] = field(default_factory=list)
    counties: list[str] = field(default_factory=list)
    cities: list[str] = field(default_factory=list)
    centroid_lat: float | None = None
    centroid_lon: float | None = None
    radius_km: float | None = None


@dataclass
class ScoringConfig:
    geographic_weight: float = 0.70
    behavioral_weight: float = 0.30
    high_threshold: float = 0.75
    medium_threshold: float = 0.40
    fuzzy_threshold: float = 0.80
    congestion_threshold: float = 5.0
    night_hours: tuple[int, int] = (0, 6)
    day_hours: tuple[int, int] = (10, 18)
    tier_weight: dict[int, float] = field(
        default_factory=lambda: {1: 1.0, 2: 0.78, 3: 0.58},
    )
    region_definitions: list[RegionDefinition] = field(default_factory=list)


def default_pjm_scoring_config() -> ScoringConfig:
    return ScoringConfig(
        region_definitions=[
            RegionDefinition(
                name="northern_virginia_dom",
                tier=1,
                zones=["DOM"],
                states=["VA"],
                counties=["Loudoun County", "Fairfax County", "Prince William County"],
                cities=["Ashburn", "Sterling", "Herndon", "Reston", "Chantilly", "Manassas"],
                centroid_lat=39.0438,
                centroid_lon=-77.4874,
                radius_km=45.0,
            ),
            RegionDefinition(
                name="ppl_susquehanna_berwick",
                tier=2,
                zones=["PPL"],
                states=["PA"],
                counties=["Luzerne County", "Columbia County"],
                cities=["Berwick", "Salem Township"],
                centroid_lat=41.1030,
                centroid_lon=-76.2330,
                radius_km=45.0,
            ),
            RegionDefinition(
                name="aep_columbus_ohio",
                tier=2,
                zones=["AEP"],
                states=["OH"],
                counties=["Franklin County", "Delaware County", "Licking County"],
                cities=["Columbus", "Dublin", "New Albany", "Hilliard"],
                centroid_lat=39.9612,
                centroid_lon=-82.9988,
                radius_km=55.0,
            ),
            RegionDefinition(
                name="comed_chicago_suburbs",
                tier=2,
                zones=["COMED"],
                states=["IL"],
                counties=["Cook County", "DuPage County", "Will County", "Kane County"],
                cities=["Elk Grove Village", "Aurora", "Naperville", "Joliet"],
                centroid_lat=41.8781,
                centroid_lon=-87.6298,
                radius_km=65.0,
            ),
            RegionDefinition(
                name="indiana_pjm_emerging",
                tier=3,
                zones=["AEP", "DEOK", "DUKE"],
                states=["IN"],
                counties=["Lake County", "Porter County", "Marion County"],
                cities=["Indianapolis", "Hammond", "Merrillville"],
                centroid_lat=39.7684,
                centroid_lon=-86.1581,
                radius_km=70.0,
            ),
            RegionDefinition(
                name="western_pa_wv_rural",
                tier=3,
                zones=["APS", "ATSI", "PENELEC"],
                states=["PA", "WV"],
                counties=["Allegheny County", "Washington County", "Monongalia County"],
                cities=["Pittsburgh", "Morgantown", "Canonsburg"],
                centroid_lat=40.4406,
                centroid_lon=-79.9959,
                radius_km=90.0,
            ),
        ]
    )


def _normalize_text(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).strip().lower()
    return " ".join(s.split())


def _fuzzy_ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, _normalize_text(a), _normalize_text(b)).ratio()


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    lat1_r = radians(lat1)
    lat2_r = radians(lat2)
    a = sin(dlat / 2) ** 2 + cos(lat1_r) * cos(lat2_r) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return r * c


def _distance_score(distance_km: float, radius_km: float) -> float:
    if radius_km <= 0:
        return 0.0
    if distance_km <= radius_km:
        return max(0.0, 1.0 - (distance_km / radius_km) * 0.2)
    if distance_km <= radius_km * 2:
        return max(0.0, 0.8 - ((distance_km - radius_km) / radius_km) * 0.8)
    return 0.0


def score_node_geography(node_row: pd.Series, config: ScoringConfig) -> dict[str, Any]:
    zone = str(node_row.get("zone") or node_row.get("regionId") or "").upper()
    state = str(node_row.get("state") or "").upper()
    county = str(node_row.get("county") or "")
    city = str(node_row.get("city") or "")
    node_name = str(node_row.get("name") or "")
    lat = node_row.get("lat")
    lon = node_row.get("lon")

    best_region = ""
    best_score = 0.0
    best_reasons: list[str] = []
    best_debug: dict[str, Any] = {}

    for region in config.region_definitions:
        tier_mult = config.tier_weight.get(region.tier, 0.5)
        zone_match = 1.0 if zone and zone in set(region.zones) else 0.0
        state_match = 1.0 if state and state in set(region.states) else 0.0

        county_ratios = [_fuzzy_ratio(county, c) for c in region.counties] if county else [0.0]
        city_ratios = [_fuzzy_ratio(city, c) for c in region.cities] if city else [0.0]
        name_ratios = [_fuzzy_ratio(node_name, c) for c in (region.cities + region.counties)] if node_name else [0.0]
        county_match = max(county_ratios) if county_ratios else 0.0
        city_match = max(city_ratios) if city_ratios else 0.0
        node_name_match = max(name_ratios) if name_ratios else 0.0

        distance_km = np.nan
        distance_component = 0.0
        if (
            pd.notna(lat)
            and pd.notna(lon)
            and region.centroid_lat is not None
            and region.centroid_lon is not None
            and region.radius_km is not None
        ):
            distance_km = _haversine_km(float(lat), float(lon), region.centroid_lat, region.centroid_lon)
            distance_component = _distance_score(distance_km, region.radius_km)

        # Weighted geography evidence before tier scaling.
        raw_geo = (
            0.25 * zone_match
            + 0.10 * state_match
            + 0.20 * county_match
            + 0.15 * city_match
            + 0.10 * node_name_match
            + 0.20 * distance_component
        )
        geo_score = float(max(0.0, min(1.0, raw_geo * tier_mult)))

        reasons: list[str] = []
        if county_match >= config.fuzzy_threshold:
            reasons.append(f"county matched {region.name} county list (strong signal)")
        if city_match >= config.fuzzy_threshold:
            reasons.append(f"city matched {region.name} city list (strong signal)")
        if zone_match > 0:
            if county_match < config.fuzzy_threshold and city_match < config.fuzzy_threshold:
                reasons.append(f"zone = {zone} matched {region.name}, but no strong county/city match")
            else:
                reasons.append(f"zone = {zone} aligned with {region.name}")
        if node_name_match >= config.fuzzy_threshold:
            reasons.append(f"node name matched known locality in {region.name}")
        if pd.notna(distance_km) and region.radius_km:
            if distance_km <= region.radius_km:
                reasons.append(f"within {int(distance_km)} km of {region.name} centroid")
            elif distance_km <= region.radius_km * 2:
                reasons.append(f"near {region.name} centroid at {int(distance_km)} km")

        if geo_score > best_score:
            best_score = geo_score
            best_region = region.name
            best_reasons = reasons
            best_debug = {
                "region_tier": region.tier,
                "zone_match": round(zone_match, 4),
                "state_match": round(state_match, 4),
                "county_fuzzy": round(county_match, 4),
                "city_fuzzy": round(city_match, 4),
                "node_name_fuzzy": round(node_name_match, 4),
                "distance_km": None if pd.isna(distance_km) else round(float(distance_km), 2),
                "distance_component": round(distance_component, 4),
                "raw_geo_score": round(raw_geo, 4),
            }

    return {
        "geographic_score": round(best_score, 4),
        "matched_region": best_region if best_region else None,
        "geo_reason_codes": best_reasons,
        "geo_debug": best_debug,
    }


def compute_behavioral_features(ts_df: pd.DataFrame, config: ScoringConfig) -> pd.DataFrame:
    """
    Compute optional node-level behavioral proxies from hourly time series.
    Expected columns: node_id, timestamp, lmp, congestion(optional), temperature(optional)
    """
    if ts_df.empty:
        return pd.DataFrame()

    work = ts_df.copy()
    req_cols = {"node_id", "timestamp", "lmp"}
    missing = req_cols - set(work.columns)
    if missing:
        raise ValueError(f"time-series data missing required columns: {sorted(missing)}")

    work["timestamp"] = pd.to_datetime(work["timestamp"], errors="coerce")
    work = work.dropna(subset=["timestamp", "lmp"]).copy()
    work["hour"] = work["timestamp"].dt.hour
    work["dow"] = work["timestamp"].dt.dayofweek

    n0, n1 = config.night_hours
    d0, d1 = config.day_hours
    night = work[(work["hour"] >= n0) & (work["hour"] <= n1)]
    day = work[(work["hour"] >= d0) & (work["hour"] <= d1)]

    node_mean = work.groupby("node_id")["lmp"].mean().rename("node_lmp_mean")
    node_std = work.groupby("node_id")["lmp"].std(ddof=0).fillna(0.0).rename("node_lmp_std")
    night_mean = night.groupby("node_id")["lmp"].mean().rename("night_mean")
    day_mean = day.groupby("node_id")["lmp"].mean().rename("day_mean")
    weekday = work[work["dow"] < 5].groupby("node_id")["lmp"].mean().rename("weekday_mean")
    weekend = work[work["dow"] >= 5].groupby("node_id")["lmp"].mean().rename("weekend_mean")

    out = pd.concat([node_mean, node_std, night_mean, day_mean, weekday, weekend], axis=1).fillna(np.nan)
    out["night_day_ratio"] = out["night_mean"] / out["day_mean"]
    out["weekday_weekend_ratio"] = out["weekday_mean"] / out["weekend_mean"]
    out["coefficient_of_variation"] = out["node_lmp_std"] / out["node_lmp_mean"].replace(0, np.nan)
    out["baseload_flatness_score"] = (1.0 - out["coefficient_of_variation"].clip(lower=0.0, upper=1.5) / 1.5).clip(
        lower=0.0, upper=1.0
    )

    if "congestion" in work.columns:
        work["congestion"] = pd.to_numeric(work["congestion"], errors="coerce")
        congested = (work["congestion"] > config.congestion_threshold).astype(float)
        out["congestion_persistence"] = congested.groupby(work["node_id"]).mean()
        out["avg_congestion_premium_vs_mean"] = (
            work.groupby("node_id")["congestion"].mean() / out["node_lmp_mean"].replace(0, np.nan)
        ).fillna(0.0)
    else:
        out["congestion_persistence"] = np.nan
        out["avg_congestion_premium_vs_mean"] = np.nan

    out = out.reset_index()
    return out


def score_behavioral_row(row: pd.Series) -> tuple[float, list[str], dict[str, Any]]:
    if row.empty:
        return 0.0, [], {}

    ndr = row.get("night_day_ratio")
    wwr = row.get("weekday_weekend_ratio")
    flat = row.get("baseload_flatness_score")
    cong_p = row.get("congestion_persistence")
    cong_prem = row.get("avg_congestion_premium_vs_mean")

    components: list[float] = []
    reasons: list[str] = []
    debug: dict[str, Any] = {}

    if pd.notna(ndr):
        # closer to 1 => flatter day/night
        c = max(0.0, 1.0 - min(abs(float(ndr) - 1.0), 1.0))
        components.append(c)
        debug["night_day_component"] = round(c, 4)
        if c > 0.8:
            reasons.append("night/day LMP ratio near 1.0 (flat diurnal profile)")
    if pd.notna(wwr):
        c = max(0.0, 1.0 - min(abs(float(wwr) - 1.0), 1.0))
        components.append(c)
        debug["weekday_weekend_component"] = round(c, 4)
        if c > 0.8:
            reasons.append("weekday/weekend ratio near 1.0 (steady weekly demand)")
    if pd.notna(flat):
        c = float(np.clip(flat, 0.0, 1.0))
        components.append(c)
        debug["flatness_component"] = round(c, 4)
        if c > 0.7:
            reasons.append("high baseload flatness (low relative variability)")
    if pd.notna(cong_p):
        c = float(np.clip(cong_p, 0.0, 1.0))
        components.append(c)
        debug["congestion_persistence_component"] = round(c, 4)
        if c > 0.6:
            reasons.append("persistent congestion signal")
    if pd.notna(cong_prem):
        c = float(np.clip(cong_prem, 0.0, 1.0))
        components.append(c)
        debug["congestion_premium_component"] = round(c, 4)

    if not components:
        return 0.0, [], debug
    return float(np.mean(components)), reasons, debug


def _label_from_score(score: float, config: ScoringConfig) -> str:
    if score >= config.high_threshold:
        return "high_likelihood"
    if score >= config.medium_threshold:
        return "medium_likelihood"
    return "low_likelihood"


def assign_data_center_likelihood(
    nodes_df: pd.DataFrame,
    config: ScoringConfig,
    time_series_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Score nodes and return explainable likelihood output.
    Required in nodes_df: node_id or id, zone or regionId; optional county/city/state/lat/lon.
    """
    if nodes_df.empty:
        return nodes_df.copy()

    work = nodes_df.copy()
    if "node_id" not in work.columns and "id" in work.columns:
        work["node_id"] = work["id"].astype(str)
    work["node_id"] = work["node_id"].astype(str)

    geo_rows = []
    for _, r in work.iterrows():
        geo_rows.append(score_node_geography(r, config))
    geo_df = pd.DataFrame(geo_rows)
    out = pd.concat([work.reset_index(drop=True), geo_df], axis=1)

    behavior_df = pd.DataFrame()
    if time_series_df is not None and not time_series_df.empty:
        behavior_df = compute_behavioral_features(time_series_df, config)
        behavior_df["node_id"] = behavior_df["node_id"].astype(str)
        out = out.merge(behavior_df, on="node_id", how="left")

    scores: list[dict[str, Any]] = []
    for _, row in out.iterrows():
        geo = float(row.get("geographic_score") or 0.0)
        behavior_score, behavior_reasons, behavior_debug = score_behavioral_row(row)
        has_behavior = bool(behavior_debug)

        if has_behavior:
            w_geo = config.geographic_weight
            w_behavior = config.behavioral_weight
            w_sum = max(1e-9, w_geo + w_behavior)
            final_score = (w_geo * geo + w_behavior * behavior_score) / w_sum
        else:
            final_score = geo

        reason_codes = list(row.get("geo_reason_codes") or [])
        reason_codes.extend(behavior_reasons)
        if not reason_codes:
            reason_codes = ["no strong geographic or behavioral signal; conservative low likelihood"]

        text_presence = sum(
            [
                1 if _normalize_text(row.get("county")) else 0,
                1 if _normalize_text(row.get("city")) else 0,
                1 if _normalize_text(row.get("state")) else 0,
                1 if _normalize_text(row.get("zone") or row.get("regionId")) else 0,
            ]
        ) / 4.0
        latlon_presence = 1.0 if pd.notna(row.get("lat")) and pd.notna(row.get("lon")) else 0.0
        behavior_presence = 1.0 if has_behavior else 0.0
        data_completeness = 0.45 * text_presence + 0.35 * latlon_presence + 0.20 * behavior_presence
        signal_strength = min(1.0, max(geo, behavior_score))
        consistency = 1.0 - abs(geo - behavior_score) if has_behavior else 0.65
        confidence = 0.45 * data_completeness + 0.35 * signal_strength + 0.20 * consistency
        confidence = float(np.clip(confidence, 0.0, 1.0))

        scores.append(
            {
                "data_center_likelihood_score": round(float(np.clip(final_score, 0.0, 1.0)), 4),
                "confidence_score": round(confidence, 4),
                "classification_label": _label_from_score(final_score, config),
                "reason_codes": reason_codes,
                "behavioral_score": round(float(np.clip(behavior_score, 0.0, 1.0)), 4),
                "intermediate_features": {
                    "geographic_score": round(geo, 4),
                    "behavioral_score": round(float(np.clip(behavior_score, 0.0, 1.0)), 4),
                    "geo_debug": row.get("geo_debug") or {},
                    "behavior_debug": behavior_debug,
                    "data_completeness": round(data_completeness, 4),
                    "signal_strength": round(signal_strength, 4),
                    "consistency": round(consistency, 4),
                },
            }
        )

    scored_df = pd.concat([out.reset_index(drop=True), pd.DataFrame(scores)], axis=1)
    return scored_df


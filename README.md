# Energy, Weather & Data Centers (PJM-focused)

React web app to explore how the relationship between **weather patterns** and **grid demand/pricing**
may be shifting in **data-center-heavy** regions.

## Run the web app

```bash
npm install
npm run dev
```

Open the dev server URL (typically `http://localhost:5173/`).

## What data you already have (local)

Download the PJM+features dataset (packaged as the `GridIntelligence-1/Data` directory) from Duke Box:

- [Duke Box data bundle](https://duke.box.com/s/xtdrmjv1463wf0o60i1rmts0g0urxp01)

After downloading, extract it so the `Data` folder matches the path below (this is the path hard-coded in `scripts/build_analysis_exports.py`):

- `C:\Users\Jaipa\OneDrive\Desktop\GridIntelligence-1\Data`

We detected:
- `pjm_da_full_system_parquet/` (hourly Day-Ahead LMP by pnode)
- `pjm_load_forecast_parquet/` (hourly load forecasts by zone)
- `feature_data/` (node index, zone mapping, node coordinates)

## Integrate existing PJM metadata into the app

The React app reads static JSON under `public/data/`. Generate `regions.json`, `nodes.json`, and a
small case-study file:

```bash
python scripts/export_pjm_metadata.py
```

This writes `public/data/regions.json` and `public/data/nodes.json` (and a small case-study seed) via the normal export/sync flow.

## Pull NOAA ISD weather (what’s still missing)

Weather features are not yet present in your PJM snapshot. This script:
- downloads `isd-history.csv` (station catalog)\n+- finds the nearest station per node\n+- downloads NOAA **global-hourly** CSVs for chosen years\n+
```bash
python scripts/noaa_isd_pull.py --years 2021 2022 2023 2024 2025 --limit-nodes 30 --max-km 50
```

Outputs:
- mapping: `data/node_to_isd_station.json`
- weather CSVs: `data/noaa_isd_global_hourly/`

## Next step (analysis exports)

Once weather is pulled, we’ll add a join + feature engineering script to export:
- `public/data/correlations_by_region_period.json`
- `public/data/model_performance.json`
- `public/data/case_studies/{nodeId}.json`

# Energy, Weather & Data Centers (PJM-focused)

React web app to explore how the relationship between **weather patterns** and **grid demand/pricing**
may be shifting in **data-center-heavy** regions.

## Run the web app (easiest solution)

```bash
npm install
npm run dev
```

Open the dev server URL (typically `http://localhost:5173/`).

You can now use the app with our precomputed correlations. If you want to go through the full pipeline of recomputing correlations from weather data and prce/energy usage information, review the following sections.

## Precomputed data (default workflow)

This repository is configured to use precomputed JSON exports so the app can run without bundling large raw PJM datasets. The remaining sections are optional.

The frontend reads from `public/data/` (synced from `data/exports/`), including:

- `regions.json`
- `nodes.json`
- `correlations_by_region_period.json`
- `model_performance.json`
- `case_studies/*.json`

To refresh frontend data from existing exports:

```bash
npm run sync:data
```

### OPTIONAL: Getting all optional app data (no recompute)

If you just want the app to work with precomputed results:

1. Download the `data` folder snapshot from Box: [Duke Box data bundle](https://duke.box.com/s/xtdrmjv1463wf0o60i1rmts0g0urxp01)
2. Replace your local repo `data/` directory with the downloaded `data/` directory.
3. Run:

```bash
npm run sync:data
npm run dev
```

## Recomputing correlations (optional, full data workflow)

Recomputing correlations requires raw PJM data + weather pulls. We do **not** require this for normal app usage, and we keep precomputed exports to avoid excessive data uploads/check-ins.

If you want to recompute, first download the PJM+features dataset from Duke Box:

- [Duke Box data bundle](https://duke.box.com/s/xtdrmjv1463wf0o60i1rmts0g0urxp01)

After downloading, extract it to the repo-relative default location:

- `./data/pjm data`

If you keep the dataset elsewhere, set an environment variable before running scripts:

```powershell
$env:PJM_DATA_ROOT="C:\path\to\pjm data"
```

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

## Pull NOAA ISD weather

Weather features are not yet present in your PJM snapshot. This script:
- downloads `isd-history.csv` (station catalog)
- finds the nearest station per node
- downloads NOAA **global-hourly** CSVs for chosen years
```bash
python scripts/noaa_isd_pull.py --years 2021 2022 2023 2024 2025 --limit-nodes 30 --max-km 50
```

Outputs:
- mapping: `data/node_to_isd_station.json`
- weather CSVs: `data/noaa_isd_global_hourly/`

After generating exports, sync them into the frontend:

```bash
npm run sync:data
```

## Next step (analysis exports)

Once weather is pulled, we’ll add a join + feature engineering script to export:
- `public/data/correlations_by_region_period.json`
- `public/data/model_performance.json`
- `public/data/case_studies/{nodeId}.json`

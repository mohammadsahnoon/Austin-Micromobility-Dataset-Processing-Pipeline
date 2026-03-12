# Austin, TX Micromobility Dataset Pipeline (Paper A)

This repository contains a clean, reproducible data-processing pipeline for the Austin, TX micromobility study used in Paper A (IEEE ITS journal workflow).

The pipeline is limited to:
- raw trip record acquisition
- Census tract centroid mapping
- cleaned 2019 e-scooter dataset generation
- hourly pickup/dropoff demand image generation

It does **not** include lag analysis, ranking, model training, or statistical tests.

## Relation to Paper A

This code operationalizes the dataset-preparation pipeline used before model development:
1. ingest raw Austin trip records
2. map trip start/end Census tract IDs to spatial coordinates
3. produce a cleaned 2019 e-scooter trip table
4. generate hourly grid-based pickup/dropoff demand images

## Pipeline Stages

### Stage 1: Download Raw Trips + Tract Centroid Mapping
- Downloads Austin trip records from Socrata dataset `7d8e-dm7r`.
- Default limit is `15000000` (same as original workflow).
- Attaches `startx/starty/endx/endy` by matching tract IDs to centroids from:
  - `data/reference/Austin_205_tracts_from_TIGER.csv`

Output:
- `data/interim/stage1_austin_trip_records_with_tract_centroids.csv`

### Stage 2: Standardize Core Trip Table
- Converts timestamps to US/Central local time.
- Builds `start_date`, `start_hour`, `start_day_of_week`.
- Converts:
  - `trip_duration` seconds -> `trip_duration_min`
  - `trip_distance` meters -> `trip_length_km`
- Keeps the core columns used downstream.

Output:
- `data/processed/stage2_austin_trips_standardized.csv`

### Stage 3: Build Final 2019 E-Scooter Dataset
- Filters to scooter trips.
- Filters to calendar year 2019 (local start date).
- Applies quality rules:
  - `trip_duration_min` in `[1, 120]`
  - `trip_length_km` in `[0.1, 35]`
  - `avg_speed_kmh` in `[2, 26]`
- Drops rows with missing required fields.
- Keeps rows whose start and end tracts are in the 205-tract reference.

Output:
- `data/final/final_austin_escooter_2019_dataset.csv`

### Stage 4: Generate Hourly Demand Images
- Projects lon/lat to UTM 14N (`EPSG:32614`).
- Builds raster grid from Austin city boundary:
  - `data/reference/BOUNDARIES_jurisdictions_20250809.geojson`
- Uses fixed cell size:
  - `240m x 220m`
- Generates full 2019 hourly image sets:
  - pickup: `pickup_{index:04}_{YYYY-MM-DD}_{hour}.png`
  - dropoff: `dropoff_{index:04}_{YYYY-MM-DD}_{hour}.png`

Output folders:
- `data/outputs/pickup_scooter_Austin_2019/`
- `data/outputs/dropoff_scooter_Austin_2019/`

The PNG filename format is intentionally kept identical to the original workflow.

## Repository Structure

```text
austin_tx_dataset_pipeline/
├── config/
│   └── pipeline_config.example.yaml
├── data/
│   ├── reference/
│   │   ├── Austin_205_tracts_from_TIGER.csv
│   │   └── BOUNDARIES_jurisdictions_20250809.geojson
│   ├── raw/
│   ├── interim/
│   ├── processed/
│   ├── final/
│   └── outputs/
├── scripts/
│   ├── stage1_download_and_match_tract_centroids.py
│   ├── stage2_build_processed_trip_table.py
│   ├── stage3_build_final_2019_escooter_dataset.py
│   ├── stage4_generate_hourly_demand_images.py
│   └── run_full_pipeline.py
├── src/
│   └── austin_tx_pipeline/
│       ├── config.py
│       ├── logging_utils.py
│       ├── stage1_download_and_match.py
│       ├── stage2_standardize_table.py
│       ├── stage3_build_final_dataset.py
│       ├── stage4_generate_demand_images.py
│       └── tract_reference.py
├── .gitignore
├── LICENSE
├── requirements.txt
└── README.md
```

## Installation

1. Create and activate a Python environment (Python 3.9+ recommended).
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Run Instructions

Run from repository root (`austin_tx_dataset_pipeline`).

### Stage-by-stage

```bash
python scripts/stage1_download_and_match_tract_centroids.py
python scripts/stage2_build_processed_trip_table.py
python scripts/stage3_build_final_2019_escooter_dataset.py
python scripts/stage4_generate_hourly_demand_images.py
```

### End-to-end (YAML config)

```bash
python scripts/run_full_pipeline.py --config config/pipeline_config.example.yaml
```

## Configuration Notes

- Stage 1 uses `limit=15000000` by default.
- For quick tests, reduce `limit` in CLI or config.
- If you have a Socrata app token, set `SOCRATA_APP_TOKEN` or pass `--app-token`.

## Required Inputs

- Online Austin Socrata dataset (`7d8e-dm7r`) for raw trip records.
- Committed local reference files:
  - `data/reference/Austin_205_tracts_from_TIGER.csv`
  - `data/reference/BOUNDARIES_jurisdictions_20250809.geojson`

## Outputs Summary

- Stage 1: enriched raw table with mapped tract centroids
- Stage 2: standardized compact trip table
- Stage 3: final cleaned 2019 e-scooter dataset
- Stage 4: hourly pickup/dropoff image tensors (PNG files)

## Reproducibility Notes

- Stage outputs depend on the downloaded Socrata snapshot at execution time.
- City boundary and tract reference are versioned in `data/reference/`.
- Image naming format is fixed and reproducible.

## Geospatial Dependencies and Assumptions

- Input coordinates are lon/lat (`EPSG:4326`).
- Raster generation uses UTM Zone 14N (`EPSG:32614`).
- Grid extent is derived from Austin city boundary geometry.
- Tract membership uses 6-digit tract code matching (`TRACTCE10`) from trip GEOIDs.

## Runtime and Storage Considerations

- Stage 1 and Stage 2 are large-scale I/O operations for 15M records.
- Ensure sufficient disk space for intermediate CSV files and PNG outputs.
- Stage 4 writes `365 x 24 = 8760` images per channel (pickup + dropoff).

## Citation

If you use this pipeline, cite:
- Paper A (IEEE ITS journal paper accompanying this repository)
- Austin Open Data source for trip records
- U.S. Census TIGER/Line tract source used for tract reference preparation

## Limitations / Disclaimer

- This repository is for research reproducibility.
- Data source schemas can evolve over time.
- Results can vary if upstream raw records change after publication date.

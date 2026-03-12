# Data Directory Layout

- `data/reference/`: committed reference geospatial files used by the pipeline.
- `data/raw/`: optional raw file snapshots.
- `data/interim/`: Stage 1 outputs.
- `data/processed/`: Stage 2 outputs.
- `data/final/`: Stage 3 final tabular dataset.
- `data/outputs/`: Stage 4 pickup/dropoff PNG images and Stage 5 global binary mask PNG.

This repository tracks only `data/reference/` by default. Other folders are ignored in `.gitignore`.

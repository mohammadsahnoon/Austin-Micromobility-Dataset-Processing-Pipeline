"""Stage 5: Generate a global binary activity mask for Austin (2019)."""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer

LOGGER = logging.getLogger(__name__)


def _coerce_required_columns(trips_df: pd.DataFrame) -> pd.DataFrame:
    required_columns = [
        "start_date",
        "start_hour",
        "trip_duration_min",
        "startx",
        "starty",
        "endx",
        "endy",
    ]
    missing_columns = [name for name in required_columns if name not in trips_df.columns]
    if missing_columns:
        raise ValueError(f"Input CSV missing required columns: {missing_columns}")

    cleaned_df = trips_df.copy()
    cleaned_df["start_date"] = pd.to_datetime(cleaned_df["start_date"], errors="coerce")
    cleaned_df["start_hour"] = pd.to_numeric(cleaned_df["start_hour"], errors="coerce")
    cleaned_df["trip_duration_min"] = pd.to_numeric(cleaned_df["trip_duration_min"], errors="coerce")

    for column_name in ["startx", "starty", "endx", "endy"]:
        cleaned_df[column_name] = pd.to_numeric(cleaned_df[column_name], errors="coerce")

    cleaned_df = cleaned_df.dropna(subset=required_columns).copy()
    cleaned_df = cleaned_df[cleaned_df["start_hour"].between(0, 23, inclusive="both")]
    cleaned_df["start_hour"] = cleaned_df["start_hour"].astype(int)
    return cleaned_df


def _project_lon_lat_to_xy(
    trips_df: pd.DataFrame,
    from_crs: str,
    to_crs: str,
) -> pd.DataFrame:
    transformer = Transformer.from_crs(from_crs, to_crs, always_xy=True)
    start_x_m, start_y_m = transformer.transform(
        trips_df["startx"].to_numpy(),
        trips_df["starty"].to_numpy(),
    )
    end_x_m, end_y_m = transformer.transform(
        trips_df["endx"].to_numpy(),
        trips_df["endy"].to_numpy(),
    )

    projected_df = trips_df.copy()
    projected_df["startx_m"] = start_x_m
    projected_df["starty_m"] = start_y_m
    projected_df["endx_m"] = end_x_m
    projected_df["endy_m"] = end_y_m
    return projected_df


def _build_city_grid(
    city_boundary_geojson: str | Path,
    crs_projected: str,
    cell_size_x_m: float,
    cell_size_y_m: float,
) -> tuple[float, float, float, float, int, int]:
    city_gdf = gpd.read_file(city_boundary_geojson).to_crs(crs_projected)
    min_x, min_y, max_x, max_y = city_gdf.total_bounds

    min_x = np.floor(min_x / cell_size_x_m) * cell_size_x_m
    max_x = np.ceil(max_x / cell_size_x_m) * cell_size_x_m
    min_y = np.floor(min_y / cell_size_y_m) * cell_size_y_m
    max_y = np.ceil(max_y / cell_size_y_m) * cell_size_y_m

    width = int(np.floor((max_x - min_x) / cell_size_x_m)) + 1
    height = int(np.floor((max_y - min_y) / cell_size_y_m)) + 1
    return min_x, max_x, min_y, max_y, height, width


def _to_raster_indices(
    x_values: np.ndarray,
    y_values: np.ndarray,
    min_x: float,
    max_y: float,
    cell_size_x_m: float,
    cell_size_y_m: float,
) -> tuple[np.ndarray, np.ndarray]:
    cols = np.floor((x_values - min_x) / cell_size_x_m).astype(np.int64)
    rows = np.floor((max_y - y_values) / cell_size_y_m).astype(np.int64)
    return rows, cols


def generate_global_binary_activity_mask(
    input_csv: str | Path,
    city_boundary_geojson: str | Path,
    output_png: str | Path,
    cell_size_x_m: float = 240.0,
    cell_size_y_m: float = 220.0,
    crs_geographic: str = "EPSG:4326",
    crs_projected: str = "EPSG:32614",
    image_dtype: np.dtype = np.uint16,
) -> dict:
    """
    Generate a global 0/1 activity mask from trip start/end points.

    A cell is set to 1 if at least one pickup or dropoff falls in that cell.
    """
    output_path = Path(output_png)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    trips_df = pd.read_csv(input_csv, low_memory=False)
    trips_df = _coerce_required_columns(trips_df)
    trips_df = _project_lon_lat_to_xy(
        trips_df,
        from_crs=crs_geographic,
        to_crs=crs_projected,
    )

    min_x, max_x, min_y, max_y, height, width = _build_city_grid(
        city_boundary_geojson=city_boundary_geojson,
        crs_projected=crs_projected,
        cell_size_x_m=cell_size_x_m,
        cell_size_y_m=cell_size_y_m,
    )

    start_rows, start_cols = _to_raster_indices(
        trips_df["startx_m"].to_numpy(),
        trips_df["starty_m"].to_numpy(),
        min_x=min_x,
        max_y=max_y,
        cell_size_x_m=cell_size_x_m,
        cell_size_y_m=cell_size_y_m,
    )
    end_rows, end_cols = _to_raster_indices(
        trips_df["endx_m"].to_numpy(),
        trips_df["endy_m"].to_numpy(),
        min_x=min_x,
        max_y=max_y,
        cell_size_x_m=cell_size_x_m,
        cell_size_y_m=cell_size_y_m,
    )

    counts = np.zeros((height, width), dtype=np.uint32)

    start_in_bounds = (
        (start_cols >= 0)
        & (start_cols < width)
        & (start_rows >= 0)
        & (start_rows < height)
    )
    if np.any(start_in_bounds):
        np.add.at(counts, (start_rows[start_in_bounds], start_cols[start_in_bounds]), 1)

    end_in_bounds = (
        (end_cols >= 0)
        & (end_cols < width)
        & (end_rows >= 0)
        & (end_rows < height)
    )
    if np.any(end_in_bounds):
        np.add.at(counts, (end_rows[end_in_bounds], end_cols[end_in_bounds]), 1)

    mask = (counts > 0).astype(image_dtype)
    success = cv2.imwrite(str(output_path), mask)
    if not success:
        raise RuntimeError(f"Failed to write mask PNG: {output_path}")

    active_cells = int(np.count_nonzero(mask))
    LOGGER.info(
        "Stage 5 complete. Global mask saved to %s (shape=%dx%d, active_cells=%d)",
        output_path,
        height,
        width,
        active_cells,
    )
    return {
        "path": str(output_path),
        "width": width,
        "height": height,
        "active_cells": active_cells,
        "cell_size_x_m": float(cell_size_x_m),
        "cell_size_y_m": float(cell_size_y_m),
        "crs": crs_projected,
        "min_x": float(min_x),
        "max_x": float(max_x),
        "min_y": float(min_y),
        "max_y": float(max_y),
    }

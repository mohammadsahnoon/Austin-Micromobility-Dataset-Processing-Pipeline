"""Stage 4: Generate hourly pickup and dropoff demand images."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

import cv2
import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
from tqdm import tqdm

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


def _compute_end_datetime_columns(trips_df: pd.DataFrame) -> pd.DataFrame:
    start_datetime = trips_df["start_date"] + pd.to_timedelta(trips_df["start_hour"], unit="h")
    end_datetime = start_datetime + pd.to_timedelta(trips_df["trip_duration_min"], unit="m")

    trips_df = trips_df.copy()
    trips_df["start_day"] = start_datetime.dt.floor("D")
    trips_df["end_day"] = end_datetime.dt.floor("D")
    trips_df["end_hour"] = end_datetime.dt.hour.astype(int)
    return trips_df


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

    # Snap city extent to pixel grid for stable raster coordinates.
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
    rows = np.floor((max_y - y_values) / cell_size_y_m).astype(np.int64)  # north-up
    return rows, cols


def _rasterize_points(
    rows: np.ndarray,
    cols: np.ndarray,
    height: int,
    width: int,
    dtype: np.dtype,
) -> np.ndarray:
    image = np.zeros((height, width), dtype=dtype)
    in_bounds = (cols >= 0) & (cols < width) & (rows >= 0) & (rows < height)
    if np.any(in_bounds):
        np.add.at(image, (rows[in_bounds], cols[in_bounds]), 1)
    return image


def _verify_full_year(folder_path: str | Path, prefix: str, year: int = 2019) -> None:
    dates = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")
    expected_slots = {(date.strftime("%Y-%m-%d"), hour) for date in dates for hour in range(24)}

    pattern = re.compile(
        rf"^{re.escape(prefix)}_\d+_(\d{{4}}-\d{{2}}-\d{{2}})_(\d{{1,2}})\.png$",
        flags=re.IGNORECASE,
    )

    discovered_slots: set[tuple[str, int]] = set()
    for filename in os.listdir(folder_path):
        match = pattern.match(filename)
        if not match:
            continue
        date_string, hour_string = match.group(1), match.group(2)
        try:
            hour_value = int(hour_string)
        except ValueError:
            continue
        if 0 <= hour_value <= 23:
            discovered_slots.add((date_string, hour_value))

    missing_slots = sorted(expected_slots - discovered_slots)
    if missing_slots:
        LOGGER.warning("Missing %d image slots in %s. Sample: %s", len(missing_slots), folder_path, missing_slots[:10])
    else:
        LOGGER.info("%s has full %d-hour coverage for year %d.", folder_path, len(expected_slots), year)


def generate_hourly_demand_images(
    input_csv: str | Path,
    city_boundary_geojson: str | Path,
    pickup_output_dir: str | Path,
    dropoff_output_dir: str | Path,
    cell_size_x_m: float = 240.0,
    cell_size_y_m: float = 220.0,
    crs_geographic: str = "EPSG:4326",
    crs_projected: str = "EPSG:32614",
    image_dtype: np.dtype = np.uint16,
) -> tuple[int, int]:
    """
    Generate 2019 pickup/dropoff images with fixed naming format.

    PNG filenames intentionally follow original format:
    - pickup_{index:04}_{YYYY-MM-DD}_{hour}.png
    - dropoff_{index:04}_{YYYY-MM-DD}_{hour}.png
    """
    pickup_dir = Path(pickup_output_dir)
    dropoff_dir = Path(dropoff_output_dir)
    pickup_dir.mkdir(parents=True, exist_ok=True)
    dropoff_dir.mkdir(parents=True, exist_ok=True)

    trips_df = pd.read_csv(input_csv, low_memory=False)
    trips_df = _coerce_required_columns(trips_df)
    trips_df = _compute_end_datetime_columns(trips_df)
    trips_df = _project_lon_lat_to_xy(trips_df, from_crs=crs_geographic, to_crs=crs_projected)

    min_x, max_x, min_y, max_y, height, width = _build_city_grid(
        city_boundary_geojson=city_boundary_geojson,
        crs_projected=crs_projected,
        cell_size_x_m=cell_size_x_m,
        cell_size_y_m=cell_size_y_m,
    )
    LOGGER.info(
        "Grid built from city bounds: width=%d height=%d cell=(%.1f, %.1f)m",
        width,
        height,
        cell_size_x_m,
        cell_size_y_m,
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

    start_day_values = pd.to_datetime(trips_df["start_day"]).dt.strftime("%Y-%m-%d").to_numpy()
    start_hour_values = trips_df["start_hour"].to_numpy()
    end_day_values = pd.to_datetime(trips_df["end_day"]).dt.strftime("%Y-%m-%d").to_numpy()
    end_hour_values = trips_df["end_hour"].to_numpy()

    year = 2019
    days_2019 = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")
    blank_image = np.zeros((height, width), dtype=image_dtype)

    LOGGER.info("Generating pickup images...")
    pickup_count = 0
    for day_timestamp in tqdm(days_2019, desc="Pickup Days"):
        day_string = day_timestamp.strftime("%Y-%m-%d")
        day_mask = start_day_values == day_string
        for hour in range(24):
            slice_indices = np.flatnonzero(day_mask & (start_hour_values == hour))
            if slice_indices.size == 0:
                image = blank_image
            else:
                image = _rasterize_points(
                    rows=start_rows[slice_indices],
                    cols=start_cols[slice_indices],
                    height=height,
                    width=width,
                    dtype=image_dtype,
                )
            filename = f"pickup_{pickup_count:04}_{day_string}_{hour}.png"
            cv2.imwrite(str(pickup_dir / filename), image)
            pickup_count += 1

    LOGGER.info("Generating dropoff images...")
    dropoff_count = 0
    for day_timestamp in tqdm(days_2019, desc="Dropoff Days"):
        day_string = day_timestamp.strftime("%Y-%m-%d")
        day_mask = end_day_values == day_string
        for hour in range(24):
            slice_indices = np.flatnonzero(day_mask & (end_hour_values == hour))
            if slice_indices.size == 0:
                image = blank_image
            else:
                image = _rasterize_points(
                    rows=end_rows[slice_indices],
                    cols=end_cols[slice_indices],
                    height=height,
                    width=width,
                    dtype=image_dtype,
                )
            filename = f"dropoff_{dropoff_count:04}_{day_string}_{hour}.png"
            cv2.imwrite(str(dropoff_dir / filename), image)
            dropoff_count += 1

    _verify_full_year(pickup_dir, "pickup", year=year)
    _verify_full_year(dropoff_dir, "dropoff", year=year)
    LOGGER.info("Stage 4 complete. Pickup images=%d, Dropoff images=%d", pickup_count, dropoff_count)
    return pickup_count, dropoff_count

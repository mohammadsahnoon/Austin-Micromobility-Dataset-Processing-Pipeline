"""Stage 2: Standardize and reduce Stage 1 output into the core processed trip table."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

LOGGER = logging.getLogger(__name__)

OUTPUT_COLUMNS = [
    "ID",
    "device_id",
    "vehicle_type",
    "start_date",
    "start_hour",
    "start_day_of_week",
    "trip_duration_min",
    "trip_length_km",
    "census_geoid_start",
    "census_geoid_end",
    "startx",
    "starty",
    "endx",
    "endy",
]

DAY_OF_WEEK_MAP = {
    0: "0 Sunday",
    1: "1 Monday",
    2: "2 Tuesday",
    3: "3 Wednesday",
    4: "4 Thursday",
    5: "5 Friday",
    6: "6 Saturday",
}


def _build_local_start_datetime(chunk_df: pd.DataFrame) -> pd.Series:
    if "start_time" in chunk_df.columns:
        start_utc = pd.to_datetime(chunk_df["start_time"], errors="coerce", utc=True)
        return start_utc.dt.tz_convert("US/Central")

    if "start_time_us_central" not in chunk_df.columns:
        raise ValueError("Stage 1 input must include either 'start_time' or 'start_time_us_central'.")

    start_local = pd.to_datetime(chunk_df["start_time_us_central"], errors="coerce")
    if getattr(start_local.dt, "tz", None) is None:
        return start_local.dt.tz_localize(
            "US/Central",
            nonexistent="shift_forward",
            ambiguous="NaT",
        )
    return start_local.dt.tz_convert("US/Central")


def _transform_chunk(chunk_df: pd.DataFrame) -> pd.DataFrame:
    transformed_df = chunk_df.copy()
    start_local = _build_local_start_datetime(transformed_df)

    transformed_df["start_date"] = start_local.dt.date.astype(str)
    transformed_df["start_hour"] = start_local.dt.hour

    day_of_week = (start_local.dt.dayofweek + 1) % 7  # Monday=0 -> Sunday=0
    transformed_df["start_day_of_week"] = day_of_week.map(DAY_OF_WEEK_MAP)

    if "trip_duration" in transformed_df.columns:
        transformed_df["trip_duration_min"] = pd.to_numeric(
            transformed_df["trip_duration"], errors="coerce"
        ) / 60.0
    elif "trip_duration_sec" in transformed_df.columns:
        transformed_df["trip_duration_min"] = pd.to_numeric(
            transformed_df["trip_duration_sec"], errors="coerce"
        ) / 60.0
    else:
        transformed_df["trip_duration_min"] = pd.NA

    if "trip_distance" in transformed_df.columns:
        transformed_df["trip_length_km"] = pd.to_numeric(
            transformed_df["trip_distance"], errors="coerce"
        ) / 1000.0
    else:
        transformed_df["trip_length_km"] = pd.NA

    transformed_df = transformed_df.rename(columns={"trip_id": "ID"})

    for column_name in OUTPUT_COLUMNS:
        if column_name not in transformed_df.columns:
            transformed_df[column_name] = pd.NA

    return transformed_df[OUTPUT_COLUMNS]


def build_processed_trip_table(
    input_csv: str | Path,
    output_csv: str | Path,
    chunksize: int = 500_000,
) -> int:
    """Create processed Stage 2 table from Stage 1 CSV."""
    input_path = Path(input_csv)
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    total_rows_written = 0
    write_header = True

    for chunk_index, chunk_df in enumerate(
        pd.read_csv(input_path, low_memory=False, chunksize=chunksize),
        start=1,
    ):
        transformed_chunk = _transform_chunk(chunk_df)
        transformed_chunk.to_csv(
            output_path,
            mode="w" if write_header else "a",
            index=False,
            header=write_header,
        )
        write_header = False

        total_rows_written += len(transformed_chunk)
        LOGGER.info(
            "Processed Stage 2 chunk %d, rows=%d, cumulative=%d",
            chunk_index,
            len(transformed_chunk),
            total_rows_written,
        )

    LOGGER.info("Stage 2 complete. Output: %s", output_path)
    return total_rows_written

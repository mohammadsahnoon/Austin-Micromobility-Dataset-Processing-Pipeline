"""Stage 3: Build final cleaned 2019 e-scooter dataset."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from .tract_reference import extract_last_six_digits, load_valid_tract_codes

LOGGER = logging.getLogger(__name__)

STAGE2_COLUMNS = [
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

FINAL_COLUMNS = STAGE2_COLUMNS + ["avg_speed_kmh"]


def _transform_stage3_chunk(chunk_df: pd.DataFrame, valid_tract_codes: set[str]) -> pd.DataFrame:
    working_df = chunk_df.copy()
    working_df["vehicle_type"] = working_df["vehicle_type"].astype(str).str.lower()
    working_df = working_df[working_df["vehicle_type"] == "scooter"].copy()
    if working_df.empty:
        return working_df

    working_df["start_date"] = pd.to_datetime(working_df["start_date"], errors="coerce")
    working_df["start_hour"] = pd.to_numeric(working_df["start_hour"], errors="coerce")
    working_df["trip_duration_min"] = pd.to_numeric(working_df["trip_duration_min"], errors="coerce")
    working_df["trip_length_km"] = pd.to_numeric(working_df["trip_length_km"], errors="coerce")
    working_df["startx"] = pd.to_numeric(working_df["startx"], errors="coerce")
    working_df["starty"] = pd.to_numeric(working_df["starty"], errors="coerce")
    working_df["endx"] = pd.to_numeric(working_df["endx"], errors="coerce")
    working_df["endy"] = pd.to_numeric(working_df["endy"], errors="coerce")

    working_df = working_df[working_df["start_date"].dt.year == 2019].copy()
    if working_df.empty:
        return working_df

    duration_hours = working_df["trip_duration_min"] / 60.0
    working_df["avg_speed_kmh"] = working_df["trip_length_km"] / duration_hours

    quality_mask = (
        working_df["trip_duration_min"].between(1, 120, inclusive="both")
        & working_df["trip_length_km"].between(0.1, 35, inclusive="both")
        & working_df["avg_speed_kmh"].between(2, 26, inclusive="both")
    )
    working_df = working_df[quality_mask].copy()
    if working_df.empty:
        return working_df

    working_df = working_df.dropna(subset=FINAL_COLUMNS).copy()
    if working_df.empty:
        return working_df

    start_tract_6 = extract_last_six_digits(working_df["census_geoid_start"])
    end_tract_6 = extract_last_six_digits(working_df["census_geoid_end"])
    tract_mask = start_tract_6.isin(valid_tract_codes) & end_tract_6.isin(valid_tract_codes)
    working_df = working_df[tract_mask].copy()
    if working_df.empty:
        return working_df

    # Keep string date in final output to match original workflow output style.
    working_df["start_date"] = working_df["start_date"].dt.date.astype(str)
    return working_df[FINAL_COLUMNS]


def build_final_2019_escooter_dataset(
    input_csv: str | Path,
    output_csv: str | Path,
    tract_reference_csv: str | Path,
    chunksize: int = 500_000,
) -> int:
    """
    Build final Stage 3 dataset from Stage 2 output.

    Using Austin_205_tracts_from_TIGER.csv replaces suspect-tract geometry filtering:
    only trips whose start and end tracts are in the 205-tract reference are retained.
    """
    input_path = Path(input_csv)
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    valid_tract_codes = load_valid_tract_codes(tract_reference_csv)
    LOGGER.info("Loaded %d valid tract codes from %s", len(valid_tract_codes), tract_reference_csv)

    total_rows_written = 0
    write_header = True

    for chunk_index, chunk_df in enumerate(
        pd.read_csv(input_path, low_memory=False, chunksize=chunksize),
        start=1,
    ):
        filtered_chunk = _transform_stage3_chunk(chunk_df, valid_tract_codes)
        if filtered_chunk.empty:
            LOGGER.info("Stage 3 chunk %d produced 0 rows after filtering.", chunk_index)
            continue

        filtered_chunk.to_csv(
            output_path,
            mode="w" if write_header else "a",
            index=False,
            header=write_header,
        )
        write_header = False

        total_rows_written += len(filtered_chunk)
        LOGGER.info(
            "Processed Stage 3 chunk %d, rows=%d, cumulative=%d",
            chunk_index,
            len(filtered_chunk),
            total_rows_written,
        )

    LOGGER.info("Stage 3 complete. Output: %s", output_path)
    return total_rows_written

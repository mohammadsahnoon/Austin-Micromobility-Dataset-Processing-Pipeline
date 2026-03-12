"""Utilities for Census tract reference handling."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd
from shapely import wkt


def extract_last_six_digits(values: pd.Series) -> pd.Series:
    """Extract and zero-pad last 6 digits from mixed GEOID representations."""
    digits = values.astype(str).str.extract(r"(\d+)", expand=False).fillna("")
    return digits.str[-6:].str.zfill(6)


def _safe_centroid_xy(geometry_wkt: str) -> tuple[float, float] | None:
    if not isinstance(geometry_wkt, str) or not geometry_wkt.strip():
        return None
    try:
        geometry = wkt.loads(geometry_wkt)
    except Exception:
        return None
    if geometry.is_empty:
        return None
    centroid = geometry.centroid
    return centroid.x, centroid.y


def load_tract_reference_with_centroids(tract_reference_csv: str | Path) -> pd.DataFrame:
    """
    Load tract reference CSV and compute centroid coordinates.

    Supported geometry columns:
    - geometry_wkt (Austin_205_tracts_from_TIGER.csv)
    - the_geom (Boundaries__Austin_MSA_Census_Tracts_2010_20240306.csv)
    """
    tract_reference_path = Path(tract_reference_csv)
    tract_df = pd.read_csv(tract_reference_path, low_memory=False)
    if "TRACTCE10" not in tract_df.columns:
        raise ValueError(f"'TRACTCE10' is required in tract reference: {tract_reference_path}")

    if "geometry_wkt" in tract_df.columns:
        geometry_column = "geometry_wkt"
    elif "the_geom" in tract_df.columns:
        geometry_column = "the_geom"
    else:
        raise ValueError(
            "Tract reference must include either 'geometry_wkt' or 'the_geom'."
        )

    tract_df = tract_df.copy()
    tract_df["TRACTCE10"] = extract_last_six_digits(tract_df["TRACTCE10"])
    tract_df["centroid_xy"] = tract_df[geometry_column].apply(_safe_centroid_xy)
    tract_df = tract_df[tract_df["centroid_xy"].notna()].copy()

    tract_df["centroid_x"] = tract_df["centroid_xy"].apply(lambda point: point[0])
    tract_df["centroid_y"] = tract_df["centroid_xy"].apply(lambda point: point[1])

    if "GEOID" not in tract_df.columns:
        tract_df["GEOID"] = pd.NA

    tract_df = tract_df.drop_duplicates(subset=["TRACTCE10"], keep="first").copy()
    return tract_df[["GEOID", "TRACTCE10", "centroid_x", "centroid_y"]]


def load_valid_tract_codes(tract_reference_csv: str | Path) -> set[str]:
    """Load unique 6-digit tract codes from a tract reference CSV."""
    tract_codes = pd.read_csv(tract_reference_csv, usecols=["TRACTCE10"], low_memory=False)
    return set(extract_last_six_digits(tract_codes["TRACTCE10"]).unique())


def attach_tract_centroids(
    trips_df: pd.DataFrame,
    tract_reference_df: pd.DataFrame,
) -> pd.DataFrame:
    """Attach start/end centroid coordinates based on last 6 digits of GEOIDs."""
    enriched_df = trips_df.copy()
    enriched_df["last_six_digits_start"] = extract_last_six_digits(enriched_df["census_geoid_start"])
    enriched_df["last_six_digits_end"] = extract_last_six_digits(enriched_df["census_geoid_end"])

    centroid_x_map = tract_reference_df.set_index("TRACTCE10")["centroid_x"].to_dict()
    centroid_y_map = tract_reference_df.set_index("TRACTCE10")["centroid_y"].to_dict()

    enriched_df["startx"] = enriched_df["last_six_digits_start"].map(centroid_x_map)
    enriched_df["starty"] = enriched_df["last_six_digits_start"].map(centroid_y_map)
    enriched_df["endx"] = enriched_df["last_six_digits_end"].map(centroid_x_map)
    enriched_df["endy"] = enriched_df["last_six_digits_end"].map(centroid_y_map)

    enriched_df["TRACTCE10_matched_start"] = enriched_df["last_six_digits_start"].where(
        enriched_df["last_six_digits_start"].isin(centroid_x_map)
    )
    enriched_df["TRACTCE10_matched_end"] = enriched_df["last_six_digits_end"].where(
        enriched_df["last_six_digits_end"].isin(centroid_x_map)
    )
    return enriched_df

"""Build Austin_205_tracts_from_TIGER.csv from TIGER tracts and trip GEOIDs."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from austin_tx_pipeline.logging_utils import configure_logging

LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Regenerate Austin_205_tracts_from_TIGER.csv using a trips table, "
            "Austin boundary, and statewide Texas TIGER 2010 tract zip."
        )
    )
    parser.add_argument(
        "--trips-csv",
        required=True,
        help=(
            "Trip CSV containing census_geoid_start and census_geoid_end columns. "
            "This script uses GEOIDs present in this file to select tracts."
        ),
    )
    parser.add_argument(
        "--city-boundary-geojson",
        default="data/reference/BOUNDARIES_jurisdictions_20250809.geojson",
        help="Austin jurisdictions GeoJSON path.",
    )
    parser.add_argument(
        "--tiger-zip",
        required=True,
        help="Path to tl_2010_48_tract10.zip (Texas statewide TIGER 2010 tracts).",
    )
    parser.add_argument(
        "--output-csv",
        default="data/reference/Austin_205_tracts_from_TIGER.csv",
        help="Output tract reference CSV path.",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    return parser.parse_args()


def _clean_geoid11(values: pd.Series) -> pd.Series:
    digits = values.astype(str).str.extract(r"(\d+)", expand=False).fillna("")
    cleaned = digits[digits.str.len() >= 11].str[:11]
    return cleaned


def _remove_holes(geometry):
    if isinstance(geometry, Polygon):
        return Polygon(geometry.exterior)
    if isinstance(geometry, MultiPolygon):
        return MultiPolygon([Polygon(poly.exterior) for poly in geometry.geoms])
    return geometry


def _build_tolerant_city_geometry(city_boundary_geojson: str | Path):
    city_gdf = gpd.read_file(city_boundary_geojson)
    city_gdf = city_gdf.set_crs("EPSG:4326") if city_gdf.crs is None else city_gdf.to_crs("EPSG:4326")
    city_union = city_gdf.geometry.unary_union

    eps_buffer = 1e-4
    eps_close = 2e-4
    city_buffered = city_union.buffer(eps_buffer)
    city_closed = city_union.buffer(eps_close).buffer(-eps_close)
    city_no_holes = _remove_holes(city_union)
    city_tolerant = unary_union([city_buffered, city_closed, city_no_holes])
    return city_tolerant


def build_reference_csv(
    trips_csv: str | Path,
    city_boundary_geojson: str | Path,
    tiger_zip: str | Path,
    output_csv: str | Path,
) -> int:
    trips_df = pd.read_csv(trips_csv, low_memory=False)
    required_columns = {"census_geoid_start", "census_geoid_end"}
    missing = required_columns - set(trips_df.columns)
    if missing:
        raise ValueError(f"Trips CSV missing required columns: {sorted(missing)}")

    geoid_start = _clean_geoid11(trips_df["census_geoid_start"])
    geoid_end = _clean_geoid11(trips_df["census_geoid_end"])
    geoid_set = set(pd.unique(pd.concat([geoid_start, geoid_end], ignore_index=True)))
    LOGGER.info("Unique 11-digit GEOIDs from trips: %d", len(geoid_set))

    city_tolerant = _build_tolerant_city_geometry(city_boundary_geojson)

    tiger_path = Path(tiger_zip)
    tiger_gdf = gpd.read_file(f"zip://{tiger_path}").to_crs("EPSG:4326")
    tiger_gdf["GEOID10"] = tiger_gdf["GEOID10"].astype(str)
    tiger_gdf["TRACTCE10"] = tiger_gdf["TRACTCE10"].astype(str).str.zfill(6)

    selected = tiger_gdf[tiger_gdf["GEOID10"].isin(geoid_set)].copy()
    LOGGER.info("TIGER tracts after GEOID filter: %d", len(selected))

    selected = selected[selected.intersects(city_tolerant)].copy()
    LOGGER.info("TIGER tracts after Austin-intersection filter: %d", len(selected))

    output_df = pd.DataFrame(
        {
            "GEOID": selected["GEOID10"].astype(str),
            "TRACTCE10": selected["TRACTCE10"].astype(str).str.zfill(6),
            "geometry_wkt": selected.geometry.apply(lambda geom: geom.wkt),
        }
    )
    output_df = output_df.drop_duplicates(subset=["GEOID", "TRACTCE10"]).copy()
    output_df = output_df.sort_values(["TRACTCE10", "GEOID"]).reset_index(drop=True)

    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_df.to_csv(output_path, index=False)
    LOGGER.info("Saved %d tracts to %s", len(output_df), output_path)
    return len(output_df)


def main() -> None:
    args = parse_args()
    configure_logging(verbose=args.verbose)
    build_reference_csv(
        trips_csv=args.trips_csv,
        city_boundary_geojson=args.city_boundary_geojson,
        tiger_zip=args.tiger_zip,
        output_csv=args.output_csv,
    )


if __name__ == "__main__":
    main()

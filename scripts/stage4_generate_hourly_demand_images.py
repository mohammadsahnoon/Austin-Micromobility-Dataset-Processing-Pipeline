"""CLI for Stage 4."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from austin_tx_pipeline.logging_utils import configure_logging
from austin_tx_pipeline.stage4_generate_demand_images import generate_hourly_demand_images


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage 4: Generate hourly pickup/dropoff demand images for 2019."
    )
    parser.add_argument(
        "--input-csv",
        default="data/final/final_austin_escooter_2019_dataset.csv",
        help="Stage 3 output CSV path.",
    )
    parser.add_argument(
        "--city-boundary-geojson",
        default="data/reference/BOUNDARIES_jurisdictions_20250809.geojson",
        help="City boundary GeoJSON path.",
    )
    parser.add_argument(
        "--pickup-output-dir",
        default="data/outputs/pickup_scooter_Austin_2019",
        help="Pickup image output directory.",
    )
    parser.add_argument(
        "--dropoff-output-dir",
        default="data/outputs/dropoff_scooter_Austin_2019",
        help="Dropoff image output directory.",
    )
    parser.add_argument("--cell-size-x-m", type=float, default=240.0, help="Pixel width in meters.")
    parser.add_argument("--cell-size-y-m", type=float, default=220.0, help="Pixel height in meters.")
    parser.add_argument("--crs-geographic", default="EPSG:4326", help="Source lon/lat CRS.")
    parser.add_argument("--crs-projected", default="EPSG:32614", help="Projected CRS for raster grid.")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_logging(verbose=args.verbose)
    generate_hourly_demand_images(
        input_csv=args.input_csv,
        city_boundary_geojson=args.city_boundary_geojson,
        pickup_output_dir=args.pickup_output_dir,
        dropoff_output_dir=args.dropoff_output_dir,
        cell_size_x_m=args.cell_size_x_m,
        cell_size_y_m=args.cell_size_y_m,
        crs_geographic=args.crs_geographic,
        crs_projected=args.crs_projected,
    )


if __name__ == "__main__":
    main()

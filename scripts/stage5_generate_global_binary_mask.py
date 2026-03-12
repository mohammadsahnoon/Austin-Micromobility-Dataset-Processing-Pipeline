"""CLI for Stage 5."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from austin_tx_pipeline.logging_utils import configure_logging
from austin_tx_pipeline.stage5_generate_global_mask import generate_global_binary_activity_mask


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage 5: Generate a global binary activity mask for Austin 2019."
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
        "--output-png",
        default="data/outputs/global_mask_austin/Global_Mask_Austin_2019.png",
        help="Output PNG path for the global binary mask.",
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
    generate_global_binary_activity_mask(
        input_csv=args.input_csv,
        city_boundary_geojson=args.city_boundary_geojson,
        output_png=args.output_png,
        cell_size_x_m=args.cell_size_x_m,
        cell_size_y_m=args.cell_size_y_m,
        crs_geographic=args.crs_geographic,
        crs_projected=args.crs_projected,
    )


if __name__ == "__main__":
    main()


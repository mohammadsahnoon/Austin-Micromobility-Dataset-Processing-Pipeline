"""Run all five stages using a YAML configuration file."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from austin_tx_pipeline.config import load_config
from austin_tx_pipeline.logging_utils import configure_logging
from austin_tx_pipeline.stage1_download_and_match import download_and_match_tract_centroids
from austin_tx_pipeline.stage2_standardize_table import build_processed_trip_table
from austin_tx_pipeline.stage3_build_final_dataset import build_final_2019_escooter_dataset
from austin_tx_pipeline.stage4_generate_demand_images import generate_hourly_demand_images
from austin_tx_pipeline.stage5_generate_global_mask import generate_global_binary_activity_mask


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run full Austin TX dataset pipeline.")
    parser.add_argument(
        "--config",
        default="config/pipeline_config.example.yaml",
        help="YAML config path.",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_logging(verbose=args.verbose)

    config = load_config(args.config)

    stage1_cfg = config["stage1"]
    stage2_cfg = config["stage2"]
    stage3_cfg = config["stage3"]
    stage4_cfg = config["stage4"]
    stage5_cfg = config.get("stage5", {})

    download_and_match_tract_centroids(
        output_csv=stage1_cfg["output_csv"],
        tract_reference_csv=stage1_cfg["tract_reference_csv"],
        dataset_id=stage1_cfg.get("dataset_id", "7d8e-dm7r"),
        domain=stage1_cfg.get("domain", "data.austintexas.gov"),
        limit=int(stage1_cfg.get("limit", 15_000_000)),
        batch_size=int(stage1_cfg.get("batch_size", 50_000)),
        app_token=stage1_cfg.get("app_token"),
    )

    build_processed_trip_table(
        input_csv=stage2_cfg["input_csv"],
        output_csv=stage2_cfg["output_csv"],
        chunksize=int(stage2_cfg.get("chunksize", 500_000)),
    )

    build_final_2019_escooter_dataset(
        input_csv=stage3_cfg["input_csv"],
        output_csv=stage3_cfg["output_csv"],
        tract_reference_csv=stage3_cfg["tract_reference_csv"],
        chunksize=int(stage3_cfg.get("chunksize", 500_000)),
    )

    generate_hourly_demand_images(
        input_csv=stage4_cfg["input_csv"],
        city_boundary_geojson=stage4_cfg["city_boundary_geojson"],
        pickup_output_dir=stage4_cfg["pickup_output_dir"],
        dropoff_output_dir=stage4_cfg["dropoff_output_dir"],
        cell_size_x_m=float(stage4_cfg.get("cell_size_x_m", 240.0)),
        cell_size_y_m=float(stage4_cfg.get("cell_size_y_m", 220.0)),
        crs_geographic=stage4_cfg.get("crs_geographic", "EPSG:4326"),
        crs_projected=stage4_cfg.get("crs_projected", "EPSG:32614"),
    )

    generate_global_binary_activity_mask(
        input_csv=stage5_cfg.get("input_csv", stage3_cfg["output_csv"]),
        city_boundary_geojson=stage5_cfg.get(
            "city_boundary_geojson",
            stage4_cfg["city_boundary_geojson"],
        ),
        output_png=stage5_cfg.get(
            "output_png",
            "data/outputs/global_mask_austin/Global_Mask_Austin_2019.png",
        ),
        cell_size_x_m=float(stage5_cfg.get("cell_size_x_m", stage4_cfg.get("cell_size_x_m", 240.0))),
        cell_size_y_m=float(stage5_cfg.get("cell_size_y_m", stage4_cfg.get("cell_size_y_m", 220.0))),
        crs_geographic=stage5_cfg.get("crs_geographic", stage4_cfg.get("crs_geographic", "EPSG:4326")),
        crs_projected=stage5_cfg.get("crs_projected", stage4_cfg.get("crs_projected", "EPSG:32614")),
    )


if __name__ == "__main__":
    main()

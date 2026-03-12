"""CLI for Stage 3."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from austin_tx_pipeline.logging_utils import configure_logging
from austin_tx_pipeline.stage3_build_final_dataset import build_final_2019_escooter_dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage 3: Build final cleaned 2019 e-scooter dataset."
    )
    parser.add_argument(
        "--input-csv",
        default="data/processed/stage2_austin_trips_standardized.csv",
        help="Stage 2 output CSV path.",
    )
    parser.add_argument(
        "--tract-reference-csv",
        default="data/reference/Austin_205_tracts_from_TIGER.csv",
        help="Tract reference CSV path.",
    )
    parser.add_argument(
        "--output-csv",
        default="data/final/final_austin_escooter_2019_dataset.csv",
        help="Stage 3 output CSV path.",
    )
    parser.add_argument(
        "--chunksize",
        type=int,
        default=500_000,
        help="Read/process chunk size.",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_logging(verbose=args.verbose)
    build_final_2019_escooter_dataset(
        input_csv=args.input_csv,
        output_csv=args.output_csv,
        tract_reference_csv=args.tract_reference_csv,
        chunksize=args.chunksize,
    )


if __name__ == "__main__":
    main()

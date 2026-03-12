"""CLI for Stage 2."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from austin_tx_pipeline.logging_utils import configure_logging
from austin_tx_pipeline.stage2_standardize_table import build_processed_trip_table


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage 2: Build standardized processed trip table from Stage 1 output."
    )
    parser.add_argument(
        "--input-csv",
        default="data/interim/stage1_austin_trip_records_with_tract_centroids.csv",
        help="Stage 1 output CSV path.",
    )
    parser.add_argument(
        "--output-csv",
        default="data/processed/stage2_austin_trips_standardized.csv",
        help="Stage 2 output CSV path.",
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
    build_processed_trip_table(
        input_csv=args.input_csv,
        output_csv=args.output_csv,
        chunksize=args.chunksize,
    )


if __name__ == "__main__":
    main()

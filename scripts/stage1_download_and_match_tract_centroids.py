"""CLI for Stage 1."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from austin_tx_pipeline.logging_utils import configure_logging
from austin_tx_pipeline.stage1_download_and_match import download_and_match_tract_centroids


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage 1: Download Austin raw trips and attach tract centroid coordinates."
    )
    parser.add_argument(
        "--output-csv",
        default="data/interim/stage1_austin_trip_records_with_tract_centroids.csv",
        help="Output CSV path.",
    )
    parser.add_argument(
        "--tract-reference-csv",
        default="data/reference/Austin_205_tracts_from_TIGER.csv",
        help="Tract reference CSV path (Austin_205_tracts_from_TIGER.csv).",
    )
    parser.add_argument("--domain", default="data.austintexas.gov", help="Socrata domain.")
    parser.add_argument("--dataset-id", default="7d8e-dm7r", help="Socrata dataset ID.")
    parser.add_argument(
        "--limit",
        type=int,
        default=15_000_000,
        help=(
            "Maximum records to download. Default 15000000 reproduces original workflow. "
            "Lower this for preview/sample runs."
        ),
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50_000,
        help="Socrata batch size per request.",
    )
    parser.add_argument(
        "--app-token",
        default=os.getenv("SOCRATA_APP_TOKEN"),
        help="Optional Socrata app token. Falls back to SOCRATA_APP_TOKEN env var.",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_logging(verbose=args.verbose)
    download_and_match_tract_centroids(
        output_csv=args.output_csv,
        tract_reference_csv=args.tract_reference_csv,
        dataset_id=args.dataset_id,
        domain=args.domain,
        limit=args.limit,
        batch_size=args.batch_size,
        app_token=args.app_token,
    )


if __name__ == "__main__":
    main()

"""Stage 1: Download raw Austin trip records and attach tract centroid coordinates."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from sodapy import Socrata

from .tract_reference import attach_tract_centroids, load_tract_reference_with_centroids

LOGGER = logging.getLogger(__name__)


def download_and_match_tract_centroids(
    output_csv: str | Path,
    tract_reference_csv: str | Path,
    dataset_id: str = "7d8e-dm7r",
    domain: str = "data.austintexas.gov",
    limit: int = 15_000_000,
    batch_size: int = 50_000,
    app_token: str | None = None,
) -> int:
    """
    Download Austin trips from Socrata and write enriched rows to CSV.

    Notes:
    - Default `limit=15000000` matches the original workflow.
    - Users can lower `limit` for a preview/sample run.
    """
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    tract_reference_df = load_tract_reference_with_centroids(tract_reference_csv)
    LOGGER.info("Loaded tract reference: %d tracts", len(tract_reference_df))

    total_written = 0
    offset = 0
    write_header = True
    client = Socrata(domain, app_token)

    try:
        while offset < limit:
            request_size = min(batch_size, limit - offset)
            LOGGER.info(
                "Downloading batch offset=%d limit=%d (requested total=%d)",
                offset,
                request_size,
                limit,
            )
            records = client.get(dataset_id, limit=request_size, offset=offset)
            if not records:
                LOGGER.info("No more records returned by Socrata; stopping at %d rows.", total_written)
                break

            batch_df = pd.DataFrame.from_records(records)
            if batch_df.empty:
                LOGGER.info("Received empty batch; stopping.")
                break

            required_columns = {"census_geoid_start", "census_geoid_end"}
            missing_columns = required_columns - set(batch_df.columns)
            if missing_columns:
                raise ValueError(
                    f"Downloaded batch is missing required columns: {sorted(missing_columns)}"
                )

            enriched_batch = attach_tract_centroids(batch_df, tract_reference_df)
            enriched_batch.to_csv(
                output_path,
                mode="w" if write_header else "a",
                index=False,
                header=write_header,
            )
            write_header = False

            rows_in_batch = len(enriched_batch)
            total_written += rows_in_batch
            offset += rows_in_batch

            LOGGER.info(
                "Wrote %d rows in batch; cumulative rows written=%d",
                rows_in_batch,
                total_written,
            )

            if rows_in_batch < request_size:
                LOGGER.info(
                    "Last batch smaller than request (%d < %d); stopping.",
                    rows_in_batch,
                    request_size,
                )
                break
    finally:
        client.close()

    LOGGER.info("Stage 1 complete. Output: %s", output_path)
    return total_written

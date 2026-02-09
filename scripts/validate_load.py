"""Row count validation for Snowflake RAW tables against source files.

Connects to Snowflake, executes SELECT COUNT(*) on each RAW table,
reads source file row counts from validated CSV files, and compares
with a 1% tolerance threshold. Exits with code 0 if all datasets pass.

Usage:
    python scripts/validate_load.py
"""

from __future__ import annotations

import csv
import logging
import sys
from pathlib import Path
from typing import Final

from scripts.load import TABLE_CONFIGS, LoadError, SnowflakeConnectionManager

logger: Final[logging.Logger] = logging.getLogger(__name__)

_TOLERANCE_PCT: Final[float] = 1.0
_VALIDATED_DIR: Final[Path] = Path("data/validated")

_DATASET_SUBDIRS: Final[dict[str, str]] = {
    "ttc_subway_delays": "ttc_subway",
    "ttc_bus_delays": "ttc_bus",
    "ttc_streetcar_delays": "ttc_streetcar",
    "bike_share_ridership": "bike_share",
    "weather_daily": "weather",
}


def _count_source_rows(dataset_name: str) -> int:
    """Count total data rows across all validated CSV files for a dataset.

    Args:
        dataset_name: Machine-readable dataset identifier.

    Returns:
        Total row count (excluding header rows).
    """
    subdir = _DATASET_SUBDIRS.get(dataset_name, "")
    validated_dir = _VALIDATED_DIR / subdir
    if not validated_dir.exists():
        return 0

    total = 0
    for csv_path in sorted(validated_dir.rglob("*.csv")):
        with csv_path.open("r", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            next(reader, None)  # skip header
            total += sum(1 for _ in reader)

    return total


def _count_snowflake_rows(
    dataset_name: str,
    connection_manager: SnowflakeConnectionManager,
) -> int:
    """Query SELECT COUNT(*) from the Snowflake RAW table.

    Args:
        dataset_name: Machine-readable dataset identifier.
        connection_manager: Pre-configured connection manager.

    Returns:
        Row count from the Snowflake table.

    Raises:
        LoadError: If the query fails.
    """
    config = TABLE_CONFIGS[dataset_name]
    with connection_manager as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {config.table_name}")
            result = cursor.fetchone()
            return int(result[0]) if result else 0
        finally:
            cursor.close()


def validate_row_counts() -> bool:
    """Compare source file row counts against Snowflake table counts.

    Returns:
        True if all datasets are within the 1% tolerance threshold.
    """
    connection_manager = SnowflakeConnectionManager()
    all_pass = True

    header = (
        f"{'Dataset':<30} {'Source Rows':>12} {'SF Rows':>12} "
        f"{'Diff %':>8} {'Status':<8}"
    )
    print(f"\n{'=' * 80}")
    print("Row Count Validation (1% tolerance)")
    print(f"{'=' * 80}")
    print(header)
    print("-" * 80)

    for dataset_name in TABLE_CONFIGS:
        source_rows = _count_source_rows(dataset_name)

        try:
            sf_rows = _count_snowflake_rows(dataset_name, connection_manager)
        except (LoadError, Exception) as exc:
            print(
                f"{dataset_name:<30} {source_rows:>12,} {'ERROR':>12} {'N/A':>8} FAIL"
            )
            logger.error("Query failed for %s: %s", dataset_name, exc)
            all_pass = False
            continue

        if source_rows == 0:
            diff_pct = 0.0 if sf_rows == 0 else 100.0
        else:
            diff_pct = abs(sf_rows - source_rows) / source_rows * 100

        passed = diff_pct <= _TOLERANCE_PCT
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False

        print(
            f"{dataset_name:<30} {source_rows:>12,} {sf_rows:>12,} "
            f"{diff_pct:>7.2f}% {status:<8}"
        )

    print("-" * 80)
    overall = "PASS" if all_pass else "FAIL"
    print(f"Overall: {overall}")
    print(f"{'=' * 80}\n")

    return all_pass


def main() -> int:
    """CLI entry point for row count validation.

    Returns:
        Exit code: 0 if all datasets pass, 1 otherwise.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stderr,
    )

    passed = validate_row_counts()
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

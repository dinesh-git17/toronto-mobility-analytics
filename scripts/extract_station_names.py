"""Extract distinct TTC subway station names from validated delay data.

Reads all validated TTC subway delay CSVs, extracts unique
(raw_station_name, line_code) pairs with occurrence counts and
year ranges, and writes the analysis to a working CSV file for
manual curation in S002.

Usage:
    python -m scripts.extract_station_names
"""

from __future__ import annotations

import csv
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Final

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger: Final = logging.getLogger(__name__)

_SUBWAY_DIR: Final = Path("data/validated/ttc_subway")
_WORKING_DIR: Final = Path("data/working")
_OUTPUT_FILE: Final = _WORKING_DIR / "station_name_analysis.csv"

_OUTPUT_COLUMNS: Final[list[str]] = [
    "raw_station_name",
    "line_code",
    "occurrence_count",
    "first_seen_year",
    "last_seen_year",
]


def _extract_year_from_path(csv_path: Path) -> int:
    """Derive the data year from the parent directory name."""
    return int(csv_path.parent.name)


def _collect_station_pairs(
    subway_dir: Path,
) -> tuple[
    dict[tuple[str, str], dict[str, int | set[int]]],
    list[dict[str, str | int]],
]:
    """Scan all subway CSVs and accumulate station/line pair statistics.

    Returns:
        Tuple of (pair_stats, flagged_rows) where pair_stats maps
        (station, line) to occurrence_count and year sets, and
        flagged_rows contains rows with empty/invalid station names.
    """
    pair_stats: dict[tuple[str, str], dict[str, int | set[int]]] = defaultdict(
        lambda: {"count": 0, "years": set()}
    )
    flagged_rows: list[dict[str, str | int]] = []

    csv_files = sorted(subway_dir.rglob("*.csv"))
    if not csv_files:
        logger.error("No CSV files found in %s", subway_dir)
        sys.exit(1)

    for csv_path in csv_files:
        year = _extract_year_from_path(csv_path)
        logger.info("Processing %s (%d)", csv_path.name, year)

        with csv_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, start=2):
                raw_station = row.get("Station", "")
                line_code = row.get("Line", "")

                station_stripped = raw_station.strip()
                line_stripped = line_code.strip()

                if not station_stripped:
                    flagged_rows.append(
                        {
                            "file": str(csv_path),
                            "row_number": row_num,
                            "raw_station_name": raw_station,
                            "line_code": line_stripped,
                        }
                    )
                    continue

                key = (station_stripped, line_stripped)
                stats = pair_stats[key]
                count = stats["count"]
                assert isinstance(count, int)
                stats["count"] = count + 1
                years = stats["years"]
                assert isinstance(years, set)
                years.add(year)

    return pair_stats, flagged_rows


def _write_analysis(
    pair_stats: dict[tuple[str, str], dict[str, int | set[int]]],
    output_path: Path,
) -> int:
    """Write sorted station analysis to CSV. Return total distinct pairs."""
    sorted_pairs = sorted(pair_stats.keys(), key=lambda p: (p[0], p[1]))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(_OUTPUT_COLUMNS)
        for station, line in sorted_pairs:
            stats = pair_stats[(station, line)]
            years = stats["years"]
            assert isinstance(years, set)
            count = stats["count"]
            writer.writerow(
                [
                    station,
                    line,
                    count,
                    min(years),
                    max(years),
                ]
            )

    return len(sorted_pairs)


def main() -> None:
    """Run station name extraction pipeline."""
    if not _SUBWAY_DIR.exists():
        logger.error("Subway data directory not found: %s", _SUBWAY_DIR)
        sys.exit(1)

    pair_stats, flagged_rows = _collect_station_pairs(_SUBWAY_DIR)

    total = _write_analysis(pair_stats, _OUTPUT_FILE)
    logger.info("Total distinct (station, line) pairs: %d", total)
    logger.info("Output written to %s", _OUTPUT_FILE)

    # Unique station name count (ignoring line)
    unique_names = {station for station, _ in pair_stats}
    logger.info("Total distinct raw_station_name values: %d", len(unique_names))

    # Line coverage
    lines_seen = {line for _, line in pair_stats}
    logger.info("Lines observed: %s", sorted(lines_seen))

    if flagged_rows:
        logger.warning(
            "Flagged %d rows with empty/invalid station names:", len(flagged_rows)
        )
        for entry in flagged_rows[:20]:
            logger.warning(
                "  File: %s  Row: %s  Station: '%s'  Line: '%s'",
                entry["file"],
                entry["row_number"],
                entry["raw_station_name"],
                entry["line_code"],
            )
        if len(flagged_rows) > 20:
            logger.warning("  ... and %d more flagged rows", len(flagged_rows) - 20)


if __name__ == "__main__":
    main()

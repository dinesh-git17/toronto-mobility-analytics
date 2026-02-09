"""Generate bike_station_ref.csv from Bike Share Toronto GBFS station data.

Fetches station metadata from the GBFS station_information endpoint,
caches the raw JSON for reproducibility, extracts neighborhood from
the station group taxonomy, and writes the seed CSV.

Neighborhood assignment uses the ``groups`` field in the GBFS response.
Each station belongs to one or more groups: directional quadrants
(North, South, East, West), special classifications (E-Charging), and
neighborhood-level labels. The script selects the most specific
non-directional, non-classification group as the neighborhood value.

Usage:
    python scripts/generate_bike_station_ref.py
    python scripts/generate_bike_station_ref.py --from-cache
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from pathlib import Path
from typing import Any, Final

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger: Final = logging.getLogger(__name__)

_GBFS_URL: Final = "https://tor.publicbikesystem.net/ube/gbfs/v1/en/station_information"
_CACHE_PATH: Final = Path("data/working/gbfs_station_information.json")
_OUTPUT_PATH: Final = Path("seeds/bike_station_ref.csv")

_COLUMNS: Final[list[str]] = [
    "station_id",
    "station_name",
    "latitude",
    "longitude",
    "neighborhood",
]

# Toronto bounding box (DESIGN-DOC §4.3.2 coordinate validation)
_LAT_MIN: Final = 43.58
_LAT_MAX: Final = 43.86
_LON_MIN: Final = -79.64
_LON_MAX: Final = -79.10

# Groups that represent geographic quadrants, not neighborhoods
_NON_NEIGHBORHOOD_GROUPS: Final[frozenset[str]] = frozenset(
    {
        "E-Charging",
        "North",
        "South",
        "East",
        "West",
        "Central",
    }
)

# Known GBFS typos → corrected neighborhood names
_NEIGHBORHOOD_CORRECTIONS: Final[dict[str, str]] = {
    "Watefront": "Waterfront",
}


def fetch_gbfs_json() -> dict[str, Any]:
    """Fetch station information from the Bike Share Toronto GBFS endpoint.

    Returns:
        Parsed JSON response containing station data.

    Raises:
        SystemExit: If the HTTP request fails.
    """
    import httpx

    logger.info("Fetching GBFS station data from %s", _GBFS_URL)
    response = httpx.get(_GBFS_URL, timeout=30.0)
    if response.status_code != 200:
        logger.error("GBFS request failed: HTTP %d", response.status_code)
        sys.exit(1)

    data: dict[str, Any] = response.json()
    return data


def cache_json(data: dict[str, Any], path: Path | None = None) -> Path:
    """Write GBFS JSON to the local cache file.

    Args:
        data: Parsed GBFS JSON response.
        path: Cache file path. Defaults to _CACHE_PATH.

    Returns:
        Path of the written cache file.
    """
    output = path or _CACHE_PATH
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info("Cached GBFS JSON to %s", output)
    return output


def load_cached_json(path: Path | None = None) -> dict[str, Any]:
    """Load GBFS JSON from the local cache file.

    Args:
        path: Cache file path. Defaults to _CACHE_PATH.

    Returns:
        Parsed JSON data.

    Raises:
        SystemExit: If the cache file does not exist.
    """
    source = path or _CACHE_PATH
    if not source.exists():
        logger.error("Cache file not found: %s", source)
        sys.exit(1)

    with source.open(encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    logger.info("Loaded %s", source)
    return data


def _extract_neighborhood(groups: list[str]) -> str:
    """Extract the most specific neighborhood from a station's group list.

    Filters out directional quadrants and special classifications,
    returning the first remaining group as the neighborhood name.
    Falls back to the directional quadrant if no specific neighborhood
    group exists.

    Args:
        groups: List of group labels from the GBFS station object.

    Returns:
        Neighborhood name string.
    """
    # GBFS data contains trailing whitespace in some group names
    cleaned = [g.strip() for g in groups]
    specific = [g for g in cleaned if g not in _NON_NEIGHBORHOOD_GROUPS]

    if specific:
        neighborhood = specific[0]
    else:
        directional = [g for g in cleaned if g in _NON_NEIGHBORHOOD_GROUPS]
        directional = [g for g in directional if g != "E-Charging"]
        neighborhood = directional[0] if directional else "Downtown"

    return _NEIGHBORHOOD_CORRECTIONS.get(neighborhood, neighborhood)


def parse_stations(data: dict[str, Any]) -> list[dict[str, str]]:
    """Parse GBFS JSON into a list of station reference records.

    Validates coordinates are within the Toronto bounding box and
    ensures station_id is a positive integer. Stations outside the
    bounding box are logged and skipped.

    Args:
        data: Parsed GBFS JSON response.

    Returns:
        Sorted list of station record dicts with keys matching _COLUMNS.
    """
    raw_stations: list[dict[str, Any]] = data["data"]["stations"]
    records: list[dict[str, str]] = []
    seen_ids: set[int] = set()

    for station in raw_stations:
        station_id = int(station["station_id"])
        lat = float(station["lat"])
        lon = float(station["lon"])

        if station_id <= 0:
            logger.warning("Skipping non-positive station_id: %d", station_id)
            continue

        if not (_LAT_MIN <= lat <= _LAT_MAX):
            logger.warning(
                "Station %d latitude %.6f outside Toronto bbox", station_id, lat
            )
            continue

        if not (_LON_MIN <= lon <= _LON_MAX):
            logger.warning(
                "Station %d longitude %.6f outside Toronto bbox", station_id, lon
            )
            continue

        if station_id in seen_ids:
            logger.warning("Duplicate station_id: %d", station_id)
            continue

        seen_ids.add(station_id)
        groups: list[str] = station.get("groups", [])
        neighborhood = _extract_neighborhood(groups)

        records.append(
            {
                "station_id": str(station_id),
                "station_name": station["name"],
                "latitude": f"{lat:.6f}",
                "longitude": f"{lon:.6f}",
                "neighborhood": neighborhood,
            }
        )

    records.sort(key=lambda r: int(r["station_id"]))
    return records


def write_csv(records: list[dict[str, str]], path: Path | None = None) -> Path:
    """Write station reference records to CSV.

    Args:
        records: Station record dicts.
        path: Output file path. Defaults to _OUTPUT_PATH.

    Returns:
        Path of the written CSV file.
    """
    output = path or _OUTPUT_PATH
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_COLUMNS)
        writer.writeheader()
        writer.writerows(records)

    return output


def validate_records(records: list[dict[str, str]]) -> None:
    """Run post-generation validation checks on parsed records.

    Raises:
        ValueError: If any validation check fails.
    """
    if not records:
        msg = "No stations parsed from GBFS data"
        raise ValueError(msg)

    ids = [r["station_id"] for r in records]
    if len(ids) != len(set(ids)):
        msg = "Duplicate station_id values in output"
        raise ValueError(msg)

    for record in records:
        for col in _COLUMNS:
            value = record[col].strip()
            if not value:
                sid = record["station_id"]
                msg = f"Empty value in column '{col}' for station {sid}"
                raise ValueError(msg)

    logger.info("Validation passed: %d stations", len(records))


def main() -> None:
    """Entry point: fetch, parse, validate, and write station reference."""
    parser = argparse.ArgumentParser(
        description="Generate bike_station_ref.csv from GBFS data",
    )
    parser.add_argument(
        "--from-cache",
        action="store_true",
        help="Read from cached JSON instead of fetching from GBFS endpoint",
    )
    args = parser.parse_args()

    if args.from_cache:
        data = load_cached_json()
    else:
        data = fetch_gbfs_json()
        cache_json(data)

    records = parse_stations(data)
    validate_records(records)
    output = write_csv(records)
    print(f"Wrote {len(records)} stations to {output}")


if __name__ == "__main__":
    main()

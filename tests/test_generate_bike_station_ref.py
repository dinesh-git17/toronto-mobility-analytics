"""Tests for bike station reference seed generation.

Validates GBFS JSON parsing, coordinate validation, neighborhood
extraction from station groups, and CSV output correctness.
"""

from __future__ import annotations

import csv
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from scripts.generate_bike_station_ref import (
    _COLUMNS,
    _LAT_MAX,
    _LAT_MIN,
    _LON_MAX,
    _LON_MIN,
    _extract_neighborhood,
    cache_json,
    load_cached_json,
    parse_stations,
    validate_records,
    write_csv,
)

_VALID_STATION: Final[dict[str, Any]] = {
    "station_id": "7000",
    "name": "Fort York Blvd / Capreol Ct",
    "lat": 43.639832,
    "lon": -79.395954,
    "groups": ["South", "Fort York - Entertainment District"],
}

_CHARGING_STATION: Final[dict[str, Any]] = {
    "station_id": "7001",
    "name": "Wellesley Station Green P",
    "lat": 43.66496,
    "lon": -79.38355,
    "groups": ["E-Charging", "South", "Church Wellesley / Yorkville"],
}

_DIRECTIONAL_ONLY: Final[dict[str, Any]] = {
    "station_id": "7249",
    "name": "144 Harrison St",
    "lat": 43.651145,
    "lon": -79.423742,
    "groups": ["E-Charging", "West"],
}


def _make_gbfs(
    stations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a minimal GBFS JSON structure for testing."""
    return {
        "last_updated": 1700000000,
        "ttl": 10,
        "data": {
            "stations": stations or [_VALID_STATION],
        },
    }


# ---------------------------------------------------------------------------
# Neighborhood extraction
# ---------------------------------------------------------------------------


class TestNeighborhoodExtraction:
    """Validate neighborhood logic from station groups."""

    def test_specific_neighborhood_selected(self) -> None:
        result = _extract_neighborhood(["South", "Fort York - Entertainment District"])
        assert result == "Fort York - Entertainment District"

    def test_e_charging_filtered(self) -> None:
        result = _extract_neighborhood(
            ["E-Charging", "South", "Church Wellesley / Yorkville"]
        )
        assert result == "Church Wellesley / Yorkville"

    def test_directional_fallback(self) -> None:
        result = _extract_neighborhood(["E-Charging", "West"])
        assert result == "West"

    def test_multiple_directional_uses_first(self) -> None:
        result = _extract_neighborhood(["North", "East"])
        assert result == "North"

    def test_typo_correction_watefront(self) -> None:
        result = _extract_neighborhood(["E-Charging", "South", "Watefront"])
        assert result == "Waterfront"

    def test_empty_groups_fallback(self) -> None:
        result = _extract_neighborhood([])
        assert result == "Downtown"


# ---------------------------------------------------------------------------
# Station parsing
# ---------------------------------------------------------------------------


class TestParseStations:
    """Validate GBFS JSON parsing and coordinate filtering."""

    def test_valid_station_parsed(self) -> None:
        records = parse_stations(_make_gbfs())
        assert len(records) == 1
        assert records[0]["station_id"] == "7000"
        assert records[0]["station_name"] == "Fort York Blvd / Capreol Ct"

    def test_latitude_within_bounds(self) -> None:
        records = parse_stations(_make_gbfs())
        lat = float(records[0]["latitude"])
        assert _LAT_MIN <= lat <= _LAT_MAX

    def test_longitude_within_bounds(self) -> None:
        records = parse_stations(_make_gbfs())
        lon = float(records[0]["longitude"])
        assert _LON_MIN <= lon <= _LON_MAX

    def test_station_outside_lat_bbox_skipped(self) -> None:
        bad = {**_VALID_STATION, "station_id": "9999", "lat": 44.0}
        records = parse_stations(_make_gbfs([bad]))
        assert len(records) == 0

    def test_station_outside_lon_bbox_skipped(self) -> None:
        bad = {**_VALID_STATION, "station_id": "9999", "lon": -80.0}
        records = parse_stations(_make_gbfs([bad]))
        assert len(records) == 0

    def test_duplicate_station_id_skipped(self) -> None:
        dup = {**_VALID_STATION}
        records = parse_stations(_make_gbfs([_VALID_STATION, dup]))
        assert len(records) == 1

    def test_multiple_stations_sorted_by_id(self) -> None:
        records = parse_stations(
            _make_gbfs([_DIRECTIONAL_ONLY, _VALID_STATION, _CHARGING_STATION])
        )
        ids = [r["station_id"] for r in records]
        assert ids == ["7000", "7001", "7249"]

    def test_neighborhood_assigned(self) -> None:
        records = parse_stations(_make_gbfs())
        assert records[0]["neighborhood"] == "Fort York - Entertainment District"

    def test_coordinate_precision(self) -> None:
        records = parse_stations(_make_gbfs())
        assert records[0]["latitude"] == "43.639832"
        assert records[0]["longitude"] == "-79.395954"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    """Validate post-parse validation checks."""

    def test_empty_records_raises(self) -> None:
        with pytest.raises(ValueError, match="No stations parsed"):
            validate_records([])

    def test_duplicate_ids_raises(self) -> None:
        dup = [
            {
                "station_id": "1",
                "station_name": "A",
                "latitude": "43.65",
                "longitude": "-79.38",
                "neighborhood": "X",
            },
            {
                "station_id": "1",
                "station_name": "B",
                "latitude": "43.66",
                "longitude": "-79.39",
                "neighborhood": "Y",
            },
        ]
        with pytest.raises(ValueError, match="Duplicate station_id"):
            validate_records(dup)

    def test_empty_field_raises(self) -> None:
        bad = [
            {
                "station_id": "1",
                "station_name": "",
                "latitude": "43.65",
                "longitude": "-79.38",
                "neighborhood": "X",
            },
        ]
        with pytest.raises(ValueError, match="Empty value"):
            validate_records(bad)

    def test_valid_records_pass(self) -> None:
        records = parse_stations(_make_gbfs())
        validate_records(records)


# ---------------------------------------------------------------------------
# JSON caching
# ---------------------------------------------------------------------------


class TestJsonCache:
    """Validate GBFS JSON cache read/write."""

    def test_cache_roundtrip(self, tmp_path: Path) -> None:
        cache_path = tmp_path / "gbfs.json"
        original = _make_gbfs()
        cache_json(original, cache_path)
        loaded = load_cached_json(cache_path)
        assert loaded == original

    def test_load_missing_cache_exits(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit):
            load_cached_json(tmp_path / "nonexistent.json")


# ---------------------------------------------------------------------------
# CSV output
# ---------------------------------------------------------------------------


class TestCsvOutput:
    """Validate CSV file write correctness."""

    def test_write_creates_file(self, tmp_path: Path) -> None:
        records = parse_stations(_make_gbfs())
        output = tmp_path / "bike_station_ref.csv"
        write_csv(records, output)
        assert output.exists()

    def test_write_has_correct_header(self, tmp_path: Path) -> None:
        records = parse_stations(_make_gbfs())
        output = tmp_path / "bike_station_ref.csv"
        write_csv(records, output)
        with output.open(encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
        assert header == _COLUMNS

    def test_write_row_count(self, tmp_path: Path) -> None:
        records = parse_stations(
            _make_gbfs([_VALID_STATION, _CHARGING_STATION, _DIRECTIONAL_ONLY])
        )
        output = tmp_path / "bike_station_ref.csv"
        write_csv(records, output)
        with output.open(encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)
            count = sum(1 for _ in reader)
        assert count == 3

    def test_utf8_no_bom(self, tmp_path: Path) -> None:
        records = parse_stations(_make_gbfs())
        output = tmp_path / "bike_station_ref.csv"
        write_csv(records, output)
        raw = output.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf")

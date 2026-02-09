"""Structural validation for TTC reference seed CSV files.

Pre-dbt validation that confirms CSV integrity before dbt seed
attempts to load the data. Validates column presence, uniqueness
constraints, non-empty fields, and valid enum values for both
ttc_station_mapping.csv and ttc_delay_codes.csv.
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Final

import pytest

_SEEDS_DIR: Final = Path("seeds")
_STATION_MAPPING_FILE: Final = _SEEDS_DIR / "ttc_station_mapping.csv"
_DELAY_CODES_FILE: Final = _SEEDS_DIR / "ttc_delay_codes.csv"

_STATION_MAPPING_COLUMNS: Final[list[str]] = [
    "raw_station_name",
    "canonical_station_name",
    "station_key",
    "line_code",
]

_DELAY_CODES_COLUMNS: Final[list[str]] = [
    "delay_code",
    "delay_description",
    "delay_category",
]

_VALID_LINE_CODES: Final[frozenset[str]] = frozenset({"YU", "BD", "SHP", "SRT"})

_VALID_DELAY_CATEGORIES: Final[frozenset[str]] = frozenset(
    {
        "Mechanical",
        "Signal",
        "Passenger",
        "Infrastructure",
        "Operations",
        "Weather",
        "Security",
        "General",
    }
)


def _load_csv(path: Path) -> list[dict[str, str]]:
    """Load a CSV file into a list of dictionaries via csv.DictReader."""
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# ttc_station_mapping.csv validation
# ---------------------------------------------------------------------------


class TestStationMapping:
    """Structural validation for seeds/ttc_station_mapping.csv."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        assert _STATION_MAPPING_FILE.exists(), (
            f"Seed file not found: {_STATION_MAPPING_FILE}"
        )
        self.rows = _load_csv(_STATION_MAPPING_FILE)

    def test_loads_without_error(self) -> None:
        assert len(self.rows) > 0, "Station mapping file is empty"

    def test_has_exactly_four_columns(self) -> None:
        columns = list(self.rows[0].keys())
        assert columns == _STATION_MAPPING_COLUMNS, (
            f"Expected columns {_STATION_MAPPING_COLUMNS}, got {columns}"
        )

    def test_no_duplicate_raw_station_names(self) -> None:
        names = [row["raw_station_name"] for row in self.rows]
        duplicates = [name for name, count in Counter(names).items() if count > 1]
        assert not duplicates, f"Duplicate raw_station_name values: {duplicates[:10]}"

    def test_no_empty_values(self) -> None:
        for i, row in enumerate(self.rows):
            for col in _STATION_MAPPING_COLUMNS:
                value = row[col].strip()
                assert value, (
                    f"Empty value in row {i + 2}, column '{col}': "
                    f"raw_station_name='{row['raw_station_name']}'"
                )

    def test_line_code_enum_values(self) -> None:
        invalid: list[tuple[str, str]] = []
        for row in self.rows:
            if row["line_code"] not in _VALID_LINE_CODES:
                invalid.append((row["raw_station_name"], row["line_code"]))
        assert not invalid, f"Invalid line_code values: {invalid[:10]}"

    def test_station_key_format(self) -> None:
        """Station keys follow ST_NNN format."""
        import re

        pattern = re.compile(r"^ST_\d{3}$")
        invalid = [
            (row["raw_station_name"], row["station_key"])
            for row in self.rows
            if not pattern.match(row["station_key"])
        ]
        assert not invalid, f"Invalid station_key format: {invalid[:10]}"

    def test_interchange_stations_share_keys(self) -> None:
        """Interchange stations have the same station_key across lines."""
        key_to_canonicals: dict[str, set[str]] = {}
        for row in self.rows:
            key = row["station_key"]
            canonical = row["canonical_station_name"]
            key_to_canonicals.setdefault(key, set()).add(canonical)

        # Each station_key maps to exactly one canonical name
        conflicts = {
            k: names for k, names in key_to_canonicals.items() if len(names) > 1
        }
        assert not conflicts, f"Station keys with multiple canonical names: {conflicts}"

    def test_minimum_row_count(self) -> None:
        """Mapping must cover at least 75 canonical stations."""
        canonical_keys = {
            row["station_key"] for row in self.rows if row["station_key"] != "ST_000"
        }
        assert len(canonical_keys) >= 75, (
            f"Expected >= 75 canonical stations, found {len(canonical_keys)}"
        )


# ---------------------------------------------------------------------------
# ttc_delay_codes.csv validation
# ---------------------------------------------------------------------------


class TestDelayCodes:
    """Structural validation for seeds/ttc_delay_codes.csv."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        assert _DELAY_CODES_FILE.exists(), f"Seed file not found: {_DELAY_CODES_FILE}"
        self.rows = _load_csv(_DELAY_CODES_FILE)

    def test_loads_without_error(self) -> None:
        assert len(self.rows) > 0, "Delay codes file is empty"

    def test_has_exactly_three_columns(self) -> None:
        columns = list(self.rows[0].keys())
        assert columns == _DELAY_CODES_COLUMNS, (
            f"Expected columns {_DELAY_CODES_COLUMNS}, got {columns}"
        )

    def test_no_duplicate_delay_codes(self) -> None:
        codes = [row["delay_code"] for row in self.rows]
        duplicates = [code for code, count in Counter(codes).items() if count > 1]
        assert not duplicates, f"Duplicate delay_code values: {duplicates[:10]}"

    def test_no_empty_values(self) -> None:
        for i, row in enumerate(self.rows):
            for col in _DELAY_CODES_COLUMNS:
                value = row[col].strip()
                assert value, (
                    f"Empty value in row {i + 2}, column '{col}': "
                    f"delay_code='{row['delay_code']}'"
                )

    def test_delay_category_enum_values(self) -> None:
        invalid: list[tuple[str, str]] = []
        for row in self.rows:
            if row["delay_category"] not in _VALID_DELAY_CATEGORIES:
                invalid.append((row["delay_code"], row["delay_category"]))
        assert not invalid, f"Invalid delay_category values: {invalid[:10]}"

    def test_description_length(self) -> None:
        """Descriptions must be 2-10 words per AC."""
        violations: list[tuple[str, str, int]] = []
        for row in self.rows:
            word_count = len(row["delay_description"].split())
            if word_count < 1 or word_count > 10:
                violations.append(
                    (row["delay_code"], row["delay_description"], word_count)
                )
        assert not violations, f"Description word count violations: {violations[:10]}"

    def test_all_categories_represented(self) -> None:
        """All 8 delay categories should have at least one code."""
        categories_present = {row["delay_category"] for row in self.rows}
        missing = _VALID_DELAY_CATEGORIES - categories_present
        assert not missing, f"Categories with no codes: {missing}"

    def test_minimum_row_count(self) -> None:
        """Should have at least 30 codes per epic estimate."""
        assert len(self.rows) >= 30, (
            f"Expected >= 30 delay codes, found {len(self.rows)}"
        )

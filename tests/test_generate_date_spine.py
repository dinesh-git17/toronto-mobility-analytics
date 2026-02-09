"""Tests for date spine generation script.

Validates row count, date_key uniqueness, continuity, weekend flags,
and Ontario statutory holiday computation for 2019-2026.
"""

from __future__ import annotations

import csv
import datetime
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from scripts.generate_date_spine import (
    _COLUMNS,
    _END_DATE,
    _EXPECTED_ROWS,
    _START_DATE,
    _good_friday,
    _ontario_holidays,
    _victoria_day,
    generate_date_spine,
    write_csv,
)

_ROWS: Final = generate_date_spine()


def _find_row(full_date: str) -> list[str]:
    """Locate a single row by full_date value."""
    return next(r for r in _ROWS if r[1] == full_date)


# ---------------------------------------------------------------------------
# Row count
# ---------------------------------------------------------------------------


class TestRowCount:
    """Validate total row count equals 2,922."""

    def test_exact_row_count(self) -> None:
        assert len(_ROWS) == _EXPECTED_ROWS


# ---------------------------------------------------------------------------
# Date key
# ---------------------------------------------------------------------------


class TestDateKey:
    """Validate date_key uniqueness and format."""

    def test_all_date_keys_unique(self) -> None:
        keys = [row[0] for row in _ROWS]
        assert len(keys) == len(set(keys))

    def test_date_key_yyyymmdd_format(self) -> None:
        for row in _ROWS:
            key = row[0]
            assert key.isdigit(), f"Non-numeric date_key: {key}"
            assert len(key) == 8, f"Invalid date_key length: {key}"

    def test_first_date_key(self) -> None:
        assert _ROWS[0][0] == "20190101"

    def test_last_date_key(self) -> None:
        assert _ROWS[-1][0] == "20261231"


# ---------------------------------------------------------------------------
# Date continuity
# ---------------------------------------------------------------------------


class TestDateContinuity:
    """Validate no date gaps exist in the spine."""

    def test_no_gaps(self) -> None:
        dates = [datetime.date.fromisoformat(row[1]) for row in _ROWS]
        for i in range(1, len(dates)):
            expected = dates[i - 1] + datetime.timedelta(days=1)
            assert dates[i] == expected, f"Gap between {dates[i - 1]} and {dates[i]}"

    def test_starts_at_start_date(self) -> None:
        first_date = datetime.date.fromisoformat(_ROWS[0][1])
        assert first_date == _START_DATE

    def test_ends_at_end_date(self) -> None:
        last_date = datetime.date.fromisoformat(_ROWS[-1][1])
        assert last_date == _END_DATE


# ---------------------------------------------------------------------------
# Weekend flag
# ---------------------------------------------------------------------------


class TestWeekendFlag:
    """Validate is_weekend correctness for known dates."""

    @pytest.mark.parametrize(
        ("full_date", "expected"),
        [
            ("2024-01-01", "false"),
            ("2024-01-06", "true"),
            ("2024-01-07", "true"),
            ("2024-07-01", "false"),
            ("2023-12-25", "false"),
            ("2019-01-05", "true"),
            ("2019-01-06", "true"),
            ("2019-01-07", "false"),
        ],
        ids=[
            "Monday-false",
            "Saturday-true",
            "Sunday-true",
            "Monday-Jul1",
            "Monday-Dec25",
            "Saturday-2019",
            "Sunday-2019",
            "Monday-2019",
        ],
    )
    def test_weekend_flag(self, full_date: str, expected: str) -> None:
        row = _find_row(full_date)
        assert row[8] == expected


# ---------------------------------------------------------------------------
# Holiday flag
# ---------------------------------------------------------------------------


class TestHolidayFlag:
    """Validate is_holiday correctness for Ontario statutory holidays."""

    @pytest.mark.parametrize(
        ("full_date", "description"),
        [
            ("2024-01-01", "New Year's Day 2024"),
            ("2024-02-19", "Family Day 2024"),
            ("2024-03-29", "Good Friday 2024"),
            ("2024-05-20", "Victoria Day 2024"),
            ("2024-07-01", "Canada Day 2024"),
            ("2024-08-05", "Civic Holiday 2024"),
            ("2024-09-02", "Labour Day 2024"),
            ("2024-10-14", "Thanksgiving 2024"),
            ("2024-12-25", "Christmas Day 2024"),
            ("2019-01-01", "New Year's Day 2019"),
            ("2019-04-19", "Good Friday 2019"),
            ("2023-04-07", "Good Friday 2023"),
            ("2025-04-18", "Good Friday 2025"),
            ("2026-04-03", "Good Friday 2026"),
        ],
    )
    def test_known_holidays(self, full_date: str, description: str) -> None:
        row = _find_row(full_date)
        assert row[9] == "true", f"{description} ({full_date}) should be holiday"

    @pytest.mark.parametrize(
        ("full_date", "description"),
        [
            ("2024-01-02", "Non-holiday January day"),
            ("2024-06-15", "Random summer day"),
            ("2024-11-11", "Remembrance Day (not Ontario statutory)"),
            ("2024-12-26", "Boxing Day (not Ontario statutory)"),
        ],
    )
    def test_non_holidays(self, full_date: str, description: str) -> None:
        row = _find_row(full_date)
        assert row[9] == "false", f"{description} ({full_date}) not a holiday"

    def test_nine_holidays_per_year(self) -> None:
        """Each year must have exactly 9 statutory holidays."""
        for year in range(2019, 2027):
            holidays = _ontario_holidays(year)
            assert len(holidays) == 9, f"Year {year}: {len(holidays)} holidays"


# ---------------------------------------------------------------------------
# Good Friday computation
# ---------------------------------------------------------------------------


class TestGoodFriday:
    """Validate Good Friday dates for the full range 2019-2026."""

    @pytest.mark.parametrize(
        ("year", "expected_date"),
        [
            (2019, "2019-04-19"),
            (2020, "2020-04-10"),
            (2021, "2021-04-02"),
            (2022, "2022-04-15"),
            (2023, "2023-04-07"),
            (2024, "2024-03-29"),
            (2025, "2025-04-18"),
            (2026, "2026-04-03"),
        ],
    )
    def test_good_friday(self, year: int, expected_date: str) -> None:
        result = _good_friday(year)
        assert result == datetime.date.fromisoformat(expected_date)


# ---------------------------------------------------------------------------
# Victoria Day computation
# ---------------------------------------------------------------------------


class TestVictoriaDay:
    """Validate Victoria Day computation for 2019-2026."""

    @pytest.mark.parametrize(
        ("year", "expected_date"),
        [
            (2019, "2019-05-20"),
            (2020, "2020-05-18"),
            (2021, "2021-05-24"),
            (2022, "2022-05-23"),
            (2023, "2023-05-22"),
            (2024, "2024-05-20"),
            (2025, "2025-05-19"),
            (2026, "2026-05-18"),
        ],
    )
    def test_victoria_day(self, year: int, expected_date: str) -> None:
        result = _victoria_day(year)
        assert result == datetime.date.fromisoformat(expected_date)


# ---------------------------------------------------------------------------
# Day of week / quarter
# ---------------------------------------------------------------------------


class TestDayOfWeek:
    """Validate day_of_week and day_of_week_num fields."""

    def test_monday_is_1(self) -> None:
        row = _find_row("2024-01-01")
        assert row[2] == "Monday"
        assert row[3] == "1"

    def test_sunday_is_7(self) -> None:
        row = _find_row("2024-01-07")
        assert row[2] == "Sunday"
        assert row[3] == "7"

    def test_all_days_covered_in_first_week(self) -> None:
        """The first 7 days of 2024 span Tue-Mon (1/1=Mon, 1/7=Sun)."""
        days = [_find_row(f"2024-01-0{d}")[2] for d in range(1, 8)]
        assert days == [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]


class TestQuarter:
    """Validate quarter assignment."""

    @pytest.mark.parametrize(
        ("full_date", "expected_quarter"),
        [
            ("2024-01-01", "1"),
            ("2024-03-31", "1"),
            ("2024-04-01", "2"),
            ("2024-06-30", "2"),
            ("2024-07-01", "3"),
            ("2024-09-30", "3"),
            ("2024-10-01", "4"),
            ("2024-12-31", "4"),
        ],
    )
    def test_quarter_assignment(self, full_date: str, expected_quarter: str) -> None:
        row = _find_row(full_date)
        assert row[6] == expected_quarter


# ---------------------------------------------------------------------------
# CSV output
# ---------------------------------------------------------------------------


class TestCsvOutput:
    """Validate CSV file write correctness."""

    def test_write_creates_file(self, tmp_path: Path) -> None:
        output = tmp_path / "date_spine.csv"
        write_csv(_ROWS, output)
        assert output.exists()

    def test_write_has_correct_header(self, tmp_path: Path) -> None:
        output = tmp_path / "date_spine.csv"
        write_csv(_ROWS, output)
        with output.open(encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
        assert header == _COLUMNS

    def test_write_has_correct_row_count(self, tmp_path: Path) -> None:
        output = tmp_path / "date_spine.csv"
        write_csv(_ROWS, output)
        with output.open(encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)
            count = sum(1 for _ in reader)
        assert count == _EXPECTED_ROWS

    def test_idempotent_output(self, tmp_path: Path) -> None:
        """Running generation twice produces identical CSV output."""
        path1 = tmp_path / "run1.csv"
        path2 = tmp_path / "run2.csv"
        rows1 = generate_date_spine()
        rows2 = generate_date_spine()
        write_csv(rows1, path1)
        write_csv(rows2, path2)
        assert path1.read_text() == path2.read_text()

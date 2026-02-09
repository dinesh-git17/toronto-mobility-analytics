"""Generate date_spine.csv for the Toronto Mobility Analytics seed layer.

Produces a deterministic CSV with one row per calendar day from 2019-01-01
through 2026-12-31 (2,922 rows), including Ontario statutory holiday flags.

Holiday computation uses the Anonymous Gregorian algorithm for Easter-dependent
dates and nth-Monday rules for moving holidays. No external holiday libraries
are used.

Usage:
    python scripts/generate_date_spine.py
"""

from __future__ import annotations

import csv
import datetime
from pathlib import Path
from typing import Final

_START_DATE: Final = datetime.date(2019, 1, 1)
_END_DATE: Final = datetime.date(2026, 12, 31)
_OUTPUT_PATH: Final = Path("seeds/date_spine.csv")
_EXPECTED_ROWS: Final = 2922

_COLUMNS: Final[list[str]] = [
    "date_key",
    "full_date",
    "day_of_week",
    "day_of_week_num",
    "month_num",
    "month_name",
    "quarter",
    "year",
    "is_weekend",
    "is_holiday",
]

_DAY_NAMES: Final[list[str]] = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

_MONTH_NAMES: Final[list[str]] = [
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


def _easter_sunday(year: int) -> datetime.date:
    """Compute Easter Sunday via the Anonymous Gregorian algorithm.

    Reference: Meeus/Jones/Butcher algorithm as described in
    'Astronomical Algorithms' by Jean Meeus (1991).
    """
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    el = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * el) // 451
    month, day = divmod(h + el - 7 * m + 114, 31)
    return datetime.date(year, month, day + 1)


def _good_friday(year: int) -> datetime.date:
    """Return the date of Good Friday for the given year."""
    return _easter_sunday(year) - datetime.timedelta(days=2)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> datetime.date:
    """Return the nth occurrence of a weekday in a given month.

    Args:
        year: Calendar year.
        month: Month number (1-12).
        weekday: ISO weekday (0=Monday, 6=Sunday).
        n: Occurrence number (1=first, 2=second, etc.).
    """
    first_day = datetime.date(year, month, 1)
    days_ahead = weekday - first_day.weekday()
    if days_ahead < 0:
        days_ahead += 7
    first_occurrence = first_day + datetime.timedelta(days=days_ahead)
    return first_occurrence + datetime.timedelta(weeks=n - 1)


def _victoria_day(year: int) -> datetime.date:
    """Return Victoria Day: the Monday on or before May 24."""
    may_24 = datetime.date(year, 5, 24)
    days_since_monday = may_24.weekday()
    if days_since_monday == 0:
        return may_24
    return may_24 - datetime.timedelta(days=days_since_monday)


def _ontario_holidays(year: int) -> set[datetime.date]:
    """Return the set of Ontario statutory holiday dates for a given year.

    Nine holidays computed per Ontario Employment Standards Act:
      - New Year's Day (Jan 1)
      - Family Day (3rd Monday of February)
      - Good Friday (Easter-dependent)
      - Victoria Day (Monday on or before May 24)
      - Canada Day (July 1)
      - Civic Holiday (1st Monday of August, Toronto-specific municipal)
      - Labour Day (1st Monday of September)
      - Thanksgiving (2nd Monday of October)
      - Christmas Day (December 25)
    """
    return {
        datetime.date(year, 1, 1),
        _nth_weekday(year, 2, 0, 3),
        _good_friday(year),
        _victoria_day(year),
        datetime.date(year, 7, 1),
        _nth_weekday(year, 8, 0, 1),
        _nth_weekday(year, 9, 0, 1),
        _nth_weekday(year, 10, 0, 2),
        datetime.date(year, 12, 25),
    }


def generate_date_spine() -> list[list[str]]:
    """Generate date spine rows from _START_DATE to _END_DATE inclusive.

    Returns:
        List of string lists, one per day, with columns matching
        _COLUMNS order. Boolean values use lowercase 'true'/'false'
        strings for dbt seed compatibility.
    """
    holidays: set[datetime.date] = set()
    for year in range(_START_DATE.year, _END_DATE.year + 1):
        holidays |= _ontario_holidays(year)

    rows: list[list[str]] = []
    current = _START_DATE
    one_day = datetime.timedelta(days=1)

    while current <= _END_DATE:
        iso_weekday = current.isoweekday()
        is_weekend = iso_weekday >= 6
        is_holiday = current in holidays
        quarter = (current.month - 1) // 3 + 1

        row = [
            str(current.year * 10000 + current.month * 100 + current.day),
            current.isoformat(),
            _DAY_NAMES[iso_weekday - 1],
            str(iso_weekday),
            str(current.month),
            _MONTH_NAMES[current.month],
            str(quarter),
            str(current.year),
            str(is_weekend).lower(),
            str(is_holiday).lower(),
        ]
        rows.append(row)
        current += one_day

    return rows


def write_csv(rows: list[list[str]], path: Path | None = None) -> Path:
    """Write date spine rows to CSV at the specified path.

    Args:
        rows: Data rows (without header).
        path: Output file path. Defaults to _OUTPUT_PATH.

    Returns:
        The path of the written file.
    """
    output = path or _OUTPUT_PATH
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(_COLUMNS)
        writer.writerows(rows)

    return output


def main() -> None:
    """Entry point: generate and write the date spine CSV."""
    rows = generate_date_spine()
    if len(rows) != _EXPECTED_ROWS:
        msg = f"Expected {_EXPECTED_ROWS} rows, generated {len(rows)}"
        raise ValueError(msg)

    output = write_csv(rows)
    print(f"Wrote {len(rows)} rows to {output}")


if __name__ == "__main__":
    main()

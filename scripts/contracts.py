"""Schema contract definitions for Toronto Urban Mobility source datasets.

Defines typed, frozen schema contracts for all five source datasets:
TTC subway delays, TTC bus delays, TTC streetcar delays, Bike Share
ridership, and Environment Canada daily weather. Each contract specifies
required columns, expected data types, and nullability constraints per
DESIGN-DOC.md Section 4.3.

Contracts target the 2020-present column naming convention. The 2019
TTC Bus and Streetcar files use incompatible column names (Report Date,
Delay, Gap) and are excluded from the validation scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class ColumnContract:
    """Schema expectation for a single column in a source dataset.

    Attributes:
        name: Exact column header as it appears in the source CSV.
        expected_dtype: Logical data type for validation. One of:
            DATE, TIME, STRING, INTEGER, DECIMAL, TIMESTAMP.
        nullable: Whether the column permits empty/null values.
    """

    name: str
    expected_dtype: str
    nullable: bool


@dataclass(frozen=True, slots=True)
class SchemaContract:
    """Full schema contract for a source dataset.

    Attributes:
        dataset_name: Machine-readable identifier matching config.py names.
        columns: Ordered tuple of expected column definitions.
        min_row_count: Lower-bound sanity check on file row count.
            Files with fewer rows trigger a validation warning.
    """

    dataset_name: str
    columns: tuple[ColumnContract, ...]
    min_row_count: int

    @property
    def column_names(self) -> tuple[str, ...]:
        """Return ordered tuple of expected column names."""
        return tuple(c.name for c in self.columns)

    @property
    def required_columns(self) -> frozenset[str]:
        """Return set of column names that must be present."""
        return frozenset(c.name for c in self.columns)

    @property
    def nullable_columns(self) -> frozenset[str]:
        """Return set of column names that permit null values."""
        return frozenset(c.name for c in self.columns if c.nullable)


# ---------------------------------------------------------------------------
# TTC Subway Delays — DESIGN-DOC.md Section 4.3.1
# 9 required columns. Vehicle column present in source files is treated
# as a non-blocking extra column by the validation engine.
# Station and Line are nullable in practice despite DESIGN-DOC ideals;
# the staging layer (PH-05) enforces stricter quality constraints.
# ---------------------------------------------------------------------------
TTC_SUBWAY_CONTRACT: Final[SchemaContract] = SchemaContract(
    dataset_name="ttc_subway_delays",
    columns=(
        ColumnContract(name="Date", expected_dtype="DATE", nullable=False),
        ColumnContract(name="Time", expected_dtype="TIME", nullable=False),
        ColumnContract(name="Day", expected_dtype="STRING", nullable=False),
        ColumnContract(name="Station", expected_dtype="STRING", nullable=True),
        ColumnContract(name="Code", expected_dtype="STRING", nullable=True),
        ColumnContract(name="Min Delay", expected_dtype="INTEGER", nullable=True),
        ColumnContract(name="Min Gap", expected_dtype="INTEGER", nullable=True),
        ColumnContract(name="Bound", expected_dtype="STRING", nullable=True),
        ColumnContract(name="Line", expected_dtype="STRING", nullable=True),
    ),
    min_row_count=100,
)

# ---------------------------------------------------------------------------
# TTC Bus Delays — 2020+ schema
# Differs from subway: Route (not Line), Location (not Station),
# Incident (not Code), Direction (not Bound).
# ---------------------------------------------------------------------------
TTC_BUS_CONTRACT: Final[SchemaContract] = SchemaContract(
    dataset_name="ttc_bus_delays",
    columns=(
        ColumnContract(name="Date", expected_dtype="DATE", nullable=False),
        ColumnContract(name="Route", expected_dtype="STRING", nullable=True),
        ColumnContract(name="Time", expected_dtype="TIME", nullable=False),
        ColumnContract(name="Day", expected_dtype="STRING", nullable=False),
        ColumnContract(name="Location", expected_dtype="STRING", nullable=True),
        ColumnContract(name="Incident", expected_dtype="STRING", nullable=True),
        ColumnContract(name="Min Delay", expected_dtype="INTEGER", nullable=True),
        ColumnContract(name="Min Gap", expected_dtype="INTEGER", nullable=True),
        ColumnContract(name="Direction", expected_dtype="STRING", nullable=True),
    ),
    min_row_count=100,
)

# ---------------------------------------------------------------------------
# TTC Streetcar Delays — 2020+ schema
# Uses Line and Bound (like subway), but Location and Incident (like bus).
# ---------------------------------------------------------------------------
TTC_STREETCAR_CONTRACT: Final[SchemaContract] = SchemaContract(
    dataset_name="ttc_streetcar_delays",
    columns=(
        ColumnContract(name="Date", expected_dtype="DATE", nullable=False),
        ColumnContract(name="Line", expected_dtype="STRING", nullable=True),
        ColumnContract(name="Time", expected_dtype="TIME", nullable=False),
        ColumnContract(name="Day", expected_dtype="STRING", nullable=False),
        ColumnContract(name="Location", expected_dtype="STRING", nullable=True),
        ColumnContract(name="Incident", expected_dtype="STRING", nullable=True),
        ColumnContract(name="Min Delay", expected_dtype="INTEGER", nullable=True),
        ColumnContract(name="Min Gap", expected_dtype="INTEGER", nullable=True),
        ColumnContract(name="Bound", expected_dtype="STRING", nullable=True),
    ),
    min_row_count=100,
)

# ---------------------------------------------------------------------------
# Bike Share Ridership — DESIGN-DOC.md Section 4.3.2
# Column "Trip  Duration" contains a double space in all source CSVs.
# ---------------------------------------------------------------------------
BIKE_SHARE_CONTRACT: Final[SchemaContract] = SchemaContract(
    dataset_name="bike_share_ridership",
    columns=(
        ColumnContract(name="Trip Id", expected_dtype="STRING", nullable=False),
        ColumnContract(name="Trip  Duration", expected_dtype="INTEGER", nullable=True),
        ColumnContract(
            name="Start Station Id",
            expected_dtype="INTEGER",
            nullable=True,
        ),
        ColumnContract(name="Start Time", expected_dtype="TIMESTAMP", nullable=True),
        ColumnContract(
            name="Start Station Name",
            expected_dtype="STRING",
            nullable=True,
        ),
        ColumnContract(
            name="End Station Id",
            expected_dtype="INTEGER",
            nullable=True,
        ),
        ColumnContract(name="End Time", expected_dtype="TIMESTAMP", nullable=True),
        ColumnContract(
            name="End Station Name",
            expected_dtype="STRING",
            nullable=True,
        ),
        ColumnContract(name="Bike Id", expected_dtype="INTEGER", nullable=True),
        ColumnContract(name="User Type", expected_dtype="STRING", nullable=True),
    ),
    min_row_count=100,
)

# ---------------------------------------------------------------------------
# Weather Daily — DESIGN-DOC.md Section 4.3.3
# Only the 5 key columns are contracted. Environment Canada CSVs contain
# 30+ columns; extras pass through as non-blocking warnings.
# ---------------------------------------------------------------------------
WEATHER_DAILY_CONTRACT: Final[SchemaContract] = SchemaContract(
    dataset_name="weather_daily",
    columns=(
        ColumnContract(name="Date/Time", expected_dtype="DATE", nullable=False),
        ColumnContract(
            name="Mean Temp (°C)",
            expected_dtype="DECIMAL",
            nullable=True,
        ),
        ColumnContract(
            name="Total Precip (mm)",
            expected_dtype="DECIMAL",
            nullable=True,
        ),
        ColumnContract(
            name="Snow on Grnd (cm)",
            expected_dtype="DECIMAL",
            nullable=True,
        ),
        ColumnContract(
            name="Spd of Max Gust (km/h)",
            expected_dtype="DECIMAL",
            nullable=True,
        ),
    ),
    min_row_count=100,
)

# ---------------------------------------------------------------------------
# Contract registry keyed by dataset name for programmatic lookup.
# Keys match DatasetConfig.name values in config.py.
# ---------------------------------------------------------------------------
CONTRACTS: Final[dict[str, SchemaContract]] = {
    TTC_SUBWAY_CONTRACT.dataset_name: TTC_SUBWAY_CONTRACT,
    TTC_BUS_CONTRACT.dataset_name: TTC_BUS_CONTRACT,
    TTC_STREETCAR_CONTRACT.dataset_name: TTC_STREETCAR_CONTRACT,
    BIKE_SHARE_CONTRACT.dataset_name: BIKE_SHARE_CONTRACT,
    WEATHER_DAILY_CONTRACT.dataset_name: WEATHER_DAILY_CONTRACT,
}

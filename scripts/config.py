"""Dataset configuration registry for Toronto Urban Mobility Analytics.

Defines typed configuration for all five source datasets: TTC subway delays,
TTC bus delays, TTC streetcar delays, Bike Share ridership, and Environment
Canada daily weather observations. Configuration drives the download module
with deterministic directory layout under data/raw/.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import Enum
from typing import Final


class SourceType(Enum):
    """Origin system for a dataset."""

    CKAN = "ckan"
    ENVIRONMENT_CANADA = "environment_canada"


class FileFormat(Enum):
    """Expected file format for downloaded resources."""

    XLSX = "xlsx"
    CSV = "csv"
    ZIP = "zip"


@dataclass(frozen=True, slots=True)
class DatasetConfig:
    """Immutable configuration for a single source dataset.

    Attributes:
        name: Machine-readable dataset identifier (snake_case).
        source_type: Origin system enum (CKAN or ENVIRONMENT_CANADA).
        api_base_url: Base URL for the source API or download endpoint.
        dataset_id: CKAN package identifier (None for non-CKAN sources).
        station_id: Environment Canada station ID (None for non-weather sources).
        climate_id: Environment Canada climate ID (None for non-weather sources).
        year_range: Inclusive (start_year, end_year) tuple for download scope.
        file_format: Expected format of downloaded files.
        output_dir: Relative path under data/raw/ for file storage.
    """

    name: str
    source_type: SourceType
    api_base_url: str
    dataset_id: str | None
    station_id: int | None
    climate_id: str | None
    year_range: tuple[int, int]
    file_format: FileFormat
    output_dir: str


# Year range covers 2019 through current year per DESIGN-DOC.md Section 4.1
_CURRENT_YEAR: Final[int] = datetime.datetime.now(tz=datetime.UTC).year
_START_YEAR: Final[int] = 2019

# CKAN API base for Toronto Open Data Portal
_CKAN_BASE: Final[str] = "https://ckan0.cf.opendata.inter.prod-toronto.ca"

# Environment Canada Historical Climate Data endpoint
_EC_BASE: Final[str] = "https://climate.weather.gc.ca"

# Dataset IDs sourced from Toronto Open Data Portal package URLs
_SUBWAY_DATASET_ID: Final[str] = "996cfe8d-fb35-40ce-b569-698d51fc683b"
_BUS_DATASET_ID: Final[str] = "e271cdae-8788-4980-96ce-6a5c95bc6618"
_STREETCAR_DATASET_ID: Final[str] = "b68cb71b-44a7-4394-97e2-5d2f41462a5d"
_BIKE_SHARE_DATASET_ID: Final[str] = "7e876c24-177c-4605-9cef-e50dd74c617f"

# Environment Canada identifiers for Toronto Pearson International
_EC_STATION_ID: Final[int] = 51459
_EC_CLIMATE_ID: Final[str] = "6158733"


DATASETS: Final[tuple[DatasetConfig, ...]] = (
    DatasetConfig(
        name="ttc_subway_delays",
        source_type=SourceType.CKAN,
        api_base_url=_CKAN_BASE,
        dataset_id=_SUBWAY_DATASET_ID,
        station_id=None,
        climate_id=None,
        year_range=(_START_YEAR, _CURRENT_YEAR),
        file_format=FileFormat.XLSX,
        output_dir="ttc_subway",
    ),
    DatasetConfig(
        name="ttc_bus_delays",
        source_type=SourceType.CKAN,
        api_base_url=_CKAN_BASE,
        dataset_id=_BUS_DATASET_ID,
        station_id=None,
        climate_id=None,
        year_range=(_START_YEAR, _CURRENT_YEAR),
        file_format=FileFormat.XLSX,
        output_dir="ttc_bus",
    ),
    DatasetConfig(
        name="ttc_streetcar_delays",
        source_type=SourceType.CKAN,
        api_base_url=_CKAN_BASE,
        dataset_id=_STREETCAR_DATASET_ID,
        station_id=None,
        climate_id=None,
        year_range=(_START_YEAR, _CURRENT_YEAR),
        file_format=FileFormat.XLSX,
        output_dir="ttc_streetcar",
    ),
    DatasetConfig(
        name="bike_share_ridership",
        source_type=SourceType.CKAN,
        api_base_url=_CKAN_BASE,
        dataset_id=_BIKE_SHARE_DATASET_ID,
        station_id=None,
        climate_id=None,
        year_range=(_START_YEAR, _CURRENT_YEAR),
        file_format=FileFormat.ZIP,
        output_dir="bike_share",
    ),
    DatasetConfig(
        name="weather_daily",
        source_type=SourceType.ENVIRONMENT_CANADA,
        api_base_url=_EC_BASE,
        dataset_id=None,
        station_id=_EC_STATION_ID,
        climate_id=_EC_CLIMATE_ID,
        year_range=(_START_YEAR, _CURRENT_YEAR),
        file_format=FileFormat.CSV,
        output_dir="weather",
    ),
)


def get_dataset_by_name(name: str) -> DatasetConfig:
    """Look up a dataset configuration by its machine-readable name.

    Args:
        name: Dataset name matching DatasetConfig.name field.

    Returns:
        Matching DatasetConfig instance.

    Raises:
        KeyError: If no dataset matches the given name.
    """
    for dataset in DATASETS:
        if dataset.name == name:
            return dataset
    valid_names = ", ".join(d.name for d in DATASETS)
    raise KeyError(f"Unknown dataset '{name}'. Valid names: {valid_names}")


def get_ckan_datasets() -> tuple[DatasetConfig, ...]:
    """Return all datasets sourced from the Toronto Open Data CKAN portal."""
    return tuple(d for d in DATASETS if d.source_type == SourceType.CKAN)


def get_weather_dataset() -> DatasetConfig:
    """Return the Environment Canada weather dataset configuration."""
    return get_dataset_by_name("weather_daily")

"""Comprehensive test suite for the download module.

Covers CKAN URL resolution, CKAN file download, weather URL construction,
weather file download, manifest read/write/idempotency, error handling,
and SHA-256 integrity verification. All HTTP calls are mocked via respx.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

import httpx
import pytest
import respx

from scripts.config import DatasetConfig, FileFormat, SourceType
from scripts.download import (
    DownloadError,
    DownloadManifest,
    DownloadResult,
    ManifestEntry,
    _build_weather_url,
    _extract_year_from_resource,
    _filter_resources_by_year,
    _resource_filename,
    compute_sha256,
    download_ckan_dataset,
    download_weather_data,
)

_FIXTURES_DIR: Final[Path] = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def ckan_response_json() -> dict[str, object]:
    """Load the CKAN package_show fixture."""
    raw: str = (_FIXTURES_DIR / "ckan_package_show_response.json").read_text(
        encoding="utf-8"
    )
    return json.loads(raw)  # type: ignore[no-any-return]


@pytest.fixture()
def subway_config() -> DatasetConfig:
    """Minimal CKAN dataset config for testing."""
    return DatasetConfig(
        name="ttc_subway_delays",
        source_type=SourceType.CKAN,
        api_base_url="https://ckan0.cf.opendata.inter.prod-toronto.ca",
        dataset_id="996cfe8d-fb35-40ce-b569-698d51fc683b",
        station_id=None,
        climate_id=None,
        year_range=(2022, 2023),
        file_format=FileFormat.XLSX,
        output_dir="ttc_subway",
    )


@pytest.fixture()
def weather_config() -> DatasetConfig:
    """Minimal Environment Canada dataset config for testing."""
    return DatasetConfig(
        name="weather_daily",
        source_type=SourceType.ENVIRONMENT_CANADA,
        api_base_url="https://climate.weather.gc.ca",
        dataset_id=None,
        station_id=51459,
        climate_id="6158733",
        year_range=(2023, 2023),
        file_format=FileFormat.CSV,
        output_dir="weather",
    )


# ---------------------------------------------------------------------------
# Config / helper unit tests
# ---------------------------------------------------------------------------


class TestExtractYearFromResource:
    """Tests for year extraction from CKAN resource metadata."""

    def test_year_in_name(self) -> None:
        resource: dict[str, object] = {"name": "ttc-subway-delay-data-2023"}
        assert _extract_year_from_resource(resource) == 2023

    def test_year_with_month_prefix(self) -> None:
        resource: dict[str, object] = {"name": "Jan 2022 Bus Delays"}
        assert _extract_year_from_resource(resource) == 2022

    def test_no_year_returns_none(self) -> None:
        resource: dict[str, object] = {"name": "ttc-subway-delay-codes"}
        assert _extract_year_from_resource(resource) is None

    def test_empty_name(self) -> None:
        resource: dict[str, object] = {"name": ""}
        assert _extract_year_from_resource(resource) is None


class TestFilterResourcesByYear:
    """Tests for year-range filtering of CKAN resources."""

    def test_filters_within_range(self) -> None:
        resources: list[dict[str, object]] = [
            {"name": "data-2019"},
            {"name": "data-2022"},
            {"name": "data-2023"},
        ]
        result = _filter_resources_by_year(resources, (2022, 2023))
        assert len(result) == 2

    def test_excludes_no_year(self) -> None:
        resources: list[dict[str, object]] = [{"name": "codes-reference"}]
        result = _filter_resources_by_year(resources, (2019, 2025))
        assert len(result) == 0


class TestResourceFilename:
    """Tests for filename derivation from CKAN resource entries."""

    def test_name_based(self) -> None:
        resource: dict[str, object] = {
            "name": "TTC Subway 2023",
            "format": "xlsx",
            "url": "https://example.com/file.xlsx",
        }
        result = _resource_filename(resource)
        assert result == "TTC_Subway_2023.xlsx"

    def test_fallback_to_url(self) -> None:
        resource: dict[str, object] = {
            "name": "",
            "url": "https://example.com/download/file.csv",
        }
        assert _resource_filename(resource) == "file.csv"


class TestBuildWeatherUrl:
    """Tests for Environment Canada URL construction."""

    def test_url_format(self) -> None:
        url: str = _build_weather_url(51459, 2023, 1)
        assert "stationID=51459" in url
        assert "Year=2023" in url
        assert "Month=1" in url
        assert "timeframe=2" in url
        assert url.startswith("https://climate.weather.gc.ca/")


# ---------------------------------------------------------------------------
# SHA-256 hashing
# ---------------------------------------------------------------------------


class TestComputeSha256:
    """Tests for file hash computation."""

    def test_known_content(self, tmp_path: Path) -> None:
        test_file: Path = tmp_path / "test.txt"
        content: bytes = b"hello world\n"
        test_file.write_bytes(content)

        result: str = compute_sha256(test_file)

        # Pre-computed: echo -n 'hello world\n' | sha256sum
        import hashlib

        expected: str = hashlib.sha256(content).hexdigest()
        assert result == expected

    def test_empty_file(self, tmp_path: Path) -> None:
        test_file: Path = tmp_path / "empty.txt"
        test_file.write_bytes(b"")

        result: str = compute_sha256(test_file)

        import hashlib

        assert result == hashlib.sha256(b"").hexdigest()


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


class TestDownloadManifest:
    """Tests for manifest persistence and idempotency logic."""

    def test_load_nonexistent_returns_empty(self, tmp_path: Path) -> None:
        manifest: DownloadManifest = DownloadManifest.load(tmp_path / ".manifest.json")
        assert len(manifest.entries) == 0

    def test_save_and_reload(self, tmp_path: Path) -> None:
        manifest_path: Path = tmp_path / ".manifest.json"
        manifest: DownloadManifest = DownloadManifest(
            path=manifest_path,
            entries=[
                ManifestEntry(
                    url="https://example.com/file.csv",
                    file_path=str(tmp_path / "file.csv"),
                    byte_size=1024,
                    sha256_hash="abc123",
                    download_timestamp="2024-01-01T00:00:00+00:00",
                    http_status=200,
                ),
            ],
        )
        manifest.save()

        reloaded: DownloadManifest = DownloadManifest.load(manifest_path)
        assert len(reloaded.entries) == 1
        assert reloaded.entries[0].url == "https://example.com/file.csv"
        assert reloaded.entries[0].byte_size == 1024

    def test_should_skip_with_matching_file(self, tmp_path: Path) -> None:
        test_file: Path = tmp_path / "file.csv"
        test_file.write_bytes(b"x" * 512)

        manifest: DownloadManifest = DownloadManifest(
            path=tmp_path / ".manifest.json",
            entries=[
                ManifestEntry(
                    url="https://example.com/file.csv",
                    file_path=str(test_file),
                    byte_size=512,
                    sha256_hash="abc",
                    download_timestamp="2024-01-01T00:00:00+00:00",
                    http_status=200,
                ),
            ],
        )
        assert manifest.should_skip("https://example.com/file.csv") is True

    def test_should_not_skip_missing_file(self, tmp_path: Path) -> None:
        manifest: DownloadManifest = DownloadManifest(
            path=tmp_path / ".manifest.json",
            entries=[
                ManifestEntry(
                    url="https://example.com/file.csv",
                    file_path=str(tmp_path / "missing.csv"),
                    byte_size=512,
                    sha256_hash="abc",
                    download_timestamp="2024-01-01T00:00:00+00:00",
                    http_status=200,
                ),
            ],
        )
        assert manifest.should_skip("https://example.com/file.csv") is False

    def test_should_not_skip_size_mismatch(self, tmp_path: Path) -> None:
        test_file: Path = tmp_path / "file.csv"
        test_file.write_bytes(b"short")

        manifest: DownloadManifest = DownloadManifest(
            path=tmp_path / ".manifest.json",
            entries=[
                ManifestEntry(
                    url="https://example.com/file.csv",
                    file_path=str(test_file),
                    byte_size=99999,
                    sha256_hash="abc",
                    download_timestamp="2024-01-01T00:00:00+00:00",
                    http_status=200,
                ),
            ],
        )
        assert manifest.should_skip("https://example.com/file.csv") is False

    def test_should_not_skip_unknown_url(self, tmp_path: Path) -> None:
        manifest: DownloadManifest = DownloadManifest(
            path=tmp_path / ".manifest.json",
            entries=[],
        )
        assert manifest.should_skip("https://example.com/new.csv") is False

    def test_upsert_replaces_existing(self, tmp_path: Path) -> None:
        entry_v1: ManifestEntry = ManifestEntry(
            url="https://example.com/file.csv",
            file_path="/tmp/v1.csv",
            byte_size=100,
            sha256_hash="hash_v1",
            download_timestamp="2024-01-01T00:00:00+00:00",
            http_status=200,
        )
        entry_v2: ManifestEntry = ManifestEntry(
            url="https://example.com/file.csv",
            file_path="/tmp/v2.csv",
            byte_size=200,
            sha256_hash="hash_v2",
            download_timestamp="2024-06-01T00:00:00+00:00",
            http_status=200,
        )
        manifest: DownloadManifest = DownloadManifest(
            path=tmp_path / ".manifest.json",
            entries=[entry_v1],
        )
        manifest.upsert(entry_v2)

        assert len(manifest.entries) == 1
        assert manifest.entries[0].byte_size == 200

    def test_prune_removes_missing_files(self, tmp_path: Path) -> None:
        existing: Path = tmp_path / "exists.csv"
        existing.write_bytes(b"data")

        manifest: DownloadManifest = DownloadManifest(
            path=tmp_path / ".manifest.json",
            entries=[
                ManifestEntry(
                    url="https://example.com/exists.csv",
                    file_path=str(existing),
                    byte_size=4,
                    sha256_hash="abc",
                    download_timestamp="2024-01-01T00:00:00+00:00",
                    http_status=200,
                ),
                ManifestEntry(
                    url="https://example.com/gone.csv",
                    file_path=str(tmp_path / "gone.csv"),
                    byte_size=100,
                    sha256_hash="def",
                    download_timestamp="2024-01-01T00:00:00+00:00",
                    http_status=200,
                ),
            ],
        )
        removed: int = manifest.prune()
        assert removed == 1
        assert len(manifest.entries) == 1
        assert manifest.entries[0].url == "https://example.com/exists.csv"

    def test_atomic_save_creates_file(self, tmp_path: Path) -> None:
        manifest_path: Path = tmp_path / "subdir" / ".manifest.json"
        manifest: DownloadManifest = DownloadManifest(path=manifest_path, entries=[])
        manifest.save()
        assert manifest_path.exists()


# ---------------------------------------------------------------------------
# CKAN download
# ---------------------------------------------------------------------------


class TestDownloadCkanDataset:
    """Tests for CKAN dataset download with mocked HTTP."""

    @respx.mock
    def test_downloads_filtered_resources(
        self,
        tmp_path: Path,
        subway_config: DatasetConfig,
        ckan_response_json: dict[str, object],
    ) -> None:
        """Verify CKAN download resolves and filters resources correctly."""
        api_url: str = (
            "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/package_show"
        )
        respx.get(api_url).mock(
            return_value=httpx.Response(200, json=ckan_response_json)
        )

        # Mock file download endpoints
        for res_id in ["res-001", "res-002"]:
            pattern: str = (
                "https://ckan0.cf.opendata.inter.prod-toronto.ca"
                f"/dataset/ttc-subway-delay-data/resource/{res_id}"
                f"/download/"
            )
            respx.get(url__startswith=pattern).mock(
                return_value=httpx.Response(200, content=b"fake-xlsx-data")
            )

        results: list[DownloadResult] = download_ckan_dataset(subway_config, tmp_path)

        # year_range=(2022, 2023) should match res-001 (2023) and res-002 (2022)
        assert len(results) == 2
        for result in results:
            assert result.http_status == 200
            assert result.byte_size > 0
            assert result.sha256_hash != ""
            assert not result.skipped

    @respx.mock
    def test_correct_directory_structure(
        self,
        tmp_path: Path,
        subway_config: DatasetConfig,
        ckan_response_json: dict[str, object],
    ) -> None:
        """Verify files land in <output_base>/<source>/<year>/<filename>."""
        respx.get(
            url__startswith="https://ckan0.cf.opendata.inter.prod-toronto.ca"
        ).mock(return_value=httpx.Response(200, json=ckan_response_json))
        respx.get(
            url__startswith="https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/"
        ).mock(return_value=httpx.Response(200, content=b"data"))

        results: list[DownloadResult] = download_ckan_dataset(subway_config, tmp_path)

        for result in results:
            path: Path = Path(result.file_path)
            assert path.exists()
            # Structure: tmp_path/ttc_subway/<year>/<filename>
            parts: tuple[str, ...] = path.relative_to(tmp_path).parts
            assert parts[0] == "ttc_subway"
            assert parts[1] in ("2022", "2023")

    @respx.mock
    def test_manifest_idempotency_skip(
        self,
        tmp_path: Path,
        subway_config: DatasetConfig,
        ckan_response_json: dict[str, object],
    ) -> None:
        """Verify second download with manifest skips existing files."""
        respx.get(
            url__startswith="https://ckan0.cf.opendata.inter.prod-toronto.ca"
        ).mock(return_value=httpx.Response(200, json=ckan_response_json))
        respx.get(
            url__startswith="https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/"
        ).mock(return_value=httpx.Response(200, content=b"data"))

        manifest: DownloadManifest = DownloadManifest(
            path=tmp_path / ".manifest.json", entries=[]
        )

        # First run: downloads
        results_1: list[DownloadResult] = download_ckan_dataset(
            subway_config, tmp_path, manifest
        )
        assert all(not r.skipped for r in results_1)

        # Second run: should skip
        results_2: list[DownloadResult] = download_ckan_dataset(
            subway_config, tmp_path, manifest
        )
        assert all(r.skipped for r in results_2)
        assert len(results_2) == len(results_1)

    @respx.mock
    def test_http_404_raises_download_error(
        self,
        tmp_path: Path,
        subway_config: DatasetConfig,
    ) -> None:
        """Verify DownloadError raised on CKAN API 404."""
        respx.get(
            url__startswith="https://ckan0.cf.opendata.inter.prod-toronto.ca"
        ).mock(return_value=httpx.Response(404, text="Not found"))

        with pytest.raises(DownloadError) as exc_info:
            download_ckan_dataset(subway_config, tmp_path)

        assert exc_info.value.status_code == 404
        assert "package_show" in exc_info.value.url


# ---------------------------------------------------------------------------
# Weather download
# ---------------------------------------------------------------------------


class TestDownloadWeatherData:
    """Tests for Environment Canada weather download with mocked HTTP."""

    @respx.mock
    def test_downloads_single_year(
        self,
        tmp_path: Path,
        weather_config: DatasetConfig,
    ) -> None:
        """Verify weather download for a single year."""
        respx.get(url__startswith="https://climate.weather.gc.ca/").mock(
            return_value=httpx.Response(
                200,
                content=b'"Date","Mean Temp"\n"2023-01-01","5.0"\n',
            )
        )

        results: list[DownloadResult] = download_weather_data(weather_config, tmp_path)

        assert len(results) == 1
        assert results[0].http_status == 200
        path: Path = Path(results[0].file_path)
        assert path.exists()
        assert path.name == "weather_daily_2023.csv"
        assert "weather" in str(path)

    @respx.mock
    def test_weather_manifest_skip(
        self,
        tmp_path: Path,
        weather_config: DatasetConfig,
    ) -> None:
        """Verify idempotent skip for weather downloads."""
        respx.get(url__startswith="https://climate.weather.gc.ca/").mock(
            return_value=httpx.Response(200, content=b"csv-data")
        )
        manifest: DownloadManifest = DownloadManifest(
            path=tmp_path / ".manifest.json", entries=[]
        )

        results_1: list[DownloadResult] = download_weather_data(
            weather_config, tmp_path, manifest
        )
        assert not results_1[0].skipped

        results_2: list[DownloadResult] = download_weather_data(
            weather_config, tmp_path, manifest
        )
        assert results_2[0].skipped

    @respx.mock
    def test_http_error_raises_download_error(
        self,
        tmp_path: Path,
        weather_config: DatasetConfig,
    ) -> None:
        """Verify DownloadError on Environment Canada HTTP 500."""
        respx.get(url__startswith="https://climate.weather.gc.ca/").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )

        with pytest.raises(DownloadError) as exc_info:
            download_weather_data(weather_config, tmp_path)

        assert exc_info.value.status_code == 500

    def test_missing_station_id_raises_value_error(self, tmp_path: Path) -> None:
        """Verify ValueError when station_id is None."""
        bad_config: DatasetConfig = DatasetConfig(
            name="weather_daily",
            source_type=SourceType.ENVIRONMENT_CANADA,
            api_base_url="https://climate.weather.gc.ca",
            dataset_id=None,
            station_id=None,
            climate_id=None,
            year_range=(2023, 2023),
            file_format=FileFormat.CSV,
            output_dir="weather",
        )
        with pytest.raises(ValueError, match="missing station_id"):
            download_weather_data(bad_config, tmp_path)


# ---------------------------------------------------------------------------
# DownloadError
# ---------------------------------------------------------------------------


class TestDownloadError:
    """Tests for DownloadError exception attributes."""

    def test_attributes(self) -> None:
        err: DownloadError = DownloadError(
            url="https://example.com/fail",
            status_code=403,
            body="Forbidden",
        )
        assert err.url == "https://example.com/fail"
        assert err.status_code == 403
        assert "403" in str(err)

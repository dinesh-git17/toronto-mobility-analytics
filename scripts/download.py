"""Source data acquisition module for Toronto Urban Mobility Analytics.

Downloads datasets from the Toronto Open Data Portal (CKAN API) and
Environment Canada Historical Climate Data. Implements idempotent
downloads with manifest-based tracking and SHA-256 integrity hashes.

Usage:
    python scripts/download.py --all
    python scripts/download.py --dataset ttc_subway_delays
    python scripts/download.py --dataset weather_daily --year 2023
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import httpx

from scripts.config import (
    DATASETS,
    DatasetConfig,
    SourceType,
    get_dataset_by_name,
)

logger: Final[logging.Logger] = logging.getLogger(__name__)

# Download tuning constants
_CHUNK_SIZE: Final[int] = 65_536
_CKAN_TIMEOUT: Final[int] = 300
_WEATHER_TIMEOUT: Final[int] = 120
_WEATHER_REQUEST_DELAY: Final[float] = 2.0
_RETRIES: Final[int] = 3


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


class DownloadError(Exception):
    """Raised when an HTTP request fails with a non-success status code."""

    def __init__(self, url: str, status_code: int, body: str) -> None:
        self.url: Final[str] = url
        self.status_code: Final[int] = status_code
        self.body: Final[str] = body
        super().__init__(f"HTTP {status_code} for {url}: {body[:200]}")


@dataclass(frozen=True, slots=True)
class DownloadResult:
    """Outcome of a single file download operation.

    Attributes:
        file_path: Absolute path to the downloaded file on disk.
        url: Source URL the file was fetched from.
        http_status: HTTP response status code (200 for success, 0 for skipped).
        byte_size: File size in bytes after download.
        download_timestamp: ISO-8601 timestamp of download completion.
        sha256_hash: Hex-encoded SHA-256 digest of the file contents.
        skipped: True if the download was skipped due to manifest match.
    """

    file_path: str
    url: str
    http_status: int
    byte_size: int
    download_timestamp: str
    sha256_hash: str
    skipped: bool = False


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


@dataclass
class ManifestEntry:
    """Single entry in the download manifest."""

    url: str
    file_path: str
    byte_size: int
    sha256_hash: str
    download_timestamp: str
    http_status: int


@dataclass
class DownloadManifest:
    """JSON-backed manifest tracking downloaded files for idempotency.

    Reads and writes a JSON file at the given path. Before each download,
    the caller checks whether a matching entry exists (same URL, same byte
    size on disk). If so, the download is skipped.
    """

    path: Path
    entries: list[ManifestEntry] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> DownloadManifest:
        """Load manifest from disk, returning empty manifest if absent."""
        if not path.exists():
            return cls(path=path, entries=[])
        raw: str = path.read_text(encoding="utf-8")
        data: list[dict[str, object]] = json.loads(raw)
        entries: list[ManifestEntry] = [
            ManifestEntry(
                url=str(e["url"]),
                file_path=str(e["file_path"]),
                byte_size=int(str(e["byte_size"])),
                sha256_hash=str(e["sha256_hash"]),
                download_timestamp=str(e["download_timestamp"]),
                http_status=int(str(e["http_status"])),
            )
            for e in data
        ]
        return cls(path=path, entries=entries)

    def save(self) -> None:
        """Persist manifest to disk via atomic write (temp file + replace)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path: Path = self.path.with_suffix(".tmp")
        payload: str = json.dumps(
            [asdict(e) for e in self.entries],
            indent=2,
        )
        tmp_path.write_text(payload, encoding="utf-8")
        os.replace(str(tmp_path), str(self.path))

    def find_entry(self, url: str) -> ManifestEntry | None:
        """Look up an existing manifest entry by URL."""
        for entry in self.entries:
            if entry.url == url:
                return entry
        return None

    def should_skip(self, url: str) -> bool:
        """Return True if the file for this URL already exists with correct size."""
        entry: ManifestEntry | None = self.find_entry(url)
        if entry is None:
            return False
        target: Path = Path(entry.file_path)
        if not target.exists():
            return False
        return target.stat().st_size == entry.byte_size

    def upsert(self, entry: ManifestEntry) -> None:
        """Insert or update a manifest entry keyed by URL."""
        self.entries = [e for e in self.entries if e.url != entry.url]
        self.entries.append(entry)

    def prune(self) -> int:
        """Remove entries whose files no longer exist on disk.

        Returns:
            Number of entries removed.
        """
        before: int = len(self.entries)
        self.entries = [e for e in self.entries if Path(e.file_path).exists()]
        removed: int = before - len(self.entries)
        if removed > 0:
            logger.info("Pruned %d stale manifest entries", removed)
        return removed


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 hex digest of a file using chunked reads.

    Args:
        file_path: Path to the file to hash.

    Returns:
        Lowercase hex-encoded SHA-256 digest.
    """
    hasher: hashlib._Hash = hashlib.sha256()
    with file_path.open("rb") as fh:
        while True:
            chunk: bytes = fh.read(_CHUNK_SIZE)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _build_ckan_client() -> httpx.Client:
    """Construct an httpx client configured for CKAN API requests."""
    transport: httpx.HTTPTransport = httpx.HTTPTransport(retries=_RETRIES)
    return httpx.Client(timeout=_CKAN_TIMEOUT, transport=transport)


def _build_weather_client() -> httpx.Client:
    """Construct an httpx client configured for Environment Canada requests."""
    transport: httpx.HTTPTransport = httpx.HTTPTransport(retries=_RETRIES)
    return httpx.Client(timeout=_WEATHER_TIMEOUT, transport=transport)


def _stream_to_file(
    client: httpx.Client,
    url: str,
    dest: Path,
) -> tuple[int, int]:
    """Stream an HTTP GET response to a file on disk.

    Args:
        client: Configured httpx.Client instance.
        url: URL to fetch.
        dest: Destination file path.

    Returns:
        Tuple of (http_status_code, bytes_written).

    Raises:
        DownloadError: On HTTP 4xx/5xx responses.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    with client.stream("GET", url) as response:
        if response.status_code >= 400:
            body: str = response.read().decode("utf-8", errors="replace")
            raise DownloadError(url, response.status_code, body)
        total_bytes: int = 0
        with dest.open("wb") as fh:
            for chunk in response.iter_bytes(chunk_size=_CHUNK_SIZE):
                fh.write(chunk)
                total_bytes += len(chunk)
    return response.status_code, total_bytes


# ---------------------------------------------------------------------------
# CKAN download (S002)
# ---------------------------------------------------------------------------


def _resolve_ckan_resources(
    client: httpx.Client,
    config: DatasetConfig,
) -> list[dict[str, object]]:
    """Fetch resource metadata from the CKAN package_show endpoint.

    Args:
        client: Configured httpx.Client instance.
        config: Dataset configuration with CKAN API details.

    Returns:
        List of resource dicts from the CKAN API response.

    Raises:
        DownloadError: On HTTP error from CKAN API.
    """
    url: str = f"{config.api_base_url}/api/3/action/package_show?id={config.dataset_id}"
    response: httpx.Response = client.get(url)
    if response.status_code >= 400:
        raise DownloadError(url, response.status_code, response.text)
    data: dict[str, object] = response.json()
    result: object = data.get("result", {})
    if not isinstance(result, dict):
        return []
    resources: object = result.get("resources", [])
    if not isinstance(resources, list):
        return []
    return [dict(r) for r in resources if isinstance(r, dict)]


def _extract_year_from_resource(resource: dict[str, object]) -> int | None:
    """Attempt to extract a four-digit year from a CKAN resource name.

    Scans the resource 'name' field for patterns like '2023', 'Jan 2023',
    or '2023-01'. Returns the first year found, or None if no match.
    """
    name: str = str(resource.get("name", ""))
    match: re.Match[str] | None = re.search(r"(20[1-2]\d)", name)
    if match:
        return int(match.group(1))
    return None


def _filter_resources_by_year(
    resources: list[dict[str, object]],
    year_range: tuple[int, int],
    file_format: str | None = None,
) -> list[dict[str, object]]:
    """Filter CKAN resources by year range and optionally by file format."""
    start_year, end_year = year_range
    filtered: list[dict[str, object]] = []
    for resource in resources:
        year: int | None = _extract_year_from_resource(resource)
        if year is None or not (start_year <= year <= end_year):
            continue
        if file_format is not None:
            fmt: str = str(resource.get("format", "")).upper()
            if fmt != file_format.upper():
                continue
        filtered.append(resource)
    return filtered


def _resource_filename(resource: dict[str, object]) -> str:
    """Derive a filename from a CKAN resource entry.

    Prefers the 'name' field sanitized for filesystem safety, falling
    back to the URL basename.
    """
    name: str = str(resource.get("name", ""))
    url: str = str(resource.get("url", ""))
    if name:
        # Sanitize: replace non-alphanumeric chars (except dot/dash/underscore)
        safe: str = re.sub(r"[^\w\-.]", "_", name)
        fmt: str = str(resource.get("format", "")).lower()
        if fmt and not safe.lower().endswith(f".{fmt}"):
            safe = f"{safe}.{fmt}"
        return safe
    return url.rsplit("/", maxsplit=1)[-1] or "unknown"


def download_ckan_dataset(
    config: DatasetConfig,
    output_base: Path,
    manifest: DownloadManifest | None = None,
) -> list[DownloadResult]:
    """Download all resources for a CKAN-hosted dataset.

    Resolves resource URLs via the package_show API, filters by year
    range, and downloads each file to the appropriate directory.

    Args:
        config: Dataset configuration with CKAN identifiers.
        output_base: Root directory for downloads (e.g., data/raw).
        manifest: Optional manifest for idempotency checks.

    Returns:
        List of DownloadResult for each processed resource.

    Raises:
        DownloadError: On HTTP errors from CKAN API or file downloads.
    """
    results: list[DownloadResult] = []
    with _build_ckan_client() as client:
        resources: list[dict[str, object]] = _resolve_ckan_resources(client, config)
        filtered: list[dict[str, object]] = _filter_resources_by_year(
            resources, config.year_range, file_format=config.file_format.value
        )
        logger.info(
            "Dataset '%s': resolved %d resources, %d in year range",
            config.name,
            len(resources),
            len(filtered),
        )

        for resource in filtered:
            url: str = str(resource.get("url", ""))
            if not url:
                continue
            year: int | None = _extract_year_from_resource(resource)
            year_str: str = str(year) if year else "unknown"
            filename: str = _resource_filename(resource)
            dest: Path = output_base / config.output_dir / year_str / filename

            # Idempotency check
            if manifest is not None and manifest.should_skip(url):
                logger.info("SKIPPED (manifest): %s", dest)
                entry: ManifestEntry | None = manifest.find_entry(url)
                assert entry is not None
                results.append(
                    DownloadResult(
                        file_path=str(dest),
                        url=url,
                        http_status=0,
                        byte_size=entry.byte_size,
                        download_timestamp=entry.download_timestamp,
                        sha256_hash=entry.sha256_hash,
                        skipped=True,
                    )
                )
                continue

            logger.info("Downloading: %s -> %s", url, dest)
            status, byte_size = _stream_to_file(client, url, dest)
            sha256: str = compute_sha256(dest)
            ts: str = datetime.now(tz=UTC).isoformat()

            result = DownloadResult(
                file_path=str(dest),
                url=url,
                http_status=status,
                byte_size=byte_size,
                download_timestamp=ts,
                sha256_hash=sha256,
            )
            results.append(result)

            if manifest is not None:
                manifest.upsert(
                    ManifestEntry(
                        url=url,
                        file_path=str(dest),
                        byte_size=byte_size,
                        sha256_hash=sha256,
                        download_timestamp=ts,
                        http_status=status,
                    )
                )
                manifest.save()

    return results


# ---------------------------------------------------------------------------
# Weather download (S003)
# ---------------------------------------------------------------------------


def _build_weather_url(station_id: int, year: int, month: int) -> str:
    """Construct the Environment Canada bulk download URL for daily data."""
    return (
        f"https://climate.weather.gc.ca/climate_data/bulk_data_e.html"
        f"?format=csv&stationID={station_id}"
        f"&Year={year}&Month={month}&timeframe=2"
    )


def download_weather_data(
    config: DatasetConfig,
    output_base: Path,
    manifest: DownloadManifest | None = None,
) -> list[DownloadResult]:
    """Download Environment Canada daily weather CSVs for each year in range.

    Fetches one CSV per year using timeframe=2 (daily data). Inserts a
    2-second delay between requests to respect rate limits.

    Args:
        config: Dataset configuration with Environment Canada identifiers.
        output_base: Root directory for downloads (e.g., data/raw).
        manifest: Optional manifest for idempotency checks.

    Returns:
        List of DownloadResult for each processed year.

    Raises:
        DownloadError: On HTTP errors from Environment Canada.
    """
    if config.station_id is None:
        msg: str = f"Dataset '{config.name}' missing station_id"
        raise ValueError(msg)

    results: list[DownloadResult] = []
    start_year, end_year = config.year_range

    with _build_weather_client() as client:
        for year_idx, year in enumerate(range(start_year, end_year + 1)):
            # timeframe=2 returns full year; month=1 is a required parameter
            url: str = _build_weather_url(config.station_id, year, 1)
            filename: str = f"weather_daily_{year}.csv"
            dest: Path = output_base / config.output_dir / str(year) / filename

            # Idempotency check
            if manifest is not None and manifest.should_skip(url):
                logger.info("SKIPPED (manifest): %s", dest)
                entry: ManifestEntry | None = manifest.find_entry(url)
                assert entry is not None
                results.append(
                    DownloadResult(
                        file_path=str(dest),
                        url=url,
                        http_status=0,
                        byte_size=entry.byte_size,
                        download_timestamp=entry.download_timestamp,
                        sha256_hash=entry.sha256_hash,
                        skipped=True,
                    )
                )
                continue

            # Rate limiting: wait between requests (skip first)
            if year_idx > 0:
                time.sleep(_WEATHER_REQUEST_DELAY)

            logger.info("Downloading weather %d: %s -> %s", year, url, dest)
            status, byte_size = _stream_to_file(client, url, dest)
            sha256: str = compute_sha256(dest)
            ts: str = datetime.now(tz=UTC).isoformat()

            result = DownloadResult(
                file_path=str(dest),
                url=url,
                http_status=status,
                byte_size=byte_size,
                download_timestamp=ts,
                sha256_hash=sha256,
            )
            results.append(result)

            if manifest is not None:
                manifest.upsert(
                    ManifestEntry(
                        url=url,
                        file_path=str(dest),
                        byte_size=byte_size,
                        sha256_hash=sha256,
                        download_timestamp=ts,
                        http_status=status,
                    )
                )
                manifest.save()

    return results


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def download_dataset(
    config: DatasetConfig,
    output_base: Path,
    manifest: DownloadManifest | None = None,
) -> list[DownloadResult]:
    """Route a dataset config to the appropriate download function.

    Args:
        config: Dataset configuration to download.
        output_base: Root directory for downloads.
        manifest: Optional manifest for idempotency.

    Returns:
        List of DownloadResult instances.
    """
    if config.source_type == SourceType.CKAN:
        return download_ckan_dataset(config, output_base, manifest)
    if config.source_type == SourceType.ENVIRONMENT_CANADA:
        return download_weather_data(config, output_base, manifest)
    msg: str = f"Unsupported source type: {config.source_type}"
    raise ValueError(msg)


def download_all(
    output_base: Path,
    year: int | None = None,
) -> list[DownloadResult]:
    """Download all configured datasets.

    Args:
        output_base: Root directory for downloads (e.g., data/raw).
        year: Optional year filter. If provided, overrides each dataset's
            year_range to download only the specified year.

    Returns:
        Aggregated list of DownloadResult across all datasets.
    """
    manifest_path: Path = output_base / ".manifest.json"
    manifest: DownloadManifest = DownloadManifest.load(manifest_path)
    manifest.prune()

    all_results: list[DownloadResult] = []

    for config in DATASETS:
        effective_config: DatasetConfig = config
        if year is not None:
            effective_config = DatasetConfig(
                name=config.name,
                source_type=config.source_type,
                api_base_url=config.api_base_url,
                dataset_id=config.dataset_id,
                station_id=config.station_id,
                climate_id=config.climate_id,
                year_range=(year, year),
                file_format=config.file_format,
                output_dir=config.output_dir,
            )
        try:
            results: list[DownloadResult] = download_dataset(
                effective_config, output_base, manifest
            )
            all_results.extend(results)
        except DownloadError:
            logger.exception("Failed to download dataset '%s'", config.name)
            continue

    return all_results


# ---------------------------------------------------------------------------
# CLI (S006)
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser."""
    valid_names: str = ", ".join(d.name for d in DATASETS)
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Download source datasets for Toronto Urban Mobility Analytics.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="download_all",
        help="Download all configured datasets.",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help=f"Download a specific dataset by name. Valid: {valid_names}",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Restrict downloads to a single year (e.g., 2023).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/raw",
        help="Root output directory for downloads (default: data/raw).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug-level logging.",
    )
    return parser


def _configure_logging(verbose: bool) -> None:
    """Set up structured logging for the download session."""
    level: int = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the download module.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code: 0 on success, 1 on error.
    """
    parser: argparse.ArgumentParser = _build_arg_parser()
    args: argparse.Namespace = parser.parse_args(argv)
    _configure_logging(args.verbose)

    output_base: Path = Path(args.output_dir)
    output_base.mkdir(parents=True, exist_ok=True)

    if not args.download_all and args.dataset is None:
        parser.error("Specify --all or --dataset <name>")
        return 1

    results: list[DownloadResult]

    if args.download_all:
        logger.info("Starting full acquisition for all datasets")
        results = download_all(output_base, year=args.year)
    else:
        config: DatasetConfig = get_dataset_by_name(args.dataset)
        manifest_path: Path = output_base / ".manifest.json"
        manifest: DownloadManifest = DownloadManifest.load(manifest_path)
        manifest.prune()

        effective_config: DatasetConfig = config
        if args.year is not None:
            effective_config = DatasetConfig(
                name=config.name,
                source_type=config.source_type,
                api_base_url=config.api_base_url,
                dataset_id=config.dataset_id,
                station_id=config.station_id,
                climate_id=config.climate_id,
                year_range=(args.year, args.year),
                file_format=config.file_format,
                output_dir=config.output_dir,
            )
        results = download_dataset(effective_config, output_base, manifest)

    downloaded: int = sum(1 for r in results if not r.skipped)
    skipped: int = sum(1 for r in results if r.skipped)
    logger.info(
        "Acquisition complete: %d downloaded, %d skipped, %d total",
        downloaded,
        skipped,
        len(results),
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())

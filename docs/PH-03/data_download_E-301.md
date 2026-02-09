# Data Download & Source Acquisition

| Field        | Value                      |
| ------------ | -------------------------- |
| Epic ID      | E-301                      |
| Phase        | PH-03                      |
| Owner        | @dinesh-git17              |
| Status       | Complete                   |
| Dependencies | [PH-02.E-201, PH-02.E-202] |
| Created      | 2026-02-03                 |

## Context

PH-03 requires raw source data from the Toronto Open Data Portal and Environment Canada before any schema validation or Snowflake loading can occur. The ingestion pipeline depends on reliable, repeatable acquisition of five distinct datasets: TTC subway delays, TTC bus delays, TTC streetcar delays, Bike Share ridership, and daily weather observations from Toronto Pearson (Station ID: 51459). These datasets span 2019-present and exist as a mix of XLSX and CSV files distributed across monthly and quarterly release cadences. Without a deterministic download mechanism, subsequent pipeline stages (validation, transformation, loading) have no input, making this epic the critical-path entry point for PH-03.

## Scope

### In Scope

- Python 3.12 `scripts/download.py` module for fetching all five source datasets from Toronto Open Data Portal and Environment Canada
- HTTP client implementation with retry logic, timeout configuration, and rate-limit awareness for Toronto Open Data CKAN API
- File storage management under `data/raw/` with deterministic directory structure organized by source and year
- Download manifest tracking (file URL, expected filename, download timestamp, byte size, HTTP status) for audit and idempotency
- Environment Canada Historical Weather CSV acquisition for Toronto Pearson (Station ID: 51459, Climate ID: 6158733)
- Unit and integration tests for the download module via `pytest`
- Type-annotated module passing `mypy --strict`
- Linting compliance with `ruff check` and `ruff format`

### Out of Scope

- Schema validation of downloaded files (covered by E-302)
- XLSX-to-CSV conversion (covered by E-302)
- Snowflake COPY INTO or MERGE operations (covered by E-303)
- Incremental or differential downloads (full re-download is acceptable for v1 data volumes)
- Orchestration sequencing across download → validate → transform → load (covered by E-303)

## Technical Approach

### Architecture Decisions

- **CKAN API for Toronto Open Data**: The Toronto Open Data Portal exposes a CKAN-based API. Use the `package_show` endpoint to resolve dataset resource URLs programmatically rather than hardcoding download links, which break when the portal publishes new monthly files. This aligns with DESIGN-DOC.md Section 4.1 source definitions.
- **`httpx` over `requests`**: Use `httpx` as the HTTP client for HTTP/2 support, built-in retry via `httpx.Client(transport=httpx.HTTPTransport(retries=3))`, and async-ready architecture. Python 3.12 requirement (CLAUDE.md Section 6.3) makes `httpx` the idiomatic choice.
- **Deterministic directory layout**: Store files under `data/raw/<source>/<year>/` (e.g., `data/raw/ttc_subway/2023/`). This structure supports year-level partitioning for selective re-ingestion without full re-download.
- **Idempotent downloads**: If a file already exists at the target path with matching byte size from a prior manifest entry, skip the download. This prevents redundant network traffic during iterative development.
- **Environment Canada direct CSV**: Weather data is fetched via direct CSV download from `climate.weather.gc.ca` using query parameters for station ID, year, month, and data format. No API wrapper exists; construct URLs programmatically.

### Integration Points

- Toronto Open Data Portal CKAN API (`https://ckan0.cf.opendata.inter.prod-toronto.ca`)
- Environment Canada Historical Climate Data (`https://climate.weather.gc.ca`)
- Local filesystem `data/raw/` directory (gitignored)
- Downstream: E-302 `validate.py` consumes files written by this module

### Repository Areas

- `scripts/download.py` — core download module
- `scripts/config.py` — dataset registry (URLs, expected filenames, source metadata)
- `tests/test_download.py` — unit and integration tests
- `data/raw/` — download target directory (gitignored)
- `pyproject.toml` — dependency declaration (`httpx`)

### Risks

| Risk                                                              | Likelihood | Impact | Mitigation                                                                                               |
| ----------------------------------------------------------------- | ---------- | ------ | -------------------------------------------------------------------------------------------------------- |
| Toronto Open Data Portal API changes resource URLs without notice | Medium     | High   | Resolve URLs dynamically via CKAN `package_show` rather than hardcoding; log resolved URLs for debugging |
| Environment Canada rate-limits or blocks automated downloads      | Low        | Medium | Add 2-second delay between requests; implement exponential backoff; cache downloaded files locally       |
| XLSX files exceed 100MB for bus delay annual aggregates           | Low        | Medium | Stream downloads with chunked writes; validate file size against manifest before proceeding              |
| Network timeouts on large Bike Share CSV files (~500MB annual)    | Medium     | Medium | Configure 300-second timeout; implement resumable download via HTTP Range headers if server supports it  |

## Stories

| ID   | Story                                                 | Points | Dependencies | Status |
| ---- | ----------------------------------------------------- | ------ | ------------ | ------ |
| S001 | Create dataset configuration registry                 | 3      | None         | Done   |
| S002 | Implement Toronto Open Data CKAN download client      | 5      | S001         | Done   |
| S003 | Implement Environment Canada weather download client  | 3      | S001         | Done   |
| S004 | Implement download manifest and idempotency logic     | 3      | S002, S003   | Done   |
| S005 | Add comprehensive test suite for download module      | 5      | S002, S003   | Done   |
| S006 | Execute full source data acquisition for 2019-present | 3      | S004         | Done   |

---

### S001: Create dataset configuration registry

**Description**: Build a typed configuration module that defines all five source datasets with their API endpoints, expected file patterns, date ranges, and storage paths.

**Acceptance Criteria**:

- [x] File `scripts/config.py` exists and defines a `DatasetConfig` dataclass with fields: `name`, `source_type` (enum: `CKAN` | `ENVIRONMENT_CANADA`), `api_base_url`, `dataset_id` (for CKAN datasets), `station_id` (for weather), `year_range` (tuple of start/end year), `file_format` (enum: `XLSX` | `CSV`), `output_dir` (relative path under `data/raw/`)
- [x] Registry contains entries for all five datasets: `ttc_subway_delays`, `ttc_bus_delays`, `ttc_streetcar_delays`, `bike_share_ridership`, `weather_daily`
- [x] CKAN dataset IDs match Toronto Open Data Portal identifiers: subway (`996cfe8d-fb35-40ce-b569-698d51fc683b`), bus (`e271cdae-8788-4980-96ce-6a5c95bc6571`), streetcar (`b68cb71b-44a7-4394-97e2-5d2f41462a5d`), bike share (`7e876c24-177c-4605-9cef-e50dd74c617f`)
- [x] Environment Canada entry specifies Station ID `51459` and Climate ID `6158733`
- [x] `mypy --strict scripts/config.py` passes with zero errors
- [x] `ruff check scripts/config.py && ruff format --check scripts/config.py` passes

**Technical Notes**: Use `enum.Enum` for source type and file format. Use `dataclasses.dataclass` with `frozen=True` for immutability. Store the registry as a module-level `DATASETS: tuple[DatasetConfig, ...]` constant.

**Definition of Done**:

- [x] Code committed to feature branch
- [x] Tests pass locally
- [x] PR opened with linked issue
- [x] CI checks green

---

### S002: Implement Toronto Open Data CKAN download client

**Description**: Build the core download function that resolves resource URLs from the CKAN API and downloads TTC delay and Bike Share files to the local filesystem.

**Acceptance Criteria**:

- [x] Function `download_ckan_dataset(config: DatasetConfig, output_base: Path) -> list[DownloadResult]` exists in `scripts/download.py`
- [x] Function calls CKAN `package_show` API endpoint (`/api/3/action/package_show?id=<dataset_id>`) to resolve current resource URLs
- [x] Function filters resources by year range defined in `DatasetConfig` using resource metadata (name or date fields)
- [x] Downloads write to `data/raw/<source_name>/<year>/<original_filename>` preserving the portal's original filename
- [x] HTTP client uses `httpx.Client` with `timeout=300`, `transport=httpx.HTTPTransport(retries=3)`
- [x] Function returns a list of `DownloadResult` dataclass instances containing: `file_path`, `url`, `http_status`, `byte_size`, `download_timestamp`
- [x] On HTTP 4xx/5xx response, function raises `DownloadError` with the URL, status code, and response body
- [x] `mypy --strict scripts/download.py` passes with zero errors
- [x] `ruff check scripts/download.py && ruff format --check scripts/download.py` passes

**Technical Notes**: The CKAN API returns a JSON response with `result.resources` array. Each resource has `url`, `name`, `last_modified`, and `format` fields. Filter resources by inspecting the `name` field for year indicators (e.g., "2023", "Jan 2023"). Create parent directories with `Path.mkdir(parents=True, exist_ok=True)` before writing.

**Definition of Done**:

- [x] Code committed to feature branch
- [x] Tests pass locally
- [x] PR opened with linked issue
- [x] CI checks green

---

### S003: Implement Environment Canada weather download client

**Description**: Build the download function for Environment Canada Historical Climate Data CSVs covering Toronto Pearson station from 2019 to present.

**Acceptance Criteria**:

- [x] Function `download_weather_data(config: DatasetConfig, output_base: Path) -> list[DownloadResult]` exists in `scripts/download.py`
- [x] Function constructs download URLs using the pattern: `https://climate.weather.gc.ca/climate_data/bulk_data_e.html?format=csv&stationID=51459&Year={year}&Month={month}&timeframe=2` for each year-month combination in the configured range
- [x] Downloads one CSV per year (timeframe=2 returns daily data for the full year) and writes to `data/raw/weather/<year>/weather_daily_{year}.csv`
- [x] HTTP client uses `httpx.Client` with `timeout=120`, `transport=httpx.HTTPTransport(retries=3)`
- [x] Function inserts a 2-second delay (`time.sleep(2)`) between consecutive requests to respect rate limits
- [x] Function returns `DownloadResult` instances consistent with S002
- [x] On HTTP error, function raises `DownloadError` with URL, status code, and response body
- [x] `mypy --strict scripts/download.py` passes with zero errors

**Technical Notes**: Environment Canada's bulk download endpoint returns CSV directly. The `timeframe=2` parameter selects daily granularity. Request one file per year rather than per month to reduce request count (7 requests for 2019-2025 vs. 84).

**Definition of Done**:

- [x] Code committed to feature branch
- [x] Tests pass locally
- [x] PR opened with linked issue
- [x] CI checks green

---

### S004: Implement download manifest and idempotency logic

**Description**: Build a JSON-based manifest that tracks all downloaded files, enabling idempotent re-runs that skip previously acquired files.

**Acceptance Criteria**:

- [x] File `scripts/download.py` contains a `DownloadManifest` class that reads/writes a JSON manifest at `data/raw/.manifest.json`
- [x] Manifest schema contains a list of entries, each with: `url`, `file_path`, `byte_size`, `sha256_hash`, `download_timestamp`, `http_status`
- [x] Before downloading a file, the download functions (S002, S003) consult the manifest: if an entry exists with matching `url` and the file at `file_path` exists with matching `byte_size`, the download is skipped and logged as `SKIPPED`
- [x] After a successful download, the manifest is updated atomically (write to temp file, then `os.replace` to target path)
- [x] `DownloadManifest.prune()` method removes entries whose `file_path` no longer exists on disk
- [x] SHA-256 hash is computed for each downloaded file and stored in the manifest for integrity verification
- [x] `mypy --strict` passes on all modified files
- [x] `ruff check && ruff format --check` passes on all modified files

**Technical Notes**: Use `hashlib.sha256` with chunked reads (64KB buffer) for hash computation to avoid loading large files into memory. The manifest file itself lives inside `data/raw/` which is gitignored.

**Definition of Done**:

- [x] Code committed to feature branch
- [x] Tests pass locally
- [x] PR opened with linked issue
- [x] CI checks green

---

### S005: Add comprehensive test suite for download module

**Description**: Build a pytest test suite covering the download module with mocked HTTP responses and filesystem assertions.

**Acceptance Criteria**:

- [x] File `tests/test_download.py` exists with test functions covering: CKAN URL resolution, CKAN file download, weather URL construction, weather file download, manifest read/write, manifest idempotency skip, error handling on HTTP failures
- [x] Tests mock HTTP responses using `pytest-httpx` or `respx` — no real network calls during test execution
- [x] Tests use `tmp_path` fixture for all filesystem operations
- [x] Test for CKAN download verifies correct directory structure: `<output_base>/<source_name>/<year>/<filename>`
- [x] Test for manifest idempotency verifies that a second download call with existing manifest entry and file produces `SKIPPED` status
- [x] Test for HTTP 404 verifies `DownloadError` is raised with the correct URL and status code
- [x] Test for SHA-256 hash verifies computed hash matches known value for a test fixture file
- [x] `pytest tests/test_download.py -v` passes with zero failures
- [x] `mypy --strict tests/test_download.py` passes
- [x] `ruff check tests/test_download.py && ruff format --check tests/test_download.py` passes

**Technical Notes**: Create a minimal CKAN API JSON response fixture in `tests/fixtures/ckan_package_show_response.json` for realistic mock data. Use `pytest.raises` for error path assertions.

**Definition of Done**:

- [x] Code committed to feature branch
- [x] Tests pass locally
- [x] PR opened with linked issue
- [x] CI checks green

---

### S006: Execute full source data acquisition for 2019-present

**Description**: Run the download module against all five production datasets, verify completeness of acquired files, and document the resulting file inventory.

**Acceptance Criteria**:

- [x] Running `python scripts/download.py --all` downloads all TTC delay files (subway, bus, streetcar) for years 2019-2025 from Toronto Open Data Portal
- [x] Running `python scripts/download.py --all` downloads all Bike Share ridership files for years 2019-2025
- [x] Running `python scripts/download.py --all` downloads all Environment Canada daily weather CSVs for years 2019-2025
- [x] `data/raw/.manifest.json` contains entries for every downloaded file with valid SHA-256 hashes
- [x] Re-running `python scripts/download.py --all` completes without re-downloading existing files (idempotency verified via log output showing `SKIPPED` status)
- [x] Total downloaded file count per source matches expected: TTC subway (~72 files), TTC bus (~72 files), TTC streetcar (~72 files), Bike Share (~24-28 files), weather (~7 files)
- [x] No download errors in the execution log

**Technical Notes**: Run this story on a machine with stable internet connectivity. Expected total download size is approximately 2-3 GB across all datasets. The CLI entry point uses `argparse` with `--all`, `--dataset <name>`, and `--year <YYYY>` flags for selective execution.

**Definition of Done**:

- [x] Code committed to feature branch
- [x] Tests pass locally
- [x] PR opened with linked issue
- [x] CI checks green

---

## Exit Criteria

This epic is complete when:

- [x] `scripts/download.py` and `scripts/config.py` exist, are type-annotated, and pass `mypy --strict`
- [x] All five datasets (TTC subway, TTC bus, TTC streetcar, Bike Share, weather) are downloaded to `data/raw/` with correct directory structure
- [x] Download manifest at `data/raw/.manifest.json` tracks all acquired files with SHA-256 hashes
- [x] Idempotent re-execution skips previously downloaded files
- [x] `pytest tests/test_download.py` passes with zero failures
- [x] `ruff check` and `ruff format` pass on all Python files in `scripts/` and `tests/`
- [x] Python code generated via `python-writing` skill

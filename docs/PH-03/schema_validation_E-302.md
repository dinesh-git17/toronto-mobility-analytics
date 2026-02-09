# Schema Validation & Data Transformation

| Field        | Value         |
| ------------ | ------------- |
| Epic ID      | E-302         |
| Phase        | PH-03         |
| Owner        | @dinesh-git17 |
| Status       | Complete      |
| Dependencies | [E-301]       |
| Created      | 2026-02-03    |

## Context

Raw source files acquired by E-301 arrive in heterogeneous formats (XLSX for TTC delays, ZIP archives containing monthly CSVs for Bike Share, and CSV for weather) with no guarantee of schema stability across years. The Toronto Open Data Portal has historically changed column names, added columns, and altered data types between annual releases. DESIGN-DOC.md Section 4.3 mandates fail-fast schema enforcement: if the actual schema of a downloaded file deviates from the expected contract, the entire ingestion run must abort with zero partial loads. This epic builds the validation and transformation layer that sits between raw file acquisition (E-301) and Snowflake loading (E-303), ensuring only contract-compliant CSV data reaches the loading stage.

## Scope

### In Scope

- Python 3.12 `scripts/validate.py` module implementing fail-fast schema contract enforcement per DESIGN-DOC.md Section 4.3
- Schema contract definitions for all five source datasets as typed Python datastructures matching Section 4.3.1 (TTC Subway), 4.3.2 (Bike Share), and 4.3.3 (Weather) contracts
- `SchemaValidationError` custom exception with structured error reporting (expected vs. actual columns, type mismatches, file path)
- Python 3.12 `scripts/transform.py` module for XLSX-to-CSV conversion using `openpyxl` and ZIP archive extraction for Bike Share ridership files using `zipfile`
- Encoding normalization (detect and convert to UTF-8) for source CSVs with inconsistent encodings
- Unit and integration tests for both modules via `pytest`
- Type-annotated modules passing `mypy --strict`
- Linting compliance with `ruff check` and `ruff format`

### Out of Scope

- Data quality checks beyond schema contract (value range validation, distribution analysis — covered by PH-08)
- Row-level data cleansing or imputation (staging layer responsibility, PH-05)
- Downloading source files (covered by E-301)
- Loading validated CSVs into Snowflake (covered by E-303)
- Business logic transformations (column renaming, type casting — staging layer, PH-05)

## Technical Approach

### Architecture Decisions

- **Fail-fast, zero tolerance**: Per DESIGN-DOC.md Section 4.3 schema change policy, validation raises `SchemaValidationError` on the first file that deviates from the expected contract. The orchestrator (E-303) catches this and aborts the entire run. No partial processing occurs.
- **Schema contracts as frozen dataclasses**: Define each dataset's expected schema as a `SchemaContract` dataclass containing: `required_columns` (ordered list of `ColumnContract` with name and dtype), `nullable_columns` (set of column names), and `row_validators` (optional per-row callables). This makes contracts version-controlled, diffable, and testable.
- **`openpyxl` for XLSX conversion**: Use `openpyxl` in read-only mode for memory-efficient processing of large XLSX files (TTC bus delays can exceed 100K rows per file). Write output as UTF-8 CSV with `csv.writer`. Avoid `pandas` for conversion to minimize dependency footprint and control encoding explicitly.
- **Two-phase validation**: Phase 1 validates column presence and ordering (structural). Phase 2 validates column data types by sampling the first 1,000 rows (type inference). Both phases must pass before a file is marked valid.
- **ZIP extraction for Bike Share**: Bike Share ridership files arrive as ZIP archives containing 12 monthly CSVs per year (e.g., `Bike share ridership 2023-01.csv` through `2023-12.csv`, each 23–96 MB). Use Python's `zipfile` module to extract CSVs to `data/raw/bike_share/<year>/` before validation. The extraction step is idempotent: skip extraction if target CSVs already exist with matching file sizes.
- **Encoding detection via `charset-normalizer`**: Some older TTC XLSX exports produce CSVs with Windows-1252 encoding. Use `charset-normalizer` to detect encoding and transcode to UTF-8 before validation.

### Integration Points

- Upstream: Reads files from `data/raw/<source>/<year>/` written by E-301
- Downstream: Writes validated CSV files to `data/validated/<source>/<year>/` for consumption by E-303 `load.py`
- Schema contracts reference DESIGN-DOC.md Section 4.3.1 (TTC Subway), 4.3.2 (Bike Share), 4.3.3 (Weather)

### Repository Areas

- `scripts/validate.py` — schema validation module
- `scripts/transform.py` — XLSX-to-CSV conversion and ZIP extraction module
- `scripts/contracts.py` — schema contract definitions
- `tests/test_validate.py` — validation test suite
- `tests/test_transform.py` — transformation test suite
- `tests/fixtures/` — sample XLSX and CSV files for testing
- `data/validated/` — output directory for validated CSVs (gitignored)
- `pyproject.toml` — dependency declarations (`openpyxl`, `charset-normalizer`)

### Risks

| Risk                                                                             | Likelihood | Impact | Mitigation                                                                                                                     |
| -------------------------------------------------------------------------------- | ---------- | ------ | ------------------------------------------------------------------------------------------------------------------------------ |
| TTC source files change column ordering between years while keeping column names | High       | Medium | Validate column presence as a set (not ordered list) for structural check; validate ordering only as a warning                 |
| Bike Share CSV files contain BOM (Byte Order Mark) characters                    | Medium     | Low    | Strip BOM bytes during encoding normalization before validation                                                                |
| XLSX files contain multiple worksheets with data split across sheets             | Low        | High   | Document expected worksheet name per dataset in `SchemaContract`; raise `SchemaValidationError` if target worksheet is missing |
| Large XLSX files (>200K rows) cause memory pressure during conversion            | Low        | Medium | Use `openpyxl` read-only mode with row-by-row streaming; never load entire workbook into memory                                |
| Bike Share ZIP internal directory structure changes between years                | Medium     | Medium | Discover CSV paths dynamically via `zipfile.ZipFile.infolist()` rather than hardcoding; filter by `.csv` extension             |

## Stories

| ID   | Story                                                          | Points | Dependencies                 | Status |
| ---- | -------------------------------------------------------------- | ------ | ---------------------------- | ------ |
| S001 | Define schema contracts for all five source datasets           | 5      | None                         | Draft  |
| S002 | Implement XLSX-to-CSV conversion module                        | 5      | None                         | Draft  |
| S003 | Implement schema validation engine with fail-fast behavior     | 5      | S001                         | Draft  |
| S004 | Implement encoding detection and normalization                 | 3      | None                         | Draft  |
| S007 | Implement ZIP archive extraction for Bike Share datasets       | 3      | None                         | Draft  |
| S005 | Add comprehensive test suite for validation and transformation | 5      | S001, S002, S003, S004, S007 | Draft  |
| S006 | Validate all downloaded source files against contracts         | 3      | S005, E-301.S006             | Draft  |

---

### S001: Define schema contracts for all five source datasets

**Description**: Build typed schema contract definitions for TTC subway delays, TTC bus delays, TTC streetcar delays, Bike Share ridership, and daily weather data matching DESIGN-DOC.md Section 4.3 specifications.

**Acceptance Criteria**:

- [ ] File `scripts/contracts.py` exists and defines a `ColumnContract` dataclass with fields: `name` (str), `expected_dtype` (str, one of: `DATE`, `TIME`, `STRING`, `INTEGER`, `DECIMAL`, `TIMESTAMP`), `nullable` (bool)
- [ ] File defines a `SchemaContract` dataclass with fields: `dataset_name` (str), `columns` (tuple of `ColumnContract`), `min_row_count` (int, used as sanity check)
- [ ] TTC Subway contract matches DESIGN-DOC.md Section 4.3.1 exactly: 9 columns (`Date`, `Time`, `Day`, `Station`, `Code`, `Min Delay`, `Min Gap`, `Bound`, `Line`) with correct types and nullability
- [ ] Bike Share contract matches DESIGN-DOC.md Section 4.3.2 exactly: 10 columns with correct types and nullability
- [ ] Weather contract matches DESIGN-DOC.md Section 4.3.3 exactly: 5 key columns with correct types and nullability (additional Environment Canada columns are permitted and ignored)
- [ ] TTC Bus and TTC Streetcar contracts define their expected column structures (Bus includes `Route`, `Direction`, `Location`; Streetcar includes `Route`, `Direction`, `Location`)
- [ ] Module-level constant `CONTRACTS: dict[str, SchemaContract]` maps dataset names to their contracts
- [ ] `mypy --strict scripts/contracts.py` passes with zero errors
- [ ] `ruff check scripts/contracts.py && ruff format --check scripts/contracts.py` passes

**Technical Notes**: TTC Bus and Streetcar schemas differ slightly from Subway (Route instead of Line, Location instead of Station). Verify actual column names by inspecting sample files from the 2023 and 2024 releases. Weather CSVs from Environment Canada contain 20+ columns; the contract should define the 5 required columns and allow additional columns to pass through.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Tests pass locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S002: Implement XLSX-to-CSV conversion module

**Description**: Build a streaming XLSX-to-CSV converter that processes TTC delay files (which arrive as XLSX) into UTF-8 CSV format for downstream validation and loading.

**Acceptance Criteria**:

- [ ] File `scripts/transform.py` exists and defines function `convert_xlsx_to_csv(xlsx_path: Path, csv_path: Path, sheet_name: str | None = None) -> TransformResult`
- [ ] `TransformResult` dataclass contains: `input_path`, `output_path`, `row_count`, `column_count`, `elapsed_seconds`
- [ ] Function uses `openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)` for memory-efficient reading
- [ ] Function writes output as UTF-8 CSV with `csv.writer` using `quoting=csv.QUOTE_MINIMAL`
- [ ] If `sheet_name` is `None`, function reads the first (active) worksheet
- [ ] If `sheet_name` is provided but does not exist in the workbook, function raises `TransformError` listing available sheet names
- [ ] Function creates parent directories of `csv_path` with `Path.mkdir(parents=True, exist_ok=True)`
- [ ] Function `batch_convert(source_dir: Path, output_dir: Path, file_pattern: str = "*.xlsx") -> list[TransformResult]` processes all matching XLSX files in a directory tree, preserving subdirectory structure
- [ ] `mypy --strict scripts/transform.py` passes with zero errors
- [ ] `ruff check scripts/transform.py && ruff format --check scripts/transform.py` passes

**Technical Notes**: TTC XLSX files use the default sheet name (typically "Sheet1" or the dataset name). Use `wb.active` when `sheet_name` is None. Handle `openpyxl` returning `None` for empty cells by writing empty string to CSV. Close workbook explicitly after reading to release file handles.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Tests pass locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S003: Implement schema validation engine with fail-fast behavior

**Description**: Build the core validation engine that checks CSV files against schema contracts and raises `SchemaValidationError` on the first deviation.

**Acceptance Criteria**:

- [ ] File `scripts/validate.py` exists and defines function `validate_file(csv_path: Path, contract: SchemaContract) -> ValidationResult`
- [ ] `ValidationResult` dataclass contains: `file_path`, `dataset_name`, `is_valid` (bool), `row_count`, `column_count`, `errors` (list of `ValidationError`)
- [ ] `SchemaValidationError` exception class contains: `file_path`, `expected_columns` (list of str), `actual_columns` (list of str), `mismatches` (list of str describing each deviation)
- [ ] Structural validation checks: all required columns from the contract exist in the CSV header (case-insensitive comparison)
- [ ] Structural validation identifies: missing columns, unexpected extra columns (logged as warning, not blocking), column name case mismatches
- [ ] Type validation samples the first 1,000 data rows and verifies: DATE columns parse as dates, INTEGER columns contain only digits (or empty for nullable), DECIMAL columns parse as float, TIMESTAMP columns parse as timestamps
- [ ] On first validation failure, function raises `SchemaValidationError` with the file path, expected schema, actual schema, and list of specific mismatches
- [ ] Function `validate_dataset(dataset_dir: Path, contract: SchemaContract) -> list[ValidationResult]` validates all CSV files in a directory tree against a single contract, failing fast on first invalid file
- [ ] `mypy --strict scripts/validate.py` passes with zero errors
- [ ] `ruff check scripts/validate.py && ruff format --check scripts/validate.py` passes

**Technical Notes**: Use `csv.DictReader` for header extraction. For type inference sampling, read 1,000 rows and apply regex-based type checks (`r'^\d{4}-\d{2}-\d{2}$'` for DATE, `r'^-?\d+$'` for INTEGER). Allow empty strings in nullable columns. Log validation progress to stderr for observability during long runs.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Tests pass locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S004: Implement encoding detection and normalization

**Description**: Build an encoding detection and normalization utility that converts source files with inconsistent encodings to UTF-8 before validation.

**Acceptance Criteria**:

- [ ] File `scripts/transform.py` defines function `normalize_encoding(input_path: Path, output_path: Path | None = None) -> EncodingResult`
- [ ] `EncodingResult` dataclass contains: `input_path`, `output_path`, `detected_encoding`, `confidence` (float 0-1), `byte_count`, `had_bom` (bool)
- [ ] Function uses `charset-normalizer` library to detect source encoding with minimum confidence threshold of 0.7
- [ ] If detected encoding is already UTF-8 with confidence >= 0.7, function copies file unchanged (or returns early if `output_path` is `None`)
- [ ] If encoding is not UTF-8, function reads with detected encoding and writes as UTF-8 to `output_path` (or overwrites `input_path` if `output_path` is `None`)
- [ ] Function strips UTF-8 BOM (`\xef\xbb\xbf`) and UTF-16 BOM if present at file start
- [ ] If detection confidence is below 0.7, function raises `EncodingError` with the file path and top 3 encoding candidates
- [ ] `mypy --strict scripts/transform.py` passes with zero errors

**Technical Notes**: Install `charset-normalizer` (not `chardet` — it is unmaintained). Read files in binary mode for detection, then re-read with the detected encoding for transcoding. Process files in 1MB chunks to limit memory usage on large CSVs.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Tests pass locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S007: Implement ZIP archive extraction for Bike Share datasets

**Description**: Build a ZIP extraction function that unpacks Bike Share ridership archives into individual monthly CSV files, bridging the gap between E-301's raw ZIP downloads and the schema validation pipeline.

**Acceptance Criteria**:

- [ ] File `scripts/transform.py` defines function `extract_zip(zip_path: Path, output_dir: Path) -> list[ExtractResult]`
- [ ] `ExtractResult` dataclass contains: `zip_path` (source archive), `extracted_path` (output CSV path), `original_name` (name inside archive), `byte_size` (extracted file size), `skipped` (bool, True if file already existed with matching size)
- [ ] Function discovers CSV members dynamically via `zipfile.ZipFile.infolist()` and filters to `.csv` entries only, ignoring `__MACOSX/` metadata directories and non-CSV files
- [ ] Function extracts CSVs to `output_dir/<filename>` with flattened paths (strips internal subdirectory prefixes such as `bikeshare-ridership-2023/`)
- [ ] Extraction is idempotent: if a target CSV already exists and matches the archive member's uncompressed size, extraction is skipped and logged as `SKIPPED`
- [ ] Function validates the ZIP archive integrity via `zipfile.ZipFile.testzip()` before extraction; raises `TransformError` if the archive is corrupt
- [ ] Function `batch_extract_zips(source_dir: Path, output_dir: Path, file_pattern: str = "*.zip") -> list[ExtractResult]` processes all matching ZIP files in a directory tree, preserving the `<source>/<year>/` subdirectory structure in the output
- [ ] `mypy --strict scripts/transform.py` passes with zero errors
- [ ] `ruff check scripts/transform.py && ruff format --check scripts/transform.py` passes

**Technical Notes**: Bike Share ZIP archives contain a subdirectory matching the archive name (e.g., `bikeshare-ridership-2023/Bike share ridership 2023-01.csv`). Strip this prefix during extraction to produce flat CSVs at the year level. Use `zipfile.Path` or `PurePosixPath` to handle cross-platform path separators inside archives. Each archive contains 12 monthly CSVs ranging from 23 MB to 96 MB uncompressed.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Tests pass locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S005: Add comprehensive test suite for validation and transformation

**Description**: Build pytest test suites covering schema validation, XLSX conversion, and encoding normalization with fixture files and edge cases.

**Acceptance Criteria**:

- [ ] File `tests/test_validate.py` exists with tests covering: valid CSV passes validation, missing required column raises `SchemaValidationError`, extra column logs warning but passes, type mismatch in sampled rows raises `SchemaValidationError`, nullable column with empty values passes, case-insensitive column matching works
- [ ] File `tests/test_transform.py` exists with tests covering: XLSX-to-CSV produces correct row/column count, missing worksheet raises `TransformError`, encoding detection identifies UTF-8 correctly, Windows-1252 file is transcoded to UTF-8, BOM is stripped from output, ZIP extraction produces correct CSV files, ZIP extraction skips existing files (idempotency), corrupt ZIP raises `TransformError`, ZIP extraction strips internal subdirectory prefixes
- [ ] Test fixtures exist at `tests/fixtures/`: `valid_subway_delays.csv` (10 rows matching TTC subway contract), `invalid_missing_column.csv` (subway data with "Station" column removed), `valid_delays.xlsx` (small XLSX with 10 rows), `windows_1252.csv` (file with Windows-1252 encoding)
- [ ] All tests use `tmp_path` fixture for filesystem operations — no writes to project directories
- [ ] `pytest tests/test_validate.py tests/test_transform.py -v` passes with zero failures
- [ ] `mypy --strict tests/test_validate.py tests/test_transform.py` passes
- [ ] `ruff check tests/ && ruff format --check tests/` passes on test files

**Technical Notes**: Generate XLSX fixtures programmatically in a `conftest.py` using `openpyxl` to avoid committing binary files. For encoding fixtures, encode a known UTF-8 string as Windows-1252 bytes and write to `tmp_path`.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Tests pass locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S006: Validate all downloaded source files against contracts

**Description**: Execute the validation pipeline against the full set of downloaded files from E-301, confirming all files pass schema contracts before proceeding to Snowflake loading.

**Acceptance Criteria**:

- [ ] Running `python scripts/validate.py --all --source-dir data/raw --output-dir data/validated` processes all downloaded files
- [ ] All TTC XLSX files are converted to CSV via `transform.py` before validation
- [ ] All Bike Share ZIP archives are extracted to individual monthly CSVs via `transform.py` before validation
- [ ] All converted CSVs, extracted Bike Share CSVs, and weather CSVs pass schema validation against their respective contracts
- [ ] `data/validated/` directory contains only validated, UTF-8 encoded CSV files organized as `data/validated/<source>/<year>/<filename>.csv`
- [ ] Validation summary logged to stdout reports: total files processed, files passed, files failed (must be zero), total rows across all files
- [ ] If any file fails validation, the process exits with code 1 and logs the `SchemaValidationError` details including file path and specific mismatches
- [ ] Re-running validation on already-validated files in `data/validated/` produces identical results (idempotent)

**Technical Notes**: The CLI entry point uses `argparse` with `--all`, `--dataset <name>`, `--source-dir <path>`, and `--output-dir <path>` flags. Wire up the encoding normalization step between XLSX conversion and schema validation. Log per-file progress to stderr for observability.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Tests pass locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

## Exit Criteria

This epic is complete when:

- [ ] `scripts/validate.py`, `scripts/transform.py`, and `scripts/contracts.py` exist, are type-annotated, and pass `mypy --strict`
- [ ] Schema contracts for all five datasets match DESIGN-DOC.md Section 4.3 specifications
- [ ] All downloaded source files pass schema validation with zero failures
- [ ] XLSX files are converted to UTF-8 CSV format
- [ ] ZIP archives are extracted to individual CSV files
- [ ] `SchemaValidationError` is raised and ingestion aborts on any schema deviation (fail-fast verified by test)
- [ ] `pytest tests/test_validate.py tests/test_transform.py` passes with zero failures
- [ ] `ruff check` and `ruff format` pass on all Python files
- [ ] Python code generated via `python-writing` skill

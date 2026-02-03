# Snowflake Loading & Pipeline Orchestration

| Field        | Value           |
| ------------ | --------------- |
| Epic ID      | E-303           |
| Phase        | PH-03           |
| Owner        | @dinesh-git17   |
| Status       | Draft           |
| Dependencies | [E-301, E-302]  |
| Created      | 2026-02-03      |

## Context

With source files downloaded (E-301) and validated against schema contracts (E-302), the final stage of PH-03 loads data into the Snowflake RAW schema. DESIGN-DOC.md mandates atomic transaction semantics: the Snowflake warehouse must never contain partial or corrupt data from a failed ingestion run. Loading uses Snowflake's `COPY INTO` for bulk ingestion and `MERGE` for idempotent upserts, ensuring repeated executions produce identical results. This epic also builds the top-level orchestrator (`ingest.py`) that sequences download → validate → transform → load as a single atomic pipeline, and executes the initial load populating all five RAW schema tables with 2019-present data. The exit criterion for PH-03 as a whole — RAW schema tables populated with row counts validated against source files within 1% tolerance — is verified in this epic.

## Scope

### In Scope

- Python 3.12 `scripts/load.py` module implementing Snowflake `COPY INTO` via internal stage and `MERGE` for idempotent loading
- Python 3.12 `scripts/ingest.py` orchestrator sequencing: download → transform → validate → load with atomic transaction semantics
- Snowflake internal stage creation (`@TORONTO_MOBILITY.RAW.INGESTION_STAGE`) for file upload
- `PUT` command execution to upload validated CSVs to internal stage
- `COPY INTO` execution for bulk loading from stage to RAW tables
- `MERGE` statement implementation using natural keys for idempotent upsert behavior
- Atomic transaction control: `BEGIN` / `COMMIT` / `ROLLBACK` wrapping the full load sequence per dataset
- Initial load execution for all five datasets (TTC subway, bus, streetcar, Bike Share, weather) spanning 2019-present
- Row count validation: `SELECT COUNT(*)` on each RAW table compared against source file row counts with 1% tolerance
- Snowflake Python connector (`snowflake-connector-python`) integration with LOADER_ROLE credentials
- Unit and integration tests via `pytest`
- Type-annotated modules passing `mypy --strict`
- Linting compliance with `ruff check` and `ruff format`

### Out of Scope

- Snowflake object creation (database, schemas, warehouses, roles — completed in PH-02)
- dbt transformations (staging, intermediate, marts — covered by PH-05, PH-06, PH-07)
- Incremental loading strategies (full reload is acceptable for v1 data volumes per DESIGN-DOC.md Decision D8)
- Orchestration scheduling (Airflow/Dagster — explicitly out of scope per DESIGN-DOC.md Non-Goal NG4)
- Data quality validation beyond row counts (covered by PH-08)

## Technical Approach

### Architecture Decisions

- **Internal stage over external stage**: Use a Snowflake internal named stage (`@RAW.INGESTION_STAGE`) rather than an S3/GCS external stage. Internal stages eliminate cloud storage dependencies, simplify credential management for a portfolio project, and provide sufficient throughput for the 2-3 GB total data volume. Per DESIGN-DOC.md Section 5.1, the pipeline is batch-only.
- **`COPY INTO` with `MERGE` for idempotency**: Execute `COPY INTO` to a temporary table, then `MERGE` from temporary to target using natural keys. This prevents duplicate rows on repeated runs. Natural keys are defined in DESIGN-DOC.md Section 6.4: TTC subway uses `[date, time, station, line, delay_code, min_delay]`; Bike Share uses `[trip_id]`; weather uses `[date]`.
- **Per-dataset atomic transactions**: Each dataset loads within a single Snowflake transaction. If any `COPY INTO` or `MERGE` fails, the transaction rolls back and no rows from that dataset persist. Cross-dataset atomicity is not required — partial completion (e.g., subway loaded, bus failed) is acceptable since datasets are independent.
- **`snowflake-connector-python` over SQLAlchemy**: Use the native Snowflake connector directly for `PUT`, `COPY INTO`, and `MERGE` operations. SQLAlchemy adds unnecessary abstraction for bulk loading operations and does not support `PUT` commands natively.
- **LOADER_ROLE for all load operations**: Per DESIGN-DOC.md Section 10.1, the `LOADER_ROLE` owns RAW schema objects. All Snowflake connections in `load.py` authenticate as `LOADER_SVC` with `LOADER_ROLE`.

### Integration Points

- Upstream: Reads validated CSV files from `data/validated/<source>/<year>/` produced by E-302
- Snowflake: Connects to `TORONTO_MOBILITY.RAW` schema via `snowflake-connector-python` using `LOADER_ROLE` credentials
- Snowflake internal stage: `@TORONTO_MOBILITY.RAW.INGESTION_STAGE`
- Target RAW tables: `TTC_SUBWAY_DELAYS`, `TTC_BUS_DELAYS`, `TTC_STREETCAR_DELAYS`, `BIKE_SHARE_TRIPS`, `WEATHER_DAILY` (per DESIGN-DOC.md Section 5.3)
- Credential source: Environment variables (`SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`) or `~/.snowflake/connections.toml`

### Repository Areas

- `scripts/load.py` — Snowflake loading module
- `scripts/ingest.py` — top-level pipeline orchestrator
- `tests/test_load.py` — loading test suite
- `tests/test_ingest.py` — orchestration test suite
- `pyproject.toml` — dependency declaration (`snowflake-connector-python`)

### Risks

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Snowflake trial credentials expire during initial load execution | Low | High | Verify trial expiration date before starting; complete initial load within a single session; store credentials in environment variables, not code |
| `PUT` upload of large Bike Share CSV files (500MB+) times out or fails mid-transfer | Medium | Medium | Upload files in per-year batches rather than all at once; implement retry logic on `PUT` failures with exponential backoff |
| `MERGE` natural key collisions produce incorrect deduplication for TTC delays with identical timestamp/station/code combinations | Medium | High | Natural key includes `min_delay` to disambiguate per DESIGN-DOC.md Section 6.4; add post-load row count validation to detect unexpected deduplication |
| Row count tolerance check fails due to filtered rows (Bike Share trips < 60 seconds) | Low | Medium | Apply the same 60-second filter to source file row counts before comparison; document the filter in validation output |
| Snowflake LOADER_ROLE lacks required permissions on internal stage | Low | Medium | Verify grants include `CREATE STAGE` and `USAGE` on RAW schema before first load; document grant verification in S001 |

## Stories

| ID | Story | Points | Dependencies | Status |
| --- | --- | --- | --- | --- |
| S001 | Create Snowflake internal stage and verify LOADER_ROLE permissions | 2 | None | Draft |
| S002 | Implement Snowflake connection manager with credential resolution | 3 | None | Draft |
| S003 | Implement CSV upload via PUT and COPY INTO bulk loading | 5 | S001, S002 | Draft |
| S004 | Implement MERGE-based idempotent upsert with natural keys | 5 | S003 | Draft |
| S005 | Build pipeline orchestrator with atomic transaction control | 5 | S003, S004, E-301.S002, E-302.S003 | Draft |
| S006 | Execute initial load and validate row counts for all datasets | 5 | S005 | Draft |
| S007 | Add comprehensive test suite for loading and orchestration | 5 | S003, S004, S005 | Draft |

---

### S001: Create Snowflake internal stage and verify LOADER_ROLE permissions

**Description**: Create the named internal stage in Snowflake RAW schema and verify that LOADER_ROLE has all required permissions for PUT, COPY INTO, and MERGE operations.

**Acceptance Criteria**:

- [ ] SQL script `setup/create_ingestion_stage.sql` exists and creates stage: `CREATE STAGE IF NOT EXISTS TORONTO_MOBILITY.RAW.INGESTION_STAGE FILE_FORMAT = (TYPE = 'CSV' FIELD_OPTIONALLY_ENCLOSED_BY = '"' SKIP_HEADER = 1 NULL_IF = ('', 'NULL', 'null') COMPRESSION = 'AUTO')`
- [ ] Stage file format specifies: `FIELD_DELIMITER = ','`, `RECORD_DELIMITER = '\n'`, `ENCODING = 'UTF8'`
- [ ] Script grants `USAGE` on the stage to `LOADER_ROLE`: `GRANT USAGE ON STAGE TORONTO_MOBILITY.RAW.INGESTION_STAGE TO ROLE LOADER_ROLE`
- [ ] Verification query confirms LOADER_ROLE can execute `LIST @TORONTO_MOBILITY.RAW.INGESTION_STAGE` without permission errors
- [ ] Verification query confirms LOADER_ROLE can execute `PUT` to the stage (upload a 1-row test CSV, then `REMOVE` it)
- [ ] Verification query confirms all five RAW tables exist: `TTC_SUBWAY_DELAYS`, `TTC_BUS_DELAYS`, `TTC_STREETCAR_DELAYS`, `BIKE_SHARE_TRIPS`, `WEATHER_DAILY`

**Technical Notes**: Execute this script via `snowsql` or the Snowflake web UI using SYSADMIN role. The file format definition is embedded in the stage to avoid separate file format object management. `FIELD_OPTIONALLY_ENCLOSED_BY` handles quoted fields in CSV exports.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Tests pass locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S002: Implement Snowflake connection manager with credential resolution

**Description**: Build a connection manager that resolves Snowflake credentials from environment variables or configuration file and returns authenticated cursor objects scoped to LOADER_ROLE.

**Acceptance Criteria**:

- [ ] File `scripts/load.py` defines class `SnowflakeConnectionManager` with method `connect() -> snowflake.connector.SnowflakeConnection`
- [ ] Credential resolution order: (1) environment variables `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`, (2) `~/.snowflake/connections.toml` file with `[loader]` section
- [ ] Connection parameters include: `role='LOADER_ROLE'`, `warehouse='TRANSFORM_WH'`, `database='TORONTO_MOBILITY'`, `schema='RAW'`
- [ ] Context manager protocol (`__enter__` / `__exit__`) is implemented, ensuring `connection.close()` on exit
- [ ] On connection failure, raises `LoadError` with the Snowflake error code and message (credential values are never included in the error message)
- [ ] `mypy --strict scripts/load.py` passes with zero errors
- [ ] `ruff check scripts/load.py && ruff format --check scripts/load.py` passes

**Technical Notes**: Use `snowflake.connector.connect()` directly. Do not use SQLAlchemy. Set `client_session_keep_alive=True` to prevent session timeout during long upload operations. Set `login_timeout=30` and `network_timeout=60`.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Tests pass locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S003: Implement CSV upload via PUT and COPY INTO bulk loading

**Description**: Build functions that upload validated CSV files to the Snowflake internal stage via PUT and execute COPY INTO to load data into RAW tables.

**Acceptance Criteria**:

- [ ] Function `upload_to_stage(connection: SnowflakeConnection, local_path: Path, stage_path: str) -> StageUploadResult` exists in `scripts/load.py`
- [ ] `StageUploadResult` dataclass contains: `local_path`, `stage_path`, `status` (enum: `UPLOADED`, `SKIPPED`), `source_size_bytes`, `dest_size_bytes`, `elapsed_seconds`
- [ ] Function executes `PUT file://<local_path> @TORONTO_MOBILITY.RAW.INGESTION_STAGE/<stage_path> AUTO_COMPRESS=TRUE OVERWRITE=TRUE`
- [ ] Function `copy_into_table(connection: SnowflakeConnection, table_name: str, stage_path: str, column_mapping: list[str]) -> CopyResult` exists in `scripts/load.py`
- [ ] `CopyResult` dataclass contains: `table_name`, `rows_loaded`, `rows_parsed`, `errors_seen`, `first_error` (str or None), `elapsed_seconds`
- [ ] COPY INTO statement uses: `ON_ERROR = 'ABORT_STATEMENT'` to fail on first row-level error
- [ ] COPY INTO statement uses: `PURGE = FALSE` to retain staged files for debugging
- [ ] Function `copy_into_table` accepts a `column_mapping` parameter to handle column ordering differences between CSV headers and target table DDL
- [ ] On COPY INTO failure, function raises `LoadError` with the table name, file path, row number, and error message from Snowflake
- [ ] `mypy --strict scripts/load.py` passes with zero errors

**Technical Notes**: The `PUT` command is executed via cursor's `execute()` method. Use `cursor.fetchall()` after PUT to retrieve upload status. COPY INTO uses the stage file format defined in S001. For column mapping, use `COPY INTO ... (col1, col2, ...) FROM (SELECT $1, $2, ... FROM @stage/path)` syntax when CSV column order differs from table DDL.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Tests pass locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S004: Implement MERGE-based idempotent upsert with natural keys

**Description**: Build the MERGE logic that upserts data from a staging temporary table into the target RAW table using natural keys, ensuring repeated loads produce identical results.

**Acceptance Criteria**:

- [ ] Function `merge_into_table(connection: SnowflakeConnection, target_table: str, natural_keys: list[str], all_columns: list[str]) -> MergeResult` exists in `scripts/load.py`
- [ ] `MergeResult` dataclass contains: `target_table`, `rows_inserted`, `rows_updated`, `elapsed_seconds`
- [ ] Function creates a temporary table `{target_table}_STAGING` with identical DDL to the target table
- [ ] Function executes COPY INTO the temporary table first, then MERGE from temporary to target
- [ ] MERGE ON clause joins on all columns specified in `natural_keys`
- [ ] WHEN MATCHED clause updates all non-key columns
- [ ] WHEN NOT MATCHED clause inserts all columns
- [ ] Function drops the temporary table after MERGE completes (in both success and failure paths)
- [ ] Natural key definitions per dataset match DESIGN-DOC.md Section 6.4: TTC subway `[DATE, TIME, STATION, LINE, CODE, MIN_DELAY]`, TTC bus `[DATE, TIME, ROUTE, DIRECTION, DELAY_CODE, MIN_DELAY]`, TTC streetcar `[DATE, TIME, ROUTE, DIRECTION, DELAY_CODE, MIN_DELAY]`, Bike Share `[TRIP_ID]`, weather `[DATE_TIME]`
- [ ] Running the same load twice produces identical row counts in the target table (verified by test)
- [ ] `mypy --strict scripts/load.py` passes with zero errors

**Technical Notes**: Use `CREATE TEMPORARY TABLE {target}_STAGING LIKE {target}` for DDL cloning. The temporary table is session-scoped and auto-drops on connection close, but explicit `DROP` in a `finally` block ensures cleanup on exceptions. For the MERGE statement, dynamically construct the SQL from the `natural_keys` and `all_columns` parameters using parameterized f-strings (column names only, no user input — SQL injection is not a concern for internal column names).

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Tests pass locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S005: Build pipeline orchestrator with atomic transaction control

**Description**: Build the top-level `ingest.py` script that sequences download, transform, validate, and load stages with per-dataset atomic transaction boundaries.

**Acceptance Criteria**:

- [ ] File `scripts/ingest.py` exists and defines function `run_pipeline(datasets: list[str] | None = None, skip_download: bool = False) -> PipelineResult`
- [ ] `PipelineResult` dataclass contains: `datasets_processed` (list of `DatasetResult`), `total_rows_loaded`, `total_elapsed_seconds`, `success` (bool)
- [ ] `DatasetResult` dataclass contains: `dataset_name`, `stage` (enum: `DOWNLOAD`, `TRANSFORM`, `VALIDATE`, `LOAD`), `rows_loaded`, `elapsed_seconds`, `status` (enum: `SUCCESS`, `FAILED`, `SKIPPED`)
- [ ] Pipeline sequence per dataset: (1) download via E-301 `download.py`, (2) transform XLSX→CSV via E-302 `transform.py`, (3) validate against schema contract via E-302 `validate.py`, (4) load into Snowflake via `load.py`
- [ ] Each dataset's load stage executes within a single Snowflake transaction: `connection.cursor().execute("BEGIN")` before COPY INTO / MERGE, `connection.commit()` on success, `connection.rollback()` on any exception
- [ ] If validation fails for a dataset (E-302 `SchemaValidationError`), that dataset is marked `FAILED` and subsequent datasets continue processing (fail-per-dataset, not fail-all)
- [ ] If load fails for a dataset (`LoadError`), the transaction rolls back, the dataset is marked `FAILED`, and subsequent datasets continue processing
- [ ] CLI entry point: `python scripts/ingest.py --all` runs all datasets; `python scripts/ingest.py --dataset ttc_subway_delays` runs a single dataset; `python scripts/ingest.py --all --skip-download` skips the download stage (for re-processing already-downloaded files)
- [ ] Pipeline exits with code 0 if all datasets succeed, code 1 if any dataset fails
- [ ] Execution summary is logged to stdout as structured output: dataset name, stage, status, rows, elapsed time
- [ ] `mypy --strict scripts/ingest.py` passes with zero errors
- [ ] `ruff check scripts/ingest.py && ruff format --check scripts/ingest.py` passes

**Technical Notes**: Use `argparse` for CLI parsing. Import functions from `download.py`, `transform.py`, `validate.py`, and `load.py` — do not duplicate logic. Wrap each dataset in a `try`/`except` block that catches `DownloadError`, `TransformError`, `SchemaValidationError`, and `LoadError`. Log to stderr for progress, stdout for final summary.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Tests pass locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S006: Execute initial load and validate row counts for all datasets

**Description**: Run the full ingestion pipeline against production data for 2019-present, load all five datasets into the Snowflake RAW schema, and validate row counts against source files within 1% tolerance.

**Acceptance Criteria**:

- [ ] Running `python scripts/ingest.py --all` completes with exit code 0 for all five datasets
- [ ] Snowflake table `TORONTO_MOBILITY.RAW.TTC_SUBWAY_DELAYS` contains rows and `SELECT COUNT(*)` matches source file row count within 1% tolerance (expected ~300K rows per DESIGN-DOC.md Section 4.1)
- [ ] Snowflake table `TORONTO_MOBILITY.RAW.TTC_BUS_DELAYS` contains rows and count matches source within 1% (expected ~1.2M rows)
- [ ] Snowflake table `TORONTO_MOBILITY.RAW.TTC_STREETCAR_DELAYS` contains rows and count matches source within 1% (expected ~300K rows)
- [ ] Snowflake table `TORONTO_MOBILITY.RAW.BIKE_SHARE_TRIPS` contains rows and count matches source within 1% (expected ~30M rows)
- [ ] Snowflake table `TORONTO_MOBILITY.RAW.WEATHER_DAILY` contains rows and count matches source within 1% (expected ~2,500 rows for 2019-2025)
- [ ] Row count validation script `scripts/validate_load.py` exists and executes: reads source file row counts from the download manifest, queries `SELECT COUNT(*)` from each RAW table, computes percentage difference, passes if all datasets are within 1%
- [ ] Running `python scripts/validate_load.py` exits with code 0 and prints a comparison table: dataset name, source rows, loaded rows, difference percentage
- [ ] Re-running `python scripts/ingest.py --all` produces identical row counts (idempotency verified via MERGE)
- [ ] `mypy --strict scripts/validate_load.py` passes with zero errors

**Technical Notes**: The 1% tolerance accounts for edge cases: Bike Share files occasionally contain duplicate trip IDs across quarterly files (MERGE deduplicates these), and Environment Canada CSVs sometimes include partial-month data at file boundaries. The validation script connects using LOADER_ROLE credentials. Log per-table results in a formatted table to stdout.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Tests pass locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S007: Add comprehensive test suite for loading and orchestration

**Description**: Build pytest test suites covering the Snowflake loading module and pipeline orchestrator with mocked Snowflake connections.

**Acceptance Criteria**:

- [ ] File `tests/test_load.py` exists with tests covering: connection manager credential resolution from environment variables, connection manager context manager closes connection on exit, `upload_to_stage` constructs correct PUT SQL, `copy_into_table` constructs correct COPY INTO SQL with ON_ERROR=ABORT_STATEMENT, `merge_into_table` constructs correct MERGE SQL with natural keys, `merge_into_table` drops temporary table in finally block, `LoadError` is raised on Snowflake error response
- [ ] File `tests/test_ingest.py` exists with tests covering: successful pipeline run returns PipelineResult with SUCCESS status, validation failure for one dataset does not block other datasets, load failure triggers transaction rollback, `--skip-download` flag skips download stage, CLI exits with code 1 when any dataset fails
- [ ] All Snowflake interactions are mocked using `unittest.mock.patch` on `snowflake.connector.connect` — no real Snowflake connections during test execution
- [ ] Tests verify SQL statements passed to `cursor.execute()` contain expected keywords (`PUT`, `COPY INTO`, `MERGE`, `BEGIN`, `COMMIT`, `ROLLBACK`)
- [ ] `pytest tests/test_load.py tests/test_ingest.py -v` passes with zero failures
- [ ] `mypy --strict tests/test_load.py tests/test_ingest.py` passes
- [ ] `ruff check tests/ && ruff format --check tests/` passes on test files

**Technical Notes**: Mock the Snowflake connector at the module level: `@patch('scripts.load.snowflake.connector.connect')`. Create mock cursor objects that return predefined results for `fetchall()` and `fetchone()`. For MERGE tests, verify the SQL contains both `WHEN MATCHED THEN UPDATE` and `WHEN NOT MATCHED THEN INSERT` clauses.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Tests pass locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

## Exit Criteria

This epic is complete when:

- [ ] `scripts/load.py` and `scripts/ingest.py` exist, are type-annotated, and pass `mypy --strict`
- [ ] Snowflake internal stage `@TORONTO_MOBILITY.RAW.INGESTION_STAGE` exists with correct file format and LOADER_ROLE permissions
- [ ] All five RAW schema tables are populated with 2019-present data
- [ ] Row counts for each table match source file counts within 1% tolerance
- [ ] MERGE-based loading is idempotent: re-running produces identical row counts
- [ ] Per-dataset atomic transactions prevent partial loads on failure
- [ ] `pytest tests/test_load.py tests/test_ingest.py` passes with zero failures
- [ ] `ruff check` and `ruff format` pass on all Python files in `scripts/` and `tests/`
- [ ] Python code generated via `python-writing` skill
- [ ] PH-03 exit criterion met: RAW schema tables populated with row counts validated against source files within 1% tolerance

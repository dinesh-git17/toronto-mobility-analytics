# Distribution & Anomaly Detection Tests

| Field        | Value                 |
| ------------ | --------------------- |
| Epic ID      | E-802                 |
| Phase        | PH-08                 |
| Owner        | @dinesh-git17         |
| Status       | Complete              |
| Dependencies | [E-701, E-702, E-801] |
| Created      | 2026-02-09            |

## Context

Schema tests (PH-07) enforce structural correctness — primary key uniqueness, foreign key referential integrity, and categorical value membership. Singular tests (E-801) enforce hard business rules — non-negativity, temporal validity, and duration reasonability. Neither provides statistical distribution validation or dynamic anomaly detection across runs. dbt_expectations (pinned at 0.10.4 in `packages.yml`) extends dbt's test vocabulary with distribution-aware assertions: column value range bounds and table row count thresholds. Elementary (pinned at 0.16.1 in `packages.yml`) provides runtime anomaly detection — comparing each run's data profile against a learned historical baseline to detect volume drift, freshness degradation, and schema mutations. DESIGN-DOC Section 7.7 mandates `expect_column_values_to_be_between` for `delay_minutes` (0-1440) and `trip_duration` bounds, and `expect_table_row_count_to_be_between` for all fact tables. DESIGN-DOC Section 9.5 mandates Elementary `volume_anomalies`, `freshness_anomalies`, and `schema_changes` on all mart models. These tests close the gap between static schema validation and production-grade data observability.

## Scope

### In Scope

- dbt_expectations `expect_column_values_to_be_between` test on `fct_transit_delays.delay_minutes` with `min_value: 0` and `max_value: 1440` (DESIGN-DOC Section 7.7)
- dbt_expectations `expect_column_values_to_be_between` test on `fct_bike_trips.duration_seconds` with `min_value: 60` and `max_value: 86400` (DESIGN-DOC Section 7.7, Section 8.3)
- dbt_expectations `expect_table_row_count_to_be_between` tests on `fct_transit_delays`, `fct_bike_trips`, and `fct_daily_mobility` with bounds calibrated to current data volumes (DESIGN-DOC Section 7.7)
- Elementary `volume_anomalies` test on all 7 mart models (4 dimensions + 3 facts)
- Elementary `freshness_anomalies` test on 3 mart models with timestamp or date columns: `dim_weather` (`weather_date`), `fct_transit_delays` (`incident_timestamp`), `fct_bike_trips` (`start_time`)
- Elementary `schema_changes` test on all 7 mart models
- Elementary baseline establishment via `dbt run --select elementary`
- Initial Elementary report generation via `edr report`

### Out of Scope

- Singular SQL business rule tests — complete in E-801
- Schema tests (`unique`, `not_null`, `relationships`, `accepted_values`) — complete in E-701 and E-702
- Elementary alerting integrations (Slack, email, PagerDuty) — deferred to PH-09
- Elementary dashboard hosting or external deployment
- Custom Elementary anomaly thresholds (default training period and detection settings are sufficient for baseline)
- CI pipeline modification for Elementary report generation — deferred to E-803 validation
- Modification of existing mart models or their materialization strategy

## Technical Approach

### Architecture Decisions

- **dbt_expectations tests added to existing `_mobility__models.yml`** — distribution tests on fact table columns belong in the same YAML file as the model's schema tests; this maintains a single source of truth for all tests on each model and avoids split-brain test configurations across multiple files
- **Row count bounds calibrated to 50% below and 200% above current volumes** — `fct_transit_delays` (237,446 rows): min=100000, max=500000; `fct_bike_trips` (21,795,223 rows): min=10000000, max=50000000; `fct_daily_mobility` (1,827 rows): min=1000, max=5000; these bounds detect catastrophic data loss (near-empty tables) and runaway duplication (2x+ expected volume) while accommodating legitimate growth from future data loads
- **Elementary tests configured at model level in YAML** — Elementary anomaly tests are added as model-level tests in `_core__models.yml` and `_mobility__models.yml` using the `elementary.*` test namespace; each test specifies the required `timestamp_column` parameter for time-series analysis
- **Freshness anomalies limited to models with native timestamp or date columns** — `dim_date` (static seed, no data arrival timestamp), `dim_station` (no timestamp column), `dim_ttc_delay_codes` (no timestamp column), and `fct_daily_mobility` (integer `date_key` only) are excluded from `freshness_anomalies`; `dim_weather` (`weather_date` DATE), `fct_transit_delays` (`incident_timestamp` TIMESTAMP_NTZ), and `fct_bike_trips` (`start_time` TIMESTAMP_NTZ) provide valid timestamp columns for freshness monitoring
- **Elementary baseline requires initial `dbt run --select elementary`** — Elementary materializes its own artifact tables (test results, run results, schema snapshots) on first execution; these tables serve as the historical baseline for subsequent anomaly detection; the baseline must be established before Elementary tests produce meaningful anomaly comparisons
- **`row_count` severity set to `warn`** — per DESIGN-DOC Section 8.3, row count stability tests are Warning-level; dbt_expectations `expect_table_row_count_to_be_between` tests use `config: {severity: warn}` to prevent build failures on moderate volume fluctuations while surfacing the deviation in test output

### Integration Points

- **Upstream mart models** — all 7 mart models from E-701 (`dim_date`, `dim_station`, `dim_weather`, `dim_ttc_delay_codes`) and E-702 (`fct_transit_delays`, `fct_bike_trips`, `fct_daily_mobility`) serve as test targets
- **dbt_expectations package** — `calogica/dbt_expectations` version 0.10.4 (pinned in `packages.yml`); provides `expect_column_values_to_be_between` and `expect_table_row_count_to_be_between` macros
- **Elementary package** — `elementary-data/elementary` version 0.16.1 (pinned in `packages.yml`); provides `volume_anomalies`, `freshness_anomalies`, and `schema_changes` test macros; requires `elementary-data` Python package for `edr report` CLI
- **`dbt_project.yml` flags** — `require_explicit_package_overrides_for_builtin_materializations: false` already configured for Elementary compatibility (set during PH-02)
- **Schema YAML files** — `models/marts/core/_core__models.yml` and `models/marts/mobility/_mobility__models.yml` — tests are appended to existing model definitions

### Repository Areas

- `models/marts/mobility/_mobility__models.yml` (modify — add dbt_expectations and Elementary tests)
- `models/marts/core/_core__models.yml` (modify — add Elementary tests)

### Risks

| Risk                                                                                                                                                                   | Likelihood | Impact | Mitigation                                                                                                                                                                                                                                                                             |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Elementary `volume_anomalies` produces false positives on first run due to insufficient historical baseline (single data point)                                        | High       | Low    | First run establishes baseline only — anomaly detection activates on subsequent runs; document this behavior in E-803 test strategy; Elementary defaults to 14-day training period, which requires multiple runs before triggering alerts                                              |
| `expect_table_row_count_to_be_between` bounds become stale as data grows beyond PH-08 calibration (e.g., 2026-2027 bike data added)                                    | Medium     | Medium | Bounds are intentionally generous (50% below to 200% above current volumes); document the calibration date and current volumes in YAML comments; recalibrate in PH-09 or when data volumes exceed upper bounds                                                                         |
| Elementary `freshness_anomalies` on `dim_weather` flags stale data because historical weather is immutable and no new data arrives until next ingestion cycle          | Medium     | Low    | Elementary `freshness_anomalies` on `dim_weather` will consistently report the most recent `weather_date`; since weather data loads are batch (not streaming), configure Elementary defaults to tolerate multi-day staleness; if false positives persist, downgrade to `warn` severity |
| `elementary-data` Python package installation conflicts with existing project dependencies (snowflake-connector-python, openpyxl)                                      | Low        | High   | Install `elementary-data` in the same virtual environment after verifying compatibility; `elementary-data` 0.16.1 supports Python 3.12 and snowflake-connector-python >=3.x; test installation before committing dependency changes                                                    |
| dbt_expectations `expect_column_values_to_be_between` on `fct_bike_trips.duration_seconds` overlaps with singular test `assert_bike_trips_reasonable_duration` (E-801) | Low        | Low    | Intentional overlap — the singular test uses `severity: warn` for values >= 86400; the dbt_expectations test enforces strict bounds (60-86400); both provide value: singular test is human-readable and debuggable, dbt_expectations test integrates with Elementary reporting         |

## Stories

| ID   | Story                                                             | Points | Dependencies | Status |
| ---- | ----------------------------------------------------------------- | ------ | ------------ | ------ |
| S001 | Add dbt_expectations value range tests for delay and trip columns | 3      | None         | Complete |
| S002 | Add dbt_expectations row count bounds for all fact tables         | 3      | None         | Complete |
| S003 | Configure Elementary anomaly detection on core dimension models   | 5      | None         | Complete |
| S004 | Configure Elementary anomaly detection on mobility fact models    | 5      | None         | Complete |
| S005 | Establish Elementary baseline and generate initial report         | 5      | S003, S004   | Complete |

---

### S001: Add dbt_expectations Value Range Tests for Delay and Trip Columns

**Description**: Add `dbt_expectations.expect_column_values_to_be_between` tests to `_mobility__models.yml` for `fct_transit_delays.delay_minutes` (0-1440) and `fct_bike_trips.duration_seconds` (60-86400), enforcing the value distribution bounds specified in DESIGN-DOC Section 7.7.

**Acceptance Criteria**:

- [ ] `_mobility__models.yml` contains `dbt_expectations.expect_column_values_to_be_between` test on `fct_transit_delays.delay_minutes` with `min_value: 0` and `max_value: 1440`
- [ ] `_mobility__models.yml` contains `dbt_expectations.expect_column_values_to_be_between` test on `fct_bike_trips.duration_seconds` with `min_value: 60` and `max_value: 86400`
- [ ] Both tests use default severity (`error`) — values outside these bounds indicate data corruption, not natural variation
- [ ] `dbt test --select fct_transit_delays` passes with the new test included
- [ ] `dbt test --select fct_bike_trips` passes with the new test included
- [ ] `dbt parse` succeeds with zero errors after YAML modifications

**Technical Notes**: The `delay_minutes` range of 0-1440 represents zero to 24 hours of delay — the maximum plausible single-incident delay for TTC operations. The `duration_seconds` range of 60-86400 represents 1 minute to 24 hours — the lower bound is enforced by the staging filter (DESIGN-DOC Decision D9), and the upper bound matches the reasonability threshold from DESIGN-DOC Section 8.3. The dbt_expectations macro handles NULL values by default (NULLs do not violate the between constraint).

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `dbt test --select fct_transit_delays fct_bike_trips` passes locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S002: Add dbt_expectations Row Count Bounds for All Fact Tables

**Description**: Add `dbt_expectations.expect_table_row_count_to_be_between` tests to `_mobility__models.yml` for all three fact tables with bounds calibrated to detect catastrophic data loss and runaway duplication.

**Acceptance Criteria**:

- [ ] `_mobility__models.yml` contains `dbt_expectations.expect_table_row_count_to_be_between` test on `fct_transit_delays` with `min_value: 100000` and `max_value: 500000`
- [ ] `_mobility__models.yml` contains `dbt_expectations.expect_table_row_count_to_be_between` test on `fct_bike_trips` with `min_value: 10000000` and `max_value: 50000000`
- [ ] `_mobility__models.yml` contains `dbt_expectations.expect_table_row_count_to_be_between` test on `fct_daily_mobility` with `min_value: 1000` and `max_value: 5000`
- [ ] All three tests include `config: {severity: warn}` — row count bounds are Warning-level per DESIGN-DOC Section 8.3
- [ ] Each test includes a YAML comment documenting the calibration date (2026-02-09) and current row count
- [ ] `dbt test --select fct_transit_delays fct_bike_trips fct_daily_mobility` passes with the new tests included
- [ ] `dbt parse` succeeds with zero errors after YAML modifications

**Technical Notes**: The `expect_table_row_count_to_be_between` macro executes a `COUNT(*)` against the target model and fails if the result falls outside the specified bounds. Bounds are intentionally wide: lower bounds at ~42-50% of current volumes (catches empty or near-empty tables), upper bounds at ~210-270% of current volumes (catches duplicate-load scenarios). Row counts per E-702: `fct_transit_delays` = 237,446; `fct_bike_trips` = 21,795,223; `fct_daily_mobility` = 1,827.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `dbt test --select fct_transit_delays fct_bike_trips fct_daily_mobility` passes locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S003: Configure Elementary Anomaly Detection on Core Dimension Models

**Description**: Add Elementary `volume_anomalies`, `freshness_anomalies` (where applicable), and `schema_changes` tests to `_core__models.yml` for all 4 dimension models, enabling dynamic anomaly detection on the core analytical layer.

**Acceptance Criteria**:

- [ ] `_core__models.yml` contains `elementary.volume_anomalies` test on `dim_date`, `dim_station`, `dim_weather`, and `dim_ttc_delay_codes` (4 tests total)
- [ ] `_core__models.yml` contains `elementary.freshness_anomalies` test on `dim_weather` only, with `timestamp_column: weather_date` — the only core dimension with a date/timestamp column suitable for freshness monitoring
- [ ] `_core__models.yml` does NOT contain `elementary.freshness_anomalies` on `dim_date` (static seed-derived), `dim_station` (no timestamp column), or `dim_ttc_delay_codes` (no timestamp column)
- [ ] `_core__models.yml` contains `elementary.schema_changes` test on `dim_date`, `dim_station`, `dim_weather`, and `dim_ttc_delay_codes` (4 tests total)
- [ ] Total Elementary tests added to core dimensions: 9 (4 volume + 1 freshness + 4 schema)
- [ ] `dbt parse` succeeds with zero errors after YAML modifications
- [ ] All Elementary tests appear in `dbt ls --select test_type:generic --resource-type test` output filtered to core models

**Technical Notes**: Elementary tests are added as model-level tests in the YAML schema file, not as column-level tests. The `volume_anomalies` test compares the current row count against a learned historical distribution. The `freshness_anomalies` test monitors the maximum value of the specified `timestamp_column` and alerts if data appears stale relative to historical patterns. The `schema_changes` test captures column additions, removals, and type changes between runs. Elementary tests require the Elementary artifact tables to exist (created via `dbt run --select elementary` in S005). Until the baseline is established, these tests will pass without performing anomaly detection.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `dbt parse` passes locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S004: Configure Elementary Anomaly Detection on Mobility Fact Models

**Description**: Add Elementary `volume_anomalies`, `freshness_anomalies` (where applicable), and `schema_changes` tests to `_mobility__models.yml` for all 3 fact models, enabling dynamic anomaly detection on the primary analytical surfaces.

**Acceptance Criteria**:

- [ ] `_mobility__models.yml` contains `elementary.volume_anomalies` test on `fct_transit_delays`, `fct_bike_trips`, and `fct_daily_mobility` (3 tests total)
- [ ] `_mobility__models.yml` contains `elementary.freshness_anomalies` test on `fct_transit_delays` with `timestamp_column: incident_timestamp` and `fct_bike_trips` with `timestamp_column: start_time` (2 tests total)
- [ ] `_mobility__models.yml` does NOT contain `elementary.freshness_anomalies` on `fct_daily_mobility` — `date_key` is an integer (YYYYMMDD), not a timestamp/date column
- [ ] `_mobility__models.yml` contains `elementary.schema_changes` test on `fct_transit_delays`, `fct_bike_trips`, and `fct_daily_mobility` (3 tests total)
- [ ] Total Elementary tests added to mobility facts: 8 (3 volume + 2 freshness + 3 schema)
- [ ] `dbt parse` succeeds with zero errors after YAML modifications
- [ ] All Elementary tests appear in `dbt ls --select test_type:generic --resource-type test` output filtered to mobility models

**Technical Notes**: The `fct_bike_trips` table (21.8M rows) is the largest model in the project. Elementary `volume_anomalies` on this table may require additional query time for the initial baseline count. The `incident_timestamp` column in `fct_transit_delays` and `start_time` column in `fct_bike_trips` provide natural freshness indicators — if no new records appear with recent timestamps, `freshness_anomalies` will flag the staleness. `fct_daily_mobility` uses an integer `date_key` (YYYYMMDD) as its grain — this is not compatible with Elementary's `timestamp_column` requirement for `freshness_anomalies`.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `dbt parse` passes locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S005: Establish Elementary Baseline and Generate Initial Report

**Description**: Execute the Elementary materialization to create artifact tables, run all Elementary tests to establish the anomaly detection baseline, and generate the initial Elementary HTML report via `edr report`.

**Acceptance Criteria**:

- [ ] `pip install elementary-data` succeeds in the project virtual environment without dependency conflicts
- [ ] `dbt run --select elementary` succeeds and creates Elementary artifact tables in the target database
- [ ] `dbt test --select elementary` executes all 17 Elementary tests (9 core + 8 mobility) without runtime errors
- [ ] Elementary tests report PASS on initial run (no anomalies expected on first baseline establishment)
- [ ] `edr report` generates an HTML report file
- [ ] The generated report includes all 7 mart models with their configured anomaly tests visible
- [ ] The report renders without errors when opened in a browser

**Technical Notes**: Elementary's anomaly detection requires a historical baseline to function. The first `dbt run --select elementary` creates the baseline artifact tables. The first `dbt test` run records initial metrics (row counts, freshness timestamps, column schemas) but does not flag anomalies — there is no historical data to compare against. Anomaly detection activates on the second and subsequent runs as Elementary accumulates historical data points. The `edr report` command requires the `elementary-data` Python package (separate from the dbt package). The `elementary-data` package version should match the dbt package version (0.16.1) for compatibility. The `--env ci` flag is available for CI integration but not required for local baseline establishment.

**Definition of Done**:

- [ ] Elementary artifact tables created in target database
- [ ] All 17 Elementary tests execute without runtime errors
- [ ] `edr report` generates a valid HTML report
- [ ] PR opened with linked issue
- [ ] CI checks green

## Exit Criteria

This epic is complete when:

- [ ] 2 dbt_expectations `expect_column_values_to_be_between` tests pass on `fct_transit_delays.delay_minutes` (0-1440) and `fct_bike_trips.duration_seconds` (60-86400)
- [ ] 3 dbt_expectations `expect_table_row_count_to_be_between` tests pass on all fact tables with calibrated bounds
- [ ] 17 Elementary anomaly tests configured across all 7 mart models (7 volume + 3 freshness + 7 schema)
- [ ] Elementary baseline established via `dbt run --select elementary`
- [ ] `edr report` generates an HTML report with all 7 mart models visible
- [ ] `dbt parse` succeeds with zero errors on modified YAML files
- [ ] All new tests execute without runtime errors as part of `dbt test`

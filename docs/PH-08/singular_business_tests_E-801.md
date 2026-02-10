# Singular Business Rule Tests

| Field        | Value          |
| ------------ | -------------- |
| Epic ID      | E-801          |
| Phase        | PH-08          |
| Owner        | @dinesh-git17  |
| Status       | Complete       |
| Dependencies | [E-701, E-702] |
| Created      | 2026-02-09     |

## Context

The marts layer (E-701, E-702) established 7 analytical tables with 32 schema tests covering primary key uniqueness, foreign key integrity, and categorical value validation. These schema tests enforce structural correctness but cannot validate business invariants that span columns or require conditional logic — non-negativity constraints on delay durations, temporal validity across all fact tables, trip duration reasonability, and day-over-day volume stability. DESIGN-DOC Section 8.3 defines 9 critical test cases, 5 of which require singular SQL tests in `/tests/`. One singular test (`assert_station_mapping_coverage`) already exists from E-601 with a 99% mapping threshold. Four additional singular tests are required to close the business rule validation gap and satisfy PH-08 exit criteria. All singular tests must execute as part of `dbt test` and respect the severity classifications defined in DESIGN-DOC Section 8.3 (Blocker = `error`, Warning = `warn`).

## Scope

### In Scope

- `tests/assert_no_negative_delays.sql` — singular test validating `fct_transit_delays.delay_minutes >= 0` with severity `error` (Blocker per DESIGN-DOC Section 8.3)
- `tests/assert_bike_trips_reasonable_duration.sql` — singular test validating `fct_bike_trips.duration_seconds < 86400` (24 hours) with severity `warn` (Warning per DESIGN-DOC Section 8.3)
- `tests/assert_no_future_dates.sql` — singular test validating all date_key values across `fct_transit_delays`, `fct_bike_trips`, and `fct_daily_mobility` are `<= CURRENT_DATE` equivalent, with severity `error` (Blocker per DESIGN-DOC Section 8.3)
- `tests/assert_daily_row_count_stability.sql` — singular test validating no consecutive-day activity count drop exceeding 50% in `fct_daily_mobility`, with severity `warn` (Warning per DESIGN-DOC Section 8.3)
- Validation that all 5 singular tests (4 new + 1 existing `assert_station_mapping_coverage`) pass via `dbt test --select test_type:singular`

### Out of Scope

- Schema tests (`unique`, `not_null`, `relationships`, `accepted_values`) — complete in E-701 and E-702
- dbt_expectations distribution tests — covered in E-802
- Elementary anomaly detection configuration — covered in E-802
- Test strategy documentation (`docs/TESTS.md`) — covered in E-803
- Modification of existing mart models, intermediate models, or staging logic
- Performance benchmarking or query optimization (PH-09)

## Technical Approach

### Architecture Decisions

- **Singular tests over generic tests for multi-column business rules** — dbt generic tests (`not_null`, `unique`, `accepted_values`) operate on single columns with fixed logic; the business rules in DESIGN-DOC Section 8.3 require cross-column conditions (e.g., comparing `delay_minutes` against zero), cross-model unions (e.g., future-date checks across 3 fact tables), and window functions (e.g., LAG for day-over-day comparison); singular SQL tests provide full SQL expressiveness for these patterns
- **Severity classification maps directly to DESIGN-DOC Section 8.3** — Blocker tests use `severity: error` (dbt default, no config override needed), Warning tests use `{{ config(severity='warn') }}` in the test file header; this ensures Blocker violations fail the build while Warning violations surface in test output without blocking deployment
- **Singular tests query mart models via `{{ ref() }}`** — all tests reference `fct_transit_delays`, `fct_bike_trips`, and `fct_daily_mobility` through dbt's `ref()` macro, ensuring correct schema resolution and DAG dependency tracking; no direct table references permitted
- **Future-date test uses integer `date_key` comparison** — all fact tables store dates as integer `date_key` (YYYYMMDD format); the `assert_no_future_dates` test computes `CURRENT_DATE` equivalent as `cast(to_char(current_date(), 'YYYYMMDD') as integer)` and compares directly against `date_key`, avoiding the need for date-type joins or conversions
- **Day-over-day stability test uses aggregate activity counts** — `fct_daily_mobility` contains pre-aggregated daily counts; the stability test sums `total_delay_incidents` and `total_bike_trips` (with `COALESCE` for NULL bike data on transit-only days) to produce a composite daily activity count, then applies `LAG()` window function to detect >50% drops between consecutive `date_key` values

### Integration Points

- **Upstream mart models** — `fct_transit_delays` (237,446 rows, 10 columns), `fct_bike_trips` (21,795,223 rows, 9 columns), `fct_daily_mobility` (1,827 rows, 16 columns) — all from E-702
- **Existing singular test** — `tests/assert_station_mapping_coverage.sql` (from E-601) — validates 99% subway station mapping coverage against `int_ttc_delays_enriched`
- **dbt test runner** — singular tests execute via `dbt test --select test_type:singular` or as part of full `dbt test`; results feed into Elementary test result tracking if Elementary is configured (E-802)
- **CI pipeline** — `dbt test` is a required status check; new singular tests automatically participate in CI gate

### Repository Areas

- `tests/assert_no_negative_delays.sql` (new)
- `tests/assert_bike_trips_reasonable_duration.sql` (new)
- `tests/assert_no_future_dates.sql` (new)
- `tests/assert_daily_row_count_stability.sql` (new)

### Risks

| Risk                                                                                                                                                             | Likelihood | Impact | Mitigation                                                                                                                                                                                                                                                                            |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `assert_no_future_dates` returns false positives if Snowflake session timezone causes `current_date()` to evaluate as yesterday relative to source data timezone | Low        | Medium | Toronto data uses Eastern Time; Snowflake `current_date()` returns UTC date; at most 4-5 hours offset, which is acceptable for date-level granularity since `date_key` is day-level (YYYYMMDD)                                                                                        |
| `assert_daily_row_count_stability` flags legitimate low-activity days (holidays, COVID lockdowns, data collection gaps in 2020-2021) as violations               | Medium     | Low    | Severity is `warn`, not `error`; test detects data loading failures (missing entire days), not natural variation; a genuine >50% drop in combined transit + bike activity across consecutive days is rare outside data quality issues                                                 |
| `assert_bike_trips_reasonable_duration` returns rows if staging filter (`duration >= 60s`) fails to exclude edge cases near the 86400-second boundary            | Low        | Low    | Staging filter (E-502) enforces `duration >= 60s` at the lower bound; this test enforces the upper bound independently; both constraints are documented in DESIGN-DOC Section 4.3.2 and 8.3                                                                                           |
| Singular tests on `fct_bike_trips` (21.8M rows) exceed Snowflake query timeout on X-Small warehouse                                                              | Low        | Medium | WHERE-clause filters (`duration_seconds >= 86400` or `date_key > current_date_key`) scan the table but return only violating rows; Snowflake X-Small handles full scans of this table in <5 seconds per PH-07 benchmarks; singular tests with no matches return zero rows immediately |

## Stories

| ID   | Story                                                      | Points | Dependencies           | Status |
| ---- | ---------------------------------------------------------- | ------ | ---------------------- | ------ |
| S001 | Create assert_no_negative_delays singular test             | 2      | None                   | Complete |
| S002 | Create assert_bike_trips_reasonable_duration singular test | 2      | None                   | Complete |
| S003 | Create assert_no_future_dates singular test                | 3      | None                   | Complete |
| S004 | Create assert_daily_row_count_stability singular test      | 5      | None                   | Complete |
| S005 | Validate all singular tests pass in full test suite        | 3      | S001, S002, S003, S004 | Complete |

---

### S001: Create assert_no_negative_delays Singular Test

**Description**: Create a singular dbt test that validates no transit delay record in `fct_transit_delays` contains a negative `delay_minutes` value, enforcing the non-negativity constraint from DESIGN-DOC Section 4.3.1 and Section 8.3.

**Acceptance Criteria**:

- [ ] File `tests/assert_no_negative_delays.sql` exists
- [ ] Test queries `{{ ref('fct_transit_delays') }}` and returns rows where `delay_minutes < 0`
- [ ] Test uses default severity (`error`) — no `{{ config() }}` override required since Blocker maps to dbt's default error severity
- [ ] Test returns zero rows when executed against current mart data: `dbt test --select assert_no_negative_delays` passes
- [ ] SQL includes a comment block referencing DESIGN-DOC Section 8.3 and the non-negativity constraint

**Technical Notes**: The test selects `delay_sk`, `delay_minutes`, `transit_mode`, and `date_key` from `fct_transit_delays` where `delay_minutes < 0`. Returning diagnostic columns (not just `SELECT 1`) aids debugging if the test ever fails. The staging layer does not enforce `MIN_DELAY >= 0` — it uses `TRY_CAST` which converts unparseable values to NULL, not negative numbers — so negative values would indicate a source data issue rather than a transformation bug.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `dbt test --select assert_no_negative_delays` passes locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S002: Create assert_bike_trips_reasonable_duration Singular Test

**Description**: Create a singular dbt test that validates all bike trips in `fct_bike_trips` have `duration_seconds < 86400` (24 hours), enforcing the reasonability constraint from DESIGN-DOC Section 8.3.

**Acceptance Criteria**:

- [ ] File `tests/assert_bike_trips_reasonable_duration.sql` exists
- [ ] Test includes `{{ config(severity='warn') }}` as the first Jinja block — Warning severity per DESIGN-DOC Section 8.3
- [ ] Test queries `{{ ref('fct_bike_trips') }}` and returns rows where `duration_seconds >= 86400`
- [ ] Test returns zero rows when executed against current mart data: `dbt test --select assert_bike_trips_reasonable_duration` passes (or warns with zero failures)
- [ ] SQL includes a comment block documenting the 86400-second (24-hour) threshold and its origin in DESIGN-DOC Section 8.3

**Technical Notes**: The staging filter (E-502, `stg_bike_trips`) enforces `duration >= 60 seconds` as a lower bound per DESIGN-DOC Decision D9. This test enforces the upper bound. The `warn` severity means the test result surfaces in `dbt test` output and Elementary tracking but does not block the build. The 24-hour threshold is an industry-standard reasonability check for dock-based bike-share systems — trips exceeding 24 hours indicate lost/stolen bikes or system errors, not real ridership.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `dbt test --select assert_bike_trips_reasonable_duration` passes locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S003: Create assert_no_future_dates Singular Test

**Description**: Create a singular dbt test that validates no fact table contains records with `date_key` values representing dates beyond `CURRENT_DATE`, enforcing the temporal validity constraint from DESIGN-DOC Section 8.3 across all three fact tables.

**Acceptance Criteria**:

- [ ] File `tests/assert_no_future_dates.sql` exists
- [ ] Test uses default severity (`error`) — Blocker per DESIGN-DOC Section 8.3
- [ ] Test checks `fct_transit_delays`, `fct_bike_trips`, and `fct_daily_mobility` via three CTEs unioned together
- [ ] Each CTE selects rows where `date_key > cast(to_char(current_date(), 'YYYYMMDD') as integer)`
- [ ] Each CTE includes a `source_model` literal column identifying which fact table the violating row originates from
- [ ] Test returns zero rows when executed against current mart data: `dbt test --select assert_no_future_dates` passes
- [ ] SQL includes a comment block documenting the `CURRENT_DATE` comparison logic and DESIGN-DOC Section 8.3 reference

**Technical Notes**: The `date_key` column in all three fact tables stores dates as YYYYMMDD integers (e.g., `20240315` for March 15, 2024). The test computes the current date equivalent using `cast(to_char(current_date(), 'YYYYMMDD') as integer)` and compares directly. This avoids DATE type conversions and leverages the integer-sortable property of the YYYYMMDD format. The `UNION ALL` across three CTEs ensures a single test covers all fact tables — a future-dated record in any table constitutes a failure.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `dbt test --select assert_no_future_dates` passes locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S004: Create assert_daily_row_count_stability Singular Test

**Description**: Create a singular dbt test that validates no consecutive pair of days in `fct_daily_mobility` exhibits a total activity count drop exceeding 50%, detecting data loading failures or catastrophic data loss.

**Acceptance Criteria**:

- [ ] File `tests/assert_daily_row_count_stability.sql` exists
- [ ] Test includes `{{ config(severity='warn') }}` as the first Jinja block — Warning severity per DESIGN-DOC Section 8.3
- [ ] Test queries `{{ ref('fct_daily_mobility') }}` and computes a composite daily activity count from `total_delay_incidents` and `total_bike_trips` columns (using `COALESCE` for NULL handling on days where only one data source is present)
- [ ] Test uses `LAG()` window function ordered by `date_key` to compare each day's activity count against the previous day
- [ ] Test returns rows where `current_day_count / previous_day_count < 0.5` (excluding the first day in the series where `previous_day_count` is NULL, and excluding days where `previous_day_count = 0`)
- [ ] Test returns zero rows when executed against current mart data: `dbt test --select assert_daily_row_count_stability` passes (or warns with zero failures)
- [ ] SQL includes a comment block documenting the 50% threshold and DESIGN-DOC Section 8.3 reference

**Technical Notes**: `fct_daily_mobility` contains 1,827 rows (one per day) with pre-aggregated transit and bike counts. The composite activity count is `COALESCE(total_delay_incidents, 0) + COALESCE(total_bike_trips, 0)`. The `LAG()` function provides the previous day's count for comparison. Days with `previous_day_count = 0` are excluded to avoid division-by-zero errors — zero-activity days (if any) are not a baseline for stability comparison. The 50% threshold aligns with DESIGN-DOC Section 8.3 ("Count >= 0.5 x previous run count") adapted to day-over-day granularity as specified in the PH-08 phase description.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `dbt test --select assert_daily_row_count_stability` passes locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S005: Validate All Singular Tests Pass in Full Test Suite

**Description**: Execute all singular dbt tests (4 new from S001-S004 plus 1 existing `assert_station_mapping_coverage` from E-601) as a cohesive test suite and confirm 100% pass rate.

**Acceptance Criteria**:

- [ ] `dbt test --select test_type:singular` executes all 5 singular tests
- [ ] All 5 tests report PASS (or WARN for `severity: warn` tests): `assert_no_negative_delays` (PASS), `assert_bike_trips_reasonable_duration` (PASS or WARN), `assert_no_future_dates` (PASS), `assert_daily_row_count_stability` (PASS or WARN), `assert_station_mapping_coverage` (PASS)
- [ ] Zero ERROR results in the singular test suite
- [ ] Test execution time for all 5 singular tests is under 60 seconds on X-Small warehouse

**Technical Notes**: The `test_type:singular` selector in dbt targets all SQL files in the `tests/` directory (excluding Python test files which are pytest, not dbt). The existing `assert_station_mapping_coverage` test validates 99% subway station mapping coverage against `int_ttc_delays_enriched` (E-601). This story does not create new tests — it validates the combined suite after S001-S004 are complete.

**Definition of Done**:

- [ ] All 5 singular tests pass in a single `dbt test --select test_type:singular` invocation
- [ ] Test output captured and reviewed
- [ ] PR opened with linked issue
- [ ] CI checks green

## Exit Criteria

This epic is complete when:

- [ ] 4 new singular test files exist in `/tests/`: `assert_no_negative_delays.sql`, `assert_bike_trips_reasonable_duration.sql`, `assert_no_future_dates.sql`, `assert_daily_row_count_stability.sql`
- [ ] `assert_no_negative_delays` and `assert_no_future_dates` use severity `error` (Blocker)
- [ ] `assert_bike_trips_reasonable_duration` and `assert_daily_row_count_stability` use severity `warn` (Warning)
- [ ] `dbt test --select test_type:singular` passes with 5 tests, zero ERROR results
- [ ] All tests query mart models via `{{ ref() }}` macro — no hardcoded table references

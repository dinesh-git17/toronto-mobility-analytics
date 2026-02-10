# Bike Share Enrichment and Daily Metrics Aggregation Models

| Field        | Value          |
| ------------ | -------------- |
| Epic ID      | E-602          |
| Phase        | PH-06          |
| Owner        | @dinesh-git17  |
| Status       | Complete       |
| Dependencies | [E-501, E-601] |
| Created      | 2026-02-09     |

## Context

The intermediate layer requires three additional ephemeral models beyond TTC delay enrichment: bike trip enrichment with station geography and duration bucketing, and two daily pre-aggregation models that reduce the ~1.8M delay records and ~30M bike trip records to date-level summaries for `fct_daily_mobility`. The `int_bike_trips_enriched` model joins `stg_bike_trips` with the `bike_station_ref` seed to attach latitude, longitude, and neighborhood to each trip endpoint. Duration buckets provide a categorical dimension for trip length analysis. The daily metrics models (`int_daily_transit_metrics`, `int_daily_bike_metrics`) pre-aggregate to daily grain with mode-level and user-type breakdowns respectively, enabling the `fct_daily_mobility` mart to join transit and bike metrics on `date_key`. All models materialize as ephemeral CTEs per DESIGN-DOC Decision D10.

## Scope

### In Scope

- `int_bike_trips_enriched` ephemeral model: LEFT JOIN with `bike_station_ref` seed (on start and end station IDs), duration bucket computation, `date_key` derivation from `start_time`
- `int_daily_transit_metrics` ephemeral model: daily aggregation of `int_ttc_delays_enriched` with total and per-mode delay counts and minutes
- `int_daily_bike_metrics` ephemeral model: daily aggregation of `int_bike_trips_enriched` with total and per-user-type trip counts and duration sums
- Model documentation for all three models in `models/intermediate/_int__models.yml` (extending the file created in E-601)
- Full intermediate layer validation: `dbt build --select intermediate` passes with all models and tests green

### Out of Scope

- TTC delay union and enrichment models (E-601)
- Station mapping coverage test (E-601)
- Mart-layer fact and dimension tables (PH-07)
- Bike station seed curation (completed in E-402)
- Real-time bike station availability (DESIGN-DOC Non-Goal NG1)
- Hourly weather joins (DESIGN-DOC Non-Goal NG7; weather enrichment deferred to `fct_daily_mobility` in PH-07)

## Technical Approach

### Architecture Decisions

- **Bike station enrichment uses seed directly, not dim_station** — DESIGN-DOC Section 6.3 lists `dim_station` as a source for `int_bike_trips_enriched`, but `dim_station` is a PH-07 mart model that cannot exist before the intermediate layer. The `bike_station_ref` seed (1,009 rows from E-402) provides identical station geography data. The mart layer generates surrogate keys for `dim_station` from the same seed.
- **Station key generation deferred to mart layer** — The intermediate model attaches station geography (latitude, longitude, neighborhood) but does not generate the `dim_station` surrogate FK. The mart model `fct_bike_trips` (PH-07) generates `start_station_key` and `end_station_key` using `dbt_utils.generate_surrogate_key(['BIKE_SHARE', station_id])` per DESIGN-DOC Section 6.4.
- **Duration buckets use five categories** — Under 5 min (60-299s), 5-15 min (300-899s), 15-30 min (900-1799s), 30-60 min (1800-3599s), Over 60 min (3600+s). Lower bound starts at 60s due to the `trip_duration >= 60` filter applied in staging (DESIGN-DOC Decision D9).
- **Daily metrics compute date_key for downstream join** — Both daily models output `date_key` as a YYYYMMDD integer computed via `to_number(to_char(date_column, 'YYYYMMDD'))`, matching the `date_spine` seed format for FK joins to `dim_date` in `fct_daily_mobility`.
- **Pre-aggregation includes mode-level and user-type breakdowns** — `int_daily_transit_metrics` pivots delay counts and minutes by `transit_mode` (subway, bus, streetcar) using conditional aggregation. `int_daily_bike_metrics` pivots trip counts by `user_type` (Annual Member, Casual Member) using conditional aggregation. This avoids re-scanning staging views in the mart layer.

### Integration Points

- **Upstream models** — `stg_bike_trips` (11 columns, E-502), `int_ttc_delays_enriched` (19 columns, E-601), `int_bike_trips_enriched` (this epic)
- **Seed tables** — `bike_station_ref` (1,009 rows, 5 columns: station_id, station_name, latitude, longitude, neighborhood) from E-402
- **Downstream consumers** — `fct_bike_trips`, `fct_daily_mobility`, `dim_station` (all PH-07)
- **dbt_project.yml** — Intermediate materialization already configured as `ephemeral`

### Repository Areas

- `models/intermediate/int_bike_trips_enriched.sql` (new)
- `models/intermediate/int_daily_transit_metrics.sql` (new)
- `models/intermediate/int_daily_bike_metrics.sql` (new)
- `models/intermediate/_int__models.yml` (extend from E-601)

### Risks

| Risk                                                                                                        | Likelihood | Impact | Mitigation                                                                                                                                                                     |
| ----------------------------------------------------------------------------------------------------------- | ---------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Bike station IDs in trip data not present in `bike_station_ref` seed (orphan stations)                      | Medium     | Medium | LEFT JOIN preserves all trips; unmatched stations get NULL geography; GBFS snapshot (E-402) captured 1,009 stations but historical trips may reference decommissioned stations |
| Daily aggregation grain mismatch with `fct_daily_mobility` expectations                                     | Low        | High   | Verify `date_key` computation matches `date_spine` seed format (YYYYMMDD integer); both daily models use identical `to_number(to_char(...))` pattern                           |
| Duration bucket boundaries exclude valid edge cases                                                         | Low        | Low    | CASE WHEN uses inclusive lower / exclusive upper bounds with exhaustive coverage; staging filter ensures minimum 60s                                                           |
| Ephemeral model chain depth (3 levels: staging -> unioned -> enriched -> daily) causes compilation timeouts | Low        | Medium | Snowflake handles deep CTE chains efficiently; monitor `dbt compile` time; materialization override available if needed                                                        |

## Stories

| ID   | Story                                               | Points | Dependencies                  | Status |
| ---- | --------------------------------------------------- | ------ | ----------------------------- | ------ |
| S001 | Create int_bike_trips_enriched ephemeral model      | 5      | None                          | Done   |
| S002 | Create int_daily_transit_metrics ephemeral model    | 5      | E-601.S002                    | Done   |
| S003 | Create int_daily_bike_metrics ephemeral model       | 3      | S001                          | Done   |
| S004 | Document bike and daily metrics intermediate models | 3      | S001, S002, S003              | Done   |
| S005 | Validate full intermediate layer end-to-end         | 3      | E-601, S001, S002, S003, S004 | Done   |

---

### S001: Create int_bike_trips_enriched Ephemeral Model

**Description**: Build `int_bike_trips_enriched` as an ephemeral dbt model that enriches `stg_bike_trips` with station geography from the `bike_station_ref` seed and adds duration bucket classification.

**Acceptance Criteria**:

- [x] File `models/intermediate/int_bike_trips_enriched.sql` exists with no explicit materialization config (inherits ephemeral from `dbt_project.yml`)
- [x] Model references `{{ ref('stg_bike_trips') }}` as its primary source
- [x] LEFT JOIN with `{{ ref('bike_station_ref') }}` on `start_station_id = station_id` adds columns: `start_latitude`, `start_longitude`, `start_neighborhood`
- [x] Second LEFT JOIN with `{{ ref('bike_station_ref') }}` on `end_station_id = station_id` adds columns: `end_latitude`, `end_longitude`, `end_neighborhood`
- [x] Computed column `trip_date` derived as `start_time::date`
- [x] Computed column `date_key` derived as `to_number(to_char(start_time::date, 'YYYYMMDD'))` matching `date_spine` seed format
- [x] Computed column `duration_bucket` uses CASE expression with these exact categories: `'Under 5 min'` (60-299s), `'5-15 min'` (300-899s), `'15-30 min'` (900-1799s), `'30-60 min'` (1800-3599s), `'Over 60 min'` (3600+s)
- [x] All 11 columns from `stg_bike_trips` carried forward plus 9 enrichment columns: `trip_date`, `date_key`, `start_latitude`, `start_longitude`, `start_neighborhood`, `end_latitude`, `end_longitude`, `end_neighborhood`, `duration_bucket`
- [x] Output contains exactly 20 columns total
- [x] `dbt compile --select int_bike_trips_enriched` succeeds with zero errors

**Technical Notes**: The `bike_station_ref` seed is joined twice with table aliases (e.g., `start_station`, `end_station`). LEFT JOIN ensures trips with decommissioned or missing station IDs are preserved with NULL geography. The duration bucket CASE expression uses `trip_duration_seconds` (already filtered >= 60 in staging per Decision D9). Duration bucket boundaries: `WHEN trip_duration_seconds < 300 THEN 'Under 5 min'`, `WHEN trip_duration_seconds < 900 THEN '5-15 min'`, `WHEN trip_duration_seconds < 1800 THEN '15-30 min'`, `WHEN trip_duration_seconds < 3600 THEN '30-60 min'`, `ELSE 'Over 60 min'`.

**Definition of Done**:

- [x] Code committed to feature branch
- [x] `dbt compile --select int_bike_trips_enriched` passes locally
- [x] PR opened with linked issue
- [x] CI checks green

---

### S002: Create int_daily_transit_metrics Ephemeral Model

**Description**: Build `int_daily_transit_metrics` as an ephemeral dbt model that aggregates `int_ttc_delays_enriched` to daily grain with total and per-mode delay counts and minutes.

**Acceptance Criteria**:

- [x] File `models/intermediate/int_daily_transit_metrics.sql` exists with no explicit materialization config (inherits ephemeral from `dbt_project.yml`)
- [x] Model references `{{ ref('int_ttc_delays_enriched') }}` as its primary source
- [x] GROUP BY uses `delay_date` and `date_key` columns from the enriched model
- [x] Computed column `total_delay_incidents` uses `count(*)` across all modes
- [x] Computed column `total_delay_minutes` uses `sum(delay_minutes)` across all modes
- [x] Computed column `avg_delay_minutes` uses `round(avg(delay_minutes), 2)` across all modes
- [x] Computed column `total_gap_minutes` uses `sum(gap_minutes)` across all modes
- [x] Computed column `subway_delay_incidents` uses `count_if(transit_mode = 'subway')` or equivalent conditional count
- [x] Computed column `bus_delay_incidents` uses `count_if(transit_mode = 'bus')` or equivalent conditional count
- [x] Computed column `streetcar_delay_incidents` uses `count_if(transit_mode = 'streetcar')` or equivalent conditional count
- [x] Computed column `subway_delay_minutes` uses `sum(case when transit_mode = 'subway' then delay_minutes else 0 end)` or equivalent
- [x] Computed column `bus_delay_minutes` uses `sum(case when transit_mode = 'bus' then delay_minutes else 0 end)` or equivalent
- [x] Computed column `streetcar_delay_minutes` uses `sum(case when transit_mode = 'streetcar' then delay_minutes else 0 end)` or equivalent
- [x] Output contains exactly 12 columns: `delay_date`, `date_key`, `total_delay_incidents`, `total_delay_minutes`, `avg_delay_minutes`, `total_gap_minutes`, `subway_delay_incidents`, `bus_delay_incidents`, `streetcar_delay_incidents`, `subway_delay_minutes`, `bus_delay_minutes`, `streetcar_delay_minutes`
- [x] `dbt compile --select int_daily_transit_metrics` succeeds with zero errors

**Technical Notes**: The ephemeral CTE chain is 3 levels deep: `stg_ttc_*` -> `int_ttc_delays_unioned` -> `int_ttc_delays_enriched` -> `int_daily_transit_metrics`. Snowflake handles this depth without issue. Conditional aggregation via `count_if()` is a Snowflake-native function preferred over `CASE WHEN` for readability. The `avg_delay_minutes` uses `round(..., 2)` to avoid floating-point noise in downstream aggregations. Output grain is one row per calendar date with delay activity.

**Definition of Done**:

- [x] Code committed to feature branch
- [x] `dbt compile --select int_daily_transit_metrics` passes locally
- [x] PR opened with linked issue
- [x] CI checks green

---

### S003: Create int_daily_bike_metrics Ephemeral Model

**Description**: Build `int_daily_bike_metrics` as an ephemeral dbt model that aggregates `int_bike_trips_enriched` to daily grain with total and per-user-type trip counts and duration sums.

**Acceptance Criteria**:

- [x] File `models/intermediate/int_daily_bike_metrics.sql` exists with no explicit materialization config (inherits ephemeral from `dbt_project.yml`)
- [x] Model references `{{ ref('int_bike_trips_enriched') }}` as its primary source
- [x] GROUP BY uses `trip_date` and `date_key` columns from the enriched model
- [x] Computed column `total_trips` uses `count(*)` across all user types
- [x] Computed column `total_duration_seconds` uses `sum(trip_duration_seconds)` across all user types
- [x] Computed column `avg_duration_seconds` uses `round(avg(trip_duration_seconds), 2)` across all user types
- [x] Computed column `member_trips` uses `count_if(user_type = 'Annual Member')` or equivalent conditional count
- [x] Computed column `casual_trips` uses `count_if(user_type = 'Casual Member')` or equivalent conditional count
- [x] Output contains exactly 7 columns: `trip_date`, `date_key`, `total_trips`, `total_duration_seconds`, `avg_duration_seconds`, `member_trips`, `casual_trips`
- [x] `dbt compile --select int_daily_bike_metrics` succeeds with zero errors

**Technical Notes**: The enriched model provides `trip_date` (derived from `start_time::date`) and `date_key` (YYYYMMDD integer) for grouping. The daily bike metrics output grain is one row per calendar date with bike trip activity. Conditional aggregation via `count_if()` uses the exact values from the staging `user_type` column: `'Annual Member'` and `'Casual Member'` (verified by `accepted_values` test in E-502). The `avg_duration_seconds` uses `round(..., 2)` for consistency with `int_daily_transit_metrics`.

**Definition of Done**:

- [x] Code committed to feature branch
- [x] `dbt compile --select int_daily_bike_metrics` passes locally
- [x] PR opened with linked issue
- [x] CI checks green

---

### S004: Document Bike and Daily Metrics Intermediate Models

**Description**: Extend `models/intermediate/_int__models.yml` (created in E-601 S004) with model definitions, column descriptions, and schema tests for `int_bike_trips_enriched`, `int_daily_transit_metrics`, and `int_daily_bike_metrics`.

**Acceptance Criteria**:

- [x] File `models/intermediate/_int__models.yml` contains model definitions for `int_bike_trips_enriched`, `int_daily_transit_metrics`, and `int_daily_bike_metrics` (appended to existing TTC model definitions from E-601)
- [x] Each model includes a `description` field summarizing its source, grain, and key transformations
- [x] All 20 columns of `int_bike_trips_enriched` have `description` fields
- [x] All 12 columns of `int_daily_transit_metrics` have `description` fields
- [x] All 7 columns of `int_daily_bike_metrics` have `description` fields
- [x] `trip_date` column in `int_bike_trips_enriched` has `not_null` test
- [x] `date_key` column in `int_bike_trips_enriched` has `not_null` test
- [x] `duration_bucket` column in `int_bike_trips_enriched` has `accepted_values` test with values `['Under 5 min', '5-15 min', '15-30 min', '30-60 min', 'Over 60 min']`
- [x] `user_type` column in `int_bike_trips_enriched` has `accepted_values` test with values `['Annual Member', 'Casual Member']`
- [x] `date_key` column in `int_daily_transit_metrics` has `not_null` test
- [x] `total_delay_incidents` column in `int_daily_transit_metrics` has `not_null` test
- [x] `date_key` column in `int_daily_bike_metrics` has `not_null` test
- [x] `total_trips` column in `int_daily_bike_metrics` has `not_null` test
- [x] `dbt parse` succeeds with zero errors after YAML updates
- [x] All defined schema tests execute via `dbt test --select int_bike_trips_enriched int_daily_transit_metrics int_daily_bike_metrics`

**Technical Notes**: The `_int__models.yml` file is shared across all intermediate models (single flat directory structure per DESIGN-DOC Section 15.1). Column descriptions use technical documentation voice per CLAUDE.md Section 1.2. The `duration_bucket` accepted_values test ensures exhaustive coverage of the five defined categories. All schema tests on ephemeral models compile to CTE-based test queries.

**Definition of Done**:

- [x] Code committed to feature branch
- [x] `dbt parse` passes locally
- [x] All defined tests pass against Snowflake target
- [x] PR opened with linked issue
- [x] CI checks green

---

### S005: Validate Full Intermediate Layer End-to-End

**Description**: Execute `dbt build --select intermediate` to compile and test all 5 intermediate models and the station mapping coverage singular test, confirming the full layer is operational.

**Acceptance Criteria**:

- [x] `dbt build --select intermediate` executes without errors, compiling all 5 ephemeral models: `int_ttc_delays_unioned`, `int_ttc_delays_enriched`, `int_bike_trips_enriched`, `int_daily_transit_metrics`, `int_daily_bike_metrics`
- [x] All schema tests defined in `_int__models.yml` pass (zero failures)
- [x] Singular test `tests/assert_station_mapping_coverage.sql` passes (>= 99% subway station mapping coverage)
- [x] `dbt compile` output confirms all 5 models resolve as ephemeral (no Snowflake objects created)
- [x] No compilation warnings related to missing refs, undefined columns, or deprecated syntax
- [x] `dbt docs generate` succeeds and intermediate models appear in the lineage graph between staging and marts layers (downstream connections pending PH-07)

**Technical Notes**: Since all intermediate models are ephemeral, `dbt build --select intermediate` primarily compiles CTEs and executes schema tests. The tests force Snowflake query execution by inlining the ephemeral models. The `dbt docs generate` step verifies model metadata and lineage connectivity. This validation story is the final gate before declaring PH-06 complete.

**Definition of Done**:

- [x] All 5 intermediate models compile without errors
- [x] All schema tests pass (zero failures, warnings acceptable for `severity: warn` tests)
- [x] Station mapping coverage test passes (>= 99%)
- [x] `dbt docs generate` succeeds
- [x] PR opened with linked issue
- [x] CI checks green

## Exit Criteria

This epic is complete when:

- [x] `int_bike_trips_enriched` compiles as ephemeral CTE enriching bike trips with station geography and duration buckets producing 20 columns
- [x] `int_daily_transit_metrics` compiles as ephemeral CTE aggregating TTC delays to daily grain with 12 columns
- [x] `int_daily_bike_metrics` compiles as ephemeral CTE aggregating bike trips to daily grain with 7 columns
- [x] `_int__models.yml` documents all 5 intermediate models with column descriptions and schema tests
- [x] `dbt build --select intermediate` passes with zero failures across all models and tests
- [x] Full intermediate layer lineage visible in `dbt docs generate` output

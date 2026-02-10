# Mobility Fact Models

| Field        | Value                 |
| ------------ | --------------------- |
| Epic ID      | E-702                 |
| Phase        | PH-07                 |
| Owner        | @dinesh-git17         |
| Status       | Complete              |
| Dependencies | [E-601, E-602, E-701] |
| Created      | 2026-02-09            |

## Context

The mart layer requires three fact tables to serve as the primary analytical surfaces for the Toronto Urban Mobility platform: `fct_transit_delays` (per-incident TTC delays), `fct_bike_trips` (per-trip Bike Share ridership), and `fct_daily_mobility` (cross-modal daily aggregation). These models consume the five intermediate ephemeral models built in E-601 and E-602, generate surrogate FK keys that align with the dimension tables from E-701, and materialize as persistent tables in the MARTS schema. The fact tables enable the five benchmark queries defined in DESIGN-DOC Section 15.4, all of which must execute in under 5 seconds on an X-Small Snowflake warehouse. This epic completes the medallion architecture data pipeline from RAW through STAGING, INTERMEDIATE, to MARTS — the final transformation layer.

## Scope

### In Scope

- `fct_transit_delays` table model in `models/marts/mobility/`: one row per TTC delay incident (~1.8M rows) with surrogate FK keys to `dim_date`, `dim_station`, and `dim_ttc_delay_codes`
- `fct_bike_trips` table model in `models/marts/mobility/`: one row per Bike Share trip (~30M rows) with surrogate FK keys to `dim_date` and `dim_station` (start and end)
- `fct_daily_mobility` table model in `models/marts/mobility/`: one row per calendar date (~2,200 rows) joining `int_daily_transit_metrics` and `int_daily_bike_metrics` on `date_key`
- Schema documentation in `models/marts/mobility/_mobility__models.yml` with column-level descriptions
- Comprehensive dbt tests: `unique` and `not_null` on all primary keys, `relationships` on all foreign keys, `accepted_values` on all categorical columns

### Out of Scope

- Dimension table construction (completed in E-701)
- Intermediate model modification (completed in E-601 and E-602)
- Singular dbt tests for business rules (`assert_no_negative_delays`, `assert_bike_trips_reasonable_duration`, `assert_no_future_dates`) — deferred to PH-08
- `dbt_expectations` distribution tests (deferred to PH-08)
- Elementary anomaly detection configuration (deferred to PH-08)
- Performance benchmarking (deferred to PH-09)
- Incremental materialization strategy for `fct_bike_trips` (deferred to v2 per DESIGN-DOC Section 13.1)

## Technical Approach

### Architecture Decisions

- **Table materialization for all fact models** — Per DESIGN-DOC Section 6.3 and `dbt_project.yml` (`models.toronto_mobility.marts.+materialized: table`); fact tables are the primary query targets and must persist as physical tables in the MARTS schema
- **Surrogate FK keys generated at the fact layer** — Fact models compute FK surrogates using `dbt_utils.generate_surrogate_key()` with the same natural key components used in the corresponding dimension: `station_key = generate_surrogate_key(["'TTC_SUBWAY'", 'station_id'])` must match `dim_station` exactly; `delay_code_key = generate_surrogate_key(['delay_code'])` must match `dim_ttc_delay_codes` exactly
- **Conditional station_key for transit delays** — Subway records generate `station_key` from `['TTC_SUBWAY', station_id]`; bus and streetcar records set `station_key` to NULL since no station dimension exists for surface routes; the `relationships` test on `station_key` uses `where station_key is not null` to permit NULLs
- **FULL OUTER JOIN for fct_daily_mobility** — Transit metrics and bike metrics may not cover identical date ranges; a FULL OUTER JOIN on `date_key` preserves dates with only transit data (winter months with no bike trips) or only bike data (dates without TTC delay records); `COALESCE` resolves the join key
- **Bike Share station FK uses BIKE_SHARE type literal** — `start_station_key = generate_surrogate_key(["'BIKE_SHARE'", 'start_station_id'])` and `end_station_key = generate_surrogate_key(["'BIKE_SHARE'", 'end_station_id'])`; station_id cast to VARCHAR for type alignment with the dim_station natural key column
- **Fact PKs reuse staging surrogate keys** — `fct_transit_delays.delay_sk` and `fct_bike_trips.trip_sk` are carried forward from the staging layer surrogates (already generated via `dbt_utils.generate_surrogate_key` in stg models); `fct_daily_mobility.date_key` is the integer YYYYMMDD natural key serving as both PK and FK

### Integration Points

- **Upstream intermediate models** — `int_ttc_delays_enriched` (19 columns, ~1.8M rows) from E-601; `int_bike_trips_enriched` (20 columns, ~30M rows), `int_daily_transit_metrics` (12 columns, ~2,200 rows), `int_daily_bike_metrics` (7 columns, ~2,200 rows) from E-602
- **Upstream dimension models** — `dim_date` (2,922 rows), `dim_station` (1,085 rows), `dim_ttc_delay_codes` (334 rows) from E-701 — FK targets for `relationships` tests
- **Downstream consumers** — Five benchmark queries in `analyses/` (DESIGN-DOC Section 15.4): `top_delay_stations.sql`, `bike_weather_correlation.sql`, `cross_modal_analysis.sql`, `monthly_trends.sql`, `daily_mobility_summary.sql`
- **dbt_project.yml** — Mart materialization already configured as `table` with `+schema: marts`

### Repository Areas

- `models/marts/mobility/fct_transit_delays.sql` (new)
- `models/marts/mobility/fct_bike_trips.sql` (new)
- `models/marts/mobility/fct_daily_mobility.sql` (new)
- `models/marts/mobility/_mobility__models.yml` (new)
- `models/marts/mobility/.gitkeep` (remove after model files committed)

### Risks

| Risk                                                                                                                                                     | Likelihood | Impact | Mitigation                                                                                                                                                                                                                                         |
| -------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `fct_bike_trips` materialization exceeds X-Small warehouse timeout (~30M rows table creation)                                                            | Medium     | High   | Monitor `dbt run` execution time; if creation exceeds 5 minutes, evaluate `CREATE TABLE AS SELECT` partition strategy or warehouse upsize during initial build; incremental materialization deferred to v2                                         |
| Surrogate FK mismatch between fact and dimension due to inconsistent `station_type` literal casing or `station_id` type coercion                         | Medium     | High   | Pin `station_type` literals as `'TTC_SUBWAY'` and `'BIKE_SHARE'` (UPPER_SNAKE_CASE) in both E-701 and E-702 models; cast all `station_id` values to VARCHAR before surrogate key generation; `relationships` tests detect mismatches at build time |
| FULL OUTER JOIN in `fct_daily_mobility` produces duplicate `date_key` rows when both transit and bike data exist for the same date                       | Low        | High   | COALESCE resolves the join key to a single value; GROUP BY is not needed since each intermediate model already produces one row per date; validate via `unique` test on `date_key`                                                                 |
| `relationships` test on `fct_transit_delays.delay_code_key` fails for delay codes present in staging but absent from the `ttc_delay_codes` seed          | Low        | Medium | The `delay_code_key` FK is NULL when `delay_code` is NULL; the `relationships` test config uses `where delay_code_key is not null`; E-401 seed covers all 334 known codes; unknown codes produce NULL FK (acceptable)                              |
| `fct_bike_trips.start_station_key` or `end_station_key` references a station not in `dim_station` due to Bike Share network expansion post-GBFS snapshot | Low        | Medium | The GBFS snapshot (E-402) captured 1,009 stations; new stations added after the snapshot date produce NULL FK via LEFT JOIN semantics in the enriched intermediate model; `relationships` test uses `where start_station_key is not null`          |

## Stories

| ID   | Story                                                                 | Points | Dependencies     | Status   |
| ---- | --------------------------------------------------------------------- | ------ | ---------------- | -------- |
| S001 | Create fct_transit_delays table model                                 | 5      | None             | Complete |
| S002 | Create fct_bike_trips table model                                     | 5      | None             | Complete |
| S003 | Create fct_daily_mobility cross-modal table model                     | 5      | None             | Complete |
| S004 | Document all fact models and add comprehensive FK and PK schema tests | 8      | S001, S002, S003 | Complete |

---

### S001: Create fct_transit_delays Table Model

**Description**: Build `fct_transit_delays` as a table-materialized mart model that selects from `int_ttc_delays_enriched`, generates surrogate FK keys for `dim_date`, `dim_station`, and `dim_ttc_delay_codes`, and outputs one row per TTC delay incident (~1.8M rows).

**Acceptance Criteria**:

- [x] File `models/marts/mobility/fct_transit_delays.sql` exists with no explicit materialization config (inherits `table` from `dbt_project.yml`)
- [x] Model references `{{ ref('int_ttc_delays_enriched') }}` as its sole source
- [x] Column `delay_sk` carried forward from the intermediate model as the primary key
- [x] Column `date_key` carried forward as FK to `dim_date` (integer YYYYMMDD)
- [x] Column `station_key` generated conditionally: `{{ dbt_utils.generate_surrogate_key(["'TTC_SUBWAY'", 'station_id']) }}` when `transit_mode = 'subway' AND station_id IS NOT NULL`, else `NULL`
- [x] Column `delay_code_key` generated conditionally: `{{ dbt_utils.generate_surrogate_key(['delay_code']) }}` when `delay_code IS NOT NULL`, else `NULL`
- [x] Columns carried forward without transformation: `delay_minutes`, `gap_minutes`, `transit_mode`, `line_code`, `direction`, `incident_timestamp`
- [x] Output contains exactly 10 columns: `delay_sk`, `date_key`, `station_key`, `delay_code_key`, `delay_minutes`, `gap_minutes`, `transit_mode`, `line_code`, `direction`, `incident_timestamp`
- [x] `station_key` is NULL for all bus and streetcar records (no station mapping for surface routes)
- [x] `station_key` is non-NULL for subway records where `station_id` is not NULL (99%+ per E-601 coverage test)
- [x] `dbt run --select fct_transit_delays` succeeds and creates a table in the MARTS schema

**Technical Notes**: The `station_type` literal `'TTC_SUBWAY'` must match exactly what `dim_station` (E-701 S002) uses in its surrogate key generation — case-sensitive. The `delay_code_key` generation uses `generate_surrogate_key(['delay_code'])` which must match `dim_ttc_delay_codes` (E-701 S004). The conditional CASE expression for `station_key` prevents generating a surrogate from `['TTC_SUBWAY', NULL]` which would be a deterministic hash that does not match any `dim_station` row. Bus and streetcar analytical queries use `route` and `location` from the intermediate layer; these columns are intentionally excluded from the fact table per the DESIGN-DOC ER diagram but remain accessible via the ephemeral intermediate model for ad-hoc analysis.

**Definition of Done**:

- [x] Code committed to feature branch
- [x] `dbt run --select fct_transit_delays` passes locally
- [x] PR opened with linked issue
- [x] CI checks green

---

### S002: Create fct_bike_trips Table Model

**Description**: Build `fct_bike_trips` as a table-materialized mart model that selects from `int_bike_trips_enriched`, generates surrogate FK keys for `dim_date` and `dim_station` (start and end), and outputs one row per Bike Share trip (~30M rows).

**Acceptance Criteria**:

- [x] File `models/marts/mobility/fct_bike_trips.sql` exists with no explicit materialization config (inherits `table` from `dbt_project.yml`)
- [x] Model references `{{ ref('int_bike_trips_enriched') }}` as its sole source
- [x] Column `trip_sk` carried forward from the intermediate model as the primary key
- [x] Column `date_key` carried forward as FK to `dim_date` (integer YYYYMMDD)
- [x] Column `start_station_key` generated via `{{ dbt_utils.generate_surrogate_key(["'BIKE_SHARE'", 'start_station_id']) }}` — FK to `dim_station`
- [x] Column `end_station_key` generated via `{{ dbt_utils.generate_surrogate_key(["'BIKE_SHARE'", 'end_station_id']) }}` — FK to `dim_station`
- [x] Column `trip_duration_seconds` aliased as `duration_seconds` to match DESIGN-DOC ER diagram naming
- [x] Columns carried forward without transformation: `user_type`, `bike_id`, `start_time`, `end_time`
- [x] Output contains exactly 9 columns: `trip_sk`, `date_key`, `start_station_key`, `end_station_key`, `duration_seconds`, `user_type`, `bike_id`, `start_time`, `end_time`
- [x] `start_station_key` and `end_station_key` surrogates use `start_station_id` and `end_station_id` cast to VARCHAR before key generation to match `dim_station` natural key type
- [x] `dbt run --select fct_bike_trips` succeeds and creates a table in the MARTS schema

**Technical Notes**: This is the largest table in the warehouse (~30M rows). Full-refresh materialization on an X-Small warehouse may take 2-5 minutes. The `BIKE_SHARE` literal must match exactly what `dim_station` (E-701 S002) uses. Station IDs in the enriched model are integers; they must be cast to VARCHAR (e.g., `start_station_id::varchar`) before being passed to `generate_surrogate_key` to match the `dim_station` natural key type. Incremental materialization is deferred to v2 per DESIGN-DOC Section 13.1 — full-refresh is acceptable for the portfolio project scope.

**Definition of Done**:

- [x] Code committed to feature branch
- [x] `dbt run --select fct_bike_trips` passes locally
- [x] PR opened with linked issue
- [x] CI checks green

---

### S003: Create fct_daily_mobility Cross-Modal Table Model

**Description**: Build `fct_daily_mobility` as a table-materialized mart model that joins `int_daily_transit_metrics` and `int_daily_bike_metrics` via FULL OUTER JOIN on `date_key`, producing one row per calendar date (~2,200 rows) with cross-modal transit and bike aggregates.

**Acceptance Criteria**:

- [x] File `models/marts/mobility/fct_daily_mobility.sql` exists with no explicit materialization config (inherits `table` from `dbt_project.yml`)
- [x] Model references `{{ ref('int_daily_transit_metrics') }}` and `{{ ref('int_daily_bike_metrics') }}` as its two source CTEs
- [x] CTEs joined via `FULL OUTER JOIN` on `date_key` to preserve dates with only transit data or only bike data
- [x] Column `date_key` computed as `COALESCE(transit.date_key, bike.date_key)` — serves as both PK and FK to `dim_date`
- [x] Transit metric columns carried forward: `total_delay_incidents`, `total_delay_minutes`, `avg_delay_minutes`, `total_gap_minutes`, `subway_delay_incidents`, `bus_delay_incidents`, `streetcar_delay_incidents`, `subway_delay_minutes`, `bus_delay_minutes`, `streetcar_delay_minutes`
- [x] Bike metric columns carried forward with rename: `total_trips` aliased as `total_bike_trips`, `total_duration_seconds` aliased as `total_bike_duration_seconds`, `avg_duration_seconds` aliased as `avg_bike_duration_seconds`, `member_trips`, `casual_trips`
- [x] Output contains exactly 16 columns: `date_key` + 10 transit metrics + 5 bike metrics
- [x] Rows with only transit data have NULL bike columns; rows with only bike data have NULL transit columns
- [x] `dbt run --select fct_daily_mobility` succeeds and creates a table in the MARTS schema
- [x] Row count is ~2,200 (one per distinct date across both data sources)

**Technical Notes**: The FULL OUTER JOIN ensures no data loss. Both intermediate models produce exactly one row per date (aggregated in E-602), so the join produces no duplicates. The `date_key` COALESCE pattern resolves the join ambiguity. The sample queries in DESIGN-DOC Section 15.3 reference `total_bike_trips`, `total_delay_minutes`, and `total_delay_incidents` — these column names must match exactly. The `WHERE` filters in the sample queries (`WHERE m.total_bike_trips IS NOT NULL AND m.total_delay_incidents IS NOT NULL`) confirm that NULL columns are expected and acceptable for dates outside a data source's range.

**Definition of Done**:

- [x] Code committed to feature branch
- [x] `dbt run --select fct_daily_mobility` passes locally
- [x] PR opened with linked issue
- [x] CI checks green

---

### S004: Document All Fact Models and Add Comprehensive FK and PK Schema Tests

**Description**: Create `_mobility__models.yml` with column-level descriptions for all three fact models and add schema tests covering primary key integrity (`unique`, `not_null`), foreign key referential integrity (`relationships`), and categorical value validation (`accepted_values`).

**Acceptance Criteria**:

- [x] File `models/marts/mobility/_mobility__models.yml` exists with `version: 2` header
- [x] All 3 fact models documented: `fct_transit_delays`, `fct_bike_trips`, `fct_daily_mobility`
- [x] Each model has a `description` field summarizing its grain, row count estimate, and primary use case
- [x] Every column across all 3 models has a `description` field (10 + 9 + 16 = 35 column descriptions total)
- [x] **PK tests — fct_transit_delays**: `delay_sk` has `unique` and `not_null` tests
- [x] **PK tests — fct_bike_trips**: `trip_sk` has `unique` and `not_null` tests
- [x] **PK tests — fct_daily_mobility**: `date_key` has `unique` and `not_null` tests
- [x] **FK test — fct_transit_delays.date_key**: `relationships` to `dim_date` (field: `date_key`)
- [x] **FK test — fct_transit_delays.station_key**: `relationships` to `dim_station` (field: `station_key`) with `config: {where: "station_key is not null"}`
- [x] **FK test — fct_transit_delays.delay_code_key**: `relationships` to `dim_ttc_delay_codes` (field: `delay_code_key`) with `config: {where: "delay_code_key is not null"}`
- [x] **FK test — fct_bike_trips.date_key**: `relationships` to `dim_date` (field: `date_key`)
- [x] **FK test — fct_bike_trips.start_station_key**: `relationships` to `dim_station` (field: `station_key`) with `config: {where: "start_station_key is not null"}`
- [x] **FK test — fct_bike_trips.end_station_key**: `relationships` to `dim_station` (field: `station_key`) with `config: {where: "end_station_key is not null"}`
- [x] **FK test — fct_daily_mobility.date_key**: `relationships` to `dim_date` (field: `date_key`)
- [x] **Categorical test — fct_transit_delays.transit_mode**: `accepted_values` with `['subway', 'bus', 'streetcar']`
- [x] **Categorical test — fct_bike_trips.user_type**: `accepted_values` with `['Annual Member', 'Casual Member']`
- [x] `dbt parse` succeeds with zero errors after YAML file is added
- [x] All defined schema tests execute and pass via `dbt test --select fct_transit_delays fct_bike_trips fct_daily_mobility`
- [x] Total test count: 3 PK uniqueness + 3 PK not_null + 7 FK relationships + 2 accepted_values = 15 tests minimum

**Technical Notes**: The `relationships` tests on nullable FK columns (`station_key`, `delay_code_key`, `start_station_key`, `end_station_key`) require a `where` config to exclude NULL values — dbt's default `relationships` test fails on NULL FKs because NULL does not match any PK. The `where` clause must reference the column name exactly as it appears in the model (e.g., `station_key is not null`, not `dim_station.station_key is not null`). Column descriptions follow the technical documentation voice defined in CLAUDE.md Section 1.2. The `.gitkeep` file in `models/marts/mobility/` must be removed as part of this story or an earlier one.

**Definition of Done**:

- [x] Code committed to feature branch
- [x] `dbt parse` passes locally
- [x] All 15+ defined schema tests pass against Snowflake target
- [x] PR opened with linked issue
- [x] CI checks green

## Exit Criteria

This epic is complete when:

- [x] `fct_transit_delays` materializes as a table with ~1.8M rows and surrogate FK keys aligned with `dim_date`, `dim_station`, and `dim_ttc_delay_codes`
- [x] `fct_bike_trips` materializes as a table with ~30M rows and surrogate FK keys aligned with `dim_date` and `dim_station`
- [x] `fct_daily_mobility` materializes as a table with ~2,200 rows joining transit and bike daily metrics via FULL OUTER JOIN
- [x] `_mobility__models.yml` documents all 3 models with 35 column descriptions
- [x] All PK tests pass: `unique` and `not_null` on `delay_sk`, `trip_sk`, `date_key`
- [x] All FK `relationships` tests pass: 7 FK references validated against dimension PKs
- [x] All `accepted_values` tests pass: `transit_mode`, `user_type`
- [x] `dbt build --select marts` passes with zero test failures (dimensions + facts combined)
- [x] `.gitkeep` removed from `models/marts/mobility/`

# Staging Source Definitions & TTC Delay Models

| Field        | Value          |
| ------------ | -------------- |
| Epic ID      | E-501          |
| Phase        | PH-05          |
| Owner        | @dinesh-git17  |
| Status       | Complete       |
| Dependencies | [E-401, E-402] |
| Created      | 2026-02-09     |

## Context

The staging layer is the first transformation tier in the medallion architecture, converting raw VARCHAR columns into typed, consistently named views. PH-04 delivered all reference seed data (station mappings, delay codes, bike station reference, date spine) that downstream intermediate and mart models require. This epic establishes dbt source definitions for all five RAW tables and implements the three TTC delay staging models that share a common structural pattern. Source freshness checks (warn at 45 days, error at 90 days per DESIGN-DOC Section 7.4) provide automated data staleness detection. All staging models materialize as views per DESIGN-DOC Section 6.3 and produce surrogate keys via `dbt_utils.generate_surrogate_key()` per Section 6.4.

## Scope

### In Scope

- Source YAML definitions for all 5 RAW tables across 3 domain directories (`ttc/`, `bike_share/`, `weather/`)
- Source freshness configuration with `loaded_at_field` per table
- `stg_ttc_subway_delays` staging view with type casting, surrogate key, and `transit_mode = 'subway'`
- `stg_ttc_bus_delays` staging view with type casting, surrogate key, and `transit_mode = 'bus'`
- `stg_ttc_streetcar_delays` staging view with type casting, surrogate key, and `transit_mode = 'streetcar'`
- Model documentation YAML (`_ttc__models.yml`) with column descriptions for all 3 TTC models
- Schema tests: `unique` and `not_null` on all TTC surrogate keys, `accepted_values` on categorical columns

### Out of Scope

- Bike Share and Weather staging models (E-502)
- Intermediate layer union or enrichment logic (PH-06)
- Station name mapping joins (intermediate layer responsibility)
- Delay code enrichment joins (intermediate layer responsibility)
- Business logic filtering beyond basic data quality (zero-delay exclusion)

## Technical Approach

### Architecture Decisions

- **Materialization: Views** — Staging models materialize as views per DESIGN-DOC Section 6.3; no persistent storage consumed, always computed from RAW
- **Source splitting across YAML files** — Each domain directory (`ttc/`, `bike_share/`, `weather/`) defines its own `_<domain>__sources.yml` file contributing tables to the shared `raw` source name; dbt merges source definitions across YAML files when the source name matches
- **CTE pattern: source → renamed → select** — Standard dbt staging pattern separating source reference from transformation logic, matching the example in DESIGN-DOC Section 7.4
- **Surrogate key natural components** — Subway: `[date, time, station, line, code, min_delay]`; Bus/Streetcar: `[date, time, route, direction, delay_code, min_delay]` per DESIGN-DOC Section 6.4
- **Column naming: snake_case** — All output columns use lowercase snake_case regardless of RAW UPPER_SNAKE_CASE source columns; Snowflake treats unquoted identifiers as case-insensitive
- **Zero-delay exclusion** — TTC staging models filter `MIN_DELAY > 0` as shown in DESIGN-DOC Section 7.4 example code; zero-delay records represent non-events

### Integration Points

- **RAW schema tables** — `TORONTO_MOBILITY.RAW.TTC_SUBWAY_DELAYS`, `TTC_BUS_DELAYS`, `TTC_STREETCAR_DELAYS`, `BIKE_SHARE_TRIPS`, `WEATHER_DAILY` (DDL in `setup/create_ingestion_stage.sql`)
- **dbt_utils package** — `generate_surrogate_key()` macro (pinned v1.3.0 in `packages.yml`)
- **generate_schema_name macro** — Routes staging models to `STAGING` schema via path detection (`macros/generate_schema_name.sql`)
- **dbt_project.yml** — Staging materialization already configured as `view` under `models.toronto_mobility.staging`

### Repository Areas

- `models/staging/ttc/_ttc__sources.yml` (new)
- `models/staging/bike_share/_bike_share__sources.yml` (new)
- `models/staging/weather/_weather__sources.yml` (new)
- `models/staging/ttc/stg_ttc_subway_delays.sql` (new)
- `models/staging/ttc/stg_ttc_bus_delays.sql` (new)
- `models/staging/ttc/stg_ttc_streetcar_delays.sql` (new)
- `models/staging/ttc/_ttc__models.yml` (new)

### Risks

| Risk                                                                           | Likelihood | Impact | Mitigation                                                                                                                                              |
| ------------------------------------------------------------------------------ | ---------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| VARCHAR to DATE/TIME/INTEGER cast failures on malformed RAW data               | Medium     | High   | Use `TRY_CAST` for numeric columns; validate cast success rates in tests; RAW data already passed schema validation in E-302                            |
| Source freshness `loaded_at_field` requires castable VARCHAR date column       | Low        | Medium | RAW tables store date strings in ISO-like formats; Snowflake implicit casting from VARCHAR to TIMESTAMP handles standard date formats                   |
| Surrogate key collisions from duplicate natural key combinations               | Low        | High   | `unique` test on surrogate key column catches collisions at build time; natural key components chosen per DESIGN-DOC Section 6.4 analysis               |
| Bus/Streetcar RAW column name differences from subway cause incorrect mappings | Low        | Medium | Column names verified against `setup/create_ingestion_stage.sql` DDL; bus/streetcar share identical RAW schema (ROUTE, LOCATION, DELAY_CODE, DIRECTION) |

## Stories

| ID   | Story                                                                         | Points | Dependencies     | Status |
| ---- | ----------------------------------------------------------------------------- | ------ | ---------------- | ------ |
| S001 | Define raw data sources with freshness checks across all 3 domain directories | 5      | None             | Draft  |
| S002 | Build stg_ttc_subway_delays staging view                                      | 5      | S001             | Draft  |
| S003 | Build stg_ttc_bus_delays staging view                                         | 3      | S001             | Draft  |
| S004 | Build stg_ttc_streetcar_delays staging view                                   | 2      | S001             | Draft  |
| S005 | Document TTC staging models and add schema tests                              | 5      | S002, S003, S004 | Draft  |

---

### S001: Define Raw Data Sources with Freshness Checks Across All 3 Domain Directories

**Description**: Create dbt source YAML definitions for all 5 RAW tables, split across `_ttc__sources.yml`, `_bike_share__sources.yml`, and `_weather__sources.yml`, each with freshness check configuration.

**Acceptance Criteria**:

- [ ] File `models/staging/ttc/_ttc__sources.yml` defines source `raw` with database `TORONTO_MOBILITY`, schema `RAW`, and tables `ttc_subway_delays`, `ttc_bus_delays`, `ttc_streetcar_delays`
- [ ] File `models/staging/bike_share/_bike_share__sources.yml` defines source `raw` with database `TORONTO_MOBILITY`, schema `RAW`, and table `bike_share_trips`
- [ ] File `models/staging/weather/_weather__sources.yml` defines source `raw` with database `TORONTO_MOBILITY`, schema `RAW`, and table `weather_daily`
- [ ] TTC source tables specify `loaded_at_field: date` for freshness tracking
- [ ] Bike Share source table specifies `loaded_at_field: start_time` for freshness tracking
- [ ] Weather source table specifies `loaded_at_field: date_time` for freshness tracking
- [ ] All 5 source tables include `freshness.warn_after: {count: 45, period: day}` and `freshness.error_after: {count: 90, period: day}`
- [ ] Each source table includes a `description` field summarizing its contents and grain
- [ ] Each source table lists all columns matching the RAW DDL in `setup/create_ingestion_stage.sql`
- [ ] `dbt parse` succeeds with zero errors after all 3 source files are added
- [ ] `.gitkeep` files removed from `models/staging/ttc/`, `models/staging/bike_share/`, `models/staging/weather/`

**Technical Notes**: Source YAML files contribute to the shared `raw` source name. dbt merges tables from multiple YAML files under the same source name. Column lists in source definitions must use UPPER_SNAKE_CASE to match Snowflake RAW table DDL. The `loaded_at_field` references the primary date/timestamp column in each table for freshness comparison against `CURRENT_TIMESTAMP()`.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `dbt parse` passes locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S002: Build stg_ttc_subway_delays Staging View

**Description**: Create the `stg_ttc_subway_delays` dbt model as a view that type-casts all VARCHAR columns from `raw.ttc_subway_delays`, generates a surrogate key, adds `transit_mode`, and filters zero-delay records.

**Acceptance Criteria**:

- [ ] File `models/staging/ttc/stg_ttc_subway_delays.sql` exists with `config(materialized='view')`
- [ ] Model uses CTE pattern: `source` CTE selects from `{{ source('raw', 'ttc_subway_delays') }}`; `renamed` CTE applies all transformations
- [ ] Surrogate key `delay_sk` generated via `{{ dbt_utils.generate_surrogate_key(['date', 'time', 'station', 'line', 'code', 'min_delay']) }}`
- [ ] Column `date` cast to `DATE` type as `delay_date`
- [ ] Column `time` cast to `TIME` type as `delay_time`
- [ ] Computed column `incident_timestamp` produced via `timestamp_from_parts(date::date, time::time)`
- [ ] Column `day` renamed to `day_of_week` (VARCHAR, no cast)
- [ ] Column `station` renamed to `raw_station_name` (VARCHAR, no cast)
- [ ] Column `code` renamed to `delay_code` (VARCHAR, no cast)
- [ ] Column `min_delay` cast to `INTEGER` as `delay_minutes`
- [ ] Column `min_gap` cast to `INTEGER` as `gap_minutes`
- [ ] Column `bound` renamed to `direction` (VARCHAR, no cast)
- [ ] Column `line` renamed to `line_code` (VARCHAR, no cast)
- [ ] Literal column `transit_mode` added with value `'subway'`
- [ ] WHERE clause filters `min_delay::int > 0` to exclude zero-delay records
- [ ] `dbt run --select stg_ttc_subway_delays` succeeds against Snowflake target
- [ ] Output view contains exactly 14 columns: `delay_sk`, `delay_date`, `delay_time`, `incident_timestamp`, `day_of_week`, `raw_station_name`, `delay_code`, `delay_minutes`, `gap_minutes`, `direction`, `line_code`, `transit_mode`

**Technical Notes**: RAW columns are all VARCHAR. Snowflake's `::date`, `::time`, `::int` cast operators convert standard format strings. `timestamp_from_parts` combines separate date and time components into a single TIMESTAMP_NTZ value. The 12-column output (plus surrogate key and transit_mode = 14 total) establishes the pattern for bus and streetcar models. Null values in CODE, MIN_GAP, and BOUND are preserved as NULL after casting.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Model compiles and runs locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S003: Build stg_ttc_bus_delays Staging View

**Description**: Create the `stg_ttc_bus_delays` dbt model as a view that type-casts all VARCHAR columns from `raw.ttc_bus_delays`, generates a surrogate key using bus-specific natural key components, and adds `transit_mode = 'bus'`.

**Acceptance Criteria**:

- [ ] File `models/staging/ttc/stg_ttc_bus_delays.sql` exists with `config(materialized='view')`
- [ ] Model uses CTE pattern: `source` CTE selects from `{{ source('raw', 'ttc_bus_delays') }}`; `renamed` CTE applies all transformations
- [ ] Surrogate key `delay_sk` generated via `{{ dbt_utils.generate_surrogate_key(['date', 'time', 'route', 'direction', 'delay_code', 'min_delay']) }}`
- [ ] Column `date` cast to `DATE` type as `delay_date`
- [ ] Column `time` cast to `TIME` type as `delay_time`
- [ ] Computed column `incident_timestamp` produced via `timestamp_from_parts(date::date, time::time)`
- [ ] Column `day` renamed to `day_of_week` (VARCHAR, no cast)
- [ ] Column `route` kept as `route` (VARCHAR, no cast)
- [ ] Column `location` kept as `location` (VARCHAR, no cast)
- [ ] Column `delay_code` kept as `delay_code` (VARCHAR, no cast)
- [ ] Column `min_delay` cast to `INTEGER` as `delay_minutes`
- [ ] Column `min_gap` cast to `INTEGER` as `gap_minutes`
- [ ] Column `direction` kept as `direction` (VARCHAR, no cast)
- [ ] Literal column `transit_mode` added with value `'bus'`
- [ ] WHERE clause filters `min_delay::int > 0` to exclude zero-delay records
- [ ] `dbt run --select stg_ttc_bus_delays` succeeds against Snowflake target
- [ ] Output view contains exactly 13 columns: `delay_sk`, `delay_date`, `delay_time`, `incident_timestamp`, `day_of_week`, `route`, `location`, `delay_code`, `delay_minutes`, `gap_minutes`, `direction`, `transit_mode`

**Technical Notes**: Bus RAW schema differs from subway: uses ROUTE instead of LINE, LOCATION instead of STATION, and DELAY_CODE instead of CODE (renamed from source "Incident" during ingestion per E-303). The surrogate key uses `[date, time, route, direction, delay_code, min_delay]` per DESIGN-DOC Section 6.4. Bus model outputs `route` and `location` columns; the intermediate union layer (PH-06) reconciles column names across transit modes.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Model compiles and runs locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S004: Build stg_ttc_streetcar_delays Staging View

**Description**: Create the `stg_ttc_streetcar_delays` dbt model as a view using identical column structure to `stg_ttc_bus_delays` (both share the same RAW schema after ingestion renaming) with `transit_mode = 'streetcar'`.

**Acceptance Criteria**:

- [ ] File `models/staging/ttc/stg_ttc_streetcar_delays.sql` exists with `config(materialized='view')`
- [ ] Model uses CTE pattern: `source` CTE selects from `{{ source('raw', 'ttc_streetcar_delays') }}`; `renamed` CTE applies all transformations
- [ ] Surrogate key `delay_sk` generated via `{{ dbt_utils.generate_surrogate_key(['date', 'time', 'route', 'direction', 'delay_code', 'min_delay']) }}`
- [ ] Column mappings identical to `stg_ttc_bus_delays` (S003): `delay_date`, `delay_time`, `incident_timestamp`, `day_of_week`, `route`, `location`, `delay_code`, `delay_minutes`, `gap_minutes`, `direction`
- [ ] Literal column `transit_mode` added with value `'streetcar'`
- [ ] WHERE clause filters `min_delay::int > 0` to exclude zero-delay records
- [ ] `dbt run --select stg_ttc_streetcar_delays` succeeds against Snowflake target
- [ ] Output column count and names match `stg_ttc_bus_delays` exactly (13 columns), differing only in `transit_mode` value

**Technical Notes**: Streetcar RAW table uses the same column names as bus (ROUTE, LOCATION, DELAY_CODE, DIRECTION) because the ingestion pipeline (E-303) renamed source columns Line→ROUTE, Incident→DELAY_CODE, Bound→DIRECTION for cross-mode consistency. This model is structurally identical to `stg_ttc_bus_delays` except for the source table reference and `transit_mode` literal.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Model compiles and runs locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S005: Document TTC Staging Models and Add Schema Tests

**Description**: Create `_ttc__models.yml` with column-level descriptions for all 3 TTC staging models and add `unique`, `not_null`, and `accepted_values` schema tests.

**Acceptance Criteria**:

- [ ] File `models/staging/ttc/_ttc__models.yml` defines all 3 models: `stg_ttc_subway_delays`, `stg_ttc_bus_delays`, `stg_ttc_streetcar_delays`
- [ ] Each model includes a `description` field summarizing its source, grain, and key transformations
- [ ] Every column in each model has a `description` field (no missing column descriptions)
- [ ] `delay_sk` column in all 3 models has `unique` and `not_null` tests
- [ ] `delay_date` column in all 3 models has `not_null` test
- [ ] `delay_minutes` column in all 3 models has `not_null` test
- [ ] `transit_mode` column in `stg_ttc_subway_delays` has `accepted_values` test with values `['subway']`
- [ ] `transit_mode` column in `stg_ttc_bus_delays` has `accepted_values` test with values `['bus']`
- [ ] `transit_mode` column in `stg_ttc_streetcar_delays` has `accepted_values` test with values `['streetcar']`
- [ ] `line_code` column in `stg_ttc_subway_delays` has `accepted_values` test with values `['YU', 'BD', 'SHP', 'SRT']`
- [ ] `direction` column in `stg_ttc_subway_delays` has `accepted_values` test with values `['N', 'S', 'E', 'W']` and `quote: false` configuration
- [ ] `dbt parse` succeeds with zero errors after YAML file is added
- [ ] `dbt test --select stg_ttc_subway_delays stg_ttc_bus_delays stg_ttc_streetcar_delays` executes all defined tests

**Technical Notes**: Column descriptions follow the technical documentation voice specified in CLAUDE.md Section 1.2. Tests enforce data quality invariants at the staging boundary. The `accepted_values` test on `transit_mode` serves as a regression guard against incorrect literal assignment. The `direction` `accepted_values` test uses `quote: false` because Snowflake stores single-character compass values without quoting needs.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `dbt parse` passes locally
- [ ] All defined tests pass against Snowflake target
- [ ] PR opened with linked issue
- [ ] CI checks green

## Exit Criteria

This epic is complete when:

- [ ] All 5 stories marked complete
- [ ] Source definitions exist for all 5 RAW tables across 3 YAML files
- [ ] All 3 TTC staging models compile and produce views in `STAGING` schema
- [ ] Source freshness checks configured with 45-day warn / 90-day error thresholds
- [ ] All surrogate keys pass `unique` and `not_null` tests
- [ ] All `accepted_values` tests pass on categorical columns
- [ ] Column-level documentation complete for all 3 TTC staging models
- [ ] `dbt build --select stg_ttc_subway_delays stg_ttc_bus_delays stg_ttc_streetcar_delays` passes with zero failures

# Bike Share & Weather Staging Models with Layer Validation

| Field        | Value         |
| ------------ | ------------- |
| Epic ID      | E-502         |
| Phase        | PH-05         |
| Owner        | @dinesh-git17 |
| Status       | Complete      |
| Dependencies | [E-501]       |
| Created      | 2026-02-09    |

## Context

E-501 establishes the source definitions and TTC delay staging pattern. This epic completes the staging layer by implementing the two remaining models — `stg_bike_trips` and `stg_weather_daily` — which have structurally distinct schemas from TTC delays. The Bike Share staging model applies the mandatory trip duration filter (>= 60 seconds per DESIGN-DOC Section 4.3.2 and Decision D9) that excludes accidental undocks before downstream processing. The Weather staging model transforms 31 Environment Canada VARCHAR columns into typed measurement fields required by `dim_weather` in PH-07. This epic concludes with full staging layer validation against the PH-05 exit criterion: `dbt build --select staging` passes with all tests green.

## Scope

### In Scope

- `stg_bike_trips` staging view with type casting, surrogate key from `trip_id`, and duration >= 60s filter
- `stg_weather_daily` staging view with type casting of 31 VARCHAR columns to typed measurement fields
- Model documentation YAML (`_bike_share__models.yml`) with column descriptions and schema tests
- Model documentation YAML (`_weather__models.yml`) with column descriptions and schema tests
- End-to-end staging layer build validation: `dbt build --select staging` with zero failures
- Row count validation between RAW and staging (accounting for filtered bike trips)

### Out of Scope

- Weather condition classification (intermediate/mart layer responsibility per `dim_weather` spec)
- Bike station geography enrichment joins (intermediate layer, `int_bike_trips_enriched`)
- Duration bucket computation (intermediate layer responsibility)
- TTC staging models (completed in E-501)
- Source YAML definitions (completed in E-501)

## Technical Approach

### Architecture Decisions

- **Bike trip filter at staging layer** — Duration >= 60 seconds filter applied in staging per DESIGN-DOC Section 4.3.2, consistent with the bike trip example `filter: duration >= 60 seconds` specified in Section 6.3; this is a data quality filter, not business logic
- **Weather column selection** — Staging model includes all 15 measurement columns (temperatures, precipitation, wind, degree days) and excludes the 15 flag columns and station metadata columns (LONGITUDE, LATITUDE, STATION_NAME, CLIMATE_ID, YEAR, MONTH, DAY, DATA_QUALITY); flag columns contain single-character quality indicators that provide no downstream analytical value
- **Numeric casting strategy** — Weather measurements use `TRY_CAST(... AS DECIMAL(10,1))` rather than bare `::decimal` to gracefully return NULL for non-numeric values in optional measurement columns; bike trip integers use `::int` since TRIP_DURATION, STATION_ID, and BIKE_ID are validated at ingestion
- **Surrogate key: bike trips** — Generated from `[trip_id]` per DESIGN-DOC Section 6.4; source provides unique natural identifier per trip
- **Surrogate key: weather** — Generated from `[date_time]` as the natural key; one row per observation day

### Integration Points

- **E-501 source definitions** — `stg_bike_trips` references `{{ source('raw', 'bike_share_trips') }}`; `stg_weather_daily` references `{{ source('raw', 'weather_daily') }}`; both sources defined in E-501 S001
- **RAW table DDL** — `BIKE_SHARE_TRIPS` (10 VARCHAR columns) and `WEATHER_DAILY` (31 VARCHAR columns) per `setup/create_ingestion_stage.sql`
- **Downstream consumers** — `stg_bike_trips` feeds `int_bike_trips_enriched` (PH-06); `stg_weather_daily` feeds `dim_weather` (PH-07)
- **dbt_utils package** — `generate_surrogate_key()` macro (pinned v1.3.0)

### Repository Areas

- `models/staging/bike_share/stg_bike_trips.sql` (new)
- `models/staging/bike_share/_bike_share__models.yml` (new)
- `models/staging/weather/stg_weather_daily.sql` (new)
- `models/staging/weather/_weather__models.yml` (new)

### Risks

| Risk                                                                                       | Likelihood | Impact | Mitigation                                                                                                                                        |
| ------------------------------------------------------------------------------------------ | ---------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Bike Share TRIP_DURATION contains non-integer values causing cast failures                 | Low        | High   | Ingestion schema validation (E-302) enforces integer pattern; use `TRY_CAST` as fallback if edge cases surface                                    |
| Weather measurement columns contain non-numeric strings beyond empty/NULL                  | Medium     | Medium | `TRY_CAST` returns NULL for unparseable values; Environment Canada uses empty strings for missing readings which Snowflake treats as NULL on cast |
| Row count discrepancy between RAW and staging exceeds expectations due to bike trip filter | Low        | Low    | Document expected filtered percentage (~5-10% of trips under 60s); validation story S005 explicitly compares counts with tolerance                |
| Weather RAW table has 31 columns; selecting wrong column names causes silent NULLs         | Low        | High   | Column names verified against `setup/create_ingestion_stage.sql` DDL; staging model references exact UPPER_SNAKE_CASE names from DDL              |

## Stories

| ID   | Story                                                         | Points | Dependencies                       | Status |
| ---- | ------------------------------------------------------------- | ------ | ---------------------------------- | ------ |
| S001 | Build stg_bike_trips staging view with duration filter        | 5      | E-501.S001                         | Draft  |
| S002 | Build stg_weather_daily staging view                          | 5      | E-501.S001                         | Draft  |
| S003 | Document Bike Share staging model and add schema tests        | 3      | S001                               | Draft  |
| S004 | Document Weather staging model and add schema tests           | 3      | S002                               | Draft  |
| S005 | Validate full staging layer build against PH-05 exit criteria | 3      | S001, S002, S003, S004, E-501.S005 | Draft  |

---

### S001: Build stg_bike_trips Staging View with Duration Filter

**Description**: Create the `stg_bike_trips` dbt model as a view that type-casts all VARCHAR columns from `raw.bike_share_trips`, generates a surrogate key from `trip_id`, and filters trips with duration under 60 seconds.

**Acceptance Criteria**:

- [ ] File `models/staging/bike_share/stg_bike_trips.sql` exists with `config(materialized='view')`
- [ ] Model uses CTE pattern: `source` CTE selects from `{{ source('raw', 'bike_share_trips') }}`; `renamed` CTE applies all transformations
- [ ] Surrogate key `trip_sk` generated via `{{ dbt_utils.generate_surrogate_key(['trip_id']) }}`
- [ ] Column `trip_id` kept as `trip_id` (VARCHAR, no cast)
- [ ] Column `trip_duration` cast to `INTEGER` as `trip_duration_seconds`
- [ ] Column `start_station_id` cast to `INTEGER` as `start_station_id`
- [ ] Column `start_time` cast to `TIMESTAMP_NTZ` as `start_time`
- [ ] Column `start_station_name` kept as `start_station_name` (VARCHAR, no cast)
- [ ] Column `end_station_id` cast to `INTEGER` as `end_station_id`
- [ ] Column `end_time` cast to `TIMESTAMP_NTZ` as `end_time`
- [ ] Column `end_station_name` kept as `end_station_name` (VARCHAR, no cast)
- [ ] Column `bike_id` cast to `INTEGER` as `bike_id`
- [ ] Column `user_type` kept as `user_type` (VARCHAR, no cast)
- [ ] WHERE clause filters `trip_duration::int >= 60` per DESIGN-DOC Decision D9
- [ ] `dbt run --select stg_bike_trips` succeeds against Snowflake target
- [ ] Output view contains exactly 12 columns: `trip_sk`, `trip_id`, `trip_duration_seconds`, `start_station_id`, `start_time`, `start_station_name`, `end_station_id`, `end_time`, `end_station_name`, `bike_id`, `user_type`
- [ ] `.gitkeep` removed from `models/staging/bike_share/` if still present

**Technical Notes**: The RAW `TRIP_DURATION` column stores duration in seconds as VARCHAR. Bike Share source data may contain literal "NULL" strings for missing values (identified in E-302); Snowflake casts "NULL" strings to SQL NULL on `::int` conversion, which then fails the `>= 60` filter and is correctly excluded. The `start_time` and `end_time` columns use `::timestamp_ntz` to parse the Bike Share timestamp format (`M/D/YYYY H:MM` with single-digit day/hour).

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Model compiles and runs locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S002: Build stg_weather_daily Staging View

**Description**: Create the `stg_weather_daily` dbt model as a view that type-casts the 31 VARCHAR columns from `raw.weather_daily` into typed measurement fields, extracting the 15 measurement columns and excluding flag and metadata columns.

**Acceptance Criteria**:

- [ ] File `models/staging/weather/stg_weather_daily.sql` exists with `config(materialized='view')`
- [ ] Model uses CTE pattern: `source` CTE selects from `{{ source('raw', 'weather_daily') }}`; `renamed` CTE applies all transformations
- [ ] Surrogate key `weather_sk` generated via `{{ dbt_utils.generate_surrogate_key(['date_time']) }}`
- [ ] Column `date_time` cast to `DATE` as `weather_date`
- [ ] Column `max_temp_c` cast to `DECIMAL(10,1)` via `TRY_CAST` as `max_temp_c`
- [ ] Column `min_temp_c` cast to `DECIMAL(10,1)` via `TRY_CAST` as `min_temp_c`
- [ ] Column `mean_temp_c` cast to `DECIMAL(10,1)` via `TRY_CAST` as `mean_temp_c`
- [ ] Column `heat_deg_days_c` cast to `DECIMAL(10,1)` via `TRY_CAST` as `heat_degree_days`
- [ ] Column `cool_deg_days_c` cast to `DECIMAL(10,1)` via `TRY_CAST` as `cool_degree_days`
- [ ] Column `total_rain_mm` cast to `DECIMAL(10,1)` via `TRY_CAST` as `total_rain_mm`
- [ ] Column `total_snow_cm` cast to `DECIMAL(10,1)` via `TRY_CAST` as `total_snow_cm`
- [ ] Column `total_precip_mm` cast to `DECIMAL(10,1)` via `TRY_CAST` as `total_precip_mm`
- [ ] Column `snow_on_grnd_cm` cast to `DECIMAL(10,1)` via `TRY_CAST` as `snow_on_ground_cm`
- [ ] Column `spd_of_max_gust_kmh` cast to `DECIMAL(10,1)` via `TRY_CAST` as `max_wind_gust_kmh`
- [ ] Column `dir_of_max_gust_10s_deg` cast to `INTEGER` via `TRY_CAST` as `max_wind_gust_dir_deg`
- [ ] Flag columns (MAX_TEMP_FLAG, MIN_TEMP_FLAG, MEAN_TEMP_FLAG, HEAT_DEG_DAYS_FLAG, COOL_DEG_DAYS_FLAG, TOTAL_RAIN_FLAG, TOTAL_SNOW_FLAG, TOTAL_PRECIP_FLAG, SNOW_ON_GRND_FLAG, DIR_OF_MAX_GUST_FLAG, SPD_OF_MAX_GUST_FLAG) excluded from output
- [ ] Metadata columns (LONGITUDE, LATITUDE, STATION_NAME, CLIMATE_ID, YEAR, MONTH, DAY, DATA_QUALITY) excluded from output
- [ ] `dbt run --select stg_weather_daily` succeeds against Snowflake target
- [ ] Output view contains exactly 14 columns: `weather_sk`, `weather_date`, `max_temp_c`, `min_temp_c`, `mean_temp_c`, `heat_degree_days`, `cool_degree_days`, `total_rain_mm`, `total_snow_cm`, `total_precip_mm`, `snow_on_ground_cm`, `max_wind_gust_kmh`, `max_wind_gust_dir_deg`
- [ ] `.gitkeep` removed from `models/staging/weather/` if still present

**Technical Notes**: The RAW `WEATHER_DAILY` table preserves all 31 Environment Canada daily climate columns as VARCHAR. `TRY_CAST` is used instead of direct `::decimal` casting because measurement columns may contain empty strings or special characters from Environment Canada's data quality process; `TRY_CAST` returns NULL for unparseable values. The output excludes 11 flag columns (single-character quality indicators: M=missing, E=estimated, empty=observed) and 8 metadata columns (station location and time decomposition) that provide no downstream analytical value. The `weather_date` column serves as the join key to `dim_date.full_date` in downstream mart models.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Model compiles and runs locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S003: Document Bike Share Staging Model and Add Schema Tests

**Description**: Create `_bike_share__models.yml` with column-level descriptions for `stg_bike_trips` and add surrogate key, nullability, and categorical schema tests.

**Acceptance Criteria**:

- [ ] File `models/staging/bike_share/_bike_share__models.yml` defines model `stg_bike_trips`
- [ ] Model `description` field summarizes source, grain (one row per trip with duration >= 60s), and key transformations
- [ ] Every column in `stg_bike_trips` has a `description` field (12 columns total, no missing descriptions)
- [ ] `trip_sk` column has `unique` and `not_null` tests
- [ ] `trip_id` column has `unique` and `not_null` tests
- [ ] `trip_duration_seconds` column has `not_null` test
- [ ] `start_time` column has `not_null` test
- [ ] `user_type` column has `accepted_values` test with values `['Annual Member', 'Casual Member']`
- [ ] `dbt parse` succeeds with zero errors after YAML file is added
- [ ] `dbt test --select stg_bike_trips` executes all defined tests

**Technical Notes**: The `trip_id` column receives both `unique` and `not_null` tests because it is the natural key from the source system and the sole component of the surrogate key. The `user_type` accepted values match the two categories documented in DESIGN-DOC Section 4.3.2. Both `trip_sk` and `trip_id` uniqueness tests are retained: `trip_sk` validates the surrogate key generation, `trip_id` validates source data integrity.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `dbt parse` passes locally
- [ ] All defined tests pass against Snowflake target
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S004: Document Weather Staging Model and Add Schema Tests

**Description**: Create `_weather__models.yml` with column-level descriptions for `stg_weather_daily` and add surrogate key and nullability schema tests.

**Acceptance Criteria**:

- [ ] File `models/staging/weather/_weather__models.yml` defines model `stg_weather_daily`
- [ ] Model `description` field summarizes source (Environment Canada Toronto Pearson Station ID 51459), grain (one row per calendar day), and transformation approach (TRY_CAST for measurements, flag/metadata exclusion)
- [ ] Every column in `stg_weather_daily` has a `description` field (14 columns total, no missing descriptions)
- [ ] `weather_sk` column has `unique` and `not_null` tests
- [ ] `weather_date` column has `unique` and `not_null` tests
- [ ] `mean_temp_c` column does NOT have a `not_null` test (measurement may be legitimately missing)
- [ ] `dbt parse` succeeds with zero errors after YAML file is added
- [ ] `dbt test --select stg_weather_daily` executes all defined tests

**Technical Notes**: Weather measurement columns are intentionally not tested for `not_null` because Environment Canada marks certain days as missing data (flag column value "M"). The `weather_date` uniqueness test validates the one-row-per-day grain invariant. Only `weather_sk`, `weather_date` receive `not_null` and `unique` tests since these are the structural guarantees; measurement columns have inherent gaps in the source data.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `dbt parse` passes locally
- [ ] All defined tests pass against Snowflake target
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S005: Validate Full Staging Layer Build Against PH-05 Exit Criteria

**Description**: Execute `dbt build --select staging` to compile, run, and test all 5 staging models, 3 source definitions, and all schema tests in a single invocation, validating the PH-05 exit criterion.

**Acceptance Criteria**:

- [ ] `dbt build --select staging` completes with exit code 0
- [ ] All 5 staging views created in `TORONTO_MOBILITY.STAGING` schema: `STG_TTC_SUBWAY_DELAYS`, `STG_TTC_BUS_DELAYS`, `STG_TTC_STREETCAR_DELAYS`, `STG_BIKE_TRIPS`, `STG_WEATHER_DAILY`
- [ ] All `unique` tests pass on surrogate keys (`delay_sk` x3, `trip_sk` x1, `weather_sk` x1)
- [ ] All `not_null` tests pass on required columns across all 5 models
- [ ] All `accepted_values` tests pass on categorical columns (`transit_mode`, `line_code`, `direction`, `user_type`)
- [ ] `dbt source freshness --select source:raw` executes without errors (warn/error thresholds may trigger based on data recency, but the command itself must succeed)
- [ ] `stg_bike_trips` row count is less than `raw.bike_share_trips` row count (confirming duration filter is active)
- [ ] `stg_ttc_subway_delays` row count is less than `raw.ttc_subway_delays` row count (confirming zero-delay filter is active)
- [ ] No `.gitkeep` files remain in any `models/staging/` subdirectory
- [ ] All models documented: zero missing column descriptions across all 3 `_*__models.yml` files

**Technical Notes**: This validation story serves as the phase gate. The `dbt build` command runs models and tests in dependency order. Source freshness checks may produce warnings if RAW data has not been refreshed within 45 days; this is expected and does not block the exit criterion. Row count comparisons between RAW and staging are directional checks, not exact counts, because the duration and zero-delay filters intentionally reduce row counts. The command `dbt ls --select staging --resource-type model` should return exactly 5 models.

**Definition of Done**:

- [ ] `dbt build --select staging` passes with zero test failures
- [ ] All staging views queryable in Snowflake `STAGING` schema
- [ ] PR opened with linked issue
- [ ] CI checks green
- [ ] PH-05 exit criterion met

## Exit Criteria

This epic is complete when:

- [ ] All 5 stories marked complete
- [ ] `stg_bike_trips` and `stg_weather_daily` views created in `STAGING` schema
- [ ] Duration >= 60s filter active on `stg_bike_trips` (row count < RAW)
- [ ] All surrogate keys pass `unique` and `not_null` tests
- [ ] Column-level documentation complete for Bike Share and Weather staging models
- [ ] `dbt build --select staging` passes with zero failures (PH-05 exit criterion)
- [ ] Source freshness command executes without configuration errors
- [ ] No `.gitkeep` placeholder files remain in staging model directories

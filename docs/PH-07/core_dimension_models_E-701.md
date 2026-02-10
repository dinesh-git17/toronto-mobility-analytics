# Core Dimension Models

| Field        | Value                 |
| ------------ | --------------------- |
| Epic ID      | E-701                 |
| Phase        | PH-07                 |
| Owner        | @dinesh-git17         |
| Status       | Complete              |
| Dependencies | [E-401, E-402, E-502] |
| Created      | 2026-02-09            |

## Context

The marts layer requires four dimension tables before fact tables can be constructed: `dim_date`, `dim_station`, `dim_weather`, and `dim_ttc_delay_codes`. These dimensions serve as the FK targets for all three fact tables (`fct_transit_delays`, `fct_bike_trips`, `fct_daily_mobility`) and must exist first to enable referential integrity testing. The dimension models consume seed tables (`date_spine`, `ttc_station_mapping`, `ttc_delay_codes`, `bike_station_ref`) and one staging view (`stg_weather_daily`), applying type casting, surrogate key generation, and derived column computation. All mart models materialize as tables per DESIGN-DOC Section 6.3 and `dbt_project.yml` configuration (`models.toronto_mobility.marts.+materialized: table`). Surrogate keys use `dbt_utils.generate_surrogate_key()` per DESIGN-DOC Section 6.4 and CLAUDE.md Section 5.2 — no raw MD5/SHA sequences permitted.

## Scope

### In Scope

- `dim_date` table model in `models/marts/core/`: passthrough from `date_spine` seed with type casting of `is_weekend` and `is_holiday` from string to BOOLEAN and `full_date` from string to DATE
- `dim_station` table model in `models/marts/core/`: unified dimension combining 76 canonical TTC subway stations (from `ttc_station_mapping` seed, deduplicated to canonical level including ST_000 Unknown) and 1,009 Bike Share stations (from `bike_station_ref` seed), with surrogate key generated from composite natural key `[station_type, station_id]`
- `dim_weather` table model in `models/marts/core/`: daily weather dimension from `stg_weather_daily` with derived `weather_condition` classification column and `date_key` computation
- `dim_ttc_delay_codes` table model in `models/marts/core/`: delay code lookup from `ttc_delay_codes` seed with surrogate key generated from natural key `[delay_code]`
- Schema documentation in `models/marts/core/_core__models.yml` with column-level descriptions and tests (`unique`, `not_null` on PKs; `relationships` on FKs; `accepted_values` on categoricals)

### Out of Scope

- Bus and streetcar station entries in `dim_station` (no station reference seed exists for surface routes; bus/streetcar use intersection-level `location` descriptors in the intermediate layer)
- `ward` column in `dim_station` (DESIGN-DOC ER diagram includes it, but no upstream seed provides ward data; deferred to PH-09 or future enrichment)
- Fact table construction (`fct_transit_delays`, `fct_bike_trips`, `fct_daily_mobility`) — covered in E-702
- Seed curation or modification (completed in E-401 and E-402)
- Elementary anomaly detection configuration (deferred to PH-08)

## Technical Approach

### Architecture Decisions

- **Table materialization for all mart dimensions** — Per DESIGN-DOC Section 6.3 and `dbt_project.yml` (`models.toronto_mobility.marts.+materialized: table`); dimensions are query targets and must persist as physical tables in the MARTS schema
- **Surrogate keys via `dbt_utils.generate_surrogate_key()`** — Per DESIGN-DOC Section 6.4 and CLAUDE.md Section 5.2; applied to `dim_station` (composite `[station_type, station_id]`), `dim_ttc_delay_codes` (`[delay_code]`); `dim_date` uses the pre-computed integer `date_key` from the seed as its PK; `dim_weather` uses integer `date_key` derived from `weather_date`
- **SCD strategies match DESIGN-DOC Section 6.2** — `dim_date`: Type 0 (static, generated spine); `dim_station`: Type 1 (overwrite, reflects current state); `dim_weather`: Type 0 (append-only, historical weather is immutable); `dim_ttc_delay_codes`: Type 1 (overwrite, descriptions may be refined)
- **ST_000 (Unknown) included in `dim_station`** — Required for FK integrity: `fct_transit_delays` contains subway records where the station mapping seed resolves to ST_000; omitting it would cause the `relationships` test on `station_key` to fail
- **`dim_station` deduplicates `ttc_station_mapping` to canonical level** — The seed contains 1,101 raw-name-to-canonical mappings; `dim_station` selects `DISTINCT` on `(station_key, canonical_station_name)` to extract 76 canonical rows (75 stations + ST_000 Unknown); the 5 interchange stations (Bloor-Yonge, St. George, Spadina, Sheppard-Yonge, Kennedy) appear once each since they share a single `station_key` across lines
- **Weather condition classification derived from precipitation columns** — `weather_condition` is a categorical column not present in `stg_weather_daily`; classification: `'Snow'` when `total_snow_cm > 0`, `'Rain'` when `total_rain_mm > 0` and `(total_snow_cm = 0 OR total_snow_cm IS NULL)`, `'Clear'` when `total_precip_mm = 0` or `total_precip_mm IS NULL`
- **Boolean casting for date dimension flags** — Seed stores `is_weekend` and `is_holiday` as lowercase strings (`'true'`/`'false'`); mart dimension casts these to Snowflake `BOOLEAN` type for predicate pushdown and ergonomic queries

### Integration Points

- **Upstream seeds** — `date_spine` (2,922 rows, 10 columns), `ttc_station_mapping` (1,101 rows, 4 columns), `ttc_delay_codes` (334 rows, 3 columns), `bike_station_ref` (1,009 rows, 5 columns) — all from E-401/E-402
- **Upstream staging** — `stg_weather_daily` (13 columns, ~2,200 rows) from E-502
- **Downstream consumers** — `fct_transit_delays` (FK: `date_key`, `station_key`, `delay_code_key`), `fct_bike_trips` (FK: `date_key`, `start_station_key`, `end_station_key`), `fct_daily_mobility` (FK: `date_key`) — all in E-702
- **dbt_project.yml** — Mart materialization already configured as `table` with `+schema: marts`

### Repository Areas

- `models/marts/core/dim_date.sql` (new)
- `models/marts/core/dim_station.sql` (new)
- `models/marts/core/dim_weather.sql` (new)
- `models/marts/core/dim_ttc_delay_codes.sql` (new)
- `models/marts/core/_core__models.yml` (new)
- `models/marts/core/.gitkeep` (remove after model files committed)

### Risks

| Risk                                                                                                                                                                                                       | Likelihood | Impact | Mitigation                                                                                                                                                                                                |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `dim_station` surrogate key mismatch with fact tables if `generate_surrogate_key` input literals differ between dimension and fact (e.g., `'TTC_SUBWAY'` vs `'ttc_subway'`)                                | Medium     | High   | Standardize `station_type` as UPPER_SNAKE_CASE constant in both `dim_station` and all fact models; document the exact literal in the story acceptance criteria                                            |
| `dim_weather` `date_key` computation produces integer that does not match `dim_date.date_key` for the same calendar date due to formatting differences (`CAST(TO_CHAR(...))` vs `TO_NUMBER(TO_CHAR(...))`) | Low        | High   | Use identical `date_key` derivation pattern across all models: `cast(to_char(date_col, 'YYYYMMDD') as integer)`; validate via `relationships` test between `dim_weather.date_key` and `dim_date.date_key` |
| `ttc_station_mapping` deduplication produces more than 76 rows due to canonical name variants across line codes (interchange stations mapped with different line_code values)                              | Low        | Medium | `DISTINCT` on `(station_key, canonical_station_name)` without `line_code` yields exactly one row per canonical station; interchange stations share a single `station_key` by design (E-401)               |
| Weather condition classification logic produces NULL for rows where all precipitation columns are NULL                                                                                                     | Medium     | Low    | Add explicit `ELSE 'Clear'` fallback in the CASE statement to handle fully-NULL precipitation rows as clear-weather days                                                                                  |

## Stories

| ID   | Story                                                    | Points | Dependencies           | Status   |
| ---- | -------------------------------------------------------- | ------ | ---------------------- | -------- |
| S001 | Create dim_date table model from date_spine seed         | 2      | None                   | Complete |
| S002 | Create dim_station unified dimension model               | 8      | None                   | Complete |
| S003 | Create dim_weather table model with condition derivation | 5      | None                   | Complete |
| S004 | Create dim_ttc_delay_codes table model                   | 2      | None                   | Complete |
| S005 | Document all dimension models and add schema tests       | 5      | S001, S002, S003, S004 | Complete |

---

### S001: Create dim_date Table Model from date_spine Seed

**Description**: Build `dim_date` as a table-materialized mart model that reads the `date_spine` seed and applies type casting to produce a date dimension with 10 columns and 2,922 rows spanning 2019-01-01 through 2026-12-31.

**Acceptance Criteria**:

- [x] File `models/marts/core/dim_date.sql` exists with no explicit materialization config (inherits `table` from `dbt_project.yml`)
- [x] Model references `{{ ref('date_spine') }}` as its sole source
- [x] Column `date_key` retained as `INTEGER` (YYYYMMDD format) — serves as the primary key
- [x] Column `full_date` cast from `VARCHAR` to `DATE` type
- [x] Columns `is_weekend` and `is_holiday` cast from `VARCHAR` (`'true'`/`'false'`) to `BOOLEAN` type
- [x] Columns `day_of_week_num`, `month_num`, `quarter`, `year` cast to `INTEGER`
- [x] Columns `day_of_week`, `month_name` retained as `VARCHAR`
- [x] Output contains exactly 10 columns: `date_key`, `full_date`, `day_of_week`, `day_of_week_num`, `month_num`, `month_name`, `quarter`, `year`, `is_weekend`, `is_holiday`
- [x] `dbt run --select dim_date` succeeds and creates a table in the MARTS schema
- [x] Row count is exactly 2,922

**Technical Notes**: The date_spine seed already computes all calendar attributes and holiday flags. This model applies Snowflake type casting only — no business logic. Use `full_date::date` for date conversion and `is_weekend::boolean` for boolean conversion (Snowflake parses `'true'`/`'false'` strings to BOOLEAN natively). The `.gitkeep` file in `models/marts/core/` must be removed after adding model files.

**Definition of Done**:

- [x] Code committed to feature branch
- [x] `dbt run --select dim_date` passes locally
- [x] PR opened with linked issue
- [x] CI checks green

---

### S002: Create dim_station Unified Dimension Model

**Description**: Build `dim_station` as a table-materialized mart model that unifies TTC subway stations (from `ttc_station_mapping` seed, deduplicated to 76 canonical entries) and Bike Share stations (from `bike_station_ref` seed, 1,009 entries) into a single station dimension with surrogate keys generated from the composite natural key `[station_type, station_id]`.

**Acceptance Criteria**:

- [x] File `models/marts/core/dim_station.sql` exists with no explicit materialization config (inherits `table` from `dbt_project.yml`)
- [x] Model uses two CTEs: one selecting from `{{ ref('ttc_station_mapping') }}` and one selecting from `{{ ref('bike_station_ref') }}`
- [x] TTC CTE applies `SELECT DISTINCT` on `(station_key, canonical_station_name)` to reduce 1,101 raw-name rows to 76 canonical station rows (75 named stations + ST_000 Unknown)
- [x] TTC CTE outputs: surrogate `station_key` via `{{ dbt_utils.generate_surrogate_key(["'TTC_SUBWAY'", 'station_id']) }}`, `station_key` seed column aliased as `station_id`, `canonical_station_name` aliased as `station_name`, literal `'TTC_SUBWAY'` as `station_type`, `NULL` for `latitude`, `NULL` for `longitude`, `NULL` for `neighborhood`
- [x] Bike Share CTE outputs: surrogate `station_key` via `{{ dbt_utils.generate_surrogate_key(["'BIKE_SHARE'", 'station_id']) }}`, `station_id` cast to `VARCHAR`, `station_name`, literal `'BIKE_SHARE'` as `station_type`, `latitude`, `longitude`, `neighborhood`
- [x] Final SELECT uses `UNION ALL` across both CTEs
- [x] Output contains exactly 7 columns: `station_key` (PK, surrogate), `station_id` (natural key), `station_name`, `station_type`, `latitude`, `longitude`, `neighborhood`
- [x] `station_type` values are restricted to `'TTC_SUBWAY'` and `'BIKE_SHARE'` (UPPER_SNAKE_CASE)
- [x] Total row count is 1,085 (76 TTC subway + 1,009 Bike Share)
- [x] ST_000 Unknown is present with `station_type = 'TTC_SUBWAY'` and `station_name = 'Unknown'`
- [x] `dbt run --select dim_station` succeeds and creates a table in the MARTS schema

**Technical Notes**: The composite natural key `[station_type, station_id]` prevents cross-type collision per DESIGN-DOC Section 6.4 — a TTC station_id `'ST_001'` and a Bike Share station_id `'7001'` produce different surrogates. The `station_type` literal must use UPPER_SNAKE_CASE (`'TTC_SUBWAY'`, `'BIKE_SHARE'`) consistently across `dim_station` and all downstream fact models. Bike Share `station_id` is numeric in the seed but must be cast to `VARCHAR` for type compatibility with TTC station_id values (e.g., `'ST_001'`). The 5 interchange stations (Bloor-Yonge ST_011, St. George ST_023, Spadina ST_024, Sheppard-Yonge ST_003, Kennedy ST_066) appear once each since the `DISTINCT` operates on `station_key` which is shared across lines.

**Definition of Done**:

- [x] Code committed to feature branch
- [x] `dbt run --select dim_station` passes locally
- [x] PR opened with linked issue
- [x] CI checks green

---

### S003: Create dim_weather Table Model with Condition Derivation

**Description**: Build `dim_weather` as a table-materialized mart model that selects from `stg_weather_daily`, computes `date_key` for FK alignment with `dim_date`, and derives a `weather_condition` categorical column from precipitation measurements.

**Acceptance Criteria**:

- [x] File `models/marts/core/dim_weather.sql` exists with no explicit materialization config (inherits `table` from `dbt_project.yml`)
- [x] Model references `{{ ref('stg_weather_daily') }}` as its sole source
- [x] Column `date_key` computed as `cast(to_char(weather_date, 'YYYYMMDD') as integer)` — serves as PK and FK to `dim_date`
- [x] Column `weather_condition` derived via CASE expression: `'Snow'` when `total_snow_cm > 0`, `'Rain'` when `total_rain_mm > 0 AND (total_snow_cm = 0 OR total_snow_cm IS NULL)`, `'Clear'` as the ELSE fallback (covers zero-precipitation and fully-NULL rows)
- [x] Columns carried forward from staging: `weather_date`, `mean_temp_c`, `max_temp_c`, `min_temp_c`, `total_precip_mm`, `total_rain_mm`, `total_snow_cm`, `snow_on_ground_cm`, `max_wind_gust_kmh`
- [x] Output contains exactly 12 columns: `date_key`, `weather_date`, `mean_temp_c`, `max_temp_c`, `min_temp_c`, `total_precip_mm`, `total_rain_mm`, `total_snow_cm`, `snow_on_ground_cm`, `max_wind_gust_kmh`, `max_wind_gust_dir_deg`, `weather_condition`
- [x] `weather_condition` column contains only values `'Snow'`, `'Rain'`, `'Clear'` — no NULLs
- [x] `dbt run --select dim_weather` succeeds and creates a table in the MARTS schema
- [x] Row count matches `stg_weather_daily` (one row per day, ~2,200 rows)

**Technical Notes**: The staging model already handles type casting (`TRY_CAST` for all decimal columns) and NULL handling. `dim_weather` adds the `date_key` integer and the derived `weather_condition` classification. The `max_wind_gust_dir_deg` column (compass bearing in tens of degrees) is included for completeness from staging. SCD Type 0 per DESIGN-DOC Section 6.2 — historical weather is immutable; full-refresh replaces the table on each run.

**Definition of Done**:

- [x] Code committed to feature branch
- [x] `dbt run --select dim_weather` passes locally
- [x] PR opened with linked issue
- [x] CI checks green

---

### S004: Create dim_ttc_delay_codes Table Model

**Description**: Build `dim_ttc_delay_codes` as a table-materialized mart model that reads the `ttc_delay_codes` seed and generates a surrogate key from the natural `delay_code` column.

**Acceptance Criteria**:

- [x] File `models/marts/core/dim_ttc_delay_codes.sql` exists with no explicit materialization config (inherits `table` from `dbt_project.yml`)
- [x] Model references `{{ ref('ttc_delay_codes') }}` as its sole source
- [x] Column `delay_code_key` generated via `{{ dbt_utils.generate_surrogate_key(['delay_code']) }}` — serves as the primary key
- [x] Columns carried forward: `delay_code` (natural key), `delay_description`, `delay_category`
- [x] Output contains exactly 4 columns: `delay_code_key`, `delay_code`, `delay_description`, `delay_category`
- [x] `dbt run --select dim_ttc_delay_codes` succeeds and creates a table in the MARTS schema
- [x] Row count is exactly 334 (matching the seed)

**Technical Notes**: The `ttc_delay_codes` seed already provides clean, validated data (E-401 — all 334 codes have non-null descriptions and categories within the 8 accepted category values). This model adds only the surrogate key. The `delay_code_key` surrogate must use the same `generate_surrogate_key(['delay_code'])` pattern that `fct_transit_delays` (E-702) will use to generate its FK — this alignment is critical for the `relationships` test.

**Definition of Done**:

- [x] Code committed to feature branch
- [x] `dbt run --select dim_ttc_delay_codes` passes locally
- [x] PR opened with linked issue
- [x] CI checks green

---

### S005: Document All Dimension Models and Add Schema Tests

**Description**: Create `_core__models.yml` with column-level descriptions for all four dimension models and add schema tests covering primary key integrity, foreign key relationships, and categorical value validation.

**Acceptance Criteria**:

- [x] File `models/marts/core/_core__models.yml` exists with `version: 2` header
- [x] All 4 dimension models documented: `dim_date`, `dim_station`, `dim_weather`, `dim_ttc_delay_codes`
- [x] Each model has a `description` field summarizing its grain, source, and purpose
- [x] Every column across all 4 models has a `description` field (10 + 7 + 12 + 4 = 33 column descriptions total)
- [x] `dim_date.date_key`: `unique` and `not_null` tests
- [x] `dim_date.full_date`: `unique` and `not_null` tests
- [x] `dim_date.day_of_week`: `accepted_values` test with `['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']`
- [x] `dim_station.station_key`: `unique` and `not_null` tests
- [x] `dim_station.station_type`: `accepted_values` test with `['TTC_SUBWAY', 'BIKE_SHARE']`
- [x] `dim_weather.date_key`: `unique` and `not_null` tests
- [x] `dim_weather.date_key`: `relationships` test to `dim_date` (field: `date_key`)
- [x] `dim_weather.weather_condition`: `accepted_values` test with `['Snow', 'Rain', 'Clear']`
- [x] `dim_ttc_delay_codes.delay_code_key`: `unique` and `not_null` tests
- [x] `dim_ttc_delay_codes.delay_code`: `unique` and `not_null` tests
- [x] `dim_ttc_delay_codes.delay_category`: `accepted_values` test with `['Mechanical', 'Signal', 'Passenger', 'Infrastructure', 'Operations', 'Weather', 'Security', 'General']`
- [x] `dbt parse` succeeds with zero errors after YAML file is added
- [x] All defined schema tests execute and pass via `dbt test --select dim_date dim_station dim_weather dim_ttc_delay_codes`

**Technical Notes**: Column descriptions follow the technical documentation voice defined in CLAUDE.md Section 1.2 — cold, precise, authoritative. The `relationships` test on `dim_weather.date_key` validates that every weather observation date falls within the date spine range (2019-2026); weather data outside this range would indicate a data loading issue. The `.gitkeep` file in `models/marts/core/` must be removed as part of this story or an earlier one.

**Definition of Done**:

- [x] Code committed to feature branch
- [x] `dbt parse` passes locally
- [x] All defined schema tests pass against Snowflake target
- [x] PR opened with linked issue
- [x] CI checks green

## Exit Criteria

This epic is complete when:

- [x] `dim_date` materializes as a table with 2,922 rows, BOOLEAN `is_weekend`/`is_holiday`, and DATE `full_date`
- [x] `dim_station` materializes as a table with 1,085 rows (76 TTC subway + 1,009 Bike Share) and unique surrogate keys
- [x] `dim_weather` materializes as a table with ~2,200 rows and no NULL values in `weather_condition`
- [x] `dim_ttc_delay_codes` materializes as a table with 334 rows and unique surrogate keys
- [x] `_core__models.yml` documents all 4 models with 33 column descriptions and schema tests
- [x] `dbt build --select dim_date dim_station dim_weather dim_ttc_delay_codes` passes with zero test failures
- [x] `.gitkeep` removed from `models/marts/core/`

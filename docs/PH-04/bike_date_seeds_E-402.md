# Bike Share & Date Spine Seeds with Seed Layer Documentation

| Field        | Value         |
| ------------ | ------------- |
| Epic ID      | E-402         |
| Phase        | PH-04         |
| Owner        | @dinesh-git17 |
| Status       | Complete      |
| Dependencies | [E-401]       |
| Created      | 2026-02-09    |

## Context

The medallion architecture requires three additional seed datasets beyond TTC reference data (E-401): Bike Share station reference data for geographic enrichment of trip records, a date spine for time intelligence across all fact tables, and comprehensive YAML documentation for the entire seed layer. DESIGN-DOC.md Section 5.3 defines a SEEDS schema under TRANSFORMER_ROLE ownership, and Section 6.1 specifies `dim_station` and `dim_date` dimension tables that depend on seed data for station geography and date attributes respectively. The Bike Share station reference maps station IDs to coordinates and neighborhoods, enabling the `int_bike_trips_enriched` model (PH-06) to add geographic context to trip records. The date spine pre-computes calendar attributes (day of week, quarter, holidays) for the `dim_date` mart (PH-07). This epic also delivers the `_seeds.yml` documentation file required by dbt convention, covering all four seed tables, and executes `dbt seed` to load reference data into the Snowflake SEEDS schema. Completion of this epic satisfies the PH-04 exit criterion: `dbt seed` executes successfully with all reference data loaded.

## Scope

### In Scope

- `seeds/bike_station_ref.csv` with station ID, name, coordinates, and neighborhood from Bike Share Toronto GBFS station information snapshot
- `seeds/date_spine.csv` with pre-computed date dimension attributes covering 2019-01-01 through 2026-12-31 (2,922 rows)
- Python generation script for date spine CSV (`scripts/generate_date_spine.py`) with Ontario statutory holiday definitions
- `seeds/_seeds.yml` with column-level documentation and dbt schema tests for all four seeds (ttc_station_mapping, ttc_delay_codes, bike_station_ref, date_spine)
- dbt generic tests: `unique` and `not_null` on all primary key columns across all seeds
- `dbt seed` execution and row count validation in Snowflake SEEDS schema
- Removal of `seeds/.gitkeep` placeholder file

### Out of Scope

- TTC station mapping and delay code CSV creation (completed in E-401)
- Bike Share station capacity or dock availability data (real-time data, excluded per Non-Goal NG1)
- Toronto ward boundary mapping for bike stations (ward column in dim_station is populated in PH-07 using spatial joins, not in the seed)
- Staging model creation referencing seeds (PH-05)
- Intermediate model logic consuming seeds (PH-06)
- Mart model materialization from seeds (PH-07)

## Technical Approach

### Architecture Decisions

- **GBFS snapshot for bike stations**: Bike Share Toronto publishes station information via the General Bikeshare Feed Specification (GBFS). A point-in-time snapshot of the `station_information` endpoint provides station_id, station_name, latitude, and longitude. Neighborhood assignment uses reverse lookup against Toronto neighborhood boundary data or manual curation based on station addresses. The snapshot is committed as a static CSV seed — it represents the station network at a fixed point in time. Station additions/removals between snapshots result in UNKNOWN joins in the intermediate layer, flagged by data quality tests in PH-08.
- **Python-generated date spine over SQL macro**: While `macros/get_date_spine.sql` exists for SQL-based date generation, the PH-04 deliverable is a CSV seed with pre-computed attributes including Ontario statutory holidays. Python provides native `datetime` operations, holiday libraries, and deterministic CSV output. The `dim_date` mart model (PH-07) references this seed via `{{ ref('date_spine') }}` rather than generating dates at query time.
- **Ontario statutory holidays**: The date spine includes `is_holiday` (boolean) and applies Ontario's 9 statutory holidays: New Year's Day, Family Day, Good Friday, Victoria Day, Canada Day, Civic Holiday (Toronto), Labour Day, Thanksgiving, Christmas Day. Moving holidays (Easter-dependent, nth-Monday rules) are computed programmatically per year.
- **Single \_seeds.yml for all seeds**: All four seed tables are documented in one `seeds/_seeds.yml` file following dbt convention. This file contains column descriptions, data types, and generic test definitions (`unique`, `not_null`, `accepted_values`).
- **Seed schema target**: Per `dbt_project.yml` configuration, seeds load to the `SEEDS` schema under `TRANSFORMER_ROLE` ownership (DESIGN-DOC.md Section 5.3).

### Integration Points

- Upstream: `seeds/ttc_station_mapping.csv` and `seeds/ttc_delay_codes.csv` from E-401
- Upstream: Bike Share Toronto GBFS `station_information` endpoint for bike station data
- Downstream: All four seeds consumed by staging (PH-05), intermediate (PH-06), and mart (PH-07) layers
- Downstream: `seeds/date_spine.csv` referenced by `dim_date.sql` mart model (PH-07)
- Downstream: `seeds/bike_station_ref.csv` referenced by `int_bike_trips_enriched.sql` (PH-06) and `dim_station.sql` (PH-07)
- Configuration: `dbt_project.yml` seeds section (already configured with `+schema: seeds`)

### Repository Areas

- `seeds/bike_station_ref.csv` — Bike Share station reference data
- `seeds/date_spine.csv` — pre-computed date dimension seed
- `seeds/_seeds.yml` — column documentation and schema tests for all seeds
- `scripts/generate_date_spine.py` — Python script for date spine CSV generation
- `tests/test_generate_date_spine.py` — pytest tests for date spine generation
- `dbt_project.yml` — seed configuration (already present, no changes expected)

### Risks

| Risk                                                                                                                                     | Likelihood | Impact | Mitigation                                                                                                                                                                                                              |
| ---------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Bike Share Toronto GBFS endpoint is unavailable or changes schema at time of snapshot                                                    | Low        | Medium | Cache a local copy of the GBFS JSON response in `data/working/gbfs_station_information.json`; if endpoint is down, use cached copy; validate JSON schema before parsing                                                 |
| GBFS station data lacks neighborhood information requiring manual curation for 625+ stations                                             | High       | Medium | Use Toronto neighborhood boundary polygons from Open Data Portal for point-in-polygon lookup; fall back to manual assignment based on station address substring matching (e.g., "Queen St" maps to known neighborhoods) |
| Ontario holiday dates are incorrect for edge cases (e.g., Family Day was introduced in 2008, Civic Holiday is not technically statutory) | Low        | Low    | Use well-tested date computation logic; validate against published Ontario government holiday schedules for 2019-2026; document Civic Holiday as Toronto-specific municipal holiday                                     |
| date_spine.csv exceeds dbt seed performance threshold (default 10,000 rows)                                                              | Low        | Low    | Date spine is 2,922 rows, well under the threshold; no seed configuration changes required                                                                                                                              |
| dbt seed fails due to Snowflake connectivity or TRANSFORMER_ROLE permission issues                                                       | Medium     | Medium | Verify Snowflake credentials and role grants before execution; document required grants in story acceptance criteria; provide manual verification queries                                                               |

## Stories

| ID   | Story                                                                    | Points | Dependencies                       | Status   |
| ---- | ------------------------------------------------------------------------ | ------ | ---------------------------------- | -------- |
| S001 | Build bike_station_ref.csv from Bike Share Toronto GBFS station snapshot | 5      | None                               | Complete |
| S002 | Generate date_spine.csv via Python script with date dimension attributes | 5      | None                               | Complete |
| S003 | Create \_seeds.yml with column-level documentation for all seed tables   | 3      | E-401.S002, E-401.S003, S001, S002 | Complete |
| S004 | Add dbt schema tests for all seed tables in \_seeds.yml                  | 3      | S003                               | Complete |
| S005 | Execute dbt seed and validate all seeds load to SEEDS schema             | 3      | S004                               | Complete |

---

### S001: Build bike_station_ref.csv from Bike Share Toronto GBFS station snapshot

**Description**: Create the `seeds/bike_station_ref.csv` seed file containing Bike Share Toronto station metadata (ID, name, coordinates, neighborhood) sourced from a GBFS station information snapshot, providing geographic context for trip enrichment in downstream models.

**Acceptance Criteria**:

- [ ] File `seeds/bike_station_ref.csv` exists with columns: `station_id`, `station_name`, `latitude`, `longitude`, `neighborhood`
- [ ] `station_id` values are positive integers matching the station IDs in `BIKE_SHARE_TRIPS.START_STATION_ID` and `END_STATION_ID` RAW columns
- [ ] `latitude` and `longitude` values are decimal numbers within Toronto bounding box: latitude 43.58-43.86, longitude -79.64 to -79.10
- [ ] `neighborhood` values are non-empty strings representing Toronto neighborhoods (e.g., "The Annex", "Liberty Village", "Distillery District")
- [ ] Total row count covers the active Bike Share Toronto station network (expected range: 600-900 stations)
- [ ] `station_id` column has zero duplicate values
- [ ] No column contains empty or NULL values
- [ ] File is UTF-8 encoded with no BOM, uses comma delimiter, and double-quote escaping for values containing commas
- [ ] A GBFS snapshot JSON file is cached at `data/working/gbfs_station_information.json` for reproducibility

**Technical Notes**: Fetch station data from the Bike Share Toronto GBFS `station_information` endpoint. Parse the JSON response to extract `station_id`, `name`, `lat`, `lon`. For neighborhood assignment, use one of: (1) Toronto Open Data neighborhood boundaries with point-in-polygon lookup using `shapely`, (2) manual mapping based on station name/address patterns, or (3) a pre-existing neighborhood lookup table. Option 2 or 3 is preferred to minimize external dependencies. Document the snapshot date in the PR description. Historical stations that no longer appear in GBFS but exist in trip data will result in NULL joins — this is acceptable and handled by COALESCE in the intermediate layer.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Tests pass locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S002: Generate date_spine.csv via Python script with date dimension attributes

**Description**: Create a Python generation script that produces `seeds/date_spine.csv` containing a complete date dimension with calendar attributes and Ontario statutory holidays for the range 2019-01-01 through 2026-12-31.

**Acceptance Criteria**:

- [ ] File `scripts/generate_date_spine.py` exists and produces `seeds/date_spine.csv` when executed via `python scripts/generate_date_spine.py`
- [ ] Generated CSV contains exactly 2,922 rows (one per calendar day from 2019-01-01 through 2026-12-31 inclusive)
- [ ] CSV columns are: `date_key`, `full_date`, `day_of_week`, `day_of_week_num`, `month_num`, `month_name`, `quarter`, `year`, `is_weekend`, `is_holiday`
- [ ] `date_key` is an integer in YYYYMMDD format (e.g., 20190101) and is unique across all rows
- [ ] `full_date` is ISO 8601 format (YYYY-MM-DD)
- [ ] `day_of_week` is the full day name (Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday)
- [ ] `day_of_week_num` is 1 (Monday) through 7 (Sunday) per ISO 8601 weekday numbering
- [ ] `month_num` is 1-12, `month_name` is the full month name (January through December)
- [ ] `quarter` is 1-4
- [ ] `is_weekend` is `true` for Saturday/Sunday, `false` otherwise (lowercase boolean strings)
- [ ] `is_holiday` is `true` for Ontario statutory holidays, `false` otherwise (lowercase boolean strings)
- [ ] Ontario statutory holidays included: New Year's Day (Jan 1), Family Day (3rd Monday Feb), Good Friday (Easter-dependent), Victoria Day (Monday before May 25), Canada Day (Jul 1), Civic Holiday (1st Monday Aug), Labour Day (1st Monday Sep), Thanksgiving (2nd Monday Oct), Christmas Day (Dec 25)
- [ ] When a holiday falls on a weekend, the `is_holiday` flag remains on the actual holiday date (not the observed Monday)
- [ ] `mypy --strict scripts/generate_date_spine.py` passes with zero errors
- [ ] `ruff check scripts/generate_date_spine.py && ruff format --check scripts/generate_date_spine.py` passes
- [ ] File `tests/test_generate_date_spine.py` exists with tests covering: row count is 2,922, date_key uniqueness, no date gaps, is_weekend correctness for known dates, is_holiday correctness for known holidays (e.g., 2024-01-01 is holiday, 2024-07-01 is holiday, 2024-12-25 is holiday), Good Friday computation for 2019-2026
- [ ] `pytest tests/test_generate_date_spine.py -v` passes with zero failures

**Technical Notes**: Use Python `datetime` and `calendar` modules for date arithmetic. Compute Easter dates using the Anonymous Gregorian algorithm (Meeus/Jones/Butcher) to derive Good Friday. Family Day is the 3rd Monday of February (since 2008 in Ontario). Victoria Day is the Monday on or before May 24. Civic Holiday is the 1st Monday of August. Do NOT use external holiday libraries — implement the 9 holiday rules directly to avoid dependency bloat. Script must be idempotent: re-running overwrites the CSV with identical content. The generated CSV is committed to the repository as a seed file.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Tests pass locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S003: Create \_seeds.yml with column-level documentation for all seed tables

**Description**: Create the `seeds/_seeds.yml` file containing dbt-standard column descriptions for all four seed tables (ttc_station_mapping, ttc_delay_codes, bike_station_ref, date_spine), satisfying dbt documentation requirements for the seed layer.

**Acceptance Criteria**:

- [ ] File `seeds/_seeds.yml` exists and passes `dbt parse` without errors
- [ ] YAML defines four seed models: `ttc_station_mapping`, `ttc_delay_codes`, `bike_station_ref`, `date_spine`
- [ ] Every column in every seed has a `description` field with a non-empty, technically precise description (minimum 10 characters)
- [ ] `ttc_station_mapping` documents 4 columns: `raw_station_name`, `canonical_station_name`, `station_key`, `line_code`
- [ ] `ttc_delay_codes` documents 3 columns: `delay_code`, `delay_description`, `delay_category`
- [ ] `bike_station_ref` documents 5 columns: `station_id`, `station_name`, `latitude`, `longitude`, `neighborhood`
- [ ] `date_spine` documents 10 columns: `date_key`, `full_date`, `day_of_week`, `day_of_week_num`, `month_num`, `month_name`, `quarter`, `year`, `is_weekend`, `is_holiday`
- [ ] No column description contains placeholder text (TODO, TBD, WIP)
- [ ] YAML follows dbt seed documentation convention with `version: 2` header and `seeds:` top-level key

**Technical Notes**: Use the standard dbt seed YAML structure:

```yaml
version: 2
seeds:
  - name: ttc_station_mapping
    description: "..."
    columns:
      - name: raw_station_name
        description: "..."
```

Column descriptions should state the data type semantics and source. Do not include dbt tests in this story — tests are added in S004.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Tests pass locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S004: Add dbt schema tests for all seed tables in \_seeds.yml

**Description**: Extend `seeds/_seeds.yml` with dbt generic test definitions that enforce uniqueness, non-null, and accepted value constraints on all seed primary keys and categorical columns.

**Acceptance Criteria**:

- [ ] `seeds/_seeds.yml` includes `tests` definitions for the following constraints:
- [ ] `ttc_station_mapping.raw_station_name`: `unique`, `not_null`
- [ ] `ttc_station_mapping.station_key`: `not_null`
- [ ] `ttc_station_mapping.canonical_station_name`: `not_null`
- [ ] `ttc_station_mapping.line_code`: `not_null`, `accepted_values` with values `['YU', 'BD', 'SHP', 'SRT']`
- [ ] `ttc_delay_codes.delay_code`: `unique`, `not_null`
- [ ] `ttc_delay_codes.delay_description`: `not_null`
- [ ] `ttc_delay_codes.delay_category`: `not_null`, `accepted_values` with values `['Mechanical', 'Signal', 'Passenger', 'Infrastructure', 'Operations', 'Weather', 'Security', 'General']`
- [ ] `bike_station_ref.station_id`: `unique`, `not_null`
- [ ] `bike_station_ref.station_name`: `not_null`
- [ ] `bike_station_ref.latitude`: `not_null`
- [ ] `bike_station_ref.longitude`: `not_null`
- [ ] `bike_station_ref.neighborhood`: `not_null`
- [ ] `date_spine.date_key`: `unique`, `not_null`
- [ ] `date_spine.full_date`: `unique`, `not_null`
- [ ] `date_spine.day_of_week`: `not_null`, `accepted_values` with values `['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']`
- [ ] `date_spine.is_weekend`: `not_null`, `accepted_values` with values `['true', 'false']`
- [ ] `date_spine.is_holiday`: `not_null`, `accepted_values` with values `['true', 'false']`
- [ ] `dbt parse` succeeds with the updated `_seeds.yml` (validates YAML and test definitions without Snowflake connection)

**Technical Notes**: dbt generic tests are defined inline under each column in the YAML file using the `tests:` key. The `accepted_values` test uses the `values` parameter. All tests default to `severity: error` per `dbt_project.yml` test configuration.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Tests pass locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S005: Execute dbt seed and validate all seeds load to SEEDS schema

**Description**: Run `dbt seed` to load all four seed CSV files into the Snowflake SEEDS schema and validate row counts, table existence, and schema test passage.

**Acceptance Criteria**:

- [ ] `dbt seed` completes with exit code 0 and reports 4 seeds loaded: `ttc_station_mapping`, `ttc_delay_codes`, `bike_station_ref`, `date_spine`
- [ ] Snowflake query `SELECT TABLE_NAME FROM TORONTO_MOBILITY.INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'SEEDS' ORDER BY TABLE_NAME` returns all 4 seed table names
- [ ] `SELECT COUNT(*) FROM TORONTO_MOBILITY.SEEDS.DATE_SPINE` returns 2,922
- [ ] `SELECT COUNT(*) FROM TORONTO_MOBILITY.SEEDS.BIKE_STATION_REF` returns a value in the range 600-900
- [ ] `SELECT COUNT(*) FROM TORONTO_MOBILITY.SEEDS.TTC_STATION_MAPPING` returns a value >= 100 (all raw station name variants)
- [ ] `SELECT COUNT(*) FROM TORONTO_MOBILITY.SEEDS.TTC_DELAY_CODES` returns a value in the range 30-80
- [ ] `dbt test --select seeds` passes with zero failures (all generic tests from S004 pass)
- [ ] `dbt seed --full-refresh` is idempotent: re-running produces identical row counts
- [ ] `seeds/.gitkeep` placeholder file is removed (no longer needed with actual seed files present)

**Technical Notes**: Requires active Snowflake connection with TRANSFORMER_ROLE credentials configured in `profiles.yml`. If Snowflake credentials are unavailable, document the commands and expected outputs in the PR and mark the story as blocked on credential provisioning. Run `dbt seed` before `dbt test --select seeds` since tests query the seeded tables in Snowflake.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Tests pass locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

## Exit Criteria

This epic is complete when:

- [ ] `seeds/bike_station_ref.csv` exists with Bike Share Toronto station metadata (ID, name, coordinates, neighborhood)
- [ ] `seeds/date_spine.csv` exists with 2,922 rows covering 2019-01-01 through 2026-12-31 including Ontario statutory holidays
- [ ] `scripts/generate_date_spine.py` exists, passes `mypy --strict`, and regenerates identical CSV output on re-execution
- [ ] `tests/test_generate_date_spine.py` passes with zero failures
- [ ] `seeds/_seeds.yml` documents all 4 seed tables with column-level descriptions and dbt generic tests
- [ ] `dbt seed` executes with exit code 0, loading all 4 seeds to Snowflake SEEDS schema
- [ ] `dbt test --select seeds` passes with zero failures
- [ ] All seed primary key columns pass `unique` and `not_null` tests
- [ ] All seed categorical columns pass `accepted_values` tests
- [ ] Python code generated via `python-writing` skill

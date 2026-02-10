# TTC Delay Union and Enrichment Intermediate Models

| Field        | Value         |
| ------------ | ------------- |
| Epic ID      | E-601         |
| Phase        | PH-06         |
| Owner        | @dinesh-git17 |
| Status       | Complete      |
| Dependencies | [E-501]       |
| Created      | 2026-02-09    |

## Context

The intermediate layer implements business logic transformations between staging views and mart tables in the medallion architecture. TTC delay data arrives from three separate staging models (`stg_ttc_subway_delays`, `stg_ttc_bus_delays`, `stg_ttc_streetcar_delays`) with incompatible column structures: subway uses `raw_station_name` and `line_code`, while bus and streetcar use `route` and `location`. This epic unions the three modes into a single model with aligned columns, then enriches the result by joining with the `ttc_station_mapping` and `ttc_delay_codes` seed tables. All intermediate models materialize as ephemeral CTEs per DESIGN-DOC Section 6.3 and Decision D10, producing no persistent Snowflake objects. Station mapping coverage must reach >= 99% for subway records per the phase exit criteria.

## Scope

### In Scope

- `int_ttc_delays_unioned` ephemeral model: UNION ALL of three TTC staging views with column alignment and NULL padding for mode-specific columns
- `int_ttc_delays_enriched` ephemeral model: LEFT JOIN with `ttc_station_mapping` seed (subway station resolution) and `ttc_delay_codes` seed (delay category enrichment), plus `date_key` computation
- Singular dbt test `tests/assert_station_mapping_coverage.sql` validating >= 99% of subway delay records map to a canonical station (station_key != `ST_000`)
- Model documentation in `models/intermediate/_int__models.yml` with column descriptions and schema tests for both TTC intermediate models

### Out of Scope

- Bike Share trip enrichment (E-602)
- Daily pre-aggregation models for transit or bike metrics (E-602)
- Mart-layer dimensional FK generation (`station_key` surrogate for `dim_station`) — deferred to PH-07
- Bus/streetcar station mapping (no seed exists; bus/streetcar use intersection-level `location` descriptors)
- Delay code seed curation (completed in E-401)
- Station mapping seed curation (completed in E-401)

## Technical Approach

### Architecture Decisions

- **Ephemeral materialization for all intermediate models** — Per DESIGN-DOC Decision D10 and `dbt_project.yml` configuration (`models.toronto_mobility.intermediate.+materialized: ephemeral`); no Snowflake objects created; CTEs compiled into downstream consumers
- **Column alignment via NULL padding** — Subway-specific columns (`raw_station_name`, `line_code`) set to NULL for bus/streetcar; bus/streetcar-specific columns (`route`, `location`) set to NULL for subway; preserves mode-specific attributes while enabling a single UNION ALL
- **LEFT JOIN for seed enrichment** — Both `ttc_station_mapping` and `ttc_delay_codes` joins use LEFT JOIN to preserve all delay records regardless of mapping completeness; unmapped subway stations resolve to NULL canonical values (seed maps unmapped entries to `ST_000` with canonical_station_name `Unknown`)
- **Station mapping uses seed station_key as natural identifier** — The `ttc_station_mapping` seed provides `station_key` (e.g., `ST_001`) as the natural station identifier; the mart layer (PH-07) generates the dimensional surrogate key from `[station_type, station_id]` per DESIGN-DOC Section 6.4
- **date_key computed as YYYYMMDD integer** — Matches the `date_spine` seed format (`to_number(to_char(delay_date, 'YYYYMMDD'))`) for downstream joins to `dim_date`

### Integration Points

- **Upstream staging models** — `stg_ttc_subway_delays` (12 columns), `stg_ttc_bus_delays` (12 columns), `stg_ttc_streetcar_delays` (12 columns) from PH-05/E-501
- **Seed tables** — `ttc_station_mapping` (1,101 rows, 4 columns: raw_station_name, canonical_station_name, station_key, line_code) and `ttc_delay_codes` (334 rows, 3 columns: delay_code, delay_description, delay_category) from PH-04/E-401
- **Downstream consumers** — `int_daily_transit_metrics` (E-602), `fct_transit_delays` (PH-07)
- **dbt_project.yml** — Intermediate materialization already configured as `ephemeral`

### Repository Areas

- `models/intermediate/int_ttc_delays_unioned.sql` (new)
- `models/intermediate/int_ttc_delays_enriched.sql` (new)
- `models/intermediate/_int__models.yml` (new)
- `tests/assert_station_mapping_coverage.sql` (new)

### Risks

| Risk                                                                                             | Likelihood | Impact | Mitigation                                                                                                                                             |
| ------------------------------------------------------------------------------------------------ | ---------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Column misalignment in UNION ALL causes silent data corruption (wrong values in wrong columns)   | Low        | High   | Explicit column lists in each SELECT branch; no SELECT \*; verify column order matches across all three branches                                       |
| Subway station mapping join produces NULL for records with raw_station_name variants not in seed | Low        | Medium | Seed contains all 1,101 distinct raw names from 2020-2025 data (E-401); `assert_station_mapping_coverage` test catches regressions from new data loads |
| Delay code LEFT JOIN produces NULL enrichment for codes not in seed                              | Low        | Low    | Seed contains 334 codes covering all modes (E-401); NULL delay_description/delay_category is acceptable for unknown codes                              |
| Ephemeral model compilation errors surface only when downstream models execute                   | Medium     | Medium | Add schema tests in `_int__models.yml` that force dbt to compile and execute the ephemeral models independently                                        |

## Stories

| ID   | Story                                                 | Points | Dependencies | Status |
| ---- | ----------------------------------------------------- | ------ | ------------ | ------ |
| S001 | Create int_ttc_delays_unioned ephemeral model         | 5      | None         | Done   |
| S002 | Create int_ttc_delays_enriched ephemeral model        | 5      | S001         | Done   |
| S003 | Implement station mapping coverage singular test      | 3      | S002         | Done   |
| S004 | Document TTC intermediate models and add schema tests | 3      | S001, S002   | Done   |

---

### S001: Create int_ttc_delays_unioned Ephemeral Model

**Description**: Build `int_ttc_delays_unioned` as an ephemeral dbt model that unions `stg_ttc_subway_delays`, `stg_ttc_bus_delays`, and `stg_ttc_streetcar_delays` into a single result set with aligned columns.

**Acceptance Criteria**:

- [x] File `models/intermediate/int_ttc_delays_unioned.sql` exists with no explicit materialization config (inherits ephemeral from `dbt_project.yml`)
- [x] Model uses three CTEs (`subway`, `bus`, `streetcar`) each selecting from the corresponding `{{ ref('stg_ttc_*') }}` model with explicit column lists (no `SELECT *`)
- [x] Subway CTE outputs: `delay_sk`, `delay_date`, `delay_time`, `incident_timestamp`, `day_of_week`, `transit_mode`, `line_code`, `NULL as route`, `raw_station_name`, `NULL as location`, `delay_code`, `delay_minutes`, `gap_minutes`, `direction`
- [x] Bus CTE outputs: `delay_sk`, `delay_date`, `delay_time`, `incident_timestamp`, `day_of_week`, `transit_mode`, `NULL as line_code`, `route`, `NULL as raw_station_name`, `location`, `delay_code`, `delay_minutes`, `gap_minutes`, `direction`
- [x] Streetcar CTE outputs same column structure as Bus CTE with `transit_mode = 'streetcar'` from staging
- [x] Final SELECT uses `UNION ALL` (not `UNION`) across all three CTEs to preserve duplicates and avoid sort overhead
- [x] Output contains exactly 14 columns in the order specified above
- [x] `dbt compile --select int_ttc_delays_unioned` succeeds with zero errors
- [x] Column order is identical across all three SELECT branches to prevent positional misalignment

**Technical Notes**: Each staging model already includes `transit_mode` as a literal column, so the union inherits the mode discriminator without additional logic. Column alignment requires explicit NULL casting for mode-specific columns: subway lacks `route` and `location`; bus/streetcar lack `line_code` and `raw_station_name`. The `.gitkeep` file in `models/intermediate/` must be removed after adding the first model file.

**Definition of Done**:

- [x] Code committed to feature branch
- [x] `dbt compile --select int_ttc_delays_unioned` passes locally
- [x] PR opened with linked issue
- [x] CI checks green

---

### S002: Create int_ttc_delays_enriched Ephemeral Model

**Description**: Build `int_ttc_delays_enriched` as an ephemeral dbt model that enriches `int_ttc_delays_unioned` with canonical station names from the `ttc_station_mapping` seed and delay descriptions from the `ttc_delay_codes` seed.

**Acceptance Criteria**:

- [x] File `models/intermediate/int_ttc_delays_enriched.sql` exists with no explicit materialization config (inherits ephemeral from `dbt_project.yml`)
- [x] Model references `{{ ref('int_ttc_delays_unioned') }}` as its primary source CTE
- [x] LEFT JOIN with `{{ ref('ttc_station_mapping') }}` on `raw_station_name = raw_station_name` adds columns `canonical_station_name` and `station_id` (sourced from the seed's `station_key` column, e.g., `ST_001`)
- [x] LEFT JOIN with `{{ ref('ttc_delay_codes') }}` on `delay_code = delay_code` adds columns `delay_description` and `delay_category`
- [x] Computed column `date_key` derived as `to_number(to_char(delay_date, 'YYYYMMDD'))` matching the `date_spine` seed's integer format
- [x] For subway records: `canonical_station_name` resolves to the mapped name (e.g., `Bloor-Yonge`); unmapped entries resolve to `Unknown` via seed mapping to `ST_000`
- [x] For bus and streetcar records: `canonical_station_name` and `station_id` are NULL (LEFT JOIN on NULL `raw_station_name` produces NULL output)
- [x] All 14 columns from `int_ttc_delays_unioned` are carried forward plus 5 enrichment columns: `canonical_station_name`, `station_id`, `delay_description`, `delay_category`, `date_key`
- [x] Output contains exactly 19 columns total
- [x] `dbt compile --select int_ttc_delays_enriched` succeeds with zero errors

**Technical Notes**: The `ttc_station_mapping` seed column `station_key` (e.g., `ST_001`) serves as the natural station identifier; it is aliased to `station_id` in the enriched output to align with the `dim_station` naming convention in PH-07. The LEFT JOIN preserves all delay records: subway records get station enrichment, bus/streetcar records get NULL station fields. Both seed joins are independent and can be applied in a single CTE or chained CTEs. The delay code join covers all transit modes since the `ttc_delay_codes` seed contains codes for subway, bus, and streetcar.

**Definition of Done**:

- [x] Code committed to feature branch
- [x] `dbt compile --select int_ttc_delays_enriched` passes locally
- [x] PR opened with linked issue
- [x] CI checks green

---

### S003: Implement Station Mapping Coverage Singular Test

**Description**: Create a singular dbt test that validates >= 99% of subway delay records in `int_ttc_delays_enriched` map to a canonical station (station_id != `ST_000`).

**Acceptance Criteria**:

- [x] File `tests/assert_station_mapping_coverage.sql` exists as a singular dbt test
- [x] Test query filters to `transit_mode = 'subway'` (bus/streetcar excluded from station mapping coverage calculation)
- [x] Test computes coverage ratio: `COUNT(CASE WHEN station_id != 'ST_000' THEN 1 END)::float / COUNT(*)` for subway records
- [x] Test returns rows (fails) when coverage ratio < 0.99 (i.e., more than 1% of subway records map to `ST_000` Unknown)
- [x] Test returns zero rows (passes) when coverage ratio >= 0.99
- [x] Test references `{{ ref('int_ttc_delays_enriched') }}` as its source
- [x] `dbt test --select assert_station_mapping_coverage` executes without compilation errors
- [x] Test passes against current data (E-401 achieved 99.3% station mapping coverage)

**Technical Notes**: The singular test must return failing rows. Standard pattern: `SELECT 1 WHERE (subquery_computing_coverage) < 0.99`. Since `int_ttc_delays_enriched` is ephemeral, dbt compiles it as a CTE within the test query. The 99% threshold aligns with DESIGN-DOC Risk R4 ("accept <= 1% UNKNOWN rate") and the PH-06 exit criterion. This test file is already referenced in DESIGN-DOC Section 15.1 project structure.

**Definition of Done**:

- [x] Code committed to feature branch
- [x] Test passes locally against Snowflake target
- [x] PR opened with linked issue
- [x] CI checks green

---

### S004: Document TTC Intermediate Models and Add Schema Tests

**Description**: Create `_int__models.yml` with column-level descriptions for `int_ttc_delays_unioned` and `int_ttc_delays_enriched`, and add schema tests on key columns.

**Acceptance Criteria**:

- [x] File `models/intermediate/_int__models.yml` exists with `version: 2` header
- [x] Model `int_ttc_delays_unioned` defined with `description` field summarizing its purpose (union of 3 TTC staging models with column alignment)
- [x] All 14 columns of `int_ttc_delays_unioned` have `description` fields
- [x] Model `int_ttc_delays_enriched` defined with `description` field summarizing its purpose (seed enrichment with station mapping and delay codes)
- [x] All 19 columns of `int_ttc_delays_enriched` have `description` fields
- [x] `delay_date` column in `int_ttc_delays_unioned` has `not_null` test
- [x] `delay_minutes` column in `int_ttc_delays_unioned` has `not_null` test
- [x] `transit_mode` column in `int_ttc_delays_unioned` has `accepted_values` test with values `['subway', 'bus', 'streetcar']`
- [x] `date_key` column in `int_ttc_delays_enriched` has `not_null` test
- [x] `delay_category` column in `int_ttc_delays_enriched` has `accepted_values` test with values `['Mechanical', 'Signal', 'Passenger', 'Infrastructure', 'Operations', 'Weather', 'Security', 'General']` and `severity: warn` (allows NULL for unmapped codes)
- [x] `dbt parse` succeeds with zero errors after YAML file is added
- [x] All defined schema tests execute via `dbt test --select int_ttc_delays_unioned int_ttc_delays_enriched`

**Technical Notes**: Column descriptions follow the technical documentation voice defined in CLAUDE.md Section 1.2. Ephemeral models support schema tests; dbt compiles the test query with the ephemeral model inlined as a CTE. The `delay_category` `accepted_values` test uses `severity: warn` because the LEFT JOIN with `ttc_delay_codes` can produce NULL for delay codes not present in the seed (acceptable behavior, not a data quality failure). This YAML file will be extended in E-602 with bike and daily metrics model definitions.

**Definition of Done**:

- [x] Code committed to feature branch
- [x] `dbt parse` passes locally
- [x] All defined tests pass against Snowflake target
- [x] PR opened with linked issue
- [x] CI checks green

## Exit Criteria

This epic is complete when:

- [x] `int_ttc_delays_unioned` compiles as ephemeral CTE unioning all 3 TTC staging models with 14 aligned columns
- [x] `int_ttc_delays_enriched` compiles as ephemeral CTE with station mapping and delay code enrichment producing 19 columns
- [x] `tests/assert_station_mapping_coverage.sql` passes with >= 99% subway station coverage
- [x] `_int__models.yml` documents both models with column descriptions and schema tests
- [x] All schema tests pass: `dbt test --select int_ttc_delays_unioned int_ttc_delays_enriched`
- [x] `.gitkeep` removed from `models/intermediate/`

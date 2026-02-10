# Model Documentation Completeness & dbt Docs Site

| Field        | Value                                      |
| ------------ | ------------------------------------------ |
| Epic ID      | E-901                                      |
| Phase        | PH-09                                      |
| Owner        | @dinesh-git17                              |
| Status       | Complete                                   |
| Dependencies | [E-501, E-502, E-601, E-602, E-701, E-702] |
| Created      | 2026-02-09                                 |

## Context

Phases PH-05 through PH-07 built the complete dbt model stack — 5 staging views, 5 intermediate ephemeral models, 4 dimension tables, and 3 fact tables — with column-level descriptions added to each layer's `_models.yml` file as part of each epic's Definition of Done. PH-08 added 22 tests (5 singular, 5 dbt_expectations, 17 Elementary) without modifying model definitions. However, documentation completeness has been asserted per-epic, never validated holistically. DESIGN-DOC Section 1.4 defines a success criterion: "All models documented" measured by "`dbt docs generate` with no missing descriptions." This epic performs the formal audit confirming that every column in every model and seed has a description, that `dbt docs generate` produces a catalog with zero missing descriptions, and that the generated lineage graph accurately represents the data flow defined in DESIGN-DOC Section 6.1. Without this verification pass, documentation completeness is assumed but unvalidated — a gap that undermines the portfolio-grade quality standard.

## Scope

### In Scope

- Column description audit across 17 dbt models: 5 staging (`stg_ttc_subway_delays`, `stg_ttc_bus_delays`, `stg_ttc_streetcar_delays`, `stg_bike_trips`, `stg_weather_daily`), 5 intermediate (`int_ttc_delays_unioned`, `int_ttc_delays_enriched`, `int_bike_trips_enriched`, `int_daily_transit_metrics`, `int_daily_bike_metrics`), 4 core dimensions (`dim_date`, `dim_station`, `dim_weather`, `dim_ttc_delay_codes`), 3 mobility facts (`fct_transit_delays`, `fct_bike_trips`, `fct_daily_mobility`)
- Column description audit across 4 seeds: `ttc_station_mapping`, `ttc_delay_codes`, `bike_station_ref`, `date_spine`
- Source YAML documentation validation across 3 source files: `_ttc__sources.yml`, `_bike_share__sources.yml`, `_weather__sources.yml`
- `dbt docs generate` execution and `target/catalog.json` inspection for missing descriptions
- Lineage graph verification against DESIGN-DOC Section 6.1 entity relationship diagram and Section 6.3 model specifications

### Out of Scope

- Writing new model descriptions from scratch (all models documented in PH-05 through PH-07; this epic audits and fills gaps)
- Creating or modifying dbt models, intermediate logic, or mart transformations
- dbt docs site hosting or external deployment (portfolio presentation is PH-10)
- README creation or architecture diagrams (PH-10)
- Performance benchmarking (E-902)
- Elementary CI integration or operational runbooks (E-903)

## Technical Approach

### Architecture Decisions

- **Audit uses model SQL as source of truth, YAML as target** — for each model, compare the SELECT column list in the `.sql` file against the `columns:` block in the corresponding `_models.yml` file; any column present in SQL but absent from YAML is a documentation gap; this method catches columns added during refactoring that were never documented
- **`catalog.json` serves as machine-verifiable completeness proof** — `dbt docs generate` produces `target/catalog.json` containing every column in every materialized model with its description (or empty string if missing); programmatic inspection of this file provides a deterministic answer to "are all descriptions present" without manual file-by-file review
- **Lineage verification is visual, not programmatic** — dbt's `target/manifest.json` encodes the full DAG, but the lineage graph rendered by `dbt docs serve` is the artifact that portfolio reviewers inspect; visual verification confirms that the rendered graph matches DESIGN-DOC Section 6.1, including correct fact-to-dimension relationships and staging-to-intermediate-to-marts flow
- **Source documentation validates table-level descriptions and freshness configuration** — dbt source YAML files (`_*__sources.yml`) define upstream raw tables with `description`, `loaded_at_field`, and `freshness` blocks; verifying these ensures that `dbt source freshness` and `dbt docs` render meaningful source metadata
- **Ephemeral models are absent from catalog.json** — intermediate models compile as CTEs and produce no Snowflake catalog entry; their documentation completeness is verified via YAML inspection alone in S001, not via catalog.json in S003

### Integration Points

- **Model YAML files** — `_ttc__models.yml` (244 lines, 3 models), `_bike_share__models.yml` (78 lines, 1 model), `_weather__models.yml` (81 lines, 1 model), `_int__models.yml` (440 lines, 5 models), `_core__models.yml` (252 lines, 4 models), `_mobility__models.yml` (296 lines, 3 models)
- **Source YAML files** — `_ttc__sources.yml`, `_bike_share__sources.yml`, `_weather__sources.yml`
- **Seed documentation** — `seeds/_seeds.yml` (4 seeds with column descriptions)
- **dbt artifacts** — `target/catalog.json`, `target/manifest.json`, `target/index.html`
- **CI pipeline** — `dbt docs generate` already executes in `.github/workflows/ci-dbt.yml`; `target/catalog.json` already uploaded as part of `dbt-artifacts` artifact

### Repository Areas

- `models/staging/ttc/_ttc__models.yml` (verify, potential modify)
- `models/staging/bike_share/_bike_share__models.yml` (verify, potential modify)
- `models/staging/weather/_weather__models.yml` (verify, potential modify)
- `models/intermediate/_int__models.yml` (verify, potential modify)
- `models/marts/core/_core__models.yml` (verify, potential modify)
- `models/marts/mobility/_mobility__models.yml` (verify, potential modify)
- `models/staging/ttc/_ttc__sources.yml` (verify)
- `models/staging/bike_share/_bike_share__sources.yml` (verify)
- `models/staging/weather/_weather__sources.yml` (verify)
- `seeds/_seeds.yml` (verify)

### Risks

| Risk                                                                                                                                                               | Likelihood | Impact | Mitigation                                                                                                                                                                                                                                            |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------- | ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Audit reveals undocumented columns in models that were refactored after initial YAML creation (e.g., columns added during E-602 staging fix not reflected in YAML) | Medium     | Medium | Cross-reference each model's SQL SELECT list against YAML columns; add missing descriptions inline during S001; commit YAML changes as part of E-901                                                                                                  |
| `dbt docs generate` reports warnings for ephemeral models absent from catalog (intermediate layer)                                                                 | Medium     | Low    | Ephemeral models compile as CTEs and produce no catalog entry; verify documentation completeness via YAML inspection alone for intermediate models; document this limitation in S003 technical notes                                                  |
| Lineage graph shows unexpected edges from dbt package internal models (Elementary, dbt_utils) cluttering the visualization                                         | Low        | Low    | Filter dbt docs lineage view to individual model subtrees (e.g., `+fct_daily_mobility+`) to isolate project models from package models; document any package-injected nodes                                                                           |
| Source YAML files lack column-level descriptions (only table-level descriptions added in PH-05)                                                                    | High       | Medium | Source column descriptions are not required by the PH-09 exit criterion (`dbt docs generate` evaluates model descriptions, not source column descriptions); document source column documentation as a recommended improvement but not a PH-09 blocker |

## Stories

| ID   | Story                                                            | Points | Dependencies | Status |
| ---- | ---------------------------------------------------------------- | ------ | ------------ | ------ |
| S001 | Audit column-level descriptions across all 17 models and 4 seeds | 5      | None         | Complete |
| S002 | Validate source YAML documentation completeness                  | 3      | None         | Complete |
| S003 | Generate dbt docs site and validate zero missing descriptions    | 5      | S001         | Complete |
| S004 | Verify lineage graph accuracy against DESIGN-DOC entity model    | 3      | S003         | Complete |

---

### S001: Audit Column-Level Descriptions Across All 17 Models and 4 Seeds

**Description**: Cross-reference every column in each model's SQL SELECT list against its corresponding `_models.yml` column descriptions, identifying and filling any gaps to guarantee 100% column documentation coverage.

**Acceptance Criteria**:

- [ ] Every column in `stg_ttc_subway_delays` (12 columns), `stg_ttc_bus_delays` (12 columns), `stg_ttc_streetcar_delays` (12 columns) has a non-empty description in `_ttc__models.yml`
- [ ] Every column in `stg_bike_trips` (11 columns) has a non-empty description in `_bike_share__models.yml`
- [ ] Every column in `stg_weather_daily` (13 columns) has a non-empty description in `_weather__models.yml`
- [ ] Every column in `int_ttc_delays_unioned` (14 columns), `int_ttc_delays_enriched` (19 columns), `int_bike_trips_enriched` (20 columns), `int_daily_transit_metrics` (12 columns), `int_daily_bike_metrics` (7 columns) has a non-empty description in `_int__models.yml`
- [ ] Every column in `dim_date` (10 columns), `dim_station` (7 columns), `dim_weather` (12 columns), `dim_ttc_delay_codes` (4 columns) has a non-empty description in `_core__models.yml`
- [ ] Every column in `fct_transit_delays` (10 columns), `fct_bike_trips` (9 columns), `fct_daily_mobility` (16 columns) has a non-empty description in `_mobility__models.yml`
- [ ] Every column in all 4 seeds (`ttc_station_mapping`, `ttc_delay_codes`, `bike_station_ref`, `date_spine`) has a non-empty description in `seeds/_seeds.yml`
- [ ] Any gaps discovered are filled with descriptions matching the column's type, purpose, and lineage — consistent in voice with existing descriptions
- [ ] `dbt parse` succeeds with zero errors after any YAML modifications

**Technical Notes**: Compare the `renamed` CTE's SELECT column aliases in each staging model `.sql` file against the YAML `columns:` block. For intermediate models, compare the final SELECT list. For mart models, compare the output column list. Seed column lists are defined in `_seeds.yml`. Count each model's columns by reading the SQL source; any column in SQL but not in YAML is a gap. This story is primarily a verification pass — PH-05 through PH-07 added descriptions as part of their Definition of Done — but post-refactoring gaps (e.g., the E-602 staging fix that changed `stg_bike_trips` from `::int` to `try_cast`) may have introduced undocumented changes.

**Definition of Done**:

- [ ] Audit results documented (model-by-model column count comparison)
- [ ] Any YAML gaps filled and committed to feature branch
- [ ] `dbt parse` passes locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S002: Validate Source YAML Documentation Completeness

**Description**: Verify that all 3 source YAML files contain table-level descriptions, database/schema references, and freshness configuration, ensuring dbt docs renders meaningful source metadata for upstream raw tables.

**Acceptance Criteria**:

- [ ] `_ttc__sources.yml` defines 3 sources (`ttc_subway_delays`, `ttc_bus_delays`, `ttc_streetcar_delays`) with non-empty `description` fields
- [ ] `_bike_share__sources.yml` defines 1 source (`bike_share_trips`) with non-empty `description` field
- [ ] `_weather__sources.yml` defines 1 source (`weather_daily`) with non-empty `description` field
- [ ] All 5 sources specify `database: TORONTO_MOBILITY` and `schema: RAW`
- [ ] All 5 sources have `loaded_at_field` configured for source freshness monitoring
- [ ] All 5 sources have `freshness` block with `warn_after` and `error_after` thresholds
- [ ] `dbt parse` succeeds with zero errors

**Technical Notes**: Source YAML files were created in E-501 (TTC sources) and E-502 (Bike Share, Weather sources). Table-level descriptions and freshness configuration are the primary documentation targets for sources. Column-level descriptions on sources are not required by the PH-09 exit criterion (`dbt docs generate` evaluates model descriptions, not source column descriptions), but their absence should be noted as a recommended future improvement. The `loaded_at_field` must use `try_cast` per the E-501 discovery that bare column names fail freshness evaluation on VARCHAR source columns.

**Definition of Done**:

- [ ] All 3 source YAML files verified
- [ ] Any gaps filled and committed to feature branch
- [ ] `dbt parse` passes locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S003: Generate dbt Docs Site and Validate Zero Missing Descriptions

**Description**: Execute `dbt docs generate` and inspect the output `target/catalog.json` to confirm that every model and column has a non-empty description, satisfying the PH-09 exit criterion of zero missing descriptions.

**Acceptance Criteria**:

- [ ] `dbt docs generate` succeeds with exit code 0
- [ ] `target/catalog.json` is produced and contains entries for all 7 materialized mart models (4 dimensions + 3 facts), all 5 staging views, and all 4 seeds
- [ ] No model in `catalog.json` has an empty `description` field
- [ ] No column across any model in `catalog.json` has an empty `description` field — specifically, every entry under `nodes.<model>.columns.<column>.comment` contains descriptive text
- [ ] `target/index.html` is generated for local dbt docs browsing
- [ ] Intermediate models (ephemeral) are confirmed absent from `catalog.json` — expected behavior since ephemeral models compile as CTEs and have no Snowflake catalog entry
- [ ] Intermediate model documentation completeness is confirmed via `_int__models.yml` inspection from S001 (not catalog.json)

**Technical Notes**: `dbt docs generate` produces three artifacts: `manifest.json` (compiled DAG), `catalog.json` (Snowflake INFORMATION_SCHEMA metadata including column descriptions), and `index.html` (static site entry point). Column descriptions from `_models.yml` are persisted to Snowflake via `COMMENT ON COLUMN` when models are materialized as tables/views — these appear in `catalog.json`. Ephemeral models do not exist in Snowflake's catalog and cannot be validated via `catalog.json`; YAML inspection is the only verification path for intermediate models. If the catalog shows columns without descriptions, the gap must be traced to a missing YAML entry and remediated before this story completes.

**Definition of Done**:

- [ ] `dbt docs generate` passes with exit code 0
- [ ] Zero missing descriptions in catalog.json confirmed
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S004: Verify Lineage Graph Accuracy Against DESIGN-DOC Entity Model

**Description**: Inspect the dbt docs lineage graph (via `dbt docs serve`) and confirm that all model relationships match the data flow defined in DESIGN-DOC Section 6.1 (ER diagram), Section 5.1 (architecture), and Section 6.3 (model specifications).

**Acceptance Criteria**:

- [ ] `dbt docs serve` renders the lineage graph without errors
- [ ] 5 staging models appear as leaf nodes sourcing from 5 raw tables
- [ ] 5 intermediate models appear downstream of their respective staging models: `int_ttc_delays_unioned` ← `stg_ttc_{subway,bus,streetcar}_delays`; `int_ttc_delays_enriched` ← `int_ttc_delays_unioned` + seeds; `int_bike_trips_enriched` ← `stg_bike_trips` + seed; `int_daily_transit_metrics` ← `int_ttc_delays_enriched`; `int_daily_bike_metrics` ← `int_bike_trips_enriched`
- [ ] 4 dimension models source correctly: `dim_date` ← `date_spine` seed; `dim_station` ← `ttc_station_mapping` seed + `bike_station_ref` seed; `dim_weather` ← `stg_weather_daily`; `dim_ttc_delay_codes` ← `ttc_delay_codes` seed
- [ ] 3 fact models source correctly: `fct_transit_delays` ← `int_ttc_delays_enriched`; `fct_bike_trips` ← `int_bike_trips_enriched`; `fct_daily_mobility` ← `int_daily_transit_metrics` + `int_daily_bike_metrics`
- [ ] No orphan models (nodes without upstream connections except raw sources and seeds)
- [ ] No unexpected cross-layer dependencies (e.g., marts referencing staging directly, bypassing intermediate)

**Technical Notes**: The lineage graph is the primary visual artifact for portfolio presentation and architectural review. `dbt docs serve` launches a local web server rendering the DAG from `manifest.json`. Elementary package models and dbt_utils package models appear in the graph but are external to the project's analytical DAG — filter these out when verifying project-specific lineage. The graph must demonstrate the medallion architecture flow: Sources → Staging → Intermediate → Marts, with seeds feeding into intermediate and dimension models. Any deviation from the DESIGN-DOC ER diagram (Section 6.1) indicates either a model implementation defect or a documentation inaccuracy.

**Definition of Done**:

- [ ] Lineage graph verified against DESIGN-DOC Sections 5.1, 6.1, and 6.3
- [ ] Any discrepancies documented and resolved
- [ ] PR opened with linked issue
- [ ] CI checks green

## Exit Criteria

This epic is complete when:

- [ ] All 17 models and 4 seeds have 100% column-level descriptions in their corresponding YAML files
- [ ] All 3 source YAML files have table-level descriptions and freshness configuration
- [ ] `dbt docs generate` succeeds with zero missing descriptions in `target/catalog.json`
- [ ] Lineage graph accurately represents the medallion architecture defined in DESIGN-DOC Section 6.1
- [ ] `dbt parse` and `dbt docs generate` pass with zero errors

# Performance Benchmarks & Analytical Queries

| Field        | Value          |
| ------------ | -------------- |
| Epic ID      | E-902          |
| Phase        | PH-09          |
| Owner        | @dinesh-git17  |
| Status       | Complete       |
| Dependencies | [E-701, E-702] |
| Created      | 2026-02-09     |

## Context

DESIGN-DOC Section 1.4 defines a success criterion: "Benchmark queries < 5 seconds" on an X-Small Snowflake warehouse. Section 15.4 specifies 5 benchmark queries covering the primary analytical access patterns — full fact table scan, fact-dimension joins with aggregation, cross-modal correlation, and time-series trending. Section 15.3 provides complete SQL for 3 analytical queries. The `/analyses/` directory is empty (`.gitkeep` only), and no benchmark execution results exist. TESTS.md Section 1 lists Performance Benchmarks as the top tier of the test pyramid, marked "Deferred to PH-09." This epic populates `/analyses/` with executable SQL files, runs the benchmark suite against the production Snowflake environment, and documents results with timing, row counts, and warehouse configuration. These artifacts validate that the data model meets the performance target and provide portfolio reviewers with ready-to-run analytical examples.

## Scope

### In Scope

- 5 benchmark SQL files in `/analyses/` from DESIGN-DOC Section 15.3-15.4: `daily_mobility_summary.sql`, `top_delay_stations.sql`, `bike_weather_correlation.sql`, `cross_modal_analysis.sql`, `monthly_trends.sql`
- Execution of all 5 benchmark queries on X-Small Snowflake warehouse (`TRANSFORM_WH`)
- Timing capture for each query (wall clock and Snowflake query profile metrics)
- Performance results documentation in `docs/PH-09/performance_results.md` with timing, row counts, and warehouse metadata
- Validation that all 5 queries complete under the 5-second threshold (DESIGN-DOC Section 10.1)
- Removal of `analyses/.gitkeep` after real SQL files are committed
- TESTS.md update to replace "Deferred to PH-09" with benchmark results reference

### Out of Scope

- Query optimization or index tuning (if all queries pass the 5-second threshold, no optimization is required)
- Materialization strategy changes to improve performance
- Snowflake warehouse sizing recommendations beyond X-Small (X-Small is the fixed target per DESIGN-DOC Section 10.1)
- Dashboard or visualization creation from query results
- README integration of sample queries (PH-10)

## Technical Approach

### Architecture Decisions

- **Queries use `{{ ref() }}` syntax for model references** — `/analyses/` files in dbt support Jinja templating; all queries reference mart models via `{{ ref('fct_transit_delays') }}` rather than hardcoded schema-qualified table names; this ensures correct schema resolution across environments (dev, CI, prod) and maintains dbt DAG awareness
- **Benchmark queries sourced verbatim from DESIGN-DOC Section 15.3 and 15.4** — Sections 15.3 defines exact SQL for 3 analytical queries (`top_delay_stations`, `bike_weather_correlation`, `cross_modal_analysis`); Section 15.4 references 2 additional queries by description and expected row count (`daily_mobility_summary`, `monthly_trends`); all 5 are implemented as standalone `.sql` files
- **Timing captured via Snowflake QUERY_HISTORY** — after execution, query `INFORMATION_SCHEMA.QUERY_HISTORY()` filtered by `QUERY_TAG = 'benchmark_ph09'` to extract elapsed time, bytes scanned, and rows produced; INFORMATION_SCHEMA provides real-time session results without the 45-minute latency of ACCOUNT_USAGE views
- **5-second threshold is wall clock time on X-Small warehouse** — DESIGN-DOC Section 10.1: "Any query taking > 5 seconds on production-scale data (~30M rows) is a failure"; benchmark validates this against actual production data volumes (237K transit delays, 21.8M bike trips, 1,827 daily mobility rows)
- **`.gitkeep` removed after first SQL file committed** — follows the pattern established in E-401 (`seeds/.gitkeep`), E-701 (`models/marts/core/.gitkeep`), and E-702 (`models/marts/mobility/.gitkeep`)

### Integration Points

- **Mart models** — all 5 queries reference mart layer models: `fct_transit_delays` (237,446 rows), `fct_bike_trips` (21,795,223 rows), `fct_daily_mobility` (1,827 rows), `dim_station` (1,085 rows), `dim_weather` (2,922 rows), `dim_date` (2,922 rows)
- **Snowflake warehouse** — `TRANSFORM_WH` (X-Small, auto-suspend 60s) per DESIGN-DOC Section 10.1
- **CI pipeline** — `/analyses/*.sql` files are included in `ci-dbt.yml` paths trigger but are not executed by `dbt build`; `dbt compile` resolves their `{{ ref() }}` expressions for validation
- **DESIGN-DOC Section 15.3 and 15.4** — query definitions and benchmark specifications
- **TESTS.md** — Performance Benchmarks layer currently reads "Deferred to PH-09"; update reference after benchmarks complete

### Repository Areas

- `analyses/daily_mobility_summary.sql` (new)
- `analyses/top_delay_stations.sql` (new)
- `analyses/bike_weather_correlation.sql` (new)
- `analyses/cross_modal_analysis.sql` (new)
- `analyses/monthly_trends.sql` (new)
- `analyses/.gitkeep` (remove)
- `docs/PH-09/performance_results.md` (new)
- `docs/TESTS.md` (modify — update performance benchmark reference)

### Risks

| Risk                                                                                                                                                    | Likelihood | Impact | Mitigation                                                                                                                                                                                                                                                                                                                                       |
| ------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `fct_bike_trips` full table scan (21.8M rows) exceeds 5 seconds on X-Small warehouse                                                                    | Medium     | High   | Benchmark queries aggregate `fct_daily_mobility` (1,827 rows) rather than scanning `fct_bike_trips` directly; the `top_delay_stations` query scans `fct_transit_delays` (237K rows) with a join to `dim_station` (1K rows); if any query exceeds 5 seconds, analyze the Snowflake query profile to identify bottlenecks before declaring failure |
| Snowflake warehouse cold start adds 1-2 seconds to first query execution, skewing timing results                                                        | Medium     | Low    | Execute a warm-up query (`SELECT 1 FROM fct_daily_mobility LIMIT 1`) before the benchmark suite to ensure the warehouse is active; document whether timing includes or excludes cold start                                                                                                                                                       |
| `monthly_trends.sql` is referenced in DESIGN-DOC Section 15.4 by description only — no SQL provided; implementation may not match reviewer expectations | Medium     | Low    | Implement as a time-series aggregation of `fct_daily_mobility` grouped by year-month, computing monthly averages for transit delays and bike trips; this is the natural interpretation of "Time-series aggregation by month" producing ~72 rows (6 years × 12 months)                                                                            |
| SQLFluff fails on `{{ ref() }}` Jinja syntax in analyses files due to templating conflict                                                               | Low        | Low    | SQLFluff with dbt templater handles `{{ ref() }}` in `.sql` files; if linting fails, configure SQLFluff templater in `.sqlfluff` for the analyses directory; existing `.sqlfluff` configuration already supports dbt dialect                                                                                                                     |

## Stories

| ID   | Story                                                             | Points | Dependencies | Status |
| ---- | ----------------------------------------------------------------- | ------ | ------------ | ------ |
| S001 | Create 5 benchmark SQL files in /analyses/                        | 5      | None         | Complete |
| S002 | Execute benchmark suite on X-Small warehouse and capture results  | 5      | S001         | Complete |
| S003 | Document benchmark methodology and results                        | 3      | S002         | Complete |
| S004 | Validate all queries under 5-second threshold and update TESTS.md | 3      | S002         | Complete |

---

### S001: Create 5 Benchmark SQL Files in /analyses/

**Description**: Implement the 5 benchmark queries defined in DESIGN-DOC Section 15.3-15.4 as executable dbt-compatible SQL files in `/analyses/`, replacing the `.gitkeep` placeholder.

**Acceptance Criteria**:

- [ ] File `analyses/daily_mobility_summary.sql` exists — full scan of `{{ ref('fct_daily_mobility') }}` returning ~2,200 rows with date, transit, and bike metrics (DESIGN-DOC Section 15.4 Query #1)
- [ ] File `analyses/top_delay_stations.sql` exists — aggregation on `{{ ref('fct_transit_delays') }}` joined to `{{ ref('dim_station') }}` returning top 10 stations by total delay minutes (DESIGN-DOC Section 15.3/15.4 Query #2)
- [ ] File `analyses/bike_weather_correlation.sql` exists — join of `{{ ref('fct_daily_mobility') }}` with `{{ ref('dim_weather') }}` grouping by temperature bucket, returning 4 rows (DESIGN-DOC Section 15.3/15.4 Query #3)
- [ ] File `analyses/cross_modal_analysis.sql` exists — conditional aggregation on `{{ ref('fct_daily_mobility') }}` grouping by TTC delay category, returning 3 rows (DESIGN-DOC Section 15.3/15.4 Query #4)
- [ ] File `analyses/monthly_trends.sql` exists — time-series aggregation by month across `{{ ref('fct_daily_mobility') }}` joined to `{{ ref('dim_date') }}`, returning ~72 rows (DESIGN-DOC Section 15.4 Query #5)
- [ ] Each file contains a comment header documenting: query purpose, expected row count, and DESIGN-DOC section reference
- [ ] All files use `{{ ref() }}` for model references — no hardcoded table names
- [ ] `analyses/.gitkeep` is removed
- [ ] `dbt compile` succeeds with all 5 files resolving their `{{ ref() }}` expressions

**Technical Notes**: DESIGN-DOC Section 15.3 provides complete SQL for `top_delay_stations.sql`, `bike_weather_correlation.sql`, and `cross_modal_analysis.sql`. Use the provided SQL as the starting point, adapting column names to match the actual mart model implementations (e.g., E-702 fact table column names). `daily_mobility_summary.sql` and `monthly_trends.sql` are specified by description and expected row counts in Section 15.4 — implement `daily_mobility_summary` as a full scan of `fct_daily_mobility` ordered by date, and `monthly_trends` as a GROUP BY on year/month with aggregated transit and bike metrics. dbt does not execute files in `/analyses/` during `dbt build` — they are compiled but not run. Execution requires direct Snowflake execution of the compiled SQL from `target/compiled/`.

**Definition of Done**:

- [ ] 5 SQL files committed to feature branch
- [ ] `.gitkeep` removed
- [ ] `dbt compile` passes
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S002: Execute Benchmark Suite on X-Small Warehouse and Capture Results

**Description**: Execute all 5 compiled benchmark queries against the Snowflake production environment using `TRANSFORM_WH` (X-Small), capturing execution time, rows returned, and bytes scanned for each query.

**Acceptance Criteria**:

- [ ] Snowflake session configured with `QUERY_TAG = 'benchmark_ph09'` before execution
- [ ] `TRANSFORM_WH` warehouse confirmed as X-Small size before benchmark execution
- [ ] A warm-up query executed before the benchmark suite to ensure the warehouse is active and not cold-starting
- [ ] Each of the 5 benchmark queries executed from `target/compiled/toronto_mobility/analyses/*.sql` and completed without errors
- [ ] For each query, the following metrics are captured: query ID, execution time (seconds), rows returned, bytes scanned, compilation time
- [ ] Timing results captured from `INFORMATION_SCHEMA.QUERY_HISTORY()` filtered by `QUERY_TAG = 'benchmark_ph09'`
- [ ] Raw results saved for documentation in S003

**Technical Notes**: Compile benchmark queries via `dbt compile`, then execute the compiled SQL from `target/compiled/toronto_mobility/analyses/*.sql` directly in Snowflake. Set `ALTER SESSION SET QUERY_TAG = 'benchmark_ph09';` before execution to tag all queries for retrieval. After all 5 queries complete, extract timing via:

```sql
SELECT query_id,
       query_text,
       total_elapsed_time / 1000 AS elapsed_seconds,
       rows_produced,
       bytes_scanned,
       compilation_time / 1000 AS compile_seconds
FROM table(information_schema.query_history())
WHERE query_tag = 'benchmark_ph09'
ORDER BY start_time;
```

Use `INFORMATION_SCHEMA.QUERY_HISTORY()` (table function) for real-time session results; avoid `ACCOUNT_USAGE.QUERY_HISTORY` which has up to 45-minute latency.

**Definition of Done**:

- [ ] All 5 queries executed without errors
- [ ] Timing metrics captured for all queries
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S003: Document Benchmark Methodology and Results

**Description**: Create `docs/PH-09/performance_results.md` documenting the benchmark methodology, warehouse configuration, execution results, and pass/fail assessment against the 5-second threshold.

**Acceptance Criteria**:

- [ ] File `docs/PH-09/performance_results.md` exists
- [ ] Document contains a **Methodology** section describing: warehouse size (X-Small), warm-up procedure, timing source (QUERY_HISTORY), benchmark execution date, and dbt version
- [ ] Document contains a **Warehouse Configuration** section listing: warehouse name (`TRANSFORM_WH`), size (X-Small), auto-suspend (60s), Snowflake edition, and credit cost per hour
- [ ] Document contains a **Results** table with columns: Query, File, Elapsed (s), Rows, Bytes Scanned, Status (PASS if < 5s, FAIL if >= 5s)
- [ ] Document contains a **Summary** section confirming the count of queries passing vs. failing the 5-second threshold
- [ ] If any query exceeds 5 seconds, the document contains a **Root Cause Analysis** section with Snowflake query profile findings and recommended optimizations
- [ ] Document voice is cold, precise, technical — per CLAUDE.md Section 1.2
- [ ] No AI-attribution breadcrumbs, narrative filler, or placeholder text

**Technical Notes**: The document serves as the audit trail for DESIGN-DOC Section 1.4 ("Benchmark queries < 5 seconds") and DESIGN-DOC Section 10.1 ("Any query taking > 5 seconds on production-scale data is a failure"). This file is committed to the repository as permanent documentation of the project's performance characteristics at current data volumes.

**Definition of Done**:

- [ ] Documentation committed to feature branch
- [ ] All benchmark results accurately captured
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S004: Validate All Queries Under 5-Second Threshold and Update TESTS.md

**Description**: Confirm that all 5 benchmark queries completed within the 5-second execution time target, and update TESTS.md to replace the "Deferred to PH-09" placeholder with a reference to the benchmark results document.

**Acceptance Criteria**:

- [ ] All 5 benchmark queries have elapsed time < 5.0 seconds as documented in S003
- [ ] No query required retry or warehouse upscaling to meet the threshold
- [ ] `docs/PH-09/performance_results.md` reflects a final status of PASS for all 5 queries
- [ ] `docs/TESTS.md` Section 1 test pyramid updated: "Performance Benchmarks" layer references `docs/PH-09/performance_results.md` instead of "Deferred to PH-09"
- [ ] `docs/TESTS.md` Section 1 table updated: Performance Benchmarks coverage column references "5 queries, all < 5s" instead of "Deferred to PH-09"

**Technical Notes**: If any query exceeds 5 seconds, this story cannot complete. Remediation options in order of preference: (1) analyze Snowflake query profile for optimization opportunities (partition pruning, join reordering), (2) verify X-Small warehouse was not throttled by concurrent queries during execution, (3) re-execute with warehouse pre-warmed and no concurrent load. If a legitimate performance issue exists after remediation attempts, document the finding with query profile evidence — do not change the 5-second threshold without a DESIGN-DOC amendment (Section 14 decisions log).

**Definition of Done**:

- [ ] All 5 queries confirmed under 5-second threshold
- [ ] TESTS.md updated with benchmark reference
- [ ] PR opened with linked issue
- [ ] CI checks green

## Exit Criteria

This epic is complete when:

- [ ] 5 benchmark SQL files exist in `/analyses/`: `daily_mobility_summary.sql`, `top_delay_stations.sql`, `bike_weather_correlation.sql`, `cross_modal_analysis.sql`, `monthly_trends.sql`
- [ ] All files use `{{ ref() }}` syntax and pass `dbt compile`
- [ ] `analyses/.gitkeep` is removed
- [ ] All 5 queries execute on X-Small warehouse in under 5 seconds
- [ ] `docs/PH-09/performance_results.md` documents methodology and results with timing for all queries
- [ ] `docs/TESTS.md` performance benchmark layer references the results document

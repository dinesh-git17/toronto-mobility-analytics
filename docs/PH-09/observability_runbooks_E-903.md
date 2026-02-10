# Elementary CI Integration & Operational Runbooks

| Field        | Value          |
| ------------ | -------------- |
| Epic ID      | E-903          |
| Phase        | PH-09          |
| Owner        | @dinesh-git17  |
| Status       | Complete       |
| Dependencies | [E-802, E-803] |
| Created      | 2026-02-09     |

## Context

E-802 configured 17 Elementary anomaly tests across all 7 mart models, established the Elementary baseline via `dbt run --select elementary`, and generated an initial `edr report` locally. E-803 verified that the complete test suite (135 tests) passes in CI and documented the test strategy in `docs/TESTS.md`. However, the CI pipeline (`.github/workflows/ci-dbt.yml`) does not include Elementary report generation — `dbt build` executes Elementary tests as part of the test suite, but the `edr report` HTML artifact is not produced or uploaded during CI runs. DESIGN-DOC Section 9.5 specifies Elementary CI integration: "`dbt run --select elementary` followed by `edr report --env ci`." Beyond CI integration, PH-09 requires operational documentation: runbooks for pipeline operations (ingestion, rebuild, troubleshooting) and observability procedures (Elementary report interpretation, freshness monitoring, anomaly response). Without these artifacts, the project lacks the operational context required for portfolio reviewers to assess production-readiness and for contributors to maintain the system independently.

## Scope

### In Scope

- CI pipeline modification: add Elementary report generation step (`dbt run --select elementary` and `edr report`) with HTML artifact upload to `.github/workflows/ci-dbt.yml`
- Pipeline operations runbook (`docs/RUNBOOK.md`): data refresh procedures, full rebuild from scratch, common troubleshooting scenarios, schema change response protocol, environment setup
- Observability procedures document (`docs/OBSERVABILITY.md`): Elementary report interpretation, anomaly response matrix, source freshness monitoring, dbt artifact analysis, Snowflake native monitoring
- End-to-end PH-09 exit criteria validation: `dbt docs generate` with zero missing descriptions (E-901), Elementary dashboard operational (E-802 + E-903), performance benchmarks documented (E-902)

### Out of Scope

- Elementary alerting integrations (Slack, email, PagerDuty) — DESIGN-DOC Section 9.3 notes GitHub notifications are sufficient for portfolio scope
- Elementary dashboard external hosting — the report is a local HTML file or CI artifact, not a deployed web service
- Custom Elementary anomaly thresholds or training period modifications (defaults sufficient per E-802)
- New dbt models, tests, or transformations
- README creation or architecture diagrams (PH-10)
- CI workflow structural changes beyond adding the Elementary report step

## Technical Approach

### Architecture Decisions

- **Elementary report generation added as a post-build CI step** — `dbt run --select elementary` must execute after `dbt build` (which includes model materialization and test execution) to capture the latest test results and model metadata in Elementary's artifact tables; `edr report` then generates an HTML report from these artifacts; the step is appended after the existing `dbt docs generate` step in the `dbt-build` job
- **`edr report` uses `continue-on-error: true` in CI** — Elementary's anomaly detection requires historical baseline data accumulated over multiple runs; on first CI execution (or in isolated CI schemas), Elementary may lack sufficient history to perform anomaly comparison; `continue-on-error: true` prevents this expected limitation from blocking builds during the baseline establishment period
- **Elementary report artifact uploaded via `actions/upload-artifact`** — the HTML report (`edr_target/elementary_report.html`) is uploaded as a named CI artifact (`elementary-report`) alongside the existing `dbt-artifacts` (manifest.json, run_results.json, catalog.json); this makes the report downloadable from any CI run without external hosting
- **Runbook structure follows incident response patterns** — `docs/RUNBOOK.md` organizes procedures by scenario (data refresh, full rebuild, test failure triage, schema change response) rather than by tool; each procedure includes prerequisite checks, step-by-step commands, expected outputs, and rollback instructions
- **Observability document maps Elementary test types to response actions** — `docs/OBSERVABILITY.md` creates a decision matrix for each Elementary test type (`volume_anomalies`, `freshness_anomalies`, `schema_changes`): what the test monitors, what a failure means, and what corrective action to take; this transforms raw test output into actionable operations guidance

### Integration Points

- **CI pipeline** — `.github/workflows/ci-dbt.yml` — modify the `dbt-build` job to add Elementary report generation steps and artifact upload
- **Elementary Python package** — `elementary-data` must be installed in the CI environment alongside `dbt-snowflake`; version must match the dbt package version (0.16.1) per E-802 compatibility requirement
- **dbt artifacts** — `target/manifest.json`, `target/run_results.json`, `target/catalog.json` — already uploaded in CI; Elementary report adds `edr_target/elementary_report.html`
- **Existing documentation** — `DESIGN-DOC.md` (architecture reference), `docs/TESTS.md` (test strategy), `CLAUDE.md` (governance) — runbooks cross-reference these for context
- **E-901 artifacts** — dbt docs site with zero missing descriptions (verified in E-901 S003)
- **E-902 artifacts** — `docs/PH-09/performance_results.md` with benchmark timing results (produced in E-902 S003)

### Repository Areas

- `.github/workflows/ci-dbt.yml` (modify — add Elementary report steps)
- `docs/RUNBOOK.md` (new)
- `docs/OBSERVABILITY.md` (new)

### Risks

| Risk                                                                                                                                                                  | Likelihood | Impact | Mitigation                                                                                                                                                                                                                                                                                                             |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `elementary-data` Python package installation in CI exceeds timeout or conflicts with `dbt-snowflake` dependencies                                                    | Medium     | High   | Install `elementary-data` via `uv pip install` alongside `dbt-core` and `dbt-snowflake`; pin version to match dbt package (0.16.1); test installation locally before committing CI changes; add `continue-on-error: true` to the Elementary steps to prevent blocking builds during integration                        |
| `edr report` fails in CI because Elementary artifact tables do not exist in the CI-isolated schema (CI uses per-PR schema per ci-dbt.yml)                             | High       | Medium | `dbt build` in CI materializes all models including Elementary package models; add explicit `dbt run --select elementary` after `dbt build` to ensure artifact tables are populated; CI reports show current-run metrics only (no historical anomaly comparison in isolated schemas) — document this expected behavior |
| Runbook content becomes stale as the project evolves beyond PH-09                                                                                                     | Medium     | Low    | Include "Last Updated" date and maintenance note at the top of each document (matching the pattern in TESTS.md); future phases that modify pipeline behavior must update RUNBOOK.md as part of their Definition of Done                                                                                                |
| PH-09 exit criteria validation in S004 requires Snowflake credentials for `dbt docs generate` and benchmark execution, which may not be available in all environments | Medium     | High   | E-901 and E-902 validate their respective exit criteria independently; S004 verifies artifacts exist and are complete without re-executing commands; CI pipeline validates `dbt docs generate` automatically on merge; document which criteria are CI-validated vs. locally-validated                                  |

## Stories

| ID   | Story                                           | Points | Dependencies     | Status |
| ---- | ----------------------------------------------- | ------ | ---------------- | ------ |
| S001 | Add Elementary report generation to CI pipeline | 5      | None             | Complete |
| S002 | Write pipeline operations runbook               | 5      | None             | Complete |
| S003 | Write observability and monitoring procedures   | 5      | None             | Complete |
| S004 | Validate PH-09 exit criteria end-to-end         | 3      | S001, S002, S003 | Complete |

---

### S001: Add Elementary Report Generation to CI Pipeline

**Description**: Modify `.github/workflows/ci-dbt.yml` to include Elementary model materialization, HTML report generation via `edr report`, and report artifact upload, completing the CI observability integration specified in DESIGN-DOC Section 9.5.

**Acceptance Criteria**:

- [ ] `.github/workflows/ci-dbt.yml` installs `elementary-data` Python package (version compatible with Elementary dbt package 0.16.1) before the report generation step
- [ ] `.github/workflows/ci-dbt.yml` contains a step executing `dbt run --select elementary` after the `dbt build` step, conditioned on Snowflake credentials being available
- [ ] `.github/workflows/ci-dbt.yml` contains a step executing `edr report` after the `dbt run --select elementary` step
- [ ] Both Elementary steps use `continue-on-error: true` to prevent failures from blocking the build during baseline establishment
- [ ] `.github/workflows/ci-dbt.yml` contains an `actions/upload-artifact` step uploading `edr_target/elementary_report.html` as a named artifact (`elementary-report`)
- [ ] The Elementary artifact is uploaded on both push to `main` and pull request events (when Snowflake credentials are available)
- [ ] All existing CI steps continue to function without regression
- [ ] All third-party actions remain pinned to SHA per CLAUDE.md Section 9.9

**Technical Notes**: The CI workflow currently installs `dbt-core` and `dbt-snowflake` via `uv tool install`. The `elementary-data` package must be installed separately — either `uv pip install "elementary-data[snowflake]"` or `pip install "elementary-data[snowflake]"` depending on the CI environment's pip availability. The `edr report` command generates `edr_target/elementary_report.html` by default. If `edr report` requires a specific profile target, use `edr report --profile-target ci` to reuse the CI-generated `profiles.yml`. The `continue-on-error: true` flag is intentional for the baseline establishment period — after multiple CI runs accumulate historical data, consider removing the flag in a future maintenance pass.

**Definition of Done**:

- [ ] CI workflow changes committed to feature branch
- [ ] CI pipeline executes Elementary steps without blocking on first run
- [ ] Elementary report artifact is downloadable from CI run
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S002: Write Pipeline Operations Runbook

**Description**: Create `docs/RUNBOOK.md` as the operational reference for pipeline management, covering data refresh, full rebuild, troubleshooting, and schema change response procedures.

**Acceptance Criteria**:

- [ ] File `docs/RUNBOOK.md` exists
- [ ] Document contains a **Last Updated** date and maintenance note at the top
- [ ] Document contains an **Environment Setup** section listing: required tools (Python 3.12, dbt-core 1.8+, dbt-snowflake, Snowflake account), configuration files (`profiles.yml`, environment variables), and initial setup commands (`dbt deps`, `dbt debug`)
- [ ] Document contains a **Data Refresh** section with step-by-step commands for: downloading new source files (`python scripts/ingest.py`), validating schema contracts, loading to Snowflake RAW tables, running `dbt build` to propagate changes through staging → intermediate → marts, and running `dbt test` to validate post-refresh data quality
- [ ] Document contains a **Full Rebuild** section with step-by-step commands for: dropping all dbt-managed objects (`dbt run --full-refresh`), reseeding reference data (`dbt seed --full-refresh`), running the full model build and test suite (`dbt build`), and re-establishing the Elementary baseline (`dbt run --select elementary`)
- [ ] Document contains a **Troubleshooting** section with at least 5 failure scenarios and resolution steps: schema validation failure (ingestion layer), dbt test failure by category (schema/singular/distribution/Elementary), Snowflake warehouse suspension or timeout, source freshness warnings or errors, and surrogate key collision or duplicate primary key
- [ ] Document contains a **Schema Change Response** section documenting the protocol when Toronto Open Data source schemas change: update `scripts/contracts.py`, re-run schema validation, update staging model SQL and YAML, run `dbt build --select state:modified+`
- [ ] Document cross-references `DESIGN-DOC.md` for architectural context and `docs/TESTS.md` for test strategy
- [ ] Document voice is cold, precise, technical — per CLAUDE.md Section 1.2
- [ ] No AI-attribution breadcrumbs, narrative filler, or placeholder text

**Technical Notes**: The runbook targets two audiences: (1) the project owner performing routine maintenance (data refresh, test triage), and (2) portfolio reviewers assessing operational maturity. Each procedure follows a consistent format: Prerequisites → Steps → Expected Output → Rollback. The ingestion pipeline scripts (`scripts/ingest.py`, `scripts/download.py`, `scripts/validate.py`, `scripts/transform.py`, `scripts/load.py`) were built in PH-03 (E-301, E-302, E-303); the runbook provides the operational wrapper. Commands reference exact script names and flags from the existing codebase.

**Definition of Done**:

- [ ] `docs/RUNBOOK.md` committed to feature branch
- [ ] All sections complete with actionable procedures
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S003: Write Observability and Monitoring Procedures

**Description**: Create `docs/OBSERVABILITY.md` as the operational reference for monitoring the data platform using Elementary, dbt artifacts, and Snowflake native observability, including anomaly interpretation, freshness monitoring, and response procedures.

**Acceptance Criteria**:

- [ ] File `docs/OBSERVABILITY.md` exists
- [ ] Document contains a **Last Updated** date and maintenance note at the top
- [ ] Document contains an **Elementary Report Interpretation** section explaining: how to generate the report (`edr report`), how to read the HTML dashboard (test results, model overview, lineage), and what each test type indicates (`volume_anomalies` = row count drift, `freshness_anomalies` = data staleness, `schema_changes` = column mutations)
- [ ] Document contains an **Anomaly Response Matrix** table mapping each Elementary test type to: trigger condition, severity classification, and corrective action with specific commands
- [ ] Document contains a **Source Freshness Monitoring** section documenting: `dbt source freshness` command, current thresholds (warn_after: 45 days, error_after: 90 days per DESIGN-DOC Section 7.4), and response procedures when freshness degrades
- [ ] Document contains a **dbt Artifacts** section describing: `manifest.json` (DAG and compiled SQL), `run_results.json` (execution times, test results), `catalog.json` (column metadata), and `sources.json` (freshness results) — with their locations, retention policy per DESIGN-DOC Section 9.1, and how to access them from CI artifacts
- [ ] Document contains a **Snowflake Native Monitoring** section documenting: `QUERY_HISTORY` for query performance tracking, `WAREHOUSE_METERING_HISTORY` for credit consumption, and key metrics from DESIGN-DOC Section 9.2 (model run time > 60s warning, > 300s error; source freshness > 45 days warning, > 90 days error)
- [ ] Document cross-references `DESIGN-DOC.md` Section 9 for observability architecture and `docs/TESTS.md` for test inventory
- [ ] Document voice is cold, precise, technical — per CLAUDE.md Section 1.2
- [ ] No AI-attribution breadcrumbs, narrative filler, or placeholder text

**Technical Notes**: This document bridges the gap between Elementary's technical test output and operational decision-making. Elementary's HTML report provides raw test results; this document provides the interpretation framework. The Anomaly Response Matrix is the primary operational artifact — it transforms each test failure type into a deterministic action sequence. The document complements `docs/TESTS.md` (which inventories tests and thresholds) by adding the "what to do when a test fails" dimension. All 17 Elementary tests configured in E-802 must be represented in the response matrix.

**Definition of Done**:

- [ ] `docs/OBSERVABILITY.md` committed to feature branch
- [ ] All sections complete with actionable procedures
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S004: Validate PH-09 Exit Criteria End-to-End

**Description**: Verify that all three PH-09 exit criteria from `docs/PHASES.md` are satisfied: `dbt docs generate` succeeds with zero missing descriptions, Elementary dashboard is operational, and performance benchmarks are documented.

**Acceptance Criteria**:

- [ ] **Exit Criterion 1 — Documentation completeness**: `dbt docs generate` succeeds with zero missing descriptions — confirmed by E-901 S003 (`target/catalog.json` contains no empty description fields); verification result documented
- [ ] **Exit Criterion 2 — Elementary operational**: `edr report` produces a valid HTML file with all 7 mart models visible — confirmed by E-802 S005 (initial report) and E-903 S001 (CI integration); CI artifact contains the Elementary report
- [ ] **Exit Criterion 3 — Performance benchmarks documented**: `docs/PH-09/performance_results.md` exists with timing results for 5 queries, all under 5 seconds — confirmed by E-902 S003 and S004
- [ ] All PH-09 epic exit criteria verified: E-901 (documentation completeness), E-902 (benchmark validation), E-903 S001-S003 (CI integration, runbooks)
- [ ] `dbt build` passes with zero ERROR results across all test categories (135 tests: 108 schema + 5 singular + 5 dbt_expectations + 17 Elementary)
- [ ] `docs/RUNBOOK.md` and `docs/OBSERVABILITY.md` exist with complete content
- [ ] `docs/TESTS.md` performance benchmark layer references `docs/PH-09/performance_results.md`

**Technical Notes**: This is a verification story, not an implementation story. It confirms that the artifacts produced by E-901, E-902, and E-903 S001-S003 collectively satisfy the PH-09 phase exit criteria defined in `docs/PHASES.md`. No new artifacts are produced. If any exit criterion is not met, this story identifies the gap and traces it to the responsible epic and story for remediation. The `dbt build` pass can be verified via the most recent CI run on the feature branch rather than re-executing locally.

**Definition of Done**:

- [ ] All 3 PH-09 exit criteria confirmed met
- [ ] Verification results documented
- [ ] PR opened with linked issue
- [ ] CI checks green

## Exit Criteria

This epic is complete when:

- [ ] `.github/workflows/ci-dbt.yml` includes Elementary report generation (`dbt run --select elementary` + `edr report`) with HTML artifact upload
- [ ] `docs/RUNBOOK.md` exists with complete operational procedures: environment setup, data refresh, full rebuild, troubleshooting (5+ scenarios), schema change response
- [ ] `docs/OBSERVABILITY.md` exists with complete monitoring procedures: Elementary interpretation, anomaly response matrix, source freshness monitoring, dbt artifacts, Snowflake native monitoring
- [ ] All 3 PH-09 exit criteria validated end-to-end: zero missing descriptions, Elementary operational, benchmarks documented
- [ ] `dbt build` passes with zero ERROR results

# Test Regression & Strategy Documentation

| Field        | Value               |
| ------------ | ------------------- |
| Epic ID      | E-803               |
| Phase        | PH-08               |
| Owner        | @dinesh-git17       |
| Status       | Complete            |
| Dependencies | [E-801, E-802]      |
| Created      | 2026-02-09          |

## Context

PH-08 introduces three categories of quality assurance on top of the schema tests established in PH-05 through PH-07: singular business rule tests (E-801), distribution validation via dbt_expectations (E-802), and dynamic anomaly detection via Elementary (E-802). The PH-08 exit criterion requires two specific outcomes: (1) zero test failures across the full `dbt test` suite, and (2) a documented test strategy in `docs/TESTS.md`. This epic provides the regression validation pass confirming all tests pass end-to-end, the strategy document codifying the test pyramid, test inventory, severity classifications, execution procedures, and threshold justifications, and the CI integration verification confirming that the complete test suite participates in the deployment gate. Without this epic, the testing infrastructure from E-801 and E-802 lacks a verified baseline and a human-readable reference for operators and contributors.

## Scope

### In Scope

- Full `dbt test` regression execution achieving 100% pass rate (zero ERROR results; WARN results permitted on `severity: warn` tests)
- `docs/TESTS.md` — comprehensive test strategy document covering: test pyramid (5 layers per DESIGN-DOC Section 8.1), singular test inventory (5 tests with severity and threshold for each), dbt_expectations test inventory (5 tests with bounds and calibration dates), Elementary configuration inventory (17 tests across 7 models), execution procedures (local, pre-commit, CI/CD, scheduled per DESIGN-DOC Section 8.4), and severity classification rationale
- CI pipeline verification confirming `dbt test` execution includes all test categories (schema, singular, dbt_expectations, Elementary)
- Final test count audit: document the complete test inventory with counts per category and per model

### Out of Scope

- Writing new tests (complete in E-801 and E-802)
- Fixing test failures by modifying mart models or intermediate logic (bug fixes belong as patches within E-801 or E-802)
- Performance benchmarking or query optimization (PH-09)
- dbt docs generation or lineage graph validation (PH-09)
- Elementary dashboard hosting, alerting, or external integrations (PH-09)
- CI workflow YAML modifications — this epic verifies existing CI gates include new tests, not creating new workflows

## Technical Approach

### Architecture Decisions

- **`docs/TESTS.md` follows the same authoritative voice as `DESIGN-DOC.md` and `CLAUDE.md`** — cold, precise, technical documentation per CLAUDE.md Section 1.2; no narrative filler, no AI-attribution breadcrumbs; document reads as production infrastructure documentation authored by a Senior Data Engineer
- **Test inventory organized by layer (pyramid) then by model** — aligns with DESIGN-DOC Section 8.1 test pyramid (schema → unit → integration → data quality → performance); each section within `TESTS.md` maps to one pyramid layer with a table listing every test, its target model, severity, and threshold
- **Regression pass is a single `dbt test` invocation** — not segmented by test type; the full suite must pass as a unit because CI runs `dbt test` (not `dbt test --select ...`); segmented execution (e.g., `test_type:singular` only) was used for validation in E-801 but production CI runs the complete suite
- **Test count audit includes both existing and new tests** — the regression validates the cumulative test inventory across PH-05 through PH-08, not just PH-08 additions; this ensures no regressions were introduced by YAML modifications in E-802

### Integration Points

- **All mart models** — 4 dimensions (E-701) + 3 facts (E-702) — targets of all test categories
- **All intermediate models** — `int_ttc_delays_enriched` (target of `assert_station_mapping_coverage` singular test) — validated via `dbt test`
- **CI pipeline** — `dbt test` is a required status check per CLAUDE.md Section 9.2; the regression validates that the expanded test suite (schema + singular + dbt_expectations + Elementary) executes within CI timeout limits
- **DESIGN-DOC Section 8.1-8.4** — `TESTS.md` codifies and cross-references the testing requirements defined in the design document, creating a standalone operational reference

### Repository Areas

- `docs/TESTS.md` (new)

### Risks

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Full `dbt test` regression reveals pre-existing test failures masked by prior targeted test runs (e.g., `--select marts` instead of full suite) | Low | Medium | Run `dbt test` without selectors as the first action; if failures exist, triage whether they are new (E-801/E-802 introduced) or pre-existing (PH-07 regression); fix E-801/E-802 tests in-scope, defer pre-existing issues to bug tickets |
| `dbt test` exceeds CI timeout with Elementary tests added (17 Elementary tests + 21.8M row fact table scans) | Medium | Medium | Measure total `dbt test` execution time locally on X-Small warehouse; if >5 minutes, investigate Elementary test optimization (e.g., sampling, reduced training period); Elementary tests on dimension tables (<3K rows each) should execute in <1 second each |
| `docs/TESTS.md` becomes stale as future phases add models or modify thresholds | Medium | Low | Include a "Last Updated" date and a maintenance note at the top of `TESTS.md`; future epics that add tests must update `TESTS.md` as part of their Definition of Done |

## Stories

| ID   | Story                                                       | Points | Dependencies | Status |
| ---- | ----------------------------------------------------------- | ------ | ------------ | ------ |
| S001 | Execute full dbt test regression and confirm 100% pass rate | 5      | None         | Complete |
| S002 | Write test strategy documentation in docs/TESTS.md          | 8      | S001         | Complete |
| S003 | Validate CI pipeline includes all test categories           | 3      | S001         | Complete |

---

### S001: Execute Full dbt Test Regression and Confirm 100% Pass Rate

**Description**: Run the complete `dbt test` suite (schema, singular, dbt_expectations, Elementary) against the Snowflake target and confirm zero ERROR results across all test categories.

**Acceptance Criteria**:

- [ ] `dbt test` (no selectors) executes without runtime errors
- [ ] Zero tests report ERROR status
- [ ] All `severity: warn` tests (`assert_bike_trips_reasonable_duration`, `assert_daily_row_count_stability`, 3 `expect_table_row_count_to_be_between` tests) report PASS or WARN — neither constitutes a failure
- [ ] Total test count matches the expected inventory: schema tests (existing from PH-05/PH-07) + 5 singular tests (E-801) + 5 dbt_expectations tests (E-802) + 17 Elementary tests (E-802) — document exact count from `dbt test` output
- [ ] Total execution time recorded and documented (expected: <120 seconds on X-Small warehouse)
- [ ] Test output captured to a file for audit: `dbt test 2>&1 | tee docs/PH-08/regression_output.txt`

**Technical Notes**: Run `dbt test` without `--select` to exercise the complete test suite. The output summary reports counts by status (PASS, WARN, ERROR, FAIL). Any ERROR or FAIL result blocks PH-08 completion and must be triaged. If an Elementary test fails due to missing baseline (first run), confirm `dbt run --select elementary` was executed in E-802 S005. The regression output file (`docs/PH-08/regression_output.txt`) serves as the audit trail for PH-08 exit criteria verification — this file is ephemeral and does not need to be committed.

**Definition of Done**:

- [ ] `dbt test` passes with zero ERROR results
- [ ] Total test count and execution time documented
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S002: Write Test Strategy Documentation in docs/TESTS.md

**Description**: Create `docs/TESTS.md` as the comprehensive test strategy document covering the full test pyramid, test inventory, severity classifications, execution procedures, and threshold justifications for the Toronto Urban Mobility Analytics project.

**Acceptance Criteria**:

- [ ] File `docs/TESTS.md` exists
- [ ] Document contains a **Test Pyramid** section describing all 5 layers per DESIGN-DOC Section 8.1: Schema Tests, Unit Tests (PK/FK/accepted_values), Integration Tests (relationships, cross-model consistency), Data Quality Tests (dbt_expectations distributions, Elementary anomaly detection), Performance Benchmarks (deferred to PH-09)
- [ ] Document contains a **Singular Test Inventory** table listing all 5 singular tests with columns: Test Name, Target Model, Assertion, Severity, Threshold, Epic Reference
- [ ] Document contains a **dbt_expectations Test Inventory** table listing all 5 dbt_expectations tests with columns: Test Macro, Target Model/Column, Min Value, Max Value, Severity, Epic Reference
- [ ] Document contains an **Elementary Configuration** section listing all 17 Elementary tests in a table with columns: Model, Test Type, Timestamp Column, Epic Reference
- [ ] Document contains an **Execution Procedures** section with 4 subsections per DESIGN-DOC Section 8.4: Local Development (`dbt test --select <model>`), Pre-commit (`dbt build --select state:modified+`), CI/CD (`dbt test` full suite), Scheduled (`dbt source freshness && dbt test`)
- [ ] Document contains a **Severity Classification** section explaining the mapping: Blocker → `error` (default), Warning → `warn` (config override), with rationale for each test's classification
- [ ] Document contains a **Test Count Summary** table with total tests per category and per model
- [ ] Document voice is cold, precise, technical — per CLAUDE.md Section 1.2
- [ ] No AI-attribution breadcrumbs, narrative filler, or placeholder text

**Technical Notes**: `TESTS.md` serves two audiences: (1) contributors who need to understand where to add new tests and what severity to assign, and (2) operators who need to diagnose test failures and understand threshold rationale. The document cross-references DESIGN-DOC sections for each requirement's origin. The test count summary table must match the actual `dbt test` output from S001 — any discrepancy indicates a misconfiguration. This document is committed to the repository and becomes part of the project's operational documentation.

**Definition of Done**:

- [ ] `docs/TESTS.md` committed to feature branch
- [ ] Document contains all 7 required sections with complete content
- [ ] Test inventory counts match actual `dbt test` output from S001
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S003: Validate CI Pipeline Includes All Test Categories

**Description**: Verify that the existing CI pipeline (`dbt test` as a required status check) executes all test categories — schema, singular, dbt_expectations, and Elementary — and that no test category is excluded by selector filters or configuration.

**Acceptance Criteria**:

- [ ] CI workflow file (`.github/workflows/`) contains a `dbt test` step without restrictive `--select` or `--exclude` flags that would skip test categories
- [ ] CI execution log from a feature branch push demonstrates that singular tests, dbt_expectations tests, and Elementary tests all appear in the test output
- [ ] CI execution completes within the configured timeout (no timeout failures due to expanded test suite)
- [ ] All required status checks pass on the feature branch PR per CLAUDE.md Section 9.2

**Technical Notes**: The CI pipeline was configured in PH-01 with `dbt test` as a required status check. This story verifies that the expanded test suite (from 34 tests pre-PH-08 to ~60+ tests post-PH-08) executes within CI constraints. If CI timeout is insufficient, the resolution is to request a timeout increase — not to exclude tests. Elementary tests on first CI run may not perform anomaly detection (no baseline in CI environment) but must execute without errors.

**Definition of Done**:

- [ ] CI log reviewed and all test categories confirmed present
- [ ] No test categories excluded by CI configuration
- [ ] PR opened with linked issue
- [ ] CI checks green

## Exit Criteria

This epic is complete when:

- [ ] `dbt test` passes with zero ERROR results across all test categories (schema, singular, dbt_expectations, Elementary)
- [ ] `docs/TESTS.md` exists with complete test pyramid, inventory tables, execution procedures, and severity classification
- [ ] Test count in `docs/TESTS.md` matches actual `dbt test` output
- [ ] CI pipeline executes expanded test suite without timeouts or exclusions
- [ ] PH-08 phase exit criterion satisfied: zero test failures, Elementary baseline established, test strategy documented

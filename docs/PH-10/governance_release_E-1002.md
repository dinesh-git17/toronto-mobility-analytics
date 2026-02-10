# Governance Verification & v1.0.0 Release

| Field        | Value           |
| ------------ | --------------- |
| Epic ID      | E-1002          |
| Phase        | PH-10           |
| Owner        | @dinesh-git17   |
| Status       | Draft           |
| Dependencies | [E-1001, E-903] |
| Created      | 2026-02-10      |

---

## Context

With all technical implementation (PH-01 through PH-09) and README documentation (E-1001) complete, the repository requires a final governance audit, release packaging, and version tagging before it can be declared production-ready for portfolio demonstration. CLAUDE.md Section 11 defines a 17-item Definition of Done checklist that must hold across every committed artifact — models, scripts, tests, seeds, documentation, and CI configuration. No prior phase performed a cross-cutting compliance audit because each phase validated only its own deliverables in isolation.

This epic executes the final verification sweep: confirming all CI status checks pass on `main`, validating that sample queries in `/analyses` pass SQL linting, authoring a `CHANGELOG.md` that documents every phase's deliverables, and tagging the `v1.0.0` release on GitHub. The release tag is the terminal artifact of the project — it creates a permanent, citable reference point that external reviewers can clone, build, and evaluate.

PH-10 is the correct phase for this work because governance verification requires all code to be frozen and merged. Running this audit mid-development would produce false negatives against incomplete layers. The v1.0.0 tag must be the final commit operation after all other PH-10 work (including E-1001 README) is merged.

---

## Scope

### In Scope

- Cross-cutting CLAUDE.md Section 11 Definition of Done audit across all repository layers (models, scripts, tests, seeds, docs, CI)
- Verification that all 5 required CI status checks pass on `main` branch: `detect-changes`, `detect-python`, `detect-dbt`, `protocol-zero`, `dependency-audit`
- SQL linting validation of all 5 files in `/analyses` using sqlfmt and SQLFluff (Snowflake dialect)
- `CHANGELOG.md` creation at repository root documenting all phases (PH-01 through PH-10) with deliverables, model counts, and test counts
- GitHub release creation: tag `v1.0.0` on `main` with release notes summarizing the complete system

### Out of Scope

- Code modifications to fix audit findings (if audit reveals issues, new fix stories are created — this epic only identifies and documents)
- CI workflow modifications or new workflow creation
- Snowflake runtime verification (requires active credentials; CI proxy is sufficient)
- Performance re-benchmarking (completed in E-902; results are final)
- dbt package version upgrades or dependency changes (D13: versions are pinned)
- Post-release maintenance planning or v2.0 roadmap authoring

---

## Technical Approach

### Architecture Decisions

- **Audit-only scope for governance verification:** This epic identifies compliance gaps but does not fix them. If S001 discovers violations (e.g., missing type hints, undocumented columns), those are logged as findings and tracked as separate fix stories. This separation prevents scope creep and maintains clean audit boundaries.
- **CHANGELOG follows Keep a Changelog format:** Sections per phase (not per commit) with categories: Added, Changed, Fixed. This provides a readable summary for external reviewers without duplicating git log verbosity.
- **GitHub Release via `gh release create`:** Uses GitHub CLI for deterministic release creation. Release notes reference the CHANGELOG.md rather than duplicating content. The release tag targets the `main` branch HEAD after all PH-10 PRs are merged.
- **Analyses linting as prerequisite to release:** The 5 SQL files in `/analyses` were authored during E-902 but were not subject to the same sqlfmt/SQLFluff gate as model SQL. Linting compliance must be verified (and corrected if needed) before v1.0.0.

### Integration Points

- GitHub Actions CI pipeline (5 workflows) — S002 validates all checks pass
- GitHub Releases API via `gh` CLI — S005 creates the tagged release
- sqlfmt and SQLFluff CLI tools — S003 validates analyses SQL
- CLAUDE.md Section 11 checklist — S001 audit framework
- All prior epic deliverables — audit scope covers PH-01 through PH-10

### Repository Areas

- `CHANGELOG.md` (new file, repository root)
- `analyses/*.sql` (validation only; modifications only if linting fails)
- `.github/` (validation only; no modifications)
- All `models/`, `scripts/`, `seeds/`, `tests/`, `docs/` directories (read-only audit)

### Risks

| Risk                                                                                                                                     | Likelihood | Impact | Mitigation                                                                                                                                                                                                                    |
| ---------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Governance audit discovers violations that require code changes, expanding PH-10 scope beyond documentation and release                  | Medium     | High   | Audit findings are logged as separate stories outside this epic. PH-10 release is blocked until all critical findings are resolved. Non-critical findings are documented in CHANGELOG as known limitations.                   |
| CI status checks cannot be verified because Snowflake credentials are not configured in GitHub Actions secrets for the public repository | Medium     | High   | Document which checks require Snowflake connectivity vs. which run offline (lint, governance, security). Verify offline checks pass. Note credential-dependent checks as "requires Snowflake configuration" in release notes. |
| `gh release create` fails due to insufficient GitHub token permissions or branch protection rules blocking tag creation                  | Low        | Medium | Verify `gh auth status` before release. Repository owner (@dinesh-git17) has admin bypass per CLAUDE.md Section 9.2. Create tag locally with `git tag` as fallback.                                                           |
| CHANGELOG.md content becomes stale if additional PRs are merged between authoring and release tagging                                    | Low        | Low    | Author CHANGELOG as the penultimate story (S004). Tag release (S005) immediately after CHANGELOG merge. No intervening PRs permitted between S004 merge and S005 execution.                                                   |

---

## Stories

| ID   | Story                                                        | Points | Dependencies      | Status |
| ---- | ------------------------------------------------------------ | ------ | ----------------- | ------ |
| S001 | Execute CLAUDE.md Definition of Done audit across all layers | 5      | None              | Draft  |
| S002 | Verify CI status checks pass on main branch                  | 3      | None              | Draft  |
| S003 | Validate analyses folder SQL linting compliance              | 2      | None              | Draft  |
| S004 | Author CHANGELOG.md with complete phase history              | 5      | S001, S002, S003  | Draft  |
| S005 | Create v1.0.0 GitHub release with tag                        | 2      | S004, E-1001.S006 | Draft  |

---

### S001: Execute CLAUDE.md Definition of Done Audit Across All Layers

**Description**: Perform a systematic audit of the entire repository against the 17-item Definition of Done checklist in CLAUDE.md Section 11, producing a structured findings report that identifies compliant items, non-compliant items, and items requiring Snowflake runtime verification.

**Acceptance Criteria**:

- [ ] Audit covers all 17 checklist items from CLAUDE.md Section 11 explicitly
- [ ] **Medallion architecture compliance:** Verify staging models are views, intermediate models are ephemeral, marts models are tables — confirmed via `dbt_project.yml` materialization config and individual model configs
- [ ] **SQL formatting:** Run `sqlfmt --check models/` and confirm exit code 0, or document specific files that fail
- [ ] **SQL linting:** Run `sqlfluff lint models/ --dialect snowflake` and confirm zero errors, or document specific violations
- [ ] **Python type hints:** Run `mypy --strict scripts/` and confirm zero errors, or document specific violations
- [ ] **Python linting:** Run `ruff check scripts/` and `ruff format --check scripts/` and confirm zero errors
- [ ] **dbt model documentation:** Verify every model in `models/` has a corresponding entry in a `_*__models.yml` file with column-level descriptions — confirmed via `dbt docs generate` producing zero "missing description" warnings
- [ ] **dbt tests:** Verify all mart models have `unique` and `not_null` tests on primary keys, and all fact tables have `relationships` tests on foreign keys
- [ ] **Protocol Zero compliance:** Run `grep -rn` across all `.sql`, `.py`, `.md`, and `.yml` files for CLAUDE.md Section 1.1 forbidden phrases — zero matches required
- [ ] **Commit message compliance:** Verify last 20 commits on `main` follow `type(scope): description` format per CLAUDE.md Section 9.5
- [ ] Audit results documented in a structured checklist format (pass/fail/requires-runtime per item)
- [ ] Non-compliant items (if any) logged with file paths, line numbers, and remediation instructions

**Technical Notes**: Run all validation commands from repository root. Python checks require the dev dependency group installed (`pip install -e ".[dev]"`). dbt checks require `dbt deps` to have been run. Protocol Zero grep patterns are defined in CLAUDE.md Section 1.1 and `tools/protocol-zero.sh`.

**Definition of Done**:

- [ ] All 17 checklist items evaluated
- [ ] Findings documented
- [ ] Zero critical violations (blocking release) or all critical violations resolved in separate PRs
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S002: Verify CI Status Checks Pass on Main Branch

**Description**: Confirm that all 5 required CI status checks defined in CLAUDE.md Section 9.2 pass on the `main` branch, documenting which checks execute fully and which require Snowflake credentials for runtime verification.

**Acceptance Criteria**:

- [ ] Identify the most recent CI run on `main` branch via `gh run list --branch main --limit 5`
- [ ] Verify `detect-changes` check status is passing or document its current state
- [ ] Verify `detect-python` check status is passing or document its current state
- [ ] Verify `detect-dbt` check status is passing or document its current state (note: dbt build requires Snowflake credentials)
- [ ] Verify `protocol-zero` check status is passing or document its current state
- [ ] Verify `dependency-audit` check status is passing or document its current state
- [ ] For checks that require Snowflake credentials: document that offline validation (linting, type checking, Protocol Zero) passes locally and that runtime checks are blocked by credential configuration
- [ ] Results summarized in a table: check name, status (pass/fail/skipped), notes

**Technical Notes**: Use `gh run list` and `gh run view` to inspect CI results. Checks that depend on Snowflake connectivity (`detect-dbt` specifically for `dbt build` step) will show as failed if secrets are not configured — this is expected for a public repository and must be documented rather than treated as a blocker. Offline checks (linting, governance, security scanning) should pass regardless of Snowflake connectivity.

**Definition of Done**:

- [ ] All 5 required checks evaluated
- [ ] CI status documented
- [ ] PR opened with linked issue

---

### S003: Validate Analyses Folder SQL Linting Compliance

**Description**: Run sqlfmt and SQLFluff against all 5 SQL files in `/analyses` to confirm they meet the same formatting and linting standards applied to dbt models, correcting any violations found.

**Acceptance Criteria**:

- [ ] `sqlfmt --check analyses/` returns exit code 0 (all files formatted correctly), or files are reformatted with `sqlfmt analyses/` and the diff is committed
- [ ] `sqlfluff lint analyses/ --dialect snowflake` returns zero errors, or violations are fixed and committed
- [ ] All 5 files verified: `top_delay_stations.sql`, `bike_weather_correlation.sql`, `cross_modal_analysis.sql`, `monthly_trends.sql`, `daily_mobility_summary.sql`
- [ ] Files contain valid Snowflake SQL syntax (no dbt Jinja references that prevent standalone linting — if Jinja `{{ ref() }}` is present, document that SQLFluff requires `--templater jinja` or `dbt` templater)
- [ ] No trailing whitespace, consistent indentation, uppercase SQL keywords per project SQLFluff configuration in `.sqlfluff`

**Technical Notes**: The analyses files were created during E-902 using dbt `{{ ref() }}` syntax. SQLFluff with the dbt templater (`sqlfluff lint --templater dbt`) resolves Jinja references. Alternatively, sqlfmt handles Jinja natively. Verify the `.sqlfluff` configuration file includes the correct templater setting for the `analyses/` directory.

**Definition of Done**:

- [ ] All 5 analyses files pass sqlfmt and SQLFluff
- [ ] Code committed to feature branch (if modifications required)
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S004: Author CHANGELOG.md with Complete Phase History

**Description**: Create `CHANGELOG.md` at repository root following Keep a Changelog format, documenting deliverables from all 10 phases with quantified outputs (model counts, test counts, row counts) — serving as the definitive project history for external reviewers.

**Acceptance Criteria**:

- [ ] `CHANGELOG.md` exists at repository root
- [ ] Header includes project name and link to Keep a Changelog specification
- [ ] Contains a `## [1.0.0] - YYYY-MM-DD` section (date filled at release time) with subsections for each phase
- [ ] **PH-01 entry:** Repository governance, CLAUDE.md, skills framework, Protocol Zero, pre-commit hooks, branch protection
- [ ] **PH-02 entry:** Snowflake infrastructure (database, schemas, roles, warehouse), dbt project scaffold, custom macros
- [ ] **PH-03 entry:** Python ingestion pipeline (download, validate, transform, load), 5 RAW tables populated, 22.25M rows validated, schema contract enforcement
- [ ] **PH-04 entry:** 4 seed files (ttc_station_mapping: 1,101 rows, ttc_delay_codes: 334 rows, bike_station_ref: 1,009 rows, date_spine: 2,922 rows), seed schema tests
- [ ] **PH-05 entry:** 5 staging views, 5 source definitions, source freshness checks, 33 schema tests
- [ ] **PH-06 entry:** 5 intermediate ephemeral models, station mapping coverage test (99%+ threshold), 19 tests passing
- [ ] **PH-07 entry:** 4 dimension tables, 3 fact tables, 41 tests passing, 21.8M+ fact rows
- [ ] **PH-08 entry:** Singular business rule tests, dbt_expectations distribution tests, Elementary anomaly detection baseline
- [ ] **PH-09 entry:** Column-level documentation completeness, performance benchmarks (5 queries < 1s), Elementary CI integration, operational runbooks
- [ ] **PH-10 entry:** README.md with architecture diagrams, CHANGELOG.md, governance audit, v1.0.0 release
- [ ] All quantified values match documented values from completed epics (cross-referenced against MEMORY.md and epic files)
- [ ] No AI-attribution phrases per CLAUDE.md Section 1.1
- [ ] File passes markdownlint validation

**Technical Notes**: Cross-reference quantified values against: E-302 (22.25M rows, 83 files), E-401 (1,101 stations, 334 delay codes), E-402 (1,009 bike stations, 2,922 dates), E-501/E-502 (5 staging views, 33 tests), E-601/E-602 (5 intermediate models, 19 tests), E-701/E-702 (7 mart tables, 41 tests), E-902 (5 queries < 1s). Keep a Changelog format: <https://keepachangelog.com/en/1.1.0/>

**Definition of Done**:

- [ ] CHANGELOG.md committed to feature branch
- [ ] All phase entries verified against epic documentation
- [ ] Passes markdownlint
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S005: Create v1.0.0 GitHub Release with Tag

**Description**: Tag the `main` branch as `v1.0.0` and create a GitHub Release with structured release notes referencing the CHANGELOG.md, marking the repository as production-ready for portfolio demonstration.

**Acceptance Criteria**:

- [ ] Git tag `v1.0.0` exists on `main` branch HEAD (after all PH-10 PRs including E-1001 are merged)
- [ ] GitHub Release created via `gh release create v1.0.0` with title "v1.0.0 — Toronto Urban Mobility Analytics"
- [ ] Release notes body includes: one-paragraph project summary, link to README.md, link to CHANGELOG.md, key metrics (5 data sources, 7 mart models, 75+ tests, 22.25M rows), and link to DESIGN-DOC.md
- [ ] Release notes do not duplicate CHANGELOG.md content — they reference it
- [ ] Release is marked as "Latest" (not pre-release, not draft)
- [ ] Tag is annotated (not lightweight): `git tag -a v1.0.0 -m "v1.0.0: Production-ready portfolio release"`
- [ ] No commits exist on `main` between the final PH-10 merge and the release tag

**Technical Notes**: Execute `gh release create v1.0.0 --title "v1.0.0 — Toronto Urban Mobility Analytics" --notes-file release_notes.md` where `release_notes.md` is a temporary file with structured content. Alternatively, use `--notes` with a heredoc. Verify with `gh release view v1.0.0`. The release tag must be the absolute final operation in PH-10 — no subsequent commits or PRs.

**Definition of Done**:

- [ ] Tag `v1.0.0` visible on GitHub repository tags page
- [ ] Release visible on GitHub repository releases page with status "Latest"
- [ ] Release notes contain required content
- [ ] Repository is in a clean state: `main` branch, all CI checks green, no open PH-10 PRs

---

## Exit Criteria

This epic is complete when:

- [ ] CLAUDE.md Section 11 Definition of Done audit completed with zero critical violations
- [ ] All 5 CI status checks evaluated and offline checks confirmed passing
- [ ] All 5 analyses SQL files pass sqlfmt and SQLFluff linting
- [ ] `CHANGELOG.md` exists at repository root with entries for all 10 phases
- [ ] Git tag `v1.0.0` exists on `main` branch
- [ ] GitHub Release `v1.0.0` is published with status "Latest"
- [ ] Repository is production-ready for portfolio demonstration: README complete, CI green, governance verified, release tagged

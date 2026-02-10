# Portfolio README & Architecture Documentation

| Field        | Value                 |
| ------------ | --------------------- |
| Epic ID      | E-1001                |
| Phase        | PH-10                 |
| Owner        | @dinesh-git17         |
| Status       | Draft                 |
| Dependencies | [E-901, E-902, E-903] |
| Created      | 2026-02-10            |

---

## Context

The Toronto Urban Mobility Analytics repository has completed all technical implementation across PH-01 through PH-09: ingestion pipelines, schema validation, medallion-architecture dbt models (staging, intermediate, marts), comprehensive test suites, observability infrastructure, and operational runbooks. However, the repository lacks a `README.md` — the single most critical artifact for external portfolio evaluation. Without a structured README containing architecture diagrams, reproduction instructions, and sample query documentation, the repository fails DESIGN-DOC.md Goal G4 ("Create Portfolio-Worthy Deliverable") and cannot serve its intended audience of technical reviewers, hiring managers, and peer engineers.

This epic produces the complete `README.md` with three Mermaid architecture diagrams (system overview, data flow, entity-relationship), step-by-step setup instructions covering Snowflake provisioning through initial data load, and documented sample queries referencing the five analytical SQL files in `/analyses`. The README must present the full scope of the system — 5 data sources, 22.25M validated rows, 7 mart models, 75+ dbt tests, and CI/CD automation — in a format that communicates production-grade engineering discipline within a 5-minute read.

PH-10 is the correct phase for this work because all referenced artifacts (models, tests, benchmarks, runbooks) must exist before the README can accurately describe them. Writing documentation against incomplete infrastructure produces stale references and incorrect claims.

---

## Scope

### In Scope

- `README.md` at repository root with all sections defined in this epic
- System overview architecture diagram (Mermaid) showing data sources → ingestion → Snowflake → dbt layers → marts
- Data flow diagram (Mermaid) showing medallion architecture transformations across staging, intermediate, and marts
- Entity-relationship diagram (Mermaid) showing fact and dimension tables with foreign key relationships
- Setup and reproduction instructions: prerequisites, Snowflake provisioning, dbt configuration, Python environment, initial data load
- Technology stack table with versions and rationale
- Data sources table with row counts and refresh cadence
- Project structure tree (validated against actual repository layout)
- Sample queries section referencing `/analyses` files with output shape descriptions
- Testing strategy summary with link to `docs/TESTS.md`
- CI/CD pipeline summary with link to workflow files
- Observability section with links to `docs/RUNBOOK.md` and `docs/OBSERVABILITY.md`
- License section

### Out of Scope

- Deployment of dbt docs site to GitHub Pages (future enhancement)
- Streamlit or dashboard frontend (NG3 per DESIGN-DOC.md)
- Video walkthrough or demo recording
- Badges requiring external service integration (Codecov, Snyk) beyond GitHub Actions status
- Modification of any existing model, test, or pipeline code
- Creation of new analytical queries beyond the five in `/analyses`

---

## Technical Approach

### Architecture Decisions

- **Mermaid for diagrams:** Renders natively in GitHub markdown without external image hosting. No PNG/SVG maintenance burden. Editable as code. Three diagrams: `flowchart TD` for system overview, `flowchart LR` for data flow, `erDiagram` for ER relationships.
- **Single README.md:** All portfolio documentation consolidated in one file at repository root. Avoids fragmentation across multiple docs that external reviewers must discover. Internal technical docs (RUNBOOK.md, OBSERVABILITY.md, TESTS.md) linked but not duplicated.
- **Reproducible setup instructions:** Step-by-step commands that a reviewer can execute verbatim. No implicit knowledge. Prerequisites enumerated with exact version constraints matching `pyproject.toml` and `packages.yml`.
- **Sample query output shapes:** Describe column names and row counts rather than hardcoded result values, which change with data refreshes. Reference the five `/analyses` SQL files by name with execution instructions.

### Integration Points

- References all 5 CI workflows in `.github/workflows/` (ci-dbt, ci-lint, ci-python, governance, security)
- References dbt project structure in `models/`, `seeds/`, `tests/`, `macros/`
- References Python ingestion scripts in `scripts/`
- References operational docs in `docs/` (TESTS.md, RUNBOOK.md, OBSERVABILITY.md, DESIGN-DOC.md)
- References sample queries in `analyses/`
- References Snowflake object hierarchy from DESIGN-DOC.md Section 5.3
- References ER diagram from DESIGN-DOC.md Section 6.1

### Repository Areas

- `README.md` (new file, repository root)

### Risks

| Risk                                                                                                                             | Likelihood | Impact | Mitigation                                                                                                                                                         |
| -------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Mermaid diagrams render incorrectly on GitHub due to syntax edge cases or diagram complexity exceeding GitHub's rendering limits | Medium     | Medium | Validate all three diagrams via GitHub preview before merge; keep node count under 50 per diagram; test in a draft PR                                              |
| Setup instructions reference credentials or environment-specific paths that break reproducibility for external users             | Medium     | High   | Use placeholder variables (`$SNOWFLAKE_ACCOUNT`) and `profiles.yml.example` template; test instructions against a clean environment checklist                      |
| Project structure tree drifts from actual repository layout if files were added/removed since last audit                         | Low        | Medium | Generate tree from `find` command output during implementation; validate against `ls -R` before commit                                                             |
| README length exceeds comfortable reading threshold (>1000 lines), reducing portfolio effectiveness                              | Low        | Medium | Target 400-600 lines; use collapsible `<details>` sections for verbose content (full project tree, extended setup); prioritize scanability with tables and headers |

---

## Stories

| ID   | Story                                                            | Points | Dependencies                 | Status |
| ---- | ---------------------------------------------------------------- | ------ | ---------------------------- | ------ |
| S001 | Write project overview, badges, and technology stack sections    | 3      | None                         | Draft  |
| S002 | Create three Mermaid architecture diagrams                       | 5      | None                         | Draft  |
| S003 | Write setup and reproduction instructions                        | 5      | None                         | Draft  |
| S004 | Write sample queries, testing, CI/CD, and observability sections | 3      | S002                         | Draft  |
| S005 | Write project structure tree and remaining sections              | 2      | S001                         | Draft  |
| S006 | Validate README rendering and cross-reference integrity          | 2      | S001, S002, S003, S004, S005 | Draft  |

---

### S001: Write Project Overview, Badges, and Technology Stack Sections

**Description**: Author the README header including project title, GitHub Actions CI status badge, one-paragraph executive summary, key metrics callout (data sources, row counts, models, tests), and technology stack table with pinned versions.

**Acceptance Criteria**:

- [ ] `README.md` exists at repository root
- [ ] First line is `# Toronto Urban Mobility Analytics`
- [ ] CI status badge references the `ci-dbt.yml` workflow on `main` branch using GitHub Actions badge URL format
- [ ] Executive summary is 3-5 sentences, describes the project as a production-grade data engineering portfolio demonstrating medallion architecture with dbt and Snowflake
- [ ] Key metrics section includes exact counts: 5 data sources, 22.25M+ validated rows, 5 staging views, 5 intermediate models, 7 mart tables, 75+ dbt tests
- [ ] Technology stack table includes at minimum: Snowflake, dbt Core (1.8+), Python (3.12), SQLFluff (3.3+), sqlfmt, Elementary (0.16+), GitHub Actions — each with version and one-line rationale
- [ ] Data sources table includes TTC Subway, TTC Bus, TTC Streetcar, Bike Share Toronto, and Environment Canada Weather with format, approximate row counts, and refresh cadence
- [ ] No AI-attribution phrases per CLAUDE.md Section 1

**Technical Notes**: Badge URL format: `![CI](https://github.com/dinesh-git17/toronto-mobility-analytics/actions/workflows/ci-dbt.yml/badge.svg?branch=main)`. Row counts sourced from E-302 validation results (22.25M total) and E-702 mart build outputs.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] README renders correctly in GitHub markdown preview
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S002: Create Three Mermaid Architecture Diagrams

**Description**: Author three Mermaid diagrams embedded in README.md: (1) system overview showing data sources through ingestion to Snowflake to dbt to marts, (2) data flow diagram showing medallion architecture layer transformations with model names, (3) entity-relationship diagram showing all 7 mart models with PK/FK relationships.

**Acceptance Criteria**:

- [ ] System overview diagram uses `flowchart TD` (top-down) and shows: 4 data source nodes (TTC Subway/Bus/Streetcar, Bike Share, Weather) → Python ingestion layer (download, validate, transform, load) → Snowflake RAW schema → dbt transformation (Staging → Intermediate → Marts) → 7 mart model output nodes
- [ ] Data flow diagram uses `flowchart LR` (left-right) and shows: 5 RAW tables → 5 staging views (with names) → 5 intermediate models (with names) → 4 dimension tables + 3 fact tables (with names)
- [ ] ER diagram uses `erDiagram` syntax and shows: `fct_transit_delays`, `fct_bike_trips`, `fct_daily_mobility` with FK relationships to `dim_date`, `dim_station`, `dim_weather`, `dim_ttc_delay_codes` — relationships match DESIGN-DOC.md Section 6.1
- [ ] All three diagrams render without errors in GitHub markdown preview
- [ ] Each diagram has a descriptive heading (e.g., "### System Architecture", "### Data Flow", "### Entity-Relationship Model")
- [ ] Diagram node count stays under 50 per diagram for GitHub rendering reliability

**Technical Notes**: Reference DESIGN-DOC.md Section 5.1 (system architecture ASCII art) and Section 6.1 (ER diagram) for accurate topology. Translate ASCII art to Mermaid syntax. Use subgraph blocks to group related nodes (e.g., `subgraph Snowflake`). ER diagram FK cardinality: `fct_transit_delays }|--|| dim_date`, `fct_bike_trips }|--|| dim_station`.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] All three diagrams render correctly in GitHub markdown preview
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S003: Write Setup and Reproduction Instructions

**Description**: Author step-by-step setup instructions covering prerequisites, Snowflake account provisioning, dbt project configuration, Python environment setup, dependency installation, and initial data load execution — sufficient for a reviewer to reproduce the entire pipeline from a fresh clone.

**Acceptance Criteria**:

- [ ] Prerequisites section lists: Python 3.12+, Snowflake account (Enterprise trial or existing), Git, and pip/uv
- [ ] Snowflake provisioning subsection references `setup/create_ingestion_stage.sql` for schema and table DDL, and describes RBAC setup (LOADER_ROLE, TRANSFORMER_ROLE) per DESIGN-DOC.md Section 10
- [ ] dbt configuration subsection instructs the user to copy `profiles.yml.example` to `~/.dbt/profiles.yml`, fill Snowflake credentials, and run `dbt debug` to verify connectivity
- [ ] Python environment subsection instructs: `pip install -e ".[dev]"` or equivalent from `pyproject.toml`, verifies with `ruff --version`, `mypy --version`, `pytest --version`
- [ ] Dependency installation includes `dbt deps` to install dbt packages from `packages.yml`
- [ ] Initial data load subsection describes running `python scripts/ingest.py` with expected output (download → transform → validate → load lifecycle)
- [ ] dbt build subsection instructs: `dbt seed`, `dbt build`, expected output (7 mart tables created, 75+ tests pass)
- [ ] All commands use placeholder variables for credentials (e.g., `$SNOWFLAKE_ACCOUNT`, `$SNOWFLAKE_USER`) — no hardcoded values
- [ ] Instructions tested against the actual repository file structure (all referenced files exist)

**Technical Notes**: Reference `profiles.yml.example` (already exists), `pyproject.toml` for Python deps, `packages.yml` for dbt deps, `setup/create_ingestion_stage.sql` for DDL, `scripts/ingest.py` for data load. The seed step must precede `dbt build` because intermediate models reference seed data.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] All referenced file paths verified to exist in repository
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S004: Write Sample Queries, Testing, CI/CD, and Observability Sections

**Description**: Author README sections for sample analytical queries (referencing `/analyses` files), testing strategy summary, CI/CD pipeline overview, and observability infrastructure — each with links to detailed documentation.

**Acceptance Criteria**:

- [ ] Sample queries section lists all 5 files in `/analyses`: `top_delay_stations.sql`, `bike_weather_correlation.sql`, `cross_modal_analysis.sql`, `monthly_trends.sql`, `daily_mobility_summary.sql`
- [ ] Each query entry includes: file name, one-sentence description of the analytical question it answers, expected output shape (column names and approximate row count)
- [ ] Execution instruction provided: `dbt compile` then execute compiled SQL in Snowflake, or direct execution replacing `{{ ref() }}` with fully qualified table names
- [ ] Testing section summarizes the test pyramid: schema tests, unit tests (unique/not_null), integration tests (relationships), business rule tests (singular), distribution tests (dbt_expectations), anomaly detection (Elementary) — with total test count
- [ ] Testing section links to `docs/TESTS.md` for full test strategy documentation
- [ ] CI/CD section lists all 5 GitHub Actions workflows by name and purpose: ci-dbt (model builds), ci-lint (SQL/YAML linting), ci-python (Python checks), governance (Protocol Zero), security (dependency audit)
- [ ] Observability section describes Elementary integration and links to `docs/RUNBOOK.md` and `docs/OBSERVABILITY.md`
- [ ] Performance benchmark results referenced: all 5 queries execute under 1 second on X-Small warehouse (per E-902 results)

**Technical Notes**: Sample query output shapes from E-902 performance benchmark results. Test count from E-803 regression documentation. CI workflow names from `.github/workflows/` directory listing.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] All internal links resolve to existing files
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S005: Write Project Structure Tree and Remaining Sections

**Description**: Author the project directory structure section (validated tree output), data model summary, contributing guidelines placeholder, and license section to complete all README content.

**Acceptance Criteria**:

- [ ] Project structure section contains a tree representation of the repository matching actual directory layout — includes `models/`, `scripts/`, `seeds/`, `tests/`, `analyses/`, `macros/`, `setup/`, `docs/`, `.github/workflows/`, and root configuration files
- [ ] Tree is wrapped in a collapsible `<details>` block to avoid excessive README length
- [ ] Tree excludes gitignored directories (`data/`, `target/`, `logs/`, `dbt_packages/`, `__pycache__/`, `.venv/`)
- [ ] Data model summary section provides a table of all 7 mart models: name, grain, approximate row count, primary use case — matching DESIGN-DOC.md Section 6.3
- [ ] License section states MIT License (or project-appropriate license as determined by repository owner)
- [ ] No placeholder text (TODO, TBD, WIP) exists anywhere in README.md
- [ ] Total README line count is between 400 and 700 lines

**Technical Notes**: Generate tree from actual repository layout. Validate every directory and file mentioned in the tree exists. Cross-reference mart model table against DESIGN-DOC.md Section 6.3 mart model specifications.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Tree structure validated against repository
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S006: Validate README Rendering and Cross-Reference Integrity

**Description**: Perform a complete validation pass on the final README.md: verify all Mermaid diagrams render on GitHub, all internal links resolve, all referenced files exist, no broken URLs, no AI-attribution phrases, and overall formatting consistency.

**Acceptance Criteria**:

- [ ] All three Mermaid diagrams render correctly when viewed in a GitHub PR preview or on the repository's GitHub page
- [ ] All internal relative links (`docs/TESTS.md`, `docs/RUNBOOK.md`, `docs/OBSERVABILITY.md`, `DESIGN-DOC.md`, `analyses/*.sql`, `profiles.yml.example`, `setup/create_ingestion_stage.sql`) resolve to existing files
- [ ] No external URLs return 404 (Toronto Open Data Portal links, Environment Canada links)
- [ ] Zero occurrences of CLAUDE.md Section 1.1 forbidden phrases (see Section 1.1 for the full list)
- [ ] README passes markdownlint with zero errors (consistent heading levels, no trailing whitespace, proper list formatting)
- [ ] Metrics cited in README (row counts, test counts, model counts, benchmark timings) match values documented in completed epics E-302, E-702, E-803, E-902

**Technical Notes**: Use `markdownlint-cli2` for lint validation. Use `grep -rn` for forbidden phrase detection. Verify Mermaid rendering by pushing to a draft PR branch.

**Definition of Done**:

- [ ] All validation checks pass
- [ ] Code committed to feature branch
- [ ] PR opened with linked issue
- [ ] CI checks green

---

## Exit Criteria

This epic is complete when:

- [ ] `README.md` exists at repository root with all sections specified in stories S001-S005
- [ ] Three Mermaid diagrams (system overview, data flow, ER) render correctly on GitHub
- [ ] Setup instructions reference only files that exist in the repository
- [ ] All internal links in README resolve to existing files
- [ ] README contains zero AI-attribution phrases per CLAUDE.md Section 1.1
- [ ] README passes markdownlint validation
- [ ] README line count is between 400 and 700 lines
- [ ] All cited metrics match documented values from completed epics

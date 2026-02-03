# dbt Project Scaffold

| Field        | Value         |
| ------------ | ------------- |
| Epic ID      | E-202         |
| Phase        | PH-02         |
| Owner        | @dinesh-git17 |
| Status       | Draft         |
| Dependencies | E-201         |
| Created      | 2026-02-02    |

## Context

This epic initializes the dbt Core project that powers all data transformations in the Toronto Urban Mobility Analytics pipeline. The project structure follows dbt best practices documented in the official dbt style guide, with explicit alignment to the medallion architecture (staging/intermediate/marts) defined in DESIGN-DOC.md. Package dependencies (dbt-utils, dbt-expectations, elementary) are pinned to specific versions per CLAUDE.md Section 6.2 to ensure reproducible builds across development and CI environments. The profiles.yml.example template enables contributors to configure their own Snowflake connections without exposing credentials.

## Scope

### In Scope

- dbt Core 1.8+ project initialization via `dbt init`
- dbt_project.yml configuration with model materializations and paths
- packages.yml with pinned versions (dbt-utils 1.3.0, dbt-expectations 0.10.4, elementary 0.16.1, codegen 0.12.1)
- profiles.yml.example template for Snowflake connection
- Directory structure: models/, seeds/, tests/, macros/, analyses/
- Model subdirectories: staging/, intermediate/, marts/
- .sqlfluff configuration for Snowflake dialect
- Successful `dbt deps` and `dbt debug` execution

### Out of Scope

- Actual model SQL files (PH-05 through PH-07)
- Seed CSV files (PH-04)
- CI/CD workflow configuration (PH-10)
- dbt Cloud configuration

## Technical Approach

### Architecture Decisions

- **dbt Core 1.8+ requirement**: Per DESIGN-DOC.md Section 5.2, version 1.8+ is required for latest dbt-snowflake adapter compatibility and improved incremental model performance
- **Pinned package versions**: Per CLAUDE.md Section 6.2, all packages pinned to exact versions evaluated on 2026-02-02 to prevent CI reproducibility issues
- **Ephemeral intermediate models**: All intermediate models configured as ephemeral by default, compiling to CTEs in downstream models per DESIGN-DOC.md Decision D10
- **SQLFluff + sqlfmt separation**: SQLFluff handles linting rules; sqlfmt handles formatting per DESIGN-DOC.md Decision D14

### Integration Points

- Snowflake TORONTO_MOBILITY database (E-201 dependency)
- GitHub Actions CI workflows (consume profiles.yml.example pattern)
- Pre-commit hooks (SQLFluff linting)

### Repository Areas

- `dbt_project.yml` — project configuration
- `packages.yml` — package dependencies
- `profiles.yml.example` — connection template
- `.sqlfluff` — linter configuration
- `models/` — transformation directory tree
- `seeds/` — reference data directory
- `tests/` — singular test directory
- `macros/` — custom macro directory
- `analyses/` — ad-hoc query directory

### Risks

| Risk                                | Likelihood | Impact | Mitigation                                                                |
| ----------------------------------- | ---------- | ------ | ------------------------------------------------------------------------- |
| Package version incompatibility     | Low        | Medium | Versions pre-validated on 2026-02-02; test with `dbt deps && dbt compile` |
| dbt-snowflake adapter version drift | Low        | Medium | Pin adapter version in requirements.txt or pyproject.toml                 |
| profiles.yml accidentally committed | Medium     | High   | .gitignore includes profiles.yml; pre-commit hook checks for credentials  |

## Stories

| ID   | Story                                        | Points | Dependencies     | Status |
| ---- | -------------------------------------------- | ------ | ---------------- | ------ |
| S001 | Initialize dbt project structure             | 2      | None             | Draft  |
| S002 | Configure dbt_project.yml                    | 3      | S001             | Draft  |
| S003 | Create packages.yml with pinned dependencies | 2      | S001             | Draft  |
| S004 | Create profiles.yml.example template         | 2      | S001             | Draft  |
| S005 | Configure SQLFluff for Snowflake dialect     | 2      | S001             | Draft  |
| S006 | Create model directory structure             | 2      | S002             | Draft  |
| S007 | Validate project with dbt deps and dbt debug | 3      | S003, S004, S006 | Draft  |

---

### S001: Initialize dbt project structure

**Description**: Execute `dbt init` to create the foundational project structure with default directories and configuration files.

**Acceptance Criteria**:

- [ ] `dbt init toronto_mobility` executes successfully (or manual creation if project already exists)
- [ ] Root directory contains `dbt_project.yml`
- [ ] `models/` directory exists
- [ ] `seeds/` directory exists
- [ ] `tests/` directory exists
- [ ] `macros/` directory exists
- [ ] `analyses/` directory exists
- [ ] `.gitignore` updated to exclude `target/`, `dbt_packages/`, `logs/`, `profiles.yml`

**Technical Notes**: If repository already has conflicting structure, manually create required directories. Ensure .gitignore additions do not duplicate existing entries.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Directory structure matches DESIGN-DOC.md Section 15.1
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S002: Configure dbt_project.yml

**Description**: Configure the dbt_project.yml file with project metadata, model paths, materialization defaults, and schema routing aligned to medallion architecture.

**Acceptance Criteria**:

- [ ] `name: 'toronto_mobility'` set in dbt_project.yml
- [ ] `version: '1.0.0'` set in dbt_project.yml
- [ ] `config-version: 2` set in dbt_project.yml
- [ ] `profile: 'toronto_mobility'` set in dbt_project.yml
- [ ] `model-paths: ["models"]` configured
- [ ] `seed-paths: ["seeds"]` configured
- [ ] `test-paths: ["tests"]` configured
- [ ] `macro-paths: ["macros"]` configured
- [ ] `analysis-paths: ["analyses"]` configured
- [ ] `target-path: "target"` configured
- [ ] `clean-targets: ["target", "dbt_packages"]` configured
- [ ] Model materializations configured:
  - staging: `+materialized: view`
  - intermediate: `+materialized: ephemeral`
  - marts: `+materialized: table`
- [ ] `dbt parse` executes without errors

**Technical Notes**: Use the models configuration block to set materializations by folder. Reference DESIGN-DOC.md Section 5.2 for materialization policy.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `dbt parse` passes
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S003: Create packages.yml with pinned dependencies

**Description**: Create packages.yml with exact version pins for dbt-utils, dbt-expectations, elementary, and codegen packages.

**Acceptance Criteria**:

- [ ] `packages.yml` file created at project root
- [ ] dbt-utils pinned to version `1.3.0`
- [ ] codegen pinned to version `0.12.1`
- [ ] dbt-expectations pinned to version `0.10.4`
- [ ] elementary pinned to version `0.16.1`
- [ ] `dbt deps` executes successfully
- [ ] `dbt_packages/` directory created with installed packages
- [ ] No version range specifiers used (no `>=`, `~=`, `^`)

**Technical Notes**: Package versions sourced from DESIGN-DOC.md Section 15.2. These versions were evaluated for compatibility on 2026-02-02.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `dbt deps` passes
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S004: Create profiles.yml.example template

**Description**: Create a profiles.yml.example file that documents the required Snowflake connection configuration without containing actual credentials.

**Acceptance Criteria**:

- [ ] `profiles.yml.example` file created at project root
- [ ] Profile name is `toronto_mobility`
- [ ] Default target is `dev`
- [ ] Contains `dev` output configuration with placeholders:
  - `type: snowflake`
  - `account: '<YOUR_ACCOUNT_IDENTIFIER>'`
  - `user: '<YOUR_USERNAME>'`
  - `password: '<YOUR_PASSWORD>'`
  - `role: TRANSFORMER_ROLE`
  - `database: TORONTO_MOBILITY`
  - `warehouse: TRANSFORM_WH`
  - `schema: MARTS`
  - `threads: 4`
{% raw %}- [ ] Contains `ci` output configuration with environment variable references:
  - `account: "{{ env_var('SNOWFLAKE_ACCOUNT') }}"`
  - `user: "{{ env_var('SNOWFLAKE_USER') }}"`
  - `password: "{{ env_var('SNOWFLAKE_PASSWORD') }}"`{% endraw %}
- [ ] File includes header comment explaining usage
- [ ] `profiles.yml` is in .gitignore

**Technical Notes**: The `ci` target uses Jinja env_var syntax for GitHub Actions integration. Contributors copy this file to `profiles.yml` and replace placeholders.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] File contains no actual credentials
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S005: Configure SQLFluff for Snowflake dialect

**Description**: Create .sqlfluff configuration file with Snowflake dialect settings and rule configurations aligned to project standards.

**Acceptance Criteria**:

- [ ] `.sqlfluff` file created at project root
- [ ] `dialect = snowflake` configured
- [ ] `templater = dbt` configured
- [ ] `exclude_rules` includes rules incompatible with dbt Jinja (L003 for jinja spacing)
- [ ] `max_line_length = 120` configured
- [ ] `indent_unit = space` configured
- [ ] `tab_space_size = 4` configured
- [ ] Capitalization rules configured:
  - Keywords: UPPER
  - Functions: UPPER
  - Identifiers: LOWER
- [ ] `sqlfluff lint models/ --dialect snowflake` executes without configuration errors (may have linting warnings on empty models)

**Technical Notes**: SQLFluff handles linting; sqlfmt handles formatting. Exclude rules that conflict with dbt Jinja templating. Reference DESIGN-DOC.md Section 5.2 for tool versions.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] SQLFluff configuration validated
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S006: Create model directory structure

**Description**: Create the complete model directory hierarchy with placeholder files following the medallion architecture pattern.

**Acceptance Criteria**:

- [ ] `models/staging/` directory exists
- [ ] `models/staging/ttc/` directory exists with `.gitkeep`
- [ ] `models/staging/bike_share/` directory exists with `.gitkeep`
- [ ] `models/staging/weather/` directory exists with `.gitkeep`
- [ ] `models/intermediate/` directory exists with `.gitkeep`
- [ ] `models/marts/` directory exists
- [ ] `models/marts/core/` directory exists with `.gitkeep`
- [ ] `models/marts/mobility/` directory exists with `.gitkeep`
- [ ] Directory structure matches DESIGN-DOC.md Section 15.1

**Technical Notes**: Use `.gitkeep` files to preserve empty directories in git. These placeholders are removed as actual model files are added in later phases.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] All directories exist with .gitkeep files
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S007: Validate project with dbt deps and dbt debug

**Description**: Execute full project validation confirming package installation, Snowflake connectivity, and project configuration correctness.

**Acceptance Criteria**:

- [ ] `dbt deps` completes with exit code 0
- [ ] All four packages installed in `dbt_packages/`
- [ ] Local `profiles.yml` created from `profiles.yml.example` with valid credentials
- [ ] `dbt debug` returns exit code 0
- [ ] `dbt debug` shows "All checks passed!" message
- [ ] Connection test confirms:
  - Snowflake connection successful
  - Database TORONTO_MOBILITY accessible
  - Schema MARTS accessible
  - Role TRANSFORMER_ROLE active
- [ ] `dbt compile` executes without errors (empty project compiles successfully)

**Technical Notes**: This is the phase exit criterion from PHASES.md. All connection parameters must resolve correctly. Document any warnings in PR description.

**Definition of Done**:

- [ ] `dbt debug` output captured and verified
- [ ] All checks passed
- [ ] PR opened with linked issue
- [ ] CI checks green
- [ ] Phase PH-02 exit criterion satisfied

## Exit Criteria

This epic is complete when:

- [ ] All stories marked complete
- [ ] All acceptance criteria verified
- [ ] `dbt deps` installs all packages without error
- [ ] `dbt debug` returns "All checks passed!"
- [ ] `dbt compile` executes without errors
- [ ] Project structure matches DESIGN-DOC.md Section 15.1
- [ ] No credentials committed to repository

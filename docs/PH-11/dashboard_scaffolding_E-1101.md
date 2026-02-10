# Dashboard Application Scaffolding & Page Routing

| Field        | Value         |
| ------------ | ------------- |
| Epic ID      | E-1101        |
| Phase        | PH-11         |
| Owner        | @dinesh-git17 |
| Status       | Complete      |
| Dependencies | [E-702]       |
| Created      | 2026-02-10    |

---

## Context

The Toronto Urban Mobility Analytics data platform has a complete MARTS layer — 4 dimension tables, 3 fact tables, 75+ dbt tests, and all 5 analytical benchmark queries executing under 1 second on X-Small — but no presentation tier. PH-11 establishes the Streamlit multi-page application framework that all subsequent visualization phases (PH-12 through PH-14) extend. This epic creates the foundational directory structure, application entry point, page routing mechanism, Streamlit theme configuration, dependency manifest, and credential management template per dashboard-design.md Section 5.2.

Without this scaffolding, no dashboard component — data access, design system, or page content — has a deployment target. This work belongs in PH-11 because it is a hard prerequisite for every other PH-11 epic and all subsequent visualization phases.

---

## Scope

### In Scope

- `dashboard/` directory tree at repository root per dashboard-design.md Section 5.2: `app.py`, `pages/`, `components/`, `data/`, `styles/`, `.streamlit/`
- `dashboard/app.py` entry point with Streamlit multi-page navigation and sidebar branding
- `dashboard/.streamlit/config.toml` with project theme configuration (primary color `#DA291C`, background `#FAFAFA`, text color `#334155`)
- `dashboard/requirements.txt` with pinned dashboard dependencies (Streamlit, Altair, snowflake-connector-python, pandas)
- `dashboard/secrets.toml.example` credential template with zero secrets exposed and documented defaults for warehouse, database, and role
- Dashboard-specific `.gitignore` entry for `dashboard/.streamlit/secrets.toml`
- 5 page module stubs in `dashboard/pages/` with routing integration and placeholder content
- Empty module files for `dashboard/components/`, `dashboard/data/` to establish Python import paths

### Out of Scope

- Snowflake connection implementation (E-1102)
- CSS styling, Altair theme registration, and component implementations (E-1103)
- Overview page content, hero metrics, and visualizations (E-1104)
- Page content for TTC Deep Dive, Bike Share, Weather Impact, Station Explorer (PH-12 through PH-14)
- Streamlit Community Cloud deployment configuration
- PyDeck or Plotly dependency installation (deferred to phases requiring map and treemap visualizations)
- Dashboard-specific `README.md` (deferred until dashboard is functional)

---

## Technical Approach

### Architecture Decisions

- **Streamlit native multi-page routing** — Streamlit 1.31+ supports multi-page apps via the `pages/` directory convention. Each file in `pages/` becomes a sidebar navigation entry ordered by filename prefix (`1_`, `2_`, etc.). No custom router, session-state page switching, or third-party navigation library required.
- **Numeric prefix naming for page files** — `1_Overview.py`, `2_TTC_Deep_Dive.py`, `3_Bike_Share.py`, `4_Weather_Impact.py`, `5_Station_Explorer.py`. Streamlit strips the numeric prefix and underscores in the sidebar display. This enforces deterministic navigation order matching dashboard-design.md Section 4.1.
- **Separate `requirements.txt` from `pyproject.toml`** — The dashboard is a distinct deployment target (Streamlit Community Cloud in PH-14+) with its own dependency surface. Keeping `requirements.txt` in `dashboard/` avoids coupling the ingestion pipeline's dev dependencies (ruff, mypy, pytest) with the dashboard runtime.
- **Secrets-based credential management** — Streamlit's `st.secrets` reads from `.streamlit/secrets.toml` at runtime. The `secrets.toml.example` template provides the required key structure with empty values and documented defaults. The actual `secrets.toml` is gitignored to prevent credential exposure.

### Integration Points

- **PH-07 MARTS layer** — Entry criterion: all 7 dimension and fact tables populated and passing schema tests
- **dashboard-design.md Section 5.2** — Canonical directory structure definition
- **dashboard-design.md Section 4.1** — Page structure and navigation order
- **DESIGN-DOC.md Section 10** — RBAC configuration: `TRANSFORMER_ROLE`, `TRANSFORM_WH`, `TORONTO_MOBILITY` database
- **E-1102, E-1103, E-1104** — All downstream PH-11 epics depend on this scaffolding

### Repository Areas

- `dashboard/app.py` (new)
- `dashboard/pages/1_Overview.py` (new — stub)
- `dashboard/pages/2_TTC_Deep_Dive.py` (new — stub)
- `dashboard/pages/3_Bike_Share.py` (new — stub)
- `dashboard/pages/4_Weather_Impact.py` (new — stub)
- `dashboard/pages/5_Station_Explorer.py` (new — stub)
- `dashboard/components/__init__.py` (new — empty module)
- `dashboard/data/__init__.py` (new — empty module)
- `dashboard/styles/` (new — empty directory)
- `dashboard/.streamlit/config.toml` (new)
- `dashboard/requirements.txt` (new)
- `dashboard/secrets.toml.example` (new)
- `.gitignore` (modify — add `dashboard/.streamlit/secrets.toml`)

### Risks

| Risk                                                                                                                                   | Likelihood | Impact | Mitigation                                                                                                                                                                                                                             |
| -------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Streamlit multi-page routing convention changes between 1.31 and a future pinned version, breaking page discovery or sidebar ordering  | Low        | High   | Pin `streamlit>=1.31.0,<2.0.0` in `requirements.txt`; validate routing on the exact pinned version before merge                                                                                                                        |
| `secrets.toml.example` accidentally committed with real credentials during local development, exposing Snowflake access                | Medium     | High   | `.gitignore` entry for `dashboard/.streamlit/secrets.toml` committed in S003 before any local secrets file is created; `secrets.toml.example` uses empty strings exclusively; GitHub push protection enabled per CLAUDE.md Section 9.9 |
| Page module stubs import dashboard modules (`data/`, `components/`) that do not yet exist, causing `ModuleNotFoundError` on navigation | Medium     | Medium | Stubs contain only `st.title()` and `st.info()` — no imports from `data/` or `components/`. Functional imports added when page content is implemented in E-1104 and later phases                                                       |

---

## Stories

| ID   | Story                                                            | Points | Dependencies | Status |
| ---- | ---------------------------------------------------------------- | ------ | ------------ | ------ |
| S001 | Create dashboard directory structure and Streamlit configuration | 3      | None         | Complete |
| S002 | Implement app.py entry point with multi-page navigation          | 5      | S001         | Complete |
| S003 | Create dependency manifest and credential template               | 3      | S001         | Complete |
| S004 | Create page module stubs for all 5 dashboard pages               | 5      | S002         | Complete |

---

### S001: Create Dashboard Directory Structure and Streamlit Configuration

**Description**: Create the `dashboard/` directory tree at repository root with all subdirectories per dashboard-design.md Section 5.2, and configure `.streamlit/config.toml` with the project theme.

**Acceptance Criteria**:

- [ ] Directory `dashboard/` exists at repository root
- [ ] Subdirectories exist: `dashboard/pages/`, `dashboard/components/`, `dashboard/data/`, `dashboard/styles/`, `dashboard/.streamlit/`
- [ ] File `dashboard/.streamlit/config.toml` exists with `[theme]` section
- [ ] Theme sets `primaryColor = "#DA291C"` (TTC red per dashboard-design.md Section 6.1)
- [ ] Theme sets `backgroundColor = "#FAFAFA"` (off-white per dashboard-design.md Section 6.1)
- [ ] Theme sets `secondaryBackgroundColor = "#F0F2F6"` (sidebar and container background)
- [ ] Theme sets `textColor = "#334155"` (neutral slate per dashboard-design.md Section 6.1)
- [ ] Theme sets `font = "sans serif"` (Streamlit native; custom Inter loaded via CSS in E-1103)
- [ ] File `dashboard/components/__init__.py` exists (empty, enables Python module imports)
- [ ] File `dashboard/data/__init__.py` exists (empty, enables Python module imports)

**Technical Notes**: The `.streamlit/config.toml` file configures Streamlit's built-in theming engine. The `font` setting supports `"sans serif"`, `"serif"`, or `"monospace"` — custom web fonts (Inter) are loaded via CSS injection in E-1103. The `primaryColor` applies to interactive widgets (sliders, checkboxes, links).

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Directory structure matches dashboard-design.md Section 5.2
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S002: Implement app.py Entry Point with Multi-Page Navigation

**Description**: Build `dashboard/app.py` as the Streamlit application entry point with page configuration, sidebar branding, and multi-page routing via the native `pages/` directory convention.

**Acceptance Criteria**:

- [ ] File `dashboard/app.py` exists as the Streamlit entry point
- [ ] `st.set_page_config()` called with `page_title="Toronto Mobility Dashboard"`, `layout="wide"`, and `initial_sidebar_state="expanded"`
- [ ] Sidebar displays project title "Toronto Mobility Dashboard" via `st.sidebar.title()`
- [ ] Sidebar displays a concise project description (1-2 sentences) via `st.sidebar.markdown()`
- [ ] Multi-page routing implemented via Streamlit's native `pages/` directory convention — no manual page-switching logic
- [ ] `streamlit run dashboard/app.py` launches without import errors and renders the sidebar navigation with all page entries
- [ ] Application displays the Overview page (Page 1) as the default landing view
- [ ] No credentials, API keys, or secrets present in `app.py`

**Technical Notes**: `st.set_page_config()` must be the first Streamlit command in `app.py`. The `layout="wide"` setting maximizes horizontal space for dashboard grids. Streamlit automatically discovers page modules in `pages/` and renders them in the sidebar ordered by filename prefix.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `streamlit run dashboard/app.py` launches successfully
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S003: Create Dependency Manifest and Credential Template

**Description**: Create `requirements.txt` with pinned dashboard runtime dependencies and `secrets.toml.example` with the Snowflake credential template containing zero actual secrets.

**Acceptance Criteria**:

- [ ] File `dashboard/requirements.txt` exists with pinned dependencies:
  - `streamlit>=1.31.0,<2.0.0`
  - `altair>=5.0.0,<6.0.0`
  - `snowflake-connector-python>=3.12.0,<4.0.0`
  - `pandas>=2.0.0,<3.0.0`
- [ ] No PyDeck or Plotly in `requirements.txt` (excluded from PH-11 scope)
- [ ] File `dashboard/secrets.toml.example` exists with placeholder structure containing `[snowflake]` section and keys: `account`, `user`, `password`, `warehouse`, `database`, `role`
- [ ] `secrets.toml.example` uses empty string `""` for credential values (`account`, `user`, `password`)
- [ ] `secrets.toml.example` uses documented defaults for infrastructure values: `warehouse = "TRANSFORM_WH"`, `database = "TORONTO_MOBILITY"`, `role = "TRANSFORMER_ROLE"` per DESIGN-DOC.md Section 10
- [ ] Repository `.gitignore` includes the pattern `dashboard/.streamlit/secrets.toml` to prevent credential commits
- [ ] `secrets.toml.example` contains zero actual credentials — only empty placeholders and documented defaults

**Technical Notes**: The `secrets.toml.example` serves as the single source of truth for required credential fields. Developers copy it to `dashboard/.streamlit/secrets.toml` and fill in their Snowflake credentials. The `.gitignore` entry must be committed before any local `secrets.toml` is created to prevent accidental exposure. GitHub push protection (CLAUDE.md Section 9.9) provides a secondary safety net.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `pip install -r dashboard/requirements.txt` succeeds in a clean virtual environment
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S004: Create Page Module Stubs for All 5 Dashboard Pages

**Description**: Create 5 page module files in `dashboard/pages/` with routing-compatible filenames, page titles, and placeholder content indicating implementation phase for each page.

**Acceptance Criteria**:

- [ ] File `dashboard/pages/1_Overview.py` exists with `st.set_page_config(page_title="Overview | Toronto Mobility", layout="wide")`, `st.title("Overview")`, and placeholder indicating E-1104 implementation
- [ ] File `dashboard/pages/2_TTC_Deep_Dive.py` exists with `st.set_page_config(page_title="TTC Deep Dive | Toronto Mobility", layout="wide")`, `st.title("TTC Deep Dive")`, and placeholder indicating PH-12 scope
- [ ] File `dashboard/pages/3_Bike_Share.py` exists with `st.set_page_config(page_title="Bike Share | Toronto Mobility", layout="wide")`, `st.title("Bike Share")`, and placeholder indicating PH-12 scope
- [ ] File `dashboard/pages/4_Weather_Impact.py` exists with `st.set_page_config(page_title="Weather Impact | Toronto Mobility", layout="wide")`, `st.title("Weather Impact")`, and placeholder indicating PH-13 scope
- [ ] File `dashboard/pages/5_Station_Explorer.py` exists with `st.set_page_config(page_title="Station Explorer | Toronto Mobility", layout="wide")`, `st.title("Station Explorer")`, and placeholder indicating PH-14 scope
- [ ] All 5 page modules appear as navigation entries in the Streamlit sidebar when `streamlit run dashboard/app.py` is executed
- [ ] Page titles display in the sidebar without numeric prefixes (Streamlit strips `N_` prefixes automatically)
- [ ] No `ModuleNotFoundError` or `ImportError` when navigating between any two pages
- [ ] Page stubs contain no imports from `dashboard/data/` or `dashboard/components/` (those modules are implemented in E-1102 and E-1103)

**Technical Notes**: Streamlit's multi-page convention requires files in the `pages/` directory to be valid Python modules. Each stub must call `st.set_page_config()` as its first Streamlit command. The `layout="wide"` setting must be consistent across all pages to prevent layout shifting during navigation. Placeholder content uses `st.info()` to display a styled message rather than plain text.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] All 5 pages accessible via sidebar navigation without errors
- [ ] PR opened with linked issue
- [ ] CI checks green

---

## Exit Criteria

This epic is complete when:

- [ ] `dashboard/` directory exists at repository root with subdirectories: `pages/`, `components/`, `data/`, `styles/`, `.streamlit/`
- [ ] `streamlit run dashboard/app.py` launches and renders sidebar navigation with 5 page entries
- [ ] `.streamlit/config.toml` applies project theme colors (`#DA291C` primary, `#FAFAFA` background, `#334155` text)
- [ ] `requirements.txt` contains pinned versions of Streamlit, Altair, snowflake-connector-python, and pandas
- [ ] `secrets.toml.example` committed with zero credentials and documented Snowflake defaults
- [ ] `dashboard/.streamlit/secrets.toml` pattern present in `.gitignore`
- [ ] All 5 page stubs render without import errors
- [ ] No actual Snowflake credentials exist in any committed file

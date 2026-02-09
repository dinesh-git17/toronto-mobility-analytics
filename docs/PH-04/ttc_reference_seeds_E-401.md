# TTC Reference Data Seeds

| Field        | Value         |
| ------------ | ------------- |
| Epic ID      | E-401         |
| Phase        | PH-04         |
| Owner        | @dinesh-git17 |
| Status       | Draft         |
| Dependencies | [E-303]       |
| Created      | 2026-02-09    |

## Context

TTC delay data in the RAW schema contains raw station names with inconsistent spelling across years (e.g., "BLOOR STN", "BLOOR STATION", "BLOOR-YONGE" all refer to the same physical station) and numeric/alphanumeric delay cause codes with no human-readable descriptions. DESIGN-DOC.md Section 6.5 mandates a manual seed file approach for station name resolution, chosen over fuzzy matching for higher accuracy (Decision D3). Downstream intermediate models (`int_ttc_delays_enriched` in PH-06) depend on `ttc_station_mapping` to join raw station names to canonical station keys and on `ttc_delay_codes` to enrich delay incidents with descriptive categories. Without these seeds, the staging-to-intermediate transformation chain cannot produce meaningful analytics. This epic delivers both TTC reference seed CSV files, curated from analysis of the validated source data produced by E-302 and loaded by E-303.

## Scope

### In Scope

- Analysis of distinct station names across all validated TTC subway delay CSVs (2020-2025) to catalog name variants
- `seeds/ttc_station_mapping.csv` mapping raw station name variants to canonical station names, station keys, and subway line codes per DESIGN-DOC.md Section 6.5
- Analysis of distinct delay codes across all validated TTC subway, bus, and streetcar delay CSVs
- `seeds/ttc_delay_codes.csv` mapping delay codes to human-readable descriptions and analytical categories
- Structural validation of both CSV files (column presence, no duplicates, no empty keys)

### Out of Scope

- Bus and streetcar location normalization (free-form intersection text; deferred to PH-06 intermediate layer logic)
- Bike Share station reference data (covered by E-402)
- Date spine seed generation (covered by E-402)
- `_seeds.yml` documentation file (covered by E-402)
- `dbt seed` execution against Snowflake (covered by E-402)
- Station coordinate geocoding (TTC subway station coordinates are not required for ttc_station_mapping; dim_station in PH-07 handles unified station geography)

## Technical Approach

### Architecture Decisions

- **Manual curation over fuzzy matching**: Per DESIGN-DOC.md Decision D3, station name mapping uses a manually curated CSV seed rather than algorithmic fuzzy matching. This guarantees deterministic, auditable mappings with zero false positives. The tradeoff is upfront curation effort, acceptable for a portfolio project with ~77 subway stations and ~200 name variants.
- **Station key format**: Station keys follow the pattern `ST_NNN` (e.g., `ST_001`) as sequential identifiers. These are string-typed surrogate keys that remain stable across data refreshes. The `canonical_station_name` provides the human-readable label; `station_key` provides the join key for dim_station.
- **Delay code categories**: Delay codes are grouped into analytical categories (Mechanical, Signal, Passenger, Infrastructure, Operations, Weather, Security, General) to enable aggregation-level analysis in mart models. Category assignment is based on TTC documentation and code semantics.
- **Subway-only station mapping**: The `ttc_station_mapping` seed covers subway stations exclusively. Bus and streetcar data use free-form location strings (intersections like "QUEEN ST E AT BROADVIEW AVE") that require different normalization logic in the intermediate layer. Mixing these into a single mapping seed would conflate two fundamentally different resolution strategies.
- **Source data for analysis**: Station names and delay codes are extracted from validated CSV files in `data/validated/` produced by E-302, not from Snowflake RAW tables. This avoids a Snowflake dependency for seed generation and allows offline curation.

### Integration Points

- Upstream: Reads validated CSV files from `data/validated/ttc_subway/`, `data/validated/ttc_bus/`, `data/validated/ttc_streetcar/` produced by E-302
- Downstream: `seeds/ttc_station_mapping.csv` consumed by `int_ttc_delays_enriched` (PH-06) for station name resolution
- Downstream: `seeds/ttc_delay_codes.csv` consumed by `int_ttc_delays_enriched` (PH-06) and `dim_ttc_delay_codes` (PH-07)
- Cross-reference: DESIGN-DOC.md Section 6.5 (station mapping strategy), Section 6.1 (dim_ttc_delay_codes schema)

### Repository Areas

- `seeds/ttc_station_mapping.csv` — station name variant-to-canonical mapping
- `seeds/ttc_delay_codes.csv` — delay code definitions with categories
- `scripts/` — analysis scripts for extracting distinct station names and delay codes (if Python utility is created)
- `data/validated/` — source of truth for distinct value extraction

### Risks

| Risk                                                                                              | Likelihood | Impact | Mitigation                                                                                                                                                                                     |
| ------------------------------------------------------------------------------------------------- | ---------- | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Undiscovered station name variants in future data loads cause UNKNOWN mappings above 1% threshold | Medium     | Medium | Design the mapping to cover all variants observed in 2020-2025 data; PH-06 `assert_station_mapping_coverage` test flags regressions; new variants are added to the seed file and re-seeded     |
| TTC delay codes lack official documentation for description and category assignment               | Medium     | Low    | Cross-reference code semantics with observed delay descriptions in raw data; document assumptions in \_seeds.yml; categories can be refined in later phases without breaking downstream models |
| Subway station name variants exceed 300 entries making manual curation error-prone                | Low        | Medium | Sort variants alphabetically, group by canonical station, and validate that each canonical station has exactly one station_key; add uniqueness test on (raw_station_name) column               |
| Line 3 SRT station names appear only in pre-November 2023 data and may be missed                  | Low        | Low    | Include SRT stations in mapping with line_code=SRT; document closure date (2023-11-19) in seed comments                                                                                        |

## Stories

| ID   | Story                                                                | Points | Dependencies | Status |
| ---- | -------------------------------------------------------------------- | ------ | ------------ | ------ |
| S001 | Extract and catalog distinct TTC station names from validated data   | 3      | None         | Draft  |
| S002 | Build ttc_station_mapping.csv with variant-to-canonical mappings     | 8      | S001         | Draft  |
| S003 | Build ttc_delay_codes.csv with code-description-category definitions | 5      | None         | Draft  |
| S004 | Validate TTC seed CSV structural integrity and data completeness     | 2      | S002, S003   | Draft  |

---

### S001: Extract and catalog distinct TTC station names from validated data

**Description**: Analyze all validated TTC subway delay CSV files to produce a complete catalog of distinct raw station names with frequency counts, grouped by subway line, serving as the input for manual station mapping curation.

**Acceptance Criteria**:

- [ ] All validated TTC subway CSV files in `data/validated/ttc_subway/` (spanning 2020-2025) are read and parsed
- [ ] A deduplicated list of `(raw_station_name, line_code)` pairs is extracted with occurrence counts per pair
- [ ] Output is sorted alphabetically by `raw_station_name` and written to a working file (e.g., `data/working/station_name_analysis.csv`) with columns: `raw_station_name`, `line_code`, `occurrence_count`, `first_seen_year`, `last_seen_year`
- [ ] The analysis captures station names from all 4 subway lines: YU, BD, SHP, SRT
- [ ] Total distinct `raw_station_name` values are logged to stdout (expected range: 100-300 variants for ~77 canonical stations)
- [ ] Empty or whitespace-only station names are flagged separately with their file paths and row numbers

**Technical Notes**: Use `csv.DictReader` to read validated CSVs. The subway schema has columns `Station` and `Line`. Strip leading/trailing whitespace from station names before deduplication. Include the `data/working/` directory in `.gitignore`. This analysis output is a working artifact, not a committed file.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Tests pass locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S002: Build ttc_station_mapping.csv with variant-to-canonical mappings

**Description**: Create the `seeds/ttc_station_mapping.csv` seed file that maps every observed raw TTC subway station name variant to a canonical station name, a deterministic station key, and the associated subway line code, per DESIGN-DOC.md Section 6.5.

**Acceptance Criteria**:

- [ ] File `seeds/ttc_station_mapping.csv` exists with columns: `raw_station_name`, `canonical_station_name`, `station_key`, `line_code`
- [ ] Every distinct `raw_station_name` from S001 analysis output has exactly one row in the mapping file
- [ ] `station_key` values follow the format `ST_NNN` (e.g., `ST_001`, `ST_002`) and are unique per canonical station (multiple raw variants map to the same `station_key`)
- [ ] `canonical_station_name` uses official TTC station names (e.g., "Bloor-Yonge", "St. George", "Kennedy")
- [ ] `line_code` values are restricted to: `YU`, `BD`, `SHP`, `SRT`
- [ ] Stations served by multiple lines (e.g., Bloor-Yonge on YU and BD, St. George on YU and BD) have separate rows per line with distinct `raw_station_name`/`line_code` combinations but the same `station_key`
- [ ] `raw_station_name` column has zero duplicate values (each raw variant appears exactly once)
- [ ] Line 3 SRT stations (Kennedy, Lawrence East, Ellesmere, Midland, Scarborough Centre, McCowan) are included with `line_code = SRT`
- [ ] File is UTF-8 encoded with no BOM, uses comma delimiter, and double-quote escaping for values containing commas

**Technical Notes**: Group the S001 analysis output by visual similarity to identify canonical station names. Use the official TTC subway station list (77 stations across 4 lines) as the canonical reference. Assign `station_key` values sequentially by line (YU stations first, then BD, SHP, SRT). For interchange stations (Bloor-Yonge, St. George, Spadina, Sheppard-Yonge, Kennedy), the same `station_key` is used across lines. Verify completeness by checking that every canonical subway station has at least one raw variant mapped.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Tests pass locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S003: Build ttc_delay_codes.csv with code-description-category definitions

**Description**: Create the `seeds/ttc_delay_codes.csv` seed file that maps every TTC delay cause code to a human-readable description and an analytical category, serving as the reference table for `dim_ttc_delay_codes` (PH-07) and `int_ttc_delays_enriched` (PH-06).

**Acceptance Criteria**:

- [ ] File `seeds/ttc_delay_codes.csv` exists with columns: `delay_code`, `delay_description`, `delay_category`
- [ ] Every distinct delay code observed in validated TTC subway CSV files (`Code` column), bus CSV files (`Incident`/`DELAY_CODE` column), and streetcar CSV files (`Incident`/`DELAY_CODE` column) has exactly one row
- [ ] `delay_code` column has zero duplicate values
- [ ] `delay_description` provides a concise human-readable explanation (2-10 words) for each code (e.g., "Mechanical - Loss of Power" for MUATC, "Passenger Alarm Activation" for PUOPO)
- [ ] `delay_category` assigns each code to exactly one of these categories: `Mechanical`, `Signal`, `Passenger`, `Infrastructure`, `Operations`, `Weather`, `Security`, `General`
- [ ] No `delay_description` or `delay_category` value is empty or NULL
- [ ] File is UTF-8 encoded with no BOM, uses comma delimiter, and double-quote escaping for values containing commas or special characters
- [ ] Total row count covers all unique codes across all three TTC transit modes (expected range: 30-80 distinct codes)

**Technical Notes**: Extract distinct codes from: (1) `Code` column in `data/validated/ttc_subway/` CSVs, (2) `Incident` column in `data/validated/ttc_bus/` CSVs, (3) `Incident` column in `data/validated/ttc_streetcar/` CSVs. Some codes are shared across modes; others are mode-specific. TTC publishes a partial code reference in their delay data documentation. For codes without official descriptions, infer meaning from the code mnemonic (e.g., "MU" prefix = Mechanical/Unit, "PU" prefix = Passenger/Unit, "SG" prefix = Signal). Document any codes with uncertain descriptions in the PR for review.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Tests pass locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S004: Validate TTC seed CSV structural integrity and data completeness

**Description**: Run structural validation checks on both TTC seed CSV files to confirm column presence, uniqueness constraints, and data completeness before downstream consumption.

**Acceptance Criteria**:

- [ ] `seeds/ttc_station_mapping.csv` loads without error via `csv.DictReader` and contains exactly 4 columns: `raw_station_name`, `canonical_station_name`, `station_key`, `line_code`
- [ ] `seeds/ttc_station_mapping.csv` has zero duplicate `raw_station_name` values (verified programmatically)
- [ ] `seeds/ttc_station_mapping.csv` has zero empty values in any column
- [ ] `seeds/ttc_station_mapping.csv` `line_code` values are all members of `{YU, BD, SHP, SRT}`
- [ ] `seeds/ttc_delay_codes.csv` loads without error via `csv.DictReader` and contains exactly 3 columns: `delay_code`, `delay_description`, `delay_category`
- [ ] `seeds/ttc_delay_codes.csv` has zero duplicate `delay_code` values
- [ ] `seeds/ttc_delay_codes.csv` has zero empty values in any column
- [ ] `seeds/ttc_delay_codes.csv` `delay_category` values are all members of `{Mechanical, Signal, Passenger, Infrastructure, Operations, Weather, Security, General}`
- [ ] Validation runs as a standalone script or pytest test and exits with code 0 on success, code 1 on failure

**Technical Notes**: This validation can be implemented as a pytest test in `tests/test_seeds.py` or a standalone script. Use `csv.DictReader` for parsing and Python `set` operations for uniqueness checks. This is a pre-dbt validation — it confirms CSV integrity before `dbt seed` attempts to load the data.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Tests pass locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

## Exit Criteria

This epic is complete when:

- [ ] `seeds/ttc_station_mapping.csv` exists with all observed subway station name variants mapped to canonical names and station keys
- [ ] `seeds/ttc_delay_codes.csv` exists with all observed TTC delay codes mapped to descriptions and categories
- [ ] Both CSV files pass structural integrity validation (no duplicates, no empty keys, valid column structure)
- [ ] `line_code` values in station mapping are restricted to `{YU, BD, SHP, SRT}`
- [ ] `delay_category` values are restricted to the defined 8-category taxonomy
- [ ] Every canonical TTC subway station (77 stations across 4 lines) has at least one raw variant in the mapping
- [ ] Station mapping covers >= 99% of raw station name occurrences in validated subway delay data

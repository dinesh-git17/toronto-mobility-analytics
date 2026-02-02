---
name: epic-writer
description: Generate implementation-ready epics and stories from project phases. Use when decomposing phases into epics, writing user stories, creating acceptance criteria, or planning sprint-level work. Triggers on requests for epic generation, story writing, backlog creation, or implementation planning. MANDATORY for all epic/story output in this repository.
---

# Epic Writer

Generate engineering-grade epics and stories from phase definitions. Produce implementation-ready artifacts that require zero clarification.

## Authority

This skill enforces Staff+ TPM standards for all backlog artifacts. Manual epic writing outside this skill is a governance violation.

## Workflow

### Step 1: Load Context

Read required files before generating any epic:

1. `docs/PHASES.md` — phase definitions and exit criteria
2. `DESIGN-DOC.md` — technical architecture and data contracts
3. `CLAUDE.md` — governance rules and Definition of Done
4. Current repository structure via `ls -la` on relevant directories

### Step 2: Select Target Phase

Identify the phase to decompose. Confirm phase ID matches `docs/PHASES.md`. Refuse if phase is marked `[COMPLETE]`.

### Step 3: Analyze Phase Scope

Extract from phase description:

- Concrete deliverables
- Technical components
- Exit criteria
- Dependencies on prior phases

### Step 4: Decompose into Epics

Each phase produces 1-4 epics. Each epic represents a cohesive, shippable increment.

### Step 5: Generate Stories

Each epic contains 3-8 stories. Each story is independently implementable within 1-3 days.

### Step 6: Write Output

Save epic to: `docs/<phase_id>/<epic_name>_<epic_id>.md`

Example: `docs/PH-02/snowflake_infrastructure_E001.md`

## Epic Structure

ALWAYS use this exact structure:

```markdown
# <Epic Title>

| Field        | Value                    |
| ------------ | ------------------------ |
| Epic ID      | E<NNN>                   |
| Phase        | PH-<NN>                  |
| Owner        | @dinesh-git17            |
| Status       | Draft                    |
| Dependencies | [E<NNN>, E<NNN>] or None |
| Created      | YYYY-MM-DD               |

## Context

<3-5 sentences explaining:>

- What problem this epic solves
- Why this work is necessary now
- How it relates to the phase objective
- Key technical constraints from DESIGN-DOC.md

## Scope

### In Scope

- <Specific deliverable 1>
- <Specific deliverable 2>
- <Specific deliverable 3>

### Out of Scope

- <Explicitly excluded item 1>
- <Explicitly excluded item 2>

## Technical Approach

### Architecture Decisions

- <Decision 1 with rationale>
- <Decision 2 with rationale>

### Integration Points

- <System/component this epic integrates with>

### Repository Areas

- <Directory or file path affected>

### Risks

| Risk               | Likelihood      | Impact          | Mitigation            |
| ------------------ | --------------- | --------------- | --------------------- |
| <Risk description> | Low/Medium/High | Low/Medium/High | <Mitigation strategy> |

## Stories

| ID   | Story         | Points | Dependencies | Status |
| ---- | ------------- | ------ | ------------ | ------ |
| S001 | <Story title> | <1-8>  | None         | Draft  |
| S002 | <Story title> | <1-8>  | S001         | Draft  |

---

### S001: <Story Title>

**Description**: <Single sentence describing what is built>

**Acceptance Criteria**:

- [ ] <Testable criterion 1>
- [ ] <Testable criterion 2>
- [ ] <Testable criterion 3>

**Technical Notes**: <Implementation guidance if needed>

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Tests pass locally
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S002: <Story Title>

<Repeat structure for each story>

## Exit Criteria

This epic is complete when:

- [ ] All stories marked complete
- [ ] All acceptance criteria verified
- [ ] Integration tested with dependent systems
- [ ] Documentation updated
```

## Story Writing Rules

### Story Points Scale

| Points | Complexity                       | Duration  |
| ------ | -------------------------------- | --------- |
| 1      | Trivial change, single file      | < 2 hours |
| 2      | Small change, 2-3 files          | 2-4 hours |
| 3      | Moderate change, clear path      | 4-8 hours |
| 5      | Significant work, some unknowns  | 1-2 days  |
| 8      | Large scope, multiple components | 2-3 days  |

Stories > 8 points MUST be split.

### Acceptance Criteria Rules

Each criterion MUST be:

- **Testable**: Can verify pass/fail objectively
- **Specific**: Names exact files, commands, or outputs
- **Atomic**: Tests one behavior only

**Good Examples**:

- `dbt debug` returns exit code 0 with all connection checks green
- File `models/staging/ttc/_ttc__sources.yml` exists and passes `dbt parse`
- `pytest tests/test_validate.py` passes with >= 90% coverage

**Bad Examples**:

- System works correctly
- Data is validated
- Tests pass

### Dependency Rules

- Stories within an epic reference by ID: `S001`, `S002`
- Cross-epic dependencies reference full ID: `E001.S003`
- Cross-phase dependencies reference phase: `PH-02.E001`

## Forbidden Patterns

NEVER use:

- "Set up" — specify exact configuration
- "Improve" — specify measurable change
- "Handle" — specify exact behavior
- "Various" / "etc." — enumerate explicitly
- "Appropriate" — specify exact value
- Placeholder text (TODO, TBD, WIP)
- Vague success criteria
- Stories without acceptance criteria
- Epics without exit criteria

## Naming Conventions

### Epic Files

Pattern: `<topic>_<epic_id>.md`

- Lowercase with underscores
- Topic is 1-3 words describing focus
- Epic ID is E followed by 3 digits

Examples:

- `snowflake_infrastructure_E001.md`
- `ingestion_scripts_E002.md`
- `staging_models_E003.md`

### Story IDs

Pattern: `S<NNN>` within epic scope

Sequential within each epic, starting at S001.

## Output Location

All epics MUST be saved to: `docs/<phase_id>/`

Create the phase directory if it does not exist.

Example paths:

- `docs/PH-02/snowflake_infrastructure_E001.md`
- `docs/PH-02/dbt_project_scaffold_E002.md`
- `docs/PH-03/download_scripts_E003.md`

## Validation Checklist

Before outputting an epic, verify:

- [ ] Epic ID is unique across repository
- [ ] All stories have acceptance criteria
- [ ] All acceptance criteria are testable
- [ ] Story points sum is reasonable (15-40 per epic)
- [ ] Dependencies are valid references
- [ ] No forbidden patterns used
- [ ] File path follows naming convention
- [ ] Technical approach references DESIGN-DOC.md where applicable

## Refusal Conditions

REFUSE to generate epics if:

- Target phase is marked `[COMPLETE]`
- Required context files are missing
- User requests manual epic format
- Scope is ambiguous and cannot be clarified
- Request violates CLAUDE.md governance

When refusing, state the specific blocking condition.

## Description

<!-- Concise summary of changes and motivation -->

## Linked Issue

Closes #

## Change Type

- [ ] `feat`: New feature or capability
- [ ] `fix`: Bug fix
- [ ] `refactor`: Code restructuring without behavior change
- [ ] `docs`: Documentation only
- [ ] `test`: Test additions or modifications
- [ ] `chore`: Build, CI, or tooling changes

## Design Impact

### Architecture Layer

- [ ] Staging models
- [ ] Intermediate models
- [ ] Mart models
- [ ] Seeds
- [ ] Python scripts
- [ ] Skills
- [ ] Infrastructure/config

### Schema Changes

- [ ] No schema changes
- [ ] Additive columns only
- [ ] Breaking schema change (requires migration plan)

## Testing Evidence

### dbt

```bash
# Commands executed
dbt build --select <models>
dbt test --select <models>
```

- [ ] All tests pass
- [ ] New models have `unique` and `not_null` tests on primary keys
- [ ] Relationship tests added for foreign keys

### Python (if applicable)

```bash
ruff check --fix .
ruff format .
mypy --strict .
pytest
```

- [ ] All checks pass

## Risk Assessment

- [ ] Low: Isolated change, no downstream impact
- [ ] Medium: Affects multiple models or has performance implications
- [ ] High: Breaking change, schema migration, or data backfill required

### Rollback Plan

<!-- How to revert if issues arise post-merge -->

## Deployment Notes

<!-- Special instructions for deployment: run order, manual steps, feature flags -->

## Governance Checklist

### Code Quality (CLAUDE.md Section 10)

- [ ] Code follows Medallion Architecture layers strictly
- [ ] SQL formatted via `sqlfmt` and passes `SQLFluff` linting
- [ ] Python code has 100% type hints and passes `mypy --strict`
- [ ] Python code passes `ruff check` and `ruff format`
- [ ] All new dbt models documented in `.yml` files with column descriptions
- [ ] `dbt build` passes locally with 0 test failures
- [ ] No AI-attribution markers in code or comments
- [ ] Commit messages follow Conventional Commits format

### Skill Compliance (if applicable)

- [ ] Python code generated via `/python-writing` skill
- [ ] dbt models generated via `/dbt-model` skill
- [ ] Skills created via `/skill-creator` workflow
- [ ] `validate_skill.py` passes for any skill changes

### Documentation

- [ ] `dbt docs generate` succeeds (if models changed)
- [ ] DESIGN-DOC.md updated (if architecture changed)

---
name: python-writing
description: Enforce production-grade Python standards for all code generation. Use when writing, modifying, or reviewing any Python file. Triggers on Python script creation, ingestion code, utility functions, tests, or any .py file operations. Mandatory for all Python output in this repository.
---

# Python Writing Standards

Write Python like a Google Staff Engineer. All code must be production-ready, type-safe, and maintainable.

## Language Requirements

**Version:** Python 3.12+ (mandatory)

**Required Features:**

- Type hints on all functions, methods, and variables
- f-strings for string formatting
- `pathlib.Path` over `os.path`
- Context managers for resource handling
- Dataclasses or Pydantic for data structures
- Structural pattern matching where appropriate

**Forbidden Patterns:**

- `%` or `.format()` string formatting
- `os.path` module usage
- Implicit `Any` types
- Global mutable state
- `from module import *`
- Bare `except:` clauses

## Type System

**Strict Typing Rules:**

```python
from __future__ import annotations

from typing import Final, TypeAlias
from collections.abc import Sequence, Mapping, Iterator
```

- Import `annotations` from `__future__` in every file
- Use `collections.abc` for abstract types, not `typing`
- Prefer `Sequence` over `list`, `Mapping` over `dict` for parameters
- Use `Final` for constants
- Define `TypeAlias` for complex types
- Never use `Any` without explicit justification

## Code Structure

### Functions

- Maximum 20 lines per function
- Single responsibility
- Pure functions preferred
- Explicit return types
- No side effects unless documented

```python
def calculate_delay_minutes(
    scheduled: datetime,
    actual: datetime,
) -> int:
    """Return delay in minutes between scheduled and actual times."""
    delta = actual - scheduled
    return int(delta.total_seconds() // 60)
```

### Classes

- Prefer `@dataclass` for data containers
- Use `Pydantic.BaseModel` for validated external data
- Explicit `__slots__` for performance-critical classes
- No inheritance deeper than 2 levels

```python
@dataclass(frozen=True, slots=True)
class DelayRecord:
    """Single transit delay incident."""

    station_id: str
    delay_minutes: int
    timestamp: datetime
```

## Documentation

### Docstrings

- Required on all public functions and classes
- Google style format
- First line: imperative verb, single sentence
- No redundant type information (already in signature)

```python
def load_station_mapping(path: Path) -> dict[str, str]:
    """Load station name mapping from CSV file.

    Args:
        path: Path to the mapping CSV file.

    Returns:
        Dictionary mapping raw station names to canonical names.

    Raises:
        FileNotFoundError: If the mapping file does not exist.
        ValidationError: If the CSV format is invalid.
    """
```

### Comments

Write comments like a senior engineer:

- Explain **why**, never **what**
- Concise, professional tone
- No obvious comments
- No AI-sounding language
- Reference tickets/docs for complex logic

```python
# Station names changed format in 2023 data release (see DATA-47)
normalized = raw_name.upper().replace("STN", "STATION")
```

**Forbidden Comment Patterns:**

**Forbidden Comment Patterns:**

- `# This function does X` (obvious from name)
- `# Loop through items` (obvious from code)
- `# Initialize variable` (obvious)
- `# TODO: implement later` (no placeholders)

## Error Handling

- Fail fast on invalid input
- Custom exceptions for domain errors
- Never silently swallow exceptions
- Log before re-raising

```python
class SchemaValidationError(Exception):
    """Raised when input data fails schema validation."""


def validate_schema(df: pd.DataFrame, expected: list[str]) -> None:
    """Validate DataFrame columns match expected schema."""
    missing = set(expected) - set(df.columns)
    if missing:
        raise SchemaValidationError(f"Missing columns: {missing}")
```

## Testing

### Requirements

- pytest framework
- 100% coverage on public interfaces
- Edge cases mandatory
- Deterministic (no random, no time-dependent)
- Isolated (no external dependencies)

### Structure

```python
class TestDelayCalculation:
    """Tests for delay calculation logic."""

    def test_positive_delay_returns_minutes(self) -> None:
        scheduled = datetime(2024, 1, 1, 10, 0)
        actual = datetime(2024, 1, 1, 10, 15)

        result = calculate_delay_minutes(scheduled, actual)

        assert result == 15

    def test_zero_delay_when_on_time(self) -> None:
        timestamp = datetime(2024, 1, 1, 10, 0)

        result = calculate_delay_minutes(timestamp, timestamp)

        assert result == 0
```

## Imports

### Order (enforced by Ruff)

1. `__future__` imports
2. Standard library
3. Third-party packages
4. Local modules

### Style

- Absolute imports only
- One import per line for `from` imports
- Group related imports

```python
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
from pydantic import BaseModel

from src.validation import SchemaValidator
from src.models import DelayRecord
```

## Performance

- Document Big-O complexity for non-trivial algorithms
- Prefer generators for large sequences
- Use `itertools` for iteration patterns
- Vectorize with pandas/numpy for data operations
- No nested loops on large datasets without justification

## Security

- Never commit secrets
- Validate all external input
- Use `subprocess.run` with `shell=False`
- No `eval()` or `exec()`
- Sanitize file paths

## Output Requirements

When generating Python:

1. Output complete, runnable files
2. Include all imports
3. Include type hints
4. Include docstrings
5. Include tests (separate file or inline)
6. No TODO/TBD/FIXME placeholders
7. No incomplete implementations

Refuse requests that lack sufficient specification.

## Validation

All Python code must pass:

```bash
ruff check --fix .
ruff format .
mypy --strict .
pytest
```

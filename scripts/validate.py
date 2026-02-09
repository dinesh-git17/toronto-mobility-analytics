"""Schema validation engine with fail-fast behavior.

Validates CSV files against schema contracts defined in contracts.py.
On the first deviation from the expected schema, raises
SchemaValidationError and aborts. No partial processing occurs.

Two-phase validation per DESIGN-DOC.md Section 4.3:
  Phase 1 — Structural: verifies all required columns exist (set-based,
            case-insensitive). Extra columns are logged as warnings.
  Phase 2 — Type: samples the first 1,000 data rows and validates that
            column values conform to the declared dtype.
"""

from __future__ import annotations

import argparse
import csv
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from scripts.contracts import CONTRACTS, SchemaContract

logger = logging.getLogger(__name__)

_TYPE_SAMPLE_ROWS: int = 1_000

# Regex patterns for type validation.
# DATE accepts YYYY-MM-DD and YYYY-MM-DD HH:MM:SS (openpyxl datetime str output).
# INTEGER accepts optional .0 suffix (openpyxl renders int cells as float strings).
_DATE_PATTERN: re.Pattern[str] = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]00:00:00)?$")
_TIME_PATTERN: re.Pattern[str] = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?$")
_INTEGER_PATTERN: re.Pattern[str] = re.compile(r"^-?\d+(\.0)?$")
_DECIMAL_PATTERN: re.Pattern[str] = re.compile(r"^-?\d+\.?\d*$")
_TIMESTAMP_PATTERN: re.Pattern[str] = re.compile(
    r"^\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}$"
    r"|^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?$"
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class SchemaValidationError(Exception):
    """Raised when a CSV file deviates from its schema contract.

    Attributes:
        file_path: Path to the non-conforming file.
        expected_columns: Column names defined by the contract.
        actual_columns: Column names found in the CSV header.
        mismatches: Human-readable descriptions of each deviation.
    """

    def __init__(
        self,
        file_path: Path,
        expected_columns: list[str],
        actual_columns: list[str],
        mismatches: list[str],
    ) -> None:
        self.file_path = file_path
        self.expected_columns = expected_columns
        self.actual_columns = actual_columns
        self.mismatches = mismatches
        detail = "; ".join(mismatches)
        super().__init__(f"Schema validation failed for '{file_path}': {detail}")


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Outcome of validating a single CSV file against a schema contract.

    Attributes:
        file_path: Path to the validated file.
        dataset_name: Contract dataset name used for validation.
        is_valid: Whether the file passed all validation checks.
        row_count: Total data rows in the file (excluding header).
        column_count: Number of columns in the CSV header.
        errors: List of validation error descriptions (empty if valid).
    """

    file_path: Path
    dataset_name: str
    is_valid: bool
    row_count: int
    column_count: int
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Validation engine
# ---------------------------------------------------------------------------


def validate_file(
    csv_path: Path,
    contract: SchemaContract,
) -> ValidationResult:
    """Validate a CSV file against a schema contract.

    Phase 1 checks column presence (case-insensitive set comparison).
    Phase 2 samples first 1,000 rows for type conformance.
    Raises SchemaValidationError on the first structural failure.

    Args:
        csv_path: Path to the CSV file to validate.
        contract: Schema contract to validate against.

    Returns:
        ValidationResult if the file passes all checks.

    Raises:
        SchemaValidationError: On any structural or type deviation.
    """
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise SchemaValidationError(
                file_path=csv_path,
                expected_columns=list(contract.column_names),
                actual_columns=[],
                mismatches=["File has no header row"],
            )

        actual_columns = list(reader.fieldnames)

        # Phase 1: structural validation
        _validate_structure(csv_path, contract, actual_columns)

        # Build case-insensitive column name mapping for type checks
        actual_lower_map: dict[str, str] = {col.lower(): col for col in actual_columns}

        # Phase 2: type validation on sampled rows
        rows_checked = 0
        total_rows = 0
        type_errors: list[str] = []

        for row in reader:
            total_rows += 1
            if rows_checked < _TYPE_SAMPLE_ROWS:
                row_errors = _validate_row_types(
                    row, contract, actual_lower_map, total_rows
                )
                type_errors.extend(row_errors)
                rows_checked += 1

                if type_errors:
                    raise SchemaValidationError(
                        file_path=csv_path,
                        expected_columns=list(contract.column_names),
                        actual_columns=actual_columns,
                        mismatches=type_errors,
                    )

        # Row count sanity check
        if total_rows < contract.min_row_count:
            logger.warning(
                "%s: only %d rows (expected >= %d)",
                csv_path.name,
                total_rows,
                contract.min_row_count,
            )

    logger.info(
        "VALID %s: %d rows, %d columns",
        csv_path.name,
        total_rows,
        len(actual_columns),
    )

    return ValidationResult(
        file_path=csv_path,
        dataset_name=contract.dataset_name,
        is_valid=True,
        row_count=total_rows,
        column_count=len(actual_columns),
    )


def _validate_structure(
    csv_path: Path,
    contract: SchemaContract,
    actual_columns: list[str],
) -> None:
    """Check that all required contract columns exist in the CSV header."""
    actual_lower = {col.lower() for col in actual_columns}
    expected_lower = {col.lower() for col in contract.required_columns}

    missing = expected_lower - actual_lower
    if missing:
        # Map back to original contract names for clear error messages
        missing_original = [
            c.name for c in contract.columns if c.name.lower() in missing
        ]
        raise SchemaValidationError(
            file_path=csv_path,
            expected_columns=list(contract.column_names),
            actual_columns=actual_columns,
            mismatches=[f"Missing required columns: {missing_original}"],
        )

    extra = actual_lower - expected_lower
    if extra:
        extra_original = [col for col in actual_columns if col.lower() in extra]
        logger.warning(
            "%s: extra columns not in contract (non-blocking): %s",
            csv_path.name,
            extra_original,
        )

    # Case mismatch warning
    for col_contract in contract.columns:
        for actual_col in actual_columns:
            if (
                actual_col.lower() == col_contract.name.lower()
                and actual_col != col_contract.name
            ):
                logger.warning(
                    "%s: column case mismatch: expected '%s', found '%s'",
                    csv_path.name,
                    col_contract.name,
                    actual_col,
                )


def _validate_row_types(
    row: dict[str, str | None],
    contract: SchemaContract,
    actual_lower_map: dict[str, str],
    row_number: int,
) -> list[str]:
    """Validate column values in a single row against contract dtypes."""
    errors: list[str] = []

    for col_def in contract.columns:
        actual_key = actual_lower_map.get(col_def.name.lower())
        if actual_key is None:
            continue

        value = row.get(actual_key)
        if value is None or value.strip() == "" or value.strip().upper() == "NULL":
            if not col_def.nullable:
                errors.append(
                    f"Row {row_number}: column '{col_def.name}' "
                    f"is empty but not nullable"
                )
            continue

        value = value.strip()
        if not _check_type(value, col_def.expected_dtype):
            errors.append(
                f"Row {row_number}: column '{col_def.name}' "
                f"value '{value[:50]}' does not match "
                f"expected type {col_def.expected_dtype}"
            )

    return errors


def _check_type(value: str, expected_dtype: str) -> bool:
    """Return True if value conforms to the expected logical dtype."""
    match expected_dtype:
        case "STRING":
            return True
        case "DATE":
            return bool(_DATE_PATTERN.match(value))
        case "TIME":
            return bool(_TIME_PATTERN.match(value))
        case "INTEGER":
            return bool(_INTEGER_PATTERN.match(value))
        case "DECIMAL":
            return bool(_DECIMAL_PATTERN.match(value))
        case "TIMESTAMP":
            return bool(_TIMESTAMP_PATTERN.match(value))
        case _:
            logger.warning("Unknown dtype '%s', skipping check", expected_dtype)
            return True


def validate_dataset(
    dataset_dir: Path,
    contract: SchemaContract,
) -> list[ValidationResult]:
    """Validate all CSV files in a directory tree against a contract.

    Fails fast on the first invalid file by propagating
    SchemaValidationError from validate_file.

    Args:
        dataset_dir: Root directory containing CSV files.
        contract: Schema contract to validate against.

    Returns:
        List of ValidationResult for all valid files.

    Raises:
        SchemaValidationError: On first file that fails validation.
    """
    results: list[ValidationResult] = []
    csv_files = sorted(dataset_dir.rglob("*.csv"))

    if not csv_files:
        logger.warning("No CSV files found in %s", dataset_dir)
        return results

    for csv_path in csv_files:
        result = validate_file(csv_path, contract)
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# CLI entry point (S006)
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser for the validation pipeline."""
    parser = argparse.ArgumentParser(
        description="Validate source CSV files against schema contracts.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="validate_all",
        help="Process all datasets.",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Validate a single dataset by name.",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path("data/raw"),
        help="Root directory containing raw source files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/validated"),
        help="Root directory for validated CSV output.",
    )
    return parser


def _dataset_source_dir(
    base_dir: Path,
    dataset_name: str,
) -> str:
    """Map dataset name to its subdirectory under data/raw/."""
    mapping: dict[str, str] = {
        "ttc_subway_delays": "ttc_subway",
        "ttc_bus_delays": "ttc_bus",
        "ttc_streetcar_delays": "ttc_streetcar",
        "bike_share_ridership": "bike_share",
        "weather_daily": "weather",
    }
    subdir = mapping.get(dataset_name)
    if subdir is None:
        raise ValueError(f"Unknown dataset: {dataset_name}")
    return subdir


# Contracts target the 2020+ column naming convention.
# 2019 TTC Bus and Streetcar files use incompatible column names.
_MIN_YEAR: int = 2020

# 2025+ TTC Bus and Streetcar files switched to the unified subway-style
# schema (Line, Station, Code, Bound). Remap to historical contract names.
_UNIFIED_YEAR: int = 2025

_BUS_COLUMN_RENAMES: dict[str, str] = {
    "Line": "Route",
    "Station": "Location",
    "Code": "Incident",
    "Bound": "Direction",
}

_STREETCAR_COLUMN_RENAMES: dict[str, str] = {
    "Station": "Location",
    "Code": "Incident",
}


def _extract_year(path: Path) -> int | None:
    """Extract the four-digit year from a file path's directory components."""
    for part in path.parts:
        if part.isdigit() and len(part) == 4:
            return int(part)
    return None


def _is_year_included(path: Path) -> bool:
    """Check if a file path contains a year directory >= _MIN_YEAR.

    Returns True if no year directory is found (non-year-partitioned data).
    """
    year = _extract_year(path)
    if year is None:
        return True
    return year >= _MIN_YEAR


def _run_pipeline(
    dataset_name: str,
    contract: SchemaContract,
    source_dir: Path,
    output_dir: Path,
) -> list[ValidationResult]:
    """Execute transform + validate pipeline for a single dataset.

    Steps:
    1. Convert XLSX files to CSV (TTC datasets).
    2. Extract ZIP archives (Bike Share).
    3. Normalize encoding to UTF-8.
    4. Validate all CSVs against the contract.
    5. Copy validated files to output directory.
    """
    import shutil

    from scripts.transform import (
        TransformError,
        convert_xlsx_to_csv,
        normalize_encoding,
        rename_csv_columns,
    )

    subdir = _dataset_source_dir(source_dir, dataset_name)
    raw_dir = source_dir / subdir
    validated_dir = output_dir / subdir

    if not raw_dir.exists():
        logger.warning("Source directory does not exist: %s", raw_dir)
        return []

    # Step 1: XLSX-to-CSV conversion for TTC datasets.
    # Some Open Data files have .xlsx extension but are actually CSV.
    # Handles this by falling back to a direct copy on TransformError.
    if dataset_name.startswith("ttc_"):
        logger.info("Converting XLSX files in %s", raw_dir)
        for xlsx_path in sorted(raw_dir.rglob("*.xlsx")):
            if not _is_year_included(xlsx_path):
                logger.info("Skipping %s (before %d)", xlsx_path.name, _MIN_YEAR)
                continue
            relative = xlsx_path.relative_to(raw_dir)
            csv_name = relative.with_suffix(".csv")
            csv_path = validated_dir / csv_name
            try:
                convert_xlsx_to_csv(xlsx_path, csv_path)
            except TransformError:
                logger.warning(
                    "%s is not valid XLSX; copying as CSV",
                    xlsx_path.name,
                )
                csv_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(xlsx_path, csv_path)

    # Step 2: ZIP extraction for Bike Share
    if dataset_name == "bike_share_ridership":
        logger.info("Extracting ZIP archives in %s", raw_dir)
        for zip_path in sorted(raw_dir.rglob("*.zip")):
            if not _is_year_included(zip_path):
                logger.info("Skipping %s (before %d)", zip_path.name, _MIN_YEAR)
                continue
            relative_dir = zip_path.parent.relative_to(raw_dir)
            target_dir = validated_dir / relative_dir
            from scripts.transform import extract_zip

            extract_zip(zip_path, target_dir)

    # Step 2.5: Rename columns in 2025+ bus/streetcar files to match contracts.
    # Toronto Open Data switched to a unified subway-style schema in 2025.
    if dataset_name in {"ttc_bus_delays", "ttc_streetcar_delays"}:
        rename_map = (
            _BUS_COLUMN_RENAMES
            if dataset_name == "ttc_bus_delays"
            else _STREETCAR_COLUMN_RENAMES
        )
        for csv_file in sorted(validated_dir.rglob("*.csv")):
            year = _extract_year(csv_file)
            if year is not None and year >= _UNIFIED_YEAR:
                rename_csv_columns(csv_file, rename_map)

    # Step 3: Copy weather CSVs to validated dir
    if dataset_name == "weather_daily":
        validated_dir.mkdir(parents=True, exist_ok=True)
        for csv_file in sorted(raw_dir.rglob("*.csv")):
            relative = csv_file.relative_to(raw_dir)
            dest = validated_dir / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(csv_file, dest)

    # Step 4: Normalize encoding on all CSVs in validated dir
    for csv_file in sorted(validated_dir.rglob("*.csv")):
        normalize_encoding(csv_file)

    # Step 5: Validate all CSVs against contract
    results = validate_dataset(validated_dir, contract)
    return results


def main() -> None:
    """CLI entry point for the validation pipeline."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    parser = _build_arg_parser()
    args: argparse.Namespace = parser.parse_args()

    if not args.validate_all and args.dataset is None:
        parser.error("Specify --all or --dataset <name>")

    datasets_to_process: list[str]
    if args.validate_all:
        datasets_to_process = list(CONTRACTS.keys())
    else:
        if args.dataset not in CONTRACTS:
            valid = ", ".join(CONTRACTS.keys())
            parser.error(f"Unknown dataset '{args.dataset}'. Valid: {valid}")
        datasets_to_process = [args.dataset]

    total_files = 0
    total_rows = 0
    total_passed = 0

    for dataset_name in datasets_to_process:
        contract = CONTRACTS[dataset_name]
        logger.info("Processing dataset: %s", dataset_name)

        try:
            results = _run_pipeline(
                dataset_name,
                contract,
                args.source_dir,
                args.output_dir,
            )
        except SchemaValidationError as exc:
            logger.error("VALIDATION FAILED: %s", exc)
            for mismatch in exc.mismatches:
                logger.error("  - %s", mismatch)
            sys.exit(1)

        for r in results:
            total_files += 1
            total_rows += r.row_count
            if r.is_valid:
                total_passed += 1

    failed = total_files - total_passed
    print(
        f"\nValidation Summary:\n"
        f"  Total files processed: {total_files}\n"
        f"  Files passed: {total_passed}\n"
        f"  Files failed: {failed}\n"
        f"  Total rows: {total_rows:,}"
    )

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

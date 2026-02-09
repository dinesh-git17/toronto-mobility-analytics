"""Tests for schema validation engine (scripts/validate.py).

Covers structural validation (missing columns, extra columns, case
sensitivity), type validation (sampling, regex matching), and
fail-fast behavior per DESIGN-DOC.md Section 4.3.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.contracts import TTC_SUBWAY_CONTRACT
from scripts.validate import SchemaValidationError, validate_dataset, validate_file


class TestValidateFileStructural:
    """Structural validation: column presence checks."""

    def test_valid_csv_passes(self, valid_subway_csv: Path) -> None:
        result = validate_file(valid_subway_csv, TTC_SUBWAY_CONTRACT)

        assert result.is_valid is True
        assert result.row_count == 10
        assert result.column_count == 10  # 9 contract + Vehicle extra
        assert result.dataset_name == "ttc_subway_delays"
        assert result.errors == []

    def test_missing_column_raises_error(
        self, invalid_missing_column_csv: Path
    ) -> None:
        with pytest.raises(SchemaValidationError) as exc_info:
            validate_file(invalid_missing_column_csv, TTC_SUBWAY_CONTRACT)

        err = exc_info.value
        assert err.file_path == invalid_missing_column_csv
        assert "Station" in str(err.mismatches)
        assert "Missing required columns" in err.mismatches[0]

    def test_extra_column_passes_with_warning(self, extra_column_csv: Path) -> None:
        result = validate_file(extra_column_csv, TTC_SUBWAY_CONTRACT)

        assert result.is_valid is True
        assert result.column_count == 11  # 10 + Notes

    def test_case_insensitive_matching(self, case_mismatch_csv: Path) -> None:
        result = validate_file(case_mismatch_csv, TTC_SUBWAY_CONTRACT)

        assert result.is_valid is True

    def test_nullable_empty_values_pass(self, nullable_empty_csv: Path) -> None:
        result = validate_file(nullable_empty_csv, TTC_SUBWAY_CONTRACT)

        assert result.is_valid is True


class TestValidateFileTypes:
    """Type validation: sampled row type checks."""

    def test_type_mismatch_raises_error(self, invalid_type_mismatch_csv: Path) -> None:
        with pytest.raises(SchemaValidationError) as exc_info:
            validate_file(invalid_type_mismatch_csv, TTC_SUBWAY_CONTRACT)

        err = exc_info.value
        assert "Min Delay" in str(err.mismatches)
        assert "INTEGER" in str(err.mismatches)

    def test_empty_file_raises_error(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty.csv"
        empty.write_text("", encoding="utf-8")

        with pytest.raises(SchemaValidationError) as exc_info:
            validate_file(empty, TTC_SUBWAY_CONTRACT)

        assert "no header row" in str(exc_info.value).lower()


class TestValidateDataset:
    """Dataset-level validation across directory trees."""

    def test_validates_all_csvs_in_directory(
        self, valid_subway_csv: Path, tmp_path: Path
    ) -> None:
        # Create a second valid file
        import shutil

        second = tmp_path / "second.csv"
        shutil.copy2(valid_subway_csv, second)

        results = validate_dataset(tmp_path, TTC_SUBWAY_CONTRACT)

        assert len(results) == 2
        assert all(r.is_valid for r in results)

    def test_fails_fast_on_invalid_file(self, tmp_path: Path) -> None:
        import csv as csv_mod

        # First file: valid
        valid = tmp_path / "a_valid.csv"
        with valid.open("w", newline="", encoding="utf-8") as f:
            writer = csv_mod.writer(f)
            writer.writerow(
                [
                    "Date",
                    "Time",
                    "Day",
                    "Station",
                    "Code",
                    "Min Delay",
                    "Min Gap",
                    "Bound",
                    "Line",
                    "Vehicle",
                ]
            )
            writer.writerow(
                [
                    "2023-01-01",
                    "08:00",
                    "Sunday",
                    "UNION",
                    "MUPAA",
                    "5",
                    "10",
                    "N",
                    "YU",
                    "5931",
                ]
            )

        # Second file: missing column
        invalid = tmp_path / "b_invalid.csv"
        with invalid.open("w", newline="", encoding="utf-8") as f:
            writer = csv_mod.writer(f)
            writer.writerow(
                ["Date", "Time", "Day", "Code", "Min Delay", "Min Gap", "Bound", "Line"]
            )
            writer.writerow(
                ["2023-01-01", "08:00", "Sunday", "MUPAA", "5", "10", "N", "YU"]
            )

        with pytest.raises(SchemaValidationError):
            validate_dataset(tmp_path, TTC_SUBWAY_CONTRACT)

    def test_empty_directory_returns_empty(self, tmp_path: Path) -> None:
        results = validate_dataset(tmp_path, TTC_SUBWAY_CONTRACT)
        assert results == []


class TestNullStringHandling:
    """Literal 'NULL' string treated as null value."""

    def test_null_string_accepted_for_nullable_column(self, tmp_path: Path) -> None:
        import csv as csv_mod

        csv_path = tmp_path / "null_string.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv_mod.writer(f)
            writer.writerow(
                [
                    "Date",
                    "Time",
                    "Day",
                    "Station",
                    "Code",
                    "Min Delay",
                    "Min Gap",
                    "Bound",
                    "Line",
                ]
            )
            writer.writerow(
                [
                    "2023-01-01",
                    "08:00",
                    "Sunday",
                    "NULL",
                    "NULL",
                    "5",
                    "10",
                    "NULL",
                    "NULL",
                ]
            )

        result = validate_file(csv_path, TTC_SUBWAY_CONTRACT)
        assert result.is_valid is True

    def test_null_string_rejected_for_non_nullable_column(self, tmp_path: Path) -> None:
        import csv as csv_mod

        from scripts.contracts import ColumnContract, SchemaContract

        strict_contract = SchemaContract(
            dataset_name="test",
            columns=(
                ColumnContract(name="Id", expected_dtype="STRING", nullable=False),
            ),
            min_row_count=0,
        )
        csv_path = tmp_path / "null_strict.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv_mod.writer(f)
            writer.writerow(["Id"])
            writer.writerow(["NULL"])

        with pytest.raises(SchemaValidationError):
            validate_file(csv_path, strict_contract)


class TestSchemaValidationError:
    """Exception attribute verification."""

    def test_error_attributes(self) -> None:
        err = SchemaValidationError(
            file_path=Path("/test/file.csv"),
            expected_columns=["A", "B"],
            actual_columns=["A", "C"],
            mismatches=["Missing column: B"],
        )

        assert err.file_path == Path("/test/file.csv")
        assert err.expected_columns == ["A", "B"]
        assert err.actual_columns == ["A", "C"]
        assert err.mismatches == ["Missing column: B"]
        assert "file.csv" in str(err)

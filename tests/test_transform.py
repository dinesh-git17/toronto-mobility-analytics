"""Tests for data transformation utilities (scripts/transform.py).

Covers XLSX-to-CSV conversion, encoding detection and normalization,
and ZIP archive extraction with idempotency checks.
"""

from __future__ import annotations

import csv
import zipfile
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from scripts.transform import (
    TransformError,
    batch_extract_zips,
    convert_xlsx_to_csv,
    extract_zip,
    normalize_encoding,
    rename_csv_columns,
)


class TestConvertXlsxToCsv:
    """XLSX-to-CSV conversion tests."""

    def test_produces_correct_row_and_column_count(
        self, valid_xlsx: Path, tmp_path: Path
    ) -> None:
        csv_out = tmp_path / "output.csv"
        result = convert_xlsx_to_csv(valid_xlsx, csv_out)

        assert result.row_count == 10
        assert result.column_count == 10
        assert result.output_path == csv_out
        assert result.elapsed_seconds >= 0
        assert csv_out.exists()

    def test_csv_content_matches_source(self, valid_xlsx: Path, tmp_path: Path) -> None:
        csv_out = tmp_path / "output.csv"
        convert_xlsx_to_csv(valid_xlsx, csv_out)

        with csv_out.open("r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            rows = list(reader)

        assert header[0] == "Date"
        assert header[3] == "Station"
        assert len(rows) == 10
        assert rows[0][3] == "BLOOR STATION"

    def test_creates_parent_directories(self, valid_xlsx: Path, tmp_path: Path) -> None:
        csv_out = tmp_path / "nested" / "deep" / "output.csv"
        result = convert_xlsx_to_csv(valid_xlsx, csv_out)

        assert csv_out.exists()
        assert result.output_path == csv_out

    def test_reads_named_worksheet(
        self, multi_sheet_xlsx: Path, tmp_path: Path
    ) -> None:
        csv_out = tmp_path / "delays.csv"
        result = convert_xlsx_to_csv(multi_sheet_xlsx, csv_out, sheet_name="delays")

        assert result.row_count == 10

    def test_missing_worksheet_raises_error(
        self, multi_sheet_xlsx: Path, tmp_path: Path
    ) -> None:
        csv_out = tmp_path / "output.csv"

        with pytest.raises(TransformError) as exc_info:
            convert_xlsx_to_csv(multi_sheet_xlsx, csv_out, sheet_name="nonexistent")

        assert "nonexistent" in str(exc_info.value)
        assert "delays" in str(exc_info.value)
        assert "metadata" in str(exc_info.value)

    def test_none_cells_become_empty_strings(self, tmp_path: Path) -> None:
        import openpyxl

        xlsx_path = tmp_path / "with_nulls.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        assert ws is not None
        ws.append(["A", "B", "C"])
        ws.append([1, None, 3])
        wb.save(xlsx_path)
        wb.close()

        csv_out = tmp_path / "nulls.csv"
        convert_xlsx_to_csv(xlsx_path, csv_out)

        with csv_out.open("r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            row = next(reader)

        assert row[1] == ""


class TestNormalizeEncoding:
    """Encoding detection and normalization tests."""

    def test_detects_utf8_correctly(self, valid_subway_csv: Path) -> None:
        result = normalize_encoding(valid_subway_csv)

        assert result.detected_encoding.lower().replace("-", "") in {"utf8", "ascii"}
        assert result.confidence >= 0.7
        assert result.had_bom is False

    def test_transcodes_windows_1252(
        self, windows_1252_csv: Path, tmp_path: Path
    ) -> None:
        output = tmp_path / "transcoded.csv"
        result = normalize_encoding(windows_1252_csv, output)

        assert output.exists()
        content = output.read_text(encoding="utf-8")
        assert "Café" in content
        assert "Résumé" in content
        assert result.had_bom is False

    def test_strips_utf8_bom(self, utf8_bom_csv: Path) -> None:
        result = normalize_encoding(utf8_bom_csv)

        assert result.had_bom is True
        content = utf8_bom_csv.read_bytes()
        assert not content.startswith(b"\xef\xbb\xbf")

    def test_output_path_creates_directories(
        self, valid_subway_csv: Path, tmp_path: Path
    ) -> None:
        output = tmp_path / "nested" / "dir" / "out.csv"
        result = normalize_encoding(valid_subway_csv, output)

        assert output.exists()
        assert result.output_path == output

    def test_in_place_normalization(self, windows_1252_csv: Path) -> None:
        result = normalize_encoding(windows_1252_csv)

        assert result.output_path == windows_1252_csv
        content = windows_1252_csv.read_text(encoding="utf-8")
        assert "Café" in content


class TestExtractZip:
    """ZIP archive extraction tests."""

    def test_extracts_csv_files(self, valid_zip: Path, tmp_path: Path) -> None:
        output_dir = tmp_path / "extracted"
        results = extract_zip(valid_zip, output_dir)

        assert len(results) == 2
        assert all(r.extracted_path.exists() for r in results)
        assert all(not r.skipped for r in results)
        assert all(r.byte_size > 0 for r in results)

    def test_strips_subdirectory_prefix(self, valid_zip: Path, tmp_path: Path) -> None:
        output_dir = tmp_path / "extracted"
        results = extract_zip(valid_zip, output_dir)

        filenames = [r.extracted_path.name for r in results]
        assert "Bike share ridership 2023-01.csv" in filenames
        assert "Bike share ridership 2023-02.csv" in filenames
        # No nested directories
        assert all(r.extracted_path.parent == output_dir for r in results)

    def test_idempotent_extraction(self, valid_zip: Path, tmp_path: Path) -> None:
        output_dir = tmp_path / "extracted"

        # First extraction
        results1 = extract_zip(valid_zip, output_dir)
        assert all(not r.skipped for r in results1)

        # Second extraction: should skip all
        results2 = extract_zip(valid_zip, output_dir)
        assert all(r.skipped for r in results2)

    def test_skips_macosx_metadata(self, zip_with_macosx: Path, tmp_path: Path) -> None:
        output_dir = tmp_path / "extracted"
        results = extract_zip(zip_with_macosx, output_dir)

        assert len(results) == 1
        assert results[0].extracted_path.name == "file.csv"

    def test_corrupt_zip_raises_error(self, corrupt_zip: Path, tmp_path: Path) -> None:
        output_dir = tmp_path / "extracted"

        with pytest.raises((TransformError, zipfile.BadZipFile)):
            extract_zip(corrupt_zip, output_dir)


class TestBatchExtractZips:
    """Batch ZIP extraction tests."""

    def test_processes_multiple_zips(self, tmp_path: Path) -> None:
        source = tmp_path / "source" / "bike_share"
        # Year 2023
        year_dir = source / "2023"
        year_dir.mkdir(parents=True)
        with zipfile.ZipFile(year_dir / "data2023.zip", "w") as zf:
            zf.writestr("inner/file1.csv", "a,b\n1,2\n")

        # Year 2024
        year_dir2 = source / "2024"
        year_dir2.mkdir(parents=True)
        with zipfile.ZipFile(year_dir2 / "data2024.zip", "w") as zf:
            zf.writestr("inner/file2.csv", "a,b\n3,4\n")

        output = tmp_path / "output" / "bike_share"
        results = batch_extract_zips(source, output)

        assert len(results) == 2
        # Verify directory structure preserved
        assert (output / "2023" / "file1.csv").exists()
        assert (output / "2024" / "file2.csv").exists()


class TestRenameCsvColumns:
    """Column renaming tests for 2025 unified schema handling."""

    def test_renames_matching_columns(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "data.csv"
        csv_path.write_text(
            "_id,Date,Line,Time,Day,Station\n1,2025-01-01,505,08:00,Monday,King St\n",
            encoding="utf-8",
        )

        result = rename_csv_columns(
            csv_path,
            {"Line": "Route", "Station": "Location"},
        )

        assert result is True
        header = csv_path.read_text(encoding="utf-8").split("\n")[0]
        assert "Route" in header
        assert "Location" in header
        assert "Line" not in header
        assert "Station" not in header

    def test_returns_false_when_no_columns_match(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("A,B,C\n1,2,3\n", encoding="utf-8")

        result = rename_csv_columns(csv_path, {"X": "Y"})

        assert result is False

    def test_preserves_data_rows(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "data.csv"
        csv_path.write_text(
            "Code,Value\nABC,123\nDEF,456\n",
            encoding="utf-8",
        )

        rename_csv_columns(csv_path, {"Code": "Incident"})

        lines = csv_path.read_text(encoding="utf-8").split("\n")
        assert lines[0] == "Incident,Value"
        assert lines[1] == "ABC,123"
        assert lines[2] == "DEF,456"

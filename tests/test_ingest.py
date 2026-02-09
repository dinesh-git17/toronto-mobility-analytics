"""Tests for the pipeline orchestrator (scripts/ingest.py).

All Snowflake interactions are mocked. No real connections are made.
Tests cover pipeline flow, error handling, and CLI behavior.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.download import DownloadError
from scripts.ingest import (
    DatasetResult,
    PipelineResult,
    main,
    run_pipeline,
)
from scripts.load import DatasetStatus, LoadError, MergeResult, PipelineStage
from scripts.validate import SchemaValidationError

# ---- Fixtures ----------------------------------------------------------------


@pytest.fixture()
def validated_csvs(tmp_path: Path) -> Path:
    """Create a temporary validated CSV directory structure."""
    for subdir in ("ttc_subway", "ttc_bus", "ttc_streetcar", "bike_share", "weather"):
        d = tmp_path / subdir
        d.mkdir(parents=True)
        csv_path = d / "test_2023.csv"
        csv_path.write_text("col1,col2\nval1,val2\n")
    return tmp_path


@pytest.fixture()
def mock_merge_result():
    """Return a successful MergeResult."""
    return MergeResult(
        target_table="TORONTO_MOBILITY.RAW.TTC_SUBWAY_DELAYS",
        rows_inserted=100,
        rows_updated=0,
        elapsed_seconds=1.5,
    )


# ---- Pipeline flow tests (S005) ---------------------------------------------


class TestRunPipeline:
    """Tests for the run_pipeline orchestration function."""

    @patch("scripts.ingest._run_load")
    @patch("scripts.ingest._run_transform_and_validate")
    @patch("scripts.ingest._run_download")
    @patch("scripts.ingest._get_validated_csvs")
    def test_successful_run_returns_success(
        self,
        mock_csvs,
        mock_download,
        mock_validate,
        mock_load,
        mock_merge_result,
    ):
        """Successful pipeline returns PipelineResult with success=True."""
        mock_csvs.return_value = [Path("test.csv")]
        mock_load.return_value = mock_merge_result

        result = run_pipeline(datasets=["ttc_subway_delays"])

        assert isinstance(result, PipelineResult)
        assert result.success is True
        assert len(result.datasets_processed) == 1
        assert result.datasets_processed[0].status == DatasetStatus.SUCCESS
        mock_download.assert_called_once()
        mock_validate.assert_called_once()
        mock_load.assert_called_once()

    @patch("scripts.ingest._run_load")
    @patch("scripts.ingest._run_transform_and_validate")
    @patch("scripts.ingest._run_download")
    @patch("scripts.ingest._get_validated_csvs")
    def test_validation_failure_does_not_block_other_datasets(
        self,
        mock_csvs,
        mock_download,
        mock_validate,
        mock_load,
        mock_merge_result,
    ):
        """Validation failure for one dataset allows others to continue."""
        mock_csvs.return_value = [Path("test.csv")]

        call_count = 0

        def validate_side_effect(name: str) -> None:
            nonlocal call_count
            call_count += 1
            if name == "ttc_subway_delays":
                raise SchemaValidationError(
                    file_path=Path("bad.csv"),
                    expected_columns=["Date"],
                    actual_columns=["Wrong"],
                    mismatches=["Missing column: Date"],
                )

        mock_validate.side_effect = lambda n: validate_side_effect(n)
        mock_load.return_value = mock_merge_result

        result = run_pipeline(datasets=["ttc_subway_delays", "ttc_bus_delays"])

        assert result.success is False
        statuses = {r.dataset_name: r.status for r in result.datasets_processed}
        assert statuses["ttc_subway_delays"] == DatasetStatus.FAILED
        assert statuses["ttc_bus_delays"] == DatasetStatus.SUCCESS

    @patch("scripts.ingest._run_load")
    @patch("scripts.ingest._run_transform_and_validate")
    @patch("scripts.ingest._run_download")
    @patch("scripts.ingest._get_validated_csvs")
    def test_load_failure_triggers_rollback(
        self,
        mock_csvs,
        mock_download,
        mock_validate,
        mock_load,
    ):
        """Load failure marks dataset as FAILED with LOAD stage."""
        mock_csvs.return_value = [Path("test.csv")]
        mock_load.side_effect = LoadError("COPY INTO failed", table="TEST_TABLE")

        result = run_pipeline(datasets=["ttc_subway_delays"])

        assert result.success is False
        ds = result.datasets_processed[0]
        assert ds.status == DatasetStatus.FAILED
        assert ds.stage == PipelineStage.LOAD
        assert "COPY INTO" in ds.error_message

    @patch("scripts.ingest._run_load")
    @patch("scripts.ingest._run_transform_and_validate")
    @patch("scripts.ingest._run_download")
    @patch("scripts.ingest._get_validated_csvs")
    def test_skip_download_flag(
        self,
        mock_csvs,
        mock_download,
        mock_validate,
        mock_load,
        mock_merge_result,
    ):
        """--skip-download flag prevents download stage execution."""
        mock_csvs.return_value = [Path("test.csv")]
        mock_load.return_value = mock_merge_result

        result = run_pipeline(
            datasets=["ttc_subway_delays"],
            skip_download=True,
        )

        assert result.success is True
        mock_download.assert_not_called()
        mock_validate.assert_called_once()
        mock_load.assert_called_once()

    @patch("scripts.ingest._run_load")
    @patch("scripts.ingest._run_transform_and_validate")
    @patch("scripts.ingest._run_download")
    @patch("scripts.ingest._get_validated_csvs")
    def test_download_failure_marks_failed(
        self,
        mock_csvs,
        mock_download,
        mock_validate,
        mock_load,
    ):
        """Download failure marks dataset FAILED at DOWNLOAD stage."""
        mock_download.side_effect = DownloadError(
            url="https://example.com", status_code=500, body="Server Error"
        )

        result = run_pipeline(datasets=["ttc_subway_delays"])

        assert result.success is False
        ds = result.datasets_processed[0]
        assert ds.status == DatasetStatus.FAILED
        assert ds.stage == PipelineStage.DOWNLOAD


# ---- Transaction control tests -----------------------------------------------


class TestTransactionControl:
    """Tests for per-dataset atomic transaction boundaries."""

    @patch("scripts.ingest._get_validated_csvs")
    @patch("scripts.ingest.SnowflakeConnectionManager")
    def test_begin_commit_on_success(self, mock_mgr_cls, mock_csvs, tmp_path):
        """Successful load executes BEGIN and COMMIT."""
        csv_path = tmp_path / "test.csv"
        csv_path.write_text("Date\n2023-01-01\n")
        mock_csvs.return_value = [csv_path]

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            ("f.csv", "f.gz", 100, 50, "n", "g", "UPLOADED", "")
        ]
        mock_cursor.fetchone.return_value = (50, 0)

        mock_mgr = MagicMock()
        mock_mgr.__enter__ = MagicMock(return_value=mock_conn)
        mock_mgr.__exit__ = MagicMock(return_value=False)
        mock_mgr_cls.return_value = mock_mgr

        from scripts.ingest import _run_load

        _run_load("ttc_subway_delays", mock_mgr)

        sqls = [c[0][0] for c in mock_cursor.execute.call_args_list if c[0]]
        assert any("BEGIN" in s for s in sqls)
        mock_conn.commit.assert_called_once()

    @patch("scripts.ingest._get_validated_csvs")
    @patch("scripts.ingest.SnowflakeConnectionManager")
    def test_rollback_on_failure(self, mock_mgr_cls, mock_csvs, tmp_path):
        """Failed load executes ROLLBACK."""
        import snowflake.connector.errors

        csv_path = tmp_path / "test.csv"
        csv_path.write_text("Date\n2023-01-01\n")
        mock_csvs.return_value = [csv_path]

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        # PUT succeeds, then MERGE CREATE TEMP fails
        call_idx = 0

        def execute_side_effect(sql: str) -> None:
            nonlocal call_idx
            call_idx += 1
            if "CREATE TEMPORARY" in sql:
                raise snowflake.connector.errors.Error(msg="No permissions")

        mock_cursor.execute.side_effect = execute_side_effect
        mock_cursor.fetchall.return_value = [
            ("f.csv", "f.gz", 100, 50, "n", "g", "UPLOADED", "")
        ]

        mock_mgr = MagicMock()
        mock_mgr.__enter__ = MagicMock(return_value=mock_conn)
        mock_mgr.__exit__ = MagicMock(return_value=False)
        mock_mgr_cls.return_value = mock_mgr

        from scripts.ingest import _run_load

        with pytest.raises(LoadError):
            _run_load("ttc_subway_delays", mock_mgr)

        mock_conn.rollback.assert_called_once()


# ---- CLI tests ---------------------------------------------------------------


class TestCLI:
    """Tests for the command-line interface."""

    @patch("scripts.ingest.run_pipeline")
    def test_cli_all_flag(self, mock_run):
        """--all flag runs pipeline for all datasets."""
        mock_run.return_value = PipelineResult(success=True)

        exit_code = main(["--all"])

        assert exit_code == 0
        mock_run.assert_called_once_with(
            datasets=None,
            skip_download=False,
        )

    @patch("scripts.ingest.run_pipeline")
    def test_cli_single_dataset(self, mock_run):
        """--dataset flag runs pipeline for one dataset."""
        mock_run.return_value = PipelineResult(success=True)

        exit_code = main(["--dataset", "ttc_subway_delays"])

        assert exit_code == 0
        mock_run.assert_called_once_with(
            datasets=["ttc_subway_delays"],
            skip_download=False,
        )

    @patch("scripts.ingest.run_pipeline")
    def test_cli_skip_download(self, mock_run):
        """--skip-download flag is passed through to run_pipeline."""
        mock_run.return_value = PipelineResult(success=True)

        exit_code = main(["--all", "--skip-download"])

        assert exit_code == 0
        mock_run.assert_called_once_with(
            datasets=None,
            skip_download=True,
        )

    @patch("scripts.ingest.run_pipeline")
    def test_cli_exits_1_on_failure(self, mock_run):
        """Exit code 1 when any dataset fails."""
        mock_run.return_value = PipelineResult(
            datasets_processed=[
                DatasetResult(
                    dataset_name="test",
                    stage=PipelineStage.LOAD,
                    rows_loaded=0,
                    elapsed_seconds=1.0,
                    status=DatasetStatus.FAILED,
                    error_message="Load failed",
                ),
            ],
            success=False,
        )

        exit_code = main(["--all"])

        assert exit_code == 1

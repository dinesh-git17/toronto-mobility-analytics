"""Tests for the Snowflake loading module (scripts/load.py).

All Snowflake interactions are mocked via unittest.mock.patch on
snowflake.connector.connect. No real Snowflake connections are made.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.load import (
    CopyResult,
    LoadError,
    MergeResult,
    SnowflakeConnectionManager,
    StageUploadResult,
    StageUploadStatus,
    TableConfig,
    copy_into_table,
    get_table_config,
    load_dataset,
    merge_into_table,
    upload_to_stage,
)

# ---- Fixtures ----------------------------------------------------------------


@pytest.fixture()
def mock_connection():
    """Return a MagicMock that behaves like a SnowflakeConnection."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    # PUT result columns: source, target, src/dest size, compression, status
    cursor.fetchall.return_value = [
        ("file.csv", "file.csv.gz", 1024, 512, "none", "gzip", "UPLOADED", "")
    ]
    cursor.fetchone.return_value = None
    return conn


@pytest.fixture()
def mock_cursor(mock_connection):
    """Return the cursor mock from the mock connection."""
    return mock_connection.cursor()


@pytest.fixture()
def sample_csv(tmp_path: Path) -> Path:
    """Create a small CSV file for upload testing."""
    csv_path = tmp_path / "test_delays.csv"
    csv_path.write_text("Date,Time,Day\n2023-01-01,08:00,Monday\n")
    return csv_path


# ---- Connection manager tests (S002) ----------------------------------------


class TestSnowflakeConnectionManager:
    """Tests for credential resolution and connection lifecycle."""

    @patch("scripts.load.snowflake.connector.connect")
    def test_connect_from_env_vars(self, mock_connect, monkeypatch):
        """Credentials resolved from environment variables."""
        monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "test_account")
        monkeypatch.setenv("SNOWFLAKE_USER", "test_user")
        monkeypatch.setenv("SNOWFLAKE_PASSWORD", "test_pass")

        mock_connect.return_value = MagicMock()
        mgr = SnowflakeConnectionManager()
        conn = mgr.connect()

        mock_connect.assert_called_once()
        call_kwargs = mock_connect.call_args[1]
        assert call_kwargs["account"] == "test_account"
        assert call_kwargs["user"] == "test_user"
        assert call_kwargs["password"] == "test_pass"
        assert call_kwargs["role"] == "LOADER_ROLE"
        assert call_kwargs["warehouse"] == "TRANSFORM_WH"
        assert call_kwargs["database"] == "TORONTO_MOBILITY"
        assert call_kwargs["schema"] == "RAW"
        assert call_kwargs["client_session_keep_alive"] is True
        assert call_kwargs["login_timeout"] == 30
        assert call_kwargs["network_timeout"] == 60
        assert conn is not None

    @patch("scripts.load.snowflake.connector.connect")
    def test_connect_from_toml(self, mock_connect, tmp_path, monkeypatch):
        """Credentials resolved from connections.toml when env vars missing."""
        monkeypatch.delenv("SNOWFLAKE_ACCOUNT", raising=False)
        monkeypatch.delenv("SNOWFLAKE_USER", raising=False)
        monkeypatch.delenv("SNOWFLAKE_PASSWORD", raising=False)

        toml_dir = tmp_path / ".snowflake"
        toml_dir.mkdir()
        toml_path = toml_dir / "connections.toml"
        toml_path.write_text(
            "[loader]\naccount = 'toml_acct'\nuser = 'toml_user'\n"
            "password = 'toml_pass'\n"
        )
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        mock_connect.return_value = MagicMock()

        mgr = SnowflakeConnectionManager()
        mgr.connect()

        call_kwargs = mock_connect.call_args[1]
        assert call_kwargs["account"] == "toml_acct"
        assert call_kwargs["user"] == "toml_user"
        assert call_kwargs["password"] == "toml_pass"

    def test_connect_raises_when_no_credentials(self, monkeypatch):
        """LoadError raised when no credential source is available."""
        monkeypatch.delenv("SNOWFLAKE_ACCOUNT", raising=False)
        monkeypatch.delenv("SNOWFLAKE_USER", raising=False)
        monkeypatch.delenv("SNOWFLAKE_PASSWORD", raising=False)
        monkeypatch.setattr(Path, "home", lambda: Path("/nonexistent_home_dir"))

        mgr = SnowflakeConnectionManager()
        with pytest.raises(LoadError, match="credentials not found"):
            mgr.connect()

    @patch("scripts.load.snowflake.connector.connect")
    def test_context_manager_closes_connection(self, mock_connect, monkeypatch):
        """Connection is closed when exiting the context manager."""
        monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "acct")
        monkeypatch.setenv("SNOWFLAKE_USER", "user")
        monkeypatch.setenv("SNOWFLAKE_PASSWORD", "pass")

        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        with SnowflakeConnectionManager() as conn:
            assert conn is mock_conn

        mock_conn.close.assert_called_once()

    @patch("scripts.load.snowflake.connector.connect")
    def test_connect_failure_raises_load_error(self, mock_connect, monkeypatch):
        """LoadError raised with Snowflake error details on failure."""
        monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "acct")
        monkeypatch.setenv("SNOWFLAKE_USER", "user")
        monkeypatch.setenv("SNOWFLAKE_PASSWORD", "pass")

        import snowflake.connector.errors

        mock_connect.side_effect = snowflake.connector.errors.Error(
            msg="Auth failed", errno=250001
        )

        mgr = SnowflakeConnectionManager()
        with pytest.raises(LoadError, match="connection failed"):
            mgr.connect()


# ---- Upload to stage tests (S003) -------------------------------------------


class TestUploadToStage:
    """Tests for PUT upload functionality."""

    def test_constructs_correct_put_sql(self, mock_connection, sample_csv):
        """PUT SQL contains file path, stage path, and options."""
        cursor = mock_connection.cursor()

        upload_to_stage(mock_connection, sample_csv, "ttc_subway/test.csv")

        executed_sql = cursor.execute.call_args[0][0]
        assert "PUT" in executed_sql
        assert str(sample_csv) in executed_sql
        assert "INGESTION_STAGE" in executed_sql
        assert "AUTO_COMPRESS=TRUE" in executed_sql
        assert "OVERWRITE=TRUE" in executed_sql

    def test_returns_upload_result(self, mock_connection, sample_csv):
        """StageUploadResult contains expected fields."""
        result = upload_to_stage(mock_connection, sample_csv, "ttc_subway/test.csv")

        assert isinstance(result, StageUploadResult)
        assert result.local_path == sample_csv
        assert result.stage_path == "ttc_subway/test.csv"
        assert result.status == StageUploadStatus.UPLOADED
        assert result.source_size_bytes > 0
        assert result.elapsed_seconds >= 0

    def test_skipped_status_detected(self, mock_connection, sample_csv):
        """SKIPPED status from PUT is correctly propagated."""
        cursor = mock_connection.cursor()
        cursor.fetchall.return_value = [
            ("f.csv", "f.csv.gz", 100, 50, "none", "gzip", "SKIPPED", "")
        ]

        result = upload_to_stage(mock_connection, sample_csv, "test/f.csv")
        assert result.status == StageUploadStatus.SKIPPED

    def test_put_failure_raises_load_error(self, mock_connection, sample_csv):
        """LoadError raised when PUT command fails."""
        import snowflake.connector.errors

        cursor = mock_connection.cursor()
        cursor.execute.side_effect = snowflake.connector.errors.Error(
            msg="Stage not found"
        )

        with pytest.raises(LoadError, match="PUT failed"):
            upload_to_stage(mock_connection, sample_csv, "bad/path.csv")


# ---- COPY INTO tests (S003) -------------------------------------------------


class TestCopyIntoTable:
    """Tests for COPY INTO bulk loading."""

    def test_constructs_correct_copy_sql(self, mock_connection):
        """COPY INTO SQL contains table, columns, stage path, options."""
        cursor = mock_connection.cursor()
        cursor.fetchall.return_value = [
            ("file.csv", "LOADED", 100, 100, 100, 0, None, None)
        ]

        copy_into_table(
            mock_connection,
            "TORONTO_MOBILITY.RAW.TTC_SUBWAY_DELAYS",
            "ttc_subway/",
            ["DATE", "TIME", "STATION"],
        )

        executed_sql = cursor.execute.call_args[0][0]
        assert "COPY INTO" in executed_sql
        assert "TTC_SUBWAY_DELAYS" in executed_sql
        assert "DATE, TIME, STATION" in executed_sql
        assert "$1, $2, $3" in executed_sql
        assert "ON_ERROR = 'ABORT_STATEMENT'" in executed_sql
        assert "PURGE = FALSE" in executed_sql

    def test_returns_copy_result_with_counts(self, mock_connection):
        """CopyResult contains parsed row counts from Snowflake response."""
        cursor = mock_connection.cursor()
        cursor.fetchall.return_value = [
            ("file1.csv.gz", "LOADED", 500, 500, 500, 0, None, None),
            ("file2.csv.gz", "LOADED", 300, 300, 300, 0, None, None),
        ]

        result = copy_into_table(
            mock_connection,
            "TORONTO_MOBILITY.RAW.TTC_SUBWAY_DELAYS",
            "ttc_subway/",
            ["DATE", "TIME"],
        )

        assert isinstance(result, CopyResult)
        assert result.rows_loaded == 800
        assert result.rows_parsed == 800
        assert result.errors_seen == 0
        assert result.first_error is None

    def test_copy_failure_raises_load_error(self, mock_connection):
        """LoadError raised when COPY INTO fails."""
        import snowflake.connector.errors

        cursor = mock_connection.cursor()
        cursor.execute.side_effect = snowflake.connector.errors.Error(
            msg="Table does not exist"
        )

        with pytest.raises(LoadError, match="COPY INTO"):
            copy_into_table(
                mock_connection,
                "BAD_TABLE",
                "path/",
                ["COL1"],
            )


# ---- MERGE tests (S004) -----------------------------------------------------


class TestMergeIntoTable:
    """Tests for MERGE-based idempotent upsert."""

    def _setup_merge_cursor(self, mock_connection: MagicMock) -> MagicMock:
        """Configure cursor for a successful MERGE sequence."""
        cursor: MagicMock = mock_connection.cursor()
        # Calls: CREATE TEMP, COPY INTO staging, MERGE, DROP
        cursor.execute.return_value = None
        cursor.fetchall.return_value = []
        cursor.fetchone.return_value = (100, 25)
        return cursor

    def test_constructs_correct_merge_sql(self, mock_connection):
        """MERGE SQL contains ON, WHEN MATCHED, WHEN NOT MATCHED."""
        cursor = self._setup_merge_cursor(mock_connection)

        merge_into_table(
            mock_connection,
            target_table="TORONTO_MOBILITY.RAW.TTC_SUBWAY_DELAYS",
            natural_keys=["DATE", "TIME", "STATION"],
            all_columns=["DATE", "TIME", "STATION", "CODE", "MIN_DELAY"],
            stage_path="ttc_subway/",
            column_mapping=["DATE", "TIME", "STATION", "CODE", "MIN_DELAY"],
        )

        # Collect all executed SQL statements
        sqls = [call[0][0] for call in cursor.execute.call_args_list if call[0]]

        # Verify CREATE TEMPORARY TABLE
        assert any("CREATE TEMPORARY TABLE" in s for s in sqls)

        # Verify COPY INTO staging
        assert any("COPY INTO" in s and "STAGING" in s for s in sqls)

        # Verify MERGE
        merge_sqls = [s for s in sqls if "MERGE INTO" in s]
        assert len(merge_sqls) == 1
        merge_sql = merge_sqls[0]
        assert "WHEN MATCHED THEN UPDATE SET" in merge_sql
        assert "WHEN NOT MATCHED THEN INSERT" in merge_sql
        assert "target.DATE = staging.DATE" in merge_sql
        assert "target.CODE = staging.CODE" in merge_sql

        # Verify DROP TABLE in finally block
        assert any("DROP TABLE IF EXISTS" in s for s in sqls)

    def test_returns_merge_result(self, mock_connection):
        """MergeResult contains insert and update counts."""
        self._setup_merge_cursor(mock_connection)

        result = merge_into_table(
            mock_connection,
            target_table="TORONTO_MOBILITY.RAW.TTC_SUBWAY_DELAYS",
            natural_keys=["DATE"],
            all_columns=["DATE", "CODE"],
            stage_path="test/",
            column_mapping=["DATE", "CODE"],
        )

        assert isinstance(result, MergeResult)
        assert result.rows_inserted == 100
        assert result.rows_updated == 25
        assert result.elapsed_seconds >= 0

    def test_drops_staging_table_on_failure(self, mock_connection):
        """Temporary table is dropped even when MERGE fails."""
        import snowflake.connector.errors

        cursor = mock_connection.cursor()
        call_count = 0

        def side_effect(sql: str) -> None:
            nonlocal call_count
            call_count += 1
            # Fail on the MERGE (third execute call after CREATE and COPY)
            if "MERGE INTO" in sql:
                raise snowflake.connector.errors.Error(msg="Merge failed")

        cursor.execute.side_effect = side_effect
        cursor.fetchall.return_value = []

        with pytest.raises(LoadError, match="MERGE INTO"):
            merge_into_table(
                mock_connection,
                target_table="TORONTO_MOBILITY.RAW.TEST",
                natural_keys=["ID"],
                all_columns=["ID", "VAL"],
                stage_path="test/",
                column_mapping=["ID", "VAL"],
            )

        # Verify DROP was attempted (last execute call)
        last_call = cursor.execute.call_args_list[-1]
        assert "DROP TABLE IF EXISTS" in last_call[0][0]

    def test_natural_keys_match_design_doc(self):
        """Table configs use natural keys from DESIGN-DOC Section 6.4."""
        subway = get_table_config("ttc_subway_delays")
        assert subway.natural_keys == (
            "DATE",
            "TIME",
            "STATION",
            "LINE",
            "CODE",
            "MIN_DELAY",
        )

        bus = get_table_config("ttc_bus_delays")
        assert bus.natural_keys == (
            "DATE",
            "TIME",
            "ROUTE",
            "DIRECTION",
            "DELAY_CODE",
            "MIN_DELAY",
        )

        streetcar = get_table_config("ttc_streetcar_delays")
        assert streetcar.natural_keys == (
            "DATE",
            "TIME",
            "ROUTE",
            "DIRECTION",
            "DELAY_CODE",
            "MIN_DELAY",
        )

        bike = get_table_config("bike_share_ridership")
        assert bike.natural_keys == ("TRIP_ID",)

        weather = get_table_config("weather_daily")
        assert weather.natural_keys == ("DATE_TIME",)


# ---- Load dataset tests ------------------------------------------------------


class TestLoadDataset:
    """Tests for the high-level load_dataset function."""

    def test_load_dataset_calls_put_and_merge(self, mock_connection, tmp_path):
        """load_dataset uploads files via PUT and executes MERGE."""
        cursor = mock_connection.cursor()
        cursor.fetchall.return_value = [
            ("f.csv", "f.csv.gz", 100, 50, "none", "gzip", "UPLOADED", "")
        ]
        cursor.fetchone.return_value = (50, 0)

        csv1 = tmp_path / "delays_2023.csv"
        csv1.write_text("Date,Time\n2023-01-01,08:00\n")

        result = load_dataset(mock_connection, "ttc_subway_delays", [csv1])

        assert isinstance(result, MergeResult)
        sqls = [call[0][0] for call in cursor.execute.call_args_list if call[0]]
        assert any("PUT" in s for s in sqls)
        assert any("CREATE TEMPORARY TABLE" in s for s in sqls)
        assert any("MERGE INTO" in s for s in sqls)

    def test_unknown_dataset_raises_key_error(self, mock_connection):
        """KeyError raised for unknown dataset names."""
        with pytest.raises(KeyError, match="Unknown dataset"):
            load_dataset(mock_connection, "nonexistent", [])


# ---- Table config tests -----------------------------------------------------


class TestTableConfig:
    """Tests for table configuration registry."""

    def test_all_five_datasets_configured(self):
        """All five datasets have table configurations."""
        expected = {
            "ttc_subway_delays",
            "ttc_bus_delays",
            "ttc_streetcar_delays",
            "bike_share_ridership",
            "weather_daily",
        }
        for name in expected:
            config = get_table_config(name)
            assert isinstance(config, TableConfig)
            assert config.table_name.startswith("TORONTO_MOBILITY.RAW.")

    def test_subway_config_has_nine_columns(self):
        """Subway table has 9 columns matching contract."""
        config = get_table_config("ttc_subway_delays")
        assert len(config.columns) == 9

    def test_bike_share_config_has_ten_columns(self):
        """Bike share table has 10 columns matching contract."""
        config = get_table_config("bike_share_ridership")
        assert len(config.columns) == 10

    def test_weather_config_has_31_columns(self):
        """Weather table has 31 columns for all Environment Canada fields."""
        config = get_table_config("weather_daily")
        assert len(config.columns) == 31

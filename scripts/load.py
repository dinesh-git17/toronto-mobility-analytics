"""Snowflake loading module for Toronto Urban Mobility Analytics.

Manages authenticated connections to Snowflake via LOADER_ROLE,
uploads validated CSV files to an internal stage via PUT, executes
bulk COPY INTO for raw ingestion, and performs MERGE-based idempotent
upserts using natural keys defined in DESIGN-DOC.md Section 6.4.
"""

from __future__ import annotations

import enum
import logging
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import snowflake.connector

if TYPE_CHECKING:
    from snowflake.connector import SnowflakeConnection

logger: Final[logging.Logger] = logging.getLogger(__name__)

# ---- Snowflake connection defaults (DESIGN-DOC.md Section 10) ---------------

_DEFAULT_ROLE: Final[str] = "LOADER_ROLE"
_DEFAULT_WAREHOUSE: Final[str] = "TRANSFORM_WH"
_DEFAULT_DATABASE: Final[str] = "TORONTO_MOBILITY"
_DEFAULT_SCHEMA: Final[str] = "RAW"
_STAGE_PATH: Final[str] = "@TORONTO_MOBILITY.RAW.INGESTION_STAGE"

_LOGIN_TIMEOUT: Final[int] = 30
_NETWORK_TIMEOUT: Final[int] = 60


# ---- Exceptions -------------------------------------------------------------


class LoadError(Exception):
    """Raised when a Snowflake loading operation fails.

    Attributes:
        table: Target table name, if applicable.
        file_path: Source file path, if applicable.
    """

    def __init__(
        self,
        message: str,
        *,
        table: str = "",
        file_path: str = "",
    ) -> None:
        self.table: Final[str] = table
        self.file_path: Final[str] = file_path
        super().__init__(message)


# ---- Enums ------------------------------------------------------------------


class StageUploadStatus(enum.Enum):
    """Result status of a PUT upload operation."""

    UPLOADED = "UPLOADED"
    SKIPPED = "SKIPPED"


class PipelineStage(enum.Enum):
    """Pipeline execution stage identifier."""

    DOWNLOAD = "DOWNLOAD"
    TRANSFORM = "TRANSFORM"
    VALIDATE = "VALIDATE"
    LOAD = "LOAD"


class DatasetStatus(enum.Enum):
    """Outcome status for a single dataset in the pipeline."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


# ---- Result dataclasses -----------------------------------------------------


@dataclass(frozen=True, slots=True)
class StageUploadResult:
    """Outcome of uploading a single file to the Snowflake internal stage.

    Attributes:
        local_path: Absolute path to the uploaded file on disk.
        stage_path: Relative path within the internal stage.
        status: Whether the file was uploaded or skipped.
        source_size_bytes: File size on disk before compression.
        dest_size_bytes: Compressed size reported by Snowflake.
        elapsed_seconds: Wall-clock time for the PUT operation.
    """

    local_path: Path
    stage_path: str
    status: StageUploadStatus
    source_size_bytes: int
    dest_size_bytes: int
    elapsed_seconds: float


@dataclass(frozen=True, slots=True)
class CopyResult:
    """Outcome of a COPY INTO operation from stage to table.

    Attributes:
        table_name: Fully-qualified target table.
        rows_loaded: Number of rows successfully loaded.
        rows_parsed: Number of rows parsed from staged files.
        errors_seen: Number of row-level errors encountered.
        first_error: Description of the first error, if any.
        elapsed_seconds: Wall-clock time for the COPY INTO.
    """

    table_name: str
    rows_loaded: int
    rows_parsed: int
    errors_seen: int
    first_error: str | None
    elapsed_seconds: float


@dataclass(frozen=True, slots=True)
class MergeResult:
    """Outcome of a MERGE upsert operation.

    Attributes:
        target_table: Fully-qualified target table.
        rows_inserted: Rows inserted (NOT MATCHED clause).
        rows_updated: Rows updated (MATCHED clause).
        elapsed_seconds: Wall-clock time for the full MERGE cycle.
    """

    target_table: str
    rows_inserted: int
    rows_updated: int
    elapsed_seconds: float


# ---- Table configuration registry -------------------------------------------


@dataclass(frozen=True, slots=True)
class TableConfig:
    """Mapping between a source dataset and its Snowflake RAW table.

    Attributes:
        table_name: Fully-qualified Snowflake table name.
        columns: Snowflake column names in CSV positional order.
        natural_keys: Columns forming the natural key for MERGE dedup.
        stage_prefix: Subdirectory within the internal stage.
    """

    table_name: str
    columns: tuple[str, ...]
    natural_keys: tuple[str, ...]
    stage_prefix: str


TABLE_CONFIGS: Final[dict[str, TableConfig]] = {
    "ttc_subway_delays": TableConfig(
        table_name="TORONTO_MOBILITY.RAW.TTC_SUBWAY_DELAYS",
        columns=(
            "DATE",
            "TIME",
            "DAY",
            "STATION",
            "CODE",
            "MIN_DELAY",
            "MIN_GAP",
            "BOUND",
            "LINE",
        ),
        natural_keys=("DATE", "TIME", "STATION", "LINE", "CODE", "MIN_DELAY"),
        stage_prefix="ttc_subway",
    ),
    "ttc_bus_delays": TableConfig(
        table_name="TORONTO_MOBILITY.RAW.TTC_BUS_DELAYS",
        columns=(
            "DATE",
            "ROUTE",
            "TIME",
            "DAY",
            "LOCATION",
            "DELAY_CODE",
            "MIN_DELAY",
            "MIN_GAP",
            "DIRECTION",
        ),
        natural_keys=(
            "DATE",
            "TIME",
            "ROUTE",
            "DIRECTION",
            "DELAY_CODE",
            "MIN_DELAY",
        ),
        stage_prefix="ttc_bus",
    ),
    "ttc_streetcar_delays": TableConfig(
        table_name="TORONTO_MOBILITY.RAW.TTC_STREETCAR_DELAYS",
        columns=(
            "DATE",
            "ROUTE",
            "TIME",
            "DAY",
            "LOCATION",
            "DELAY_CODE",
            "MIN_DELAY",
            "MIN_GAP",
            "DIRECTION",
        ),
        natural_keys=(
            "DATE",
            "TIME",
            "ROUTE",
            "DIRECTION",
            "DELAY_CODE",
            "MIN_DELAY",
        ),
        stage_prefix="ttc_streetcar",
    ),
    "bike_share_ridership": TableConfig(
        table_name="TORONTO_MOBILITY.RAW.BIKE_SHARE_TRIPS",
        columns=(
            "TRIP_ID",
            "TRIP_DURATION",
            "START_STATION_ID",
            "START_TIME",
            "START_STATION_NAME",
            "END_STATION_ID",
            "END_TIME",
            "END_STATION_NAME",
            "BIKE_ID",
            "USER_TYPE",
        ),
        natural_keys=("TRIP_ID",),
        stage_prefix="bike_share",
    ),
    "weather_daily": TableConfig(
        table_name="TORONTO_MOBILITY.RAW.WEATHER_DAILY",
        columns=(
            "LONGITUDE",
            "LATITUDE",
            "STATION_NAME",
            "CLIMATE_ID",
            "DATE_TIME",
            "YEAR",
            "MONTH",
            "DAY",
            "DATA_QUALITY",
            "MAX_TEMP_C",
            "MAX_TEMP_FLAG",
            "MIN_TEMP_C",
            "MIN_TEMP_FLAG",
            "MEAN_TEMP_C",
            "MEAN_TEMP_FLAG",
            "HEAT_DEG_DAYS_C",
            "HEAT_DEG_DAYS_FLAG",
            "COOL_DEG_DAYS_C",
            "COOL_DEG_DAYS_FLAG",
            "TOTAL_RAIN_MM",
            "TOTAL_RAIN_FLAG",
            "TOTAL_SNOW_CM",
            "TOTAL_SNOW_FLAG",
            "TOTAL_PRECIP_MM",
            "TOTAL_PRECIP_FLAG",
            "SNOW_ON_GRND_CM",
            "SNOW_ON_GRND_FLAG",
            "DIR_OF_MAX_GUST_10S_DEG",
            "DIR_OF_MAX_GUST_FLAG",
            "SPD_OF_MAX_GUST_KMH",
            "SPD_OF_MAX_GUST_FLAG",
        ),
        natural_keys=("DATE_TIME",),
        stage_prefix="weather",
    ),
}


def get_table_config(dataset_name: str) -> TableConfig:
    """Look up table configuration for a dataset.

    Args:
        dataset_name: Machine-readable dataset identifier.

    Returns:
        Corresponding TableConfig instance.

    Raises:
        KeyError: If no configuration exists for the dataset.
    """
    config = TABLE_CONFIGS.get(dataset_name)
    if config is None:
        valid = ", ".join(TABLE_CONFIGS)
        raise KeyError(f"Unknown dataset '{dataset_name}'. Valid: {valid}")
    return config


# ---- Connection manager (S002) ----------------------------------------------


class SnowflakeConnectionManager:
    """Manage Snowflake connections with layered credential resolution.

    Credential resolution order:
      1. Explicit constructor arguments
      2. Environment variables (SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER,
         SNOWFLAKE_PASSWORD)
      3. ``~/.snowflake/connections.toml`` ``[loader]`` section

    Implements the context manager protocol to guarantee connection
    cleanup on scope exit.
    """

    def __init__(
        self,
        *,
        account: str | None = None,
        user: str | None = None,
        password: str | None = None,
        role: str = _DEFAULT_ROLE,
        warehouse: str = _DEFAULT_WAREHOUSE,
        database: str = _DEFAULT_DATABASE,
        schema: str = _DEFAULT_SCHEMA,
    ) -> None:
        self._account = account
        self._user = user
        self._password = password
        self._role = role
        self._warehouse = warehouse
        self._database = database
        self._schema = schema
        self._connection: SnowflakeConnection | None = None

    def _resolve_credentials(self) -> dict[str, str]:
        """Resolve Snowflake credentials from available sources."""
        import os

        account = self._account or os.environ.get("SNOWFLAKE_ACCOUNT", "")
        user = self._user or os.environ.get("SNOWFLAKE_USER", "")
        password = self._password or os.environ.get("SNOWFLAKE_PASSWORD", "")

        if account and user and password:
            return {"account": account, "user": user, "password": password}

        toml_path = Path.home() / ".snowflake" / "connections.toml"
        if toml_path.exists():
            with toml_path.open("rb") as fh:
                config = tomllib.load(fh)
            loader = config.get("loader", {})
            account = account or str(loader.get("account", ""))
            user = user or str(loader.get("user", ""))
            password = password or str(loader.get("password", ""))
            if account and user and password:
                return {
                    "account": account,
                    "user": user,
                    "password": password,
                }

        raise LoadError(
            "Snowflake credentials not found. Set SNOWFLAKE_ACCOUNT, "
            "SNOWFLAKE_USER, and SNOWFLAKE_PASSWORD environment variables "
            "or configure ~/.snowflake/connections.toml with a [loader] section."
        )

    def connect(self) -> SnowflakeConnection:
        """Establish an authenticated Snowflake connection.

        Returns:
            Active SnowflakeConnection scoped to LOADER_ROLE.

        Raises:
            LoadError: On authentication or network failure.
        """
        credentials = self._resolve_credentials()
        try:
            conn: SnowflakeConnection = snowflake.connector.connect(
                account=credentials["account"],
                user=credentials["user"],
                password=credentials["password"],
                role=self._role,
                warehouse=self._warehouse,
                database=self._database,
                schema=self._schema,
                client_session_keep_alive=True,
                login_timeout=_LOGIN_TIMEOUT,
                network_timeout=_NETWORK_TIMEOUT,
            )
        except snowflake.connector.errors.Error as exc:
            errno = getattr(exc, "errno", "unknown")
            msg = getattr(exc, "msg", str(exc))
            raise LoadError(
                f"Snowflake connection failed: {msg} (error code: {errno})"
            ) from exc
        self._connection = conn
        return conn

    def __enter__(self) -> SnowflakeConnection:
        """Enter context manager; return authenticated connection."""
        return self.connect()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit context manager; close connection unconditionally."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None


# ---- Stage upload (S003) -----------------------------------------------------


def upload_to_stage(
    connection: SnowflakeConnection,
    local_path: Path,
    stage_path: str,
) -> StageUploadResult:
    """Upload a local CSV file to the Snowflake internal stage via PUT.

    Args:
        connection: Active Snowflake connection.
        local_path: Absolute path to the CSV file on disk.
        stage_path: Relative destination path within the stage.

    Returns:
        StageUploadResult with upload status and size metrics.

    Raises:
        LoadError: If the PUT command fails.
    """
    start = time.monotonic()
    source_size = local_path.stat().st_size

    put_sql = (
        f"PUT 'file://{local_path}' "
        f"'{_STAGE_PATH}/{stage_path}' "
        f"AUTO_COMPRESS=TRUE OVERWRITE=TRUE"
    )

    cursor = connection.cursor()
    try:
        cursor.execute(put_sql)
        results = list(cursor.fetchall())
    except snowflake.connector.errors.Error as exc:
        raise LoadError(
            f"PUT failed for {local_path}: {getattr(exc, 'msg', str(exc))}",
            file_path=str(local_path),
        ) from exc
    finally:
        cursor.close()

    elapsed = time.monotonic() - start

    status = StageUploadStatus.UPLOADED
    dest_size = 0
    if results:
        row = tuple(results[0])
        status_str = str(row[6]).upper() if len(row) > 6 else ""
        if status_str == "SKIPPED":
            status = StageUploadStatus.SKIPPED
        dest_size = int(row[3]) if len(row) > 3 and row[3] else 0

    logger.info(
        "PUT %s -> %s/%s [%s, %.1fs]",
        local_path.name,
        _STAGE_PATH,
        stage_path,
        status.value,
        elapsed,
    )

    return StageUploadResult(
        local_path=local_path,
        stage_path=stage_path,
        status=status,
        source_size_bytes=source_size,
        dest_size_bytes=dest_size,
        elapsed_seconds=round(elapsed, 3),
    )


# ---- COPY INTO (S003) -------------------------------------------------------


def copy_into_table(
    connection: SnowflakeConnection,
    table_name: str,
    stage_path: str,
    column_mapping: list[str],
) -> CopyResult:
    """Execute COPY INTO to bulk-load staged files into a RAW table.

    Uses positional column mapping: ``$1, $2, ...`` from the staged CSV
    are mapped to the columns listed in ``column_mapping`` in order.

    Args:
        connection: Active Snowflake connection.
        table_name: Fully-qualified target table.
        stage_path: Stage path pattern (may include wildcards).
        column_mapping: Target column names in CSV positional order.

    Returns:
        CopyResult with row counts and error details.

    Raises:
        LoadError: If COPY INTO fails with a row-level or statement error.
    """
    start = time.monotonic()

    cols = ", ".join(column_mapping)
    positional = ", ".join(f"${i}" for i in range(1, len(column_mapping) + 1))

    copy_sql = (
        f"COPY INTO {table_name} ({cols}) "
        f"FROM (SELECT {positional} FROM {_STAGE_PATH}/{stage_path}) "
        f"ON_ERROR = 'ABORT_STATEMENT' "
        f"PURGE = FALSE"
    )

    cursor = connection.cursor()
    try:
        cursor.execute(copy_sql)
        results = list(cursor.fetchall())
    except snowflake.connector.errors.Error as exc:
        raise LoadError(
            f"COPY INTO {table_name} failed: {getattr(exc, 'msg', str(exc))}",
            table=table_name,
            file_path=stage_path,
        ) from exc
    finally:
        cursor.close()

    elapsed = time.monotonic() - start

    rows_loaded = 0
    rows_parsed = 0
    errors_seen = 0
    first_error: str | None = None

    for raw_row in results:
        # COPY INTO result columns: file, status, rows_parsed, rows_loaded,
        # error_limit, errors_seen, first_error, first_error_line, ...
        row = tuple(raw_row)
        if len(row) >= 4:
            rows_parsed += int(row[2]) if row[2] else 0
            rows_loaded += int(row[3]) if row[3] else 0
        if len(row) >= 7:
            errors_seen += int(row[5]) if row[5] else 0
            if not first_error and row[6]:
                first_error = str(row[6])

    logger.info(
        "COPY INTO %s: %d rows loaded (%.1fs)",
        table_name,
        rows_loaded,
        elapsed,
    )

    return CopyResult(
        table_name=table_name,
        rows_loaded=rows_loaded,
        rows_parsed=rows_parsed,
        errors_seen=errors_seen,
        first_error=first_error,
        elapsed_seconds=round(elapsed, 3),
    )


# ---- MERGE upsert (S004) ----------------------------------------------------


def merge_into_table(
    connection: SnowflakeConnection,
    target_table: str,
    natural_keys: list[str],
    all_columns: list[str],
    *,
    stage_path: str,
    column_mapping: list[str],
) -> MergeResult:
    """Execute an idempotent MERGE upsert from staged files into target.

    Creates a session-scoped temporary table with identical DDL to the
    target, loads staged data via COPY INTO, then MERGEs into the target
    using the specified natural keys. The temporary table is dropped in
    all code paths.

    Args:
        connection: Active Snowflake connection.
        target_table: Fully-qualified target table.
        natural_keys: Columns forming the deduplication key.
        all_columns: All columns in the target table.
        stage_path: Stage path for COPY INTO the temporary table.
        column_mapping: Column names in CSV positional order for COPY.

    Returns:
        MergeResult with insert/update counts.

    Raises:
        LoadError: If COPY INTO or MERGE fails.
    """
    staging_table = f"{target_table}_STAGING"
    start = time.monotonic()

    cursor = connection.cursor()
    try:
        try:
            cursor.execute(
                f"CREATE TEMPORARY TABLE {staging_table} LIKE {target_table}"
            )
        except snowflake.connector.errors.Error as exc:
            raise LoadError(
                f"Failed to create staging table {staging_table}: "
                f"{getattr(exc, 'msg', str(exc))}",
                table=target_table,
            ) from exc

        _copy_into_staging(cursor, staging_table, stage_path, column_mapping)

        result = _execute_merge(
            cursor,
            target_table,
            staging_table,
            natural_keys,
            all_columns,
        )
    finally:
        try:
            cursor.execute(f"DROP TABLE IF EXISTS {staging_table}")
        except snowflake.connector.errors.Error:
            logger.warning("Failed to drop staging table %s", staging_table)
        cursor.close()

    elapsed = time.monotonic() - start

    logger.info(
        "MERGE INTO %s: %d inserted, %d updated (%.1fs)",
        target_table,
        result[0],
        result[1],
        elapsed,
    )

    return MergeResult(
        target_table=target_table,
        rows_inserted=result[0],
        rows_updated=result[1],
        elapsed_seconds=round(elapsed, 3),
    )


def _copy_into_staging(
    cursor: Any,
    staging_table: str,
    stage_path: str,
    column_mapping: list[str],
) -> None:
    """COPY INTO the temporary staging table from internal stage."""
    cols = ", ".join(column_mapping)
    positional = ", ".join(f"${i}" for i in range(1, len(column_mapping) + 1))

    copy_sql = (
        f"COPY INTO {staging_table} ({cols}) "
        f"FROM (SELECT {positional} FROM {_STAGE_PATH}/{stage_path}) "
        f"ON_ERROR = 'ABORT_STATEMENT' "
        f"PURGE = FALSE"
    )

    try:
        cursor.execute(copy_sql)
    except snowflake.connector.errors.Error as exc:
        raise LoadError(
            f"COPY INTO staging table {staging_table} failed: "
            f"{getattr(exc, 'msg', str(exc))}",
            table=staging_table,
            file_path=stage_path,
        ) from exc


def _execute_merge(
    cursor: Any,
    target_table: str,
    staging_table: str,
    natural_keys: list[str],
    all_columns: list[str],
) -> tuple[int, int]:
    """Build and execute MERGE statement, return (inserted, updated)."""
    on_clause = " AND ".join(f"target.{k} = staging.{k}" for k in natural_keys)

    non_key_cols = [c for c in all_columns if c not in natural_keys]

    update_set = ", ".join(f"target.{c} = staging.{c}" for c in non_key_cols)

    insert_cols = ", ".join(all_columns)
    insert_vals = ", ".join(f"staging.{c}" for c in all_columns)

    merge_sql = (
        f"MERGE INTO {target_table} AS target "
        f"USING {staging_table} AS staging "
        f"ON {on_clause}"
    )

    if update_set:
        merge_sql += f" WHEN MATCHED THEN UPDATE SET {update_set}"

    merge_sql += f" WHEN NOT MATCHED THEN INSERT ({insert_cols}) VALUES ({insert_vals})"

    try:
        cursor.execute(merge_sql)
    except snowflake.connector.errors.Error as exc:
        raise LoadError(
            f"MERGE INTO {target_table} failed: {getattr(exc, 'msg', str(exc))}",
            table=target_table,
        ) from exc

    rows_inserted = 0
    rows_updated = 0

    # Snowflake MERGE returns: number of rows inserted, number of rows updated
    result = cursor.fetchone()
    if result:
        rows_inserted = int(result[0]) if result[0] else 0
        rows_updated = int(result[1]) if len(result) > 1 and result[1] else 0

    return rows_inserted, rows_updated


# ---- Convenience: load a full dataset ----------------------------------------


def load_dataset(
    connection: SnowflakeConnection,
    dataset_name: str,
    csv_files: list[Path],
) -> MergeResult:
    """Upload and MERGE a set of CSV files for a dataset.

    Orchestrates the full load sequence: PUT each file to stage, then
    execute a single MERGE from the staged directory into the target table.
    Callers are responsible for transaction boundaries (BEGIN/COMMIT).

    Args:
        connection: Active Snowflake connection.
        dataset_name: Machine-readable dataset identifier.
        csv_files: Validated CSV file paths to load.

    Returns:
        MergeResult from the final MERGE operation.

    Raises:
        LoadError: If any PUT or MERGE operation fails.
        KeyError: If dataset_name has no table configuration.
    """
    config = get_table_config(dataset_name)

    for csv_path in csv_files:
        stage_dest = f"{config.stage_prefix}/{csv_path.name}"
        upload_to_stage(connection, csv_path, stage_dest)

    return merge_into_table(
        connection,
        target_table=config.table_name,
        natural_keys=list(config.natural_keys),
        all_columns=list(config.columns),
        stage_path=f"{config.stage_prefix}/",
        column_mapping=list(config.columns),
    )

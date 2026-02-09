"""Pipeline orchestrator for Toronto Urban Mobility data ingestion.

Sequences download, transform, validate, and Snowflake load stages
with per-dataset atomic transaction boundaries. Each dataset processes
independently: a failure in one dataset does not block others.

Usage:
    python scripts/ingest.py --all
    python scripts/ingest.py --dataset ttc_subway_delays
    python scripts/ingest.py --all --skip-download
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import snowflake.connector

from scripts.config import DATASETS, get_dataset_by_name
from scripts.contracts import CONTRACTS
from scripts.download import DownloadError, download_dataset
from scripts.download import DownloadManifest as _DownloadManifest
from scripts.load import (
    DatasetStatus,
    LoadError,
    MergeResult,
    PipelineStage,
    SnowflakeConnectionManager,
    get_table_config,
    load_dataset,
)
from scripts.validate import SchemaValidationError

logger: Final[logging.Logger] = logging.getLogger(__name__)

_RAW_DIR: Final[Path] = Path("data/raw")
_VALIDATED_DIR: Final[Path] = Path("data/validated")


# ---- Result dataclasses -----------------------------------------------------


@dataclass(frozen=True, slots=True)
class DatasetResult:
    """Outcome of processing a single dataset through the pipeline.

    Attributes:
        dataset_name: Machine-readable dataset identifier.
        stage: Last pipeline stage attempted.
        rows_loaded: Number of rows loaded into Snowflake.
        elapsed_seconds: Wall-clock time for the full dataset.
        status: Final outcome status.
        error_message: Description of failure, if any.
    """

    dataset_name: str
    stage: PipelineStage
    rows_loaded: int
    elapsed_seconds: float
    status: DatasetStatus
    error_message: str = ""


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """Aggregate outcome of a full pipeline execution.

    Attributes:
        datasets_processed: Per-dataset results.
        total_rows_loaded: Sum of rows loaded across all datasets.
        total_elapsed_seconds: Wall-clock time for the full pipeline.
        success: True only if every dataset succeeded.
    """

    datasets_processed: list[DatasetResult] = field(default_factory=list)
    total_rows_loaded: int = 0
    total_elapsed_seconds: float = 0.0
    success: bool = True


# ---- Dataset subdirectory mapping -------------------------------------------


_DATASET_SUBDIRS: Final[dict[str, str]] = {
    "ttc_subway_delays": "ttc_subway",
    "ttc_bus_delays": "ttc_bus",
    "ttc_streetcar_delays": "ttc_streetcar",
    "bike_share_ridership": "bike_share",
    "weather_daily": "weather",
}


def _get_validated_csvs(dataset_name: str) -> list[Path]:
    """Collect all validated CSV files for a dataset.

    Args:
        dataset_name: Machine-readable dataset identifier.

    Returns:
        Sorted list of CSV file paths under data/validated/.
    """
    subdir = _DATASET_SUBDIRS.get(dataset_name, "")
    validated_dir = _VALIDATED_DIR / subdir
    if not validated_dir.exists():
        return []
    return sorted(validated_dir.rglob("*.csv"))


# ---- Stage executors ---------------------------------------------------------


def _run_download(dataset_name: str) -> None:
    """Execute the download stage for a single dataset."""
    config = get_dataset_by_name(dataset_name)
    manifest_path = _RAW_DIR / ".manifest.json"
    manifest = _DownloadManifest.load(manifest_path)
    manifest.prune()
    download_dataset(config, _RAW_DIR, manifest)


def _run_transform_and_validate(dataset_name: str) -> None:
    """Execute transform and validate stages for a single dataset.

    Imports the validation pipeline runner which handles XLSX conversion,
    encoding normalization, column renaming, and schema validation.
    """
    from scripts.validate import _run_pipeline as validate_pipeline

    contract = CONTRACTS[dataset_name]
    validate_pipeline(
        dataset_name=dataset_name,
        contract=contract,
        source_dir=_RAW_DIR,
        output_dir=_VALIDATED_DIR,
    )


def _run_load(
    dataset_name: str,
    connection_manager: SnowflakeConnectionManager,
) -> MergeResult:
    """Execute the Snowflake load stage with atomic transaction control.

    Opens a dedicated connection, begins a transaction, loads all CSV
    files via PUT + MERGE, and commits on success or rolls back on
    failure.

    Args:
        dataset_name: Machine-readable dataset identifier.
        connection_manager: Pre-configured connection manager.

    Returns:
        MergeResult from the load operation.

    Raises:
        LoadError: If any load operation fails (transaction rolled back).
    """
    csv_files = _get_validated_csvs(dataset_name)
    if not csv_files:
        raise LoadError(
            f"No validated CSV files found for {dataset_name}",
            table=get_table_config(dataset_name).table_name,
        )

    with connection_manager as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("BEGIN")
            result = load_dataset(conn, dataset_name, csv_files)
            conn.commit()
            return result
        except (LoadError, snowflake.connector.errors.Error):
            conn.rollback()
            raise
        finally:
            cursor.close()


# ---- Pipeline orchestration --------------------------------------------------


def run_pipeline(
    datasets: list[str] | None = None,
    skip_download: bool = False,
) -> PipelineResult:
    """Execute the ingestion pipeline for specified datasets.

    Processes each dataset independently through four stages:
    download, transform, validate, and load. Per-dataset failures
    are captured without blocking subsequent datasets.

    Args:
        datasets: Specific datasets to process. None processes all.
        skip_download: Skip the download stage (re-process existing files).

    Returns:
        PipelineResult with per-dataset outcomes and aggregate metrics.
    """
    pipeline_start = time.monotonic()
    dataset_names = datasets or [d.name for d in DATASETS]
    connection_manager = SnowflakeConnectionManager()

    results: list[DatasetResult] = []
    all_success = True

    for name in dataset_names:
        dataset_start = time.monotonic()
        logger.info("Processing dataset: %s", name)

        try:
            _process_single_dataset(
                name,
                connection_manager,
                skip_download,
            )
        except DownloadError as exc:
            elapsed = time.monotonic() - dataset_start
            results.append(
                DatasetResult(
                    dataset_name=name,
                    stage=PipelineStage.DOWNLOAD,
                    rows_loaded=0,
                    elapsed_seconds=round(elapsed, 3),
                    status=DatasetStatus.FAILED,
                    error_message=str(exc),
                )
            )
            all_success = False
            logger.error("FAILED [%s] download: %s", name, exc)
            continue
        except SchemaValidationError as exc:
            elapsed = time.monotonic() - dataset_start
            results.append(
                DatasetResult(
                    dataset_name=name,
                    stage=PipelineStage.VALIDATE,
                    rows_loaded=0,
                    elapsed_seconds=round(elapsed, 3),
                    status=DatasetStatus.FAILED,
                    error_message=str(exc),
                )
            )
            all_success = False
            logger.error("FAILED [%s] validation: %s", name, exc)
            continue
        except LoadError as exc:
            elapsed = time.monotonic() - dataset_start
            results.append(
                DatasetResult(
                    dataset_name=name,
                    stage=PipelineStage.LOAD,
                    rows_loaded=0,
                    elapsed_seconds=round(elapsed, 3),
                    status=DatasetStatus.FAILED,
                    error_message=str(exc),
                )
            )
            all_success = False
            logger.error("FAILED [%s] load: %s", name, exc)
            continue

        elapsed = time.monotonic() - dataset_start
        csv_count = len(_get_validated_csvs(name))
        results.append(
            DatasetResult(
                dataset_name=name,
                stage=PipelineStage.LOAD,
                rows_loaded=csv_count,
                elapsed_seconds=round(elapsed, 3),
                status=DatasetStatus.SUCCESS,
            )
        )
        logger.info("SUCCESS [%s] in %.1fs", name, elapsed)

    total_rows = sum(r.rows_loaded for r in results)
    pipeline_elapsed = time.monotonic() - pipeline_start

    return PipelineResult(
        datasets_processed=results,
        total_rows_loaded=total_rows,
        total_elapsed_seconds=round(pipeline_elapsed, 3),
        success=all_success,
    )


def _process_single_dataset(
    dataset_name: str,
    connection_manager: SnowflakeConnectionManager,
    skip_download: bool,
) -> None:
    """Run all pipeline stages for a single dataset.

    Args:
        dataset_name: Machine-readable dataset identifier.
        connection_manager: Pre-configured connection manager.
        skip_download: Skip the download stage.

    Raises:
        DownloadError: If download fails.
        SchemaValidationError: If validation fails.
        LoadError: If Snowflake load fails.
    """
    if not skip_download:
        logger.info("[%s] Stage: DOWNLOAD", dataset_name)
        _run_download(dataset_name)

    logger.info("[%s] Stage: TRANSFORM + VALIDATE", dataset_name)
    _run_transform_and_validate(dataset_name)

    logger.info("[%s] Stage: LOAD", dataset_name)
    _run_load(dataset_name, connection_manager)


# ---- CLI ---------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the ingestion pipeline CLI."""
    parser = argparse.ArgumentParser(
        description="Toronto Mobility data ingestion pipeline.",
    )
    parser.add_argument(
        "--all",
        dest="run_all",
        action="store_true",
        help="Process all five datasets.",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Process a single dataset by name.",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip download stage; re-process already-downloaded files.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug-level logging.",
    )
    return parser


def _print_summary(result: PipelineResult) -> None:
    """Print structured execution summary to stdout."""
    header = f"{'Dataset':<30} {'Stage':<12} {'Status':<10} {'Rows':<10} {'Time (s)'}"
    print(f"\n{'=' * 80}")
    print("Pipeline Execution Summary")
    print(f"{'=' * 80}")
    print(header)
    print("-" * 80)

    for ds in result.datasets_processed:
        print(
            f"{ds.dataset_name:<30} "
            f"{ds.stage.value:<12} "
            f"{ds.status.value:<10} "
            f"{ds.rows_loaded:<10} "
            f"{ds.elapsed_seconds:.1f}"
        )

    print("-" * 80)
    print(
        f"Total rows: {result.total_rows_loaded}  "
        f"Elapsed: {result.total_elapsed_seconds:.1f}s  "
        f"Result: {'SUCCESS' if result.success else 'FAILED'}"
    )
    print(f"{'=' * 80}\n")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the ingestion pipeline.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code: 0 if all datasets succeed, 1 if any fail.
    """
    parser = _build_arg_parser()
    args: argparse.Namespace = parser.parse_args(argv)

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stderr,
    )

    if not args.run_all and args.dataset is None:
        parser.error("Specify --all or --dataset <name>")
        return 1

    dataset_list: list[str] | None = None
    if args.dataset is not None:
        dataset_list = [args.dataset]

    result = run_pipeline(
        datasets=dataset_list,
        skip_download=args.skip_download,
    )

    _print_summary(result)
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())

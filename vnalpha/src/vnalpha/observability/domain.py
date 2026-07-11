"""Domain-level observability logging helpers.

These functions provide best-effort structured log events for:
- warehouse migrations
- data sync operations
- feature builds
- scoring / watchlist generation
- outcome evaluation
"""

from __future__ import annotations

from vnalpha.observability.audit import log_audit
from vnalpha.observability.errors import capture_exception, capture_warning
from vnalpha.observability.logger import log_app


def log_migration_start(migration: str = "", *, run_ctx=None) -> None:
    log_audit(
        "WAREHOUSE_MIGRATION_STARTED",
        f"Warehouse migration started: {migration}",
        run_ctx=run_ctx,
    )
    log_app(
        "WAREHOUSE_MIGRATION_STARTED",
        f"Migration started: {migration}",
        module="vnalpha.warehouse.migrations",
        run_ctx=run_ctx,
    )


def log_migration_success(migration: str = "", *, run_ctx=None) -> None:
    log_audit(
        "WAREHOUSE_MIGRATION_RUN",
        f"Warehouse migration complete: {migration}",
        status="OK",
        run_ctx=run_ctx,
    )


def log_migration_failure(
    migration: str = "", *, exc: BaseException | None = None, run_ctx=None
) -> None:
    log_audit(
        "WAREHOUSE_MIGRATION_FAILED",
        f"Warehouse migration failed: {migration}",
        status="FAILED",
        level="ERROR",
        run_ctx=run_ctx,
    )
    if exc is not None:
        capture_exception(exc, run_ctx=run_ctx, likely_cause="migration DDL error")


def log_sync_start(sync_type: str, *, run_ctx=None) -> None:
    log_audit(
        "SYNC_STARTED",
        f"Data sync started: {sync_type}",
        run_ctx=run_ctx,
    )


def log_sync_success(sync_type: str, *, row_count: int = 0, run_ctx=None) -> None:
    log_audit(
        "SYNC_COMPLETED",
        f"Data sync complete: {sync_type} ({row_count} rows)",
        status="OK",
        run_ctx=run_ctx,
        extra={"sync_type": sync_type, "row_count": row_count},
    )


def log_sync_failure(
    sync_type: str, *, exc: BaseException | None = None, run_ctx=None
) -> None:
    log_audit(
        "SYNC_FAILED",
        f"Data sync failed: {sync_type}",
        status="FAILED",
        level="ERROR",
        run_ctx=run_ctx,
    )
    if exc is not None:
        capture_exception(
            exc, run_ctx=run_ctx, likely_cause="sync network or data error"
        )


def log_feature_build_start(date: str, *, run_ctx=None) -> None:
    log_audit(
        "FEATURE_BUILD_STARTED",
        f"Feature build started for {date}",
        run_ctx=run_ctx,
    )


def log_feature_build_success(
    date: str, *, built: int = 0, skipped: int = 0, run_ctx=None
) -> None:
    log_audit(
        "FEATURE_BUILD_COMPLETE",
        f"Feature build complete for {date}: {built} built, {skipped} skipped",
        status="OK",
        run_ctx=run_ctx,
        extra={"date": date, "built": built, "skipped": skipped},
    )


def log_feature_build_failure(
    date: str, *, exc: BaseException | None = None, run_ctx=None
) -> None:
    log_audit(
        "FEATURE_BUILD_FAILED",
        f"Feature build failed for {date}",
        status="FAILED",
        level="ERROR",
        run_ctx=run_ctx,
    )
    if exc is not None:
        capture_exception(
            exc, run_ctx=run_ctx, likely_cause="feature computation error"
        )


def log_market_regime_built(
    as_of_date: str,
    market_regime_state: str,
    quality_status: str,
    breadth_feature_count: int,
    caveat_count: int,
    methodology_version: str,
) -> None:
    """Record a persisted market-regime research snapshot."""
    log_audit(
        "MARKET_REGIME_BUILT",
        f"Market regime built for {as_of_date}: {market_regime_state}",
        status="OK",
        extra={
            "as_of_date": as_of_date,
            "market_regime_state": market_regime_state,
            "quality_status": quality_status,
            "breadth_feature_count": breadth_feature_count,
            "caveat_count": caveat_count,
            "methodology_version": methodology_version,
        },
    )


def log_sector_strength_built(
    as_of_date: str,
    ranked_sector_count: int,
    metadata_coverage_pct: float,
    unclassified_count: int,
    quality_status: str,
    methodology_version: str,
) -> None:
    """Record a persisted sector-strength research build."""
    log_audit(
        "SECTOR_STRENGTH_BUILT",
        f"Sector strength built for {as_of_date}: {ranked_sector_count} ranked",
        status="OK",
        extra={
            "as_of_date": as_of_date,
            "ranked_sector_count": ranked_sector_count,
            "metadata_coverage_pct": metadata_coverage_pct,
            "unclassified_count": unclassified_count,
            "quality_status": quality_status,
            "methodology_version": methodology_version,
        },
    )


def log_scoring_start(date: str, *, run_ctx=None) -> None:
    log_audit(
        "SCORING_STARTED",
        f"Scoring started for {date}",
        run_ctx=run_ctx,
    )


def log_scoring_success(
    date: str, *, scored: int = 0, saved: int = 0, run_ctx=None
) -> None:
    log_audit(
        "SCORING_COMPLETE",
        f"Scoring complete for {date}: {scored} scored, {saved} saved",
        status="OK",
        run_ctx=run_ctx,
        extra={"date": date, "scored": scored, "saved": saved},
    )


def log_scoring_failure(
    date: str, *, exc: BaseException | None = None, run_ctx=None
) -> None:
    log_audit(
        "SCORING_FAILED",
        f"Scoring failed for {date}",
        status="FAILED",
        level="ERROR",
        run_ctx=run_ctx,
    )
    if exc is not None:
        capture_exception(
            exc, run_ctx=run_ctx, likely_cause="scoring rule or data error"
        )


def log_outcome_eval_start(date: str, *, run_ctx=None) -> None:
    log_audit(
        "OUTCOME_EVALUATION_STARTED",
        f"Outcome evaluation started for {date}",
        run_ctx=run_ctx,
    )


def log_outcome_eval_success(
    date: str, *, evaluated: int = 0, persisted: int = 0, run_ctx=None
) -> None:
    log_audit(
        "OUTCOME_EVALUATION_COMPLETE",
        f"Outcome evaluation complete for {date}: {evaluated} evaluated, {persisted} persisted",
        status="OK",
        run_ctx=run_ctx,
        extra={"date": date, "evaluated": evaluated, "persisted": persisted},
    )


def log_outcome_eval_failure(
    date: str, *, exc: BaseException | None = None, run_ctx=None
) -> None:
    log_audit(
        "OUTCOME_EVALUATION_FAILED",
        f"Outcome evaluation failed for {date}",
        status="FAILED",
        level="ERROR",
        run_ctx=run_ctx,
    )
    if exc is not None:
        capture_exception(exc, run_ctx=run_ctx, likely_cause="outcome evaluation error")


def log_watchlist_start(date: str, *, run_ctx=None) -> None:
    log_audit(
        "WATCHLIST_GENERATION_STARTED",
        f"Watchlist generation started for {date}",
        run_ctx=run_ctx,
    )


def log_watchlist_success(
    date: str, *, scored: int = 0, saved: int = 0, run_ctx=None
) -> None:
    log_audit(
        "WATCHLIST_GENERATION_COMPLETE",
        f"Watchlist generation complete for {date}: {scored} scored, {saved} saved",
        status="OK",
        run_ctx=run_ctx,
        extra={"date": date, "scored": scored, "saved": saved},
    )


def log_watchlist_failure(
    date: str, *, exc: BaseException | None = None, run_ctx=None
) -> None:
    log_audit(
        "WATCHLIST_GENERATION_FAILED",
        f"Watchlist generation failed for {date}",
        status="FAILED",
        level="ERROR",
        run_ctx=run_ctx,
    )
    if exc is not None:
        capture_exception(
            exc, run_ctx=run_ctx, likely_cause="watchlist generation error"
        )


def log_data_quality_warning(message: str, *, module: str = "", run_ctx=None) -> None:
    capture_warning(
        message,
        event_type="DATA_QUALITY_WARNING",
        module=module,
        run_ctx=run_ctx,
    )

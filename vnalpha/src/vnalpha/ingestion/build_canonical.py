"""Audit-aware orchestration for validation-gated canonical OHLCV promotion."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from datetime import datetime

import duckdb

from vnalpha.core.logging import get_logger
from vnalpha.ingestion.canonical_storage import (
    count_canonical_rows,
    delete_canonical_bar,
    delete_stray_intraday_canonical_rows,
    load_ranked_candidates,
    persist_quarantine,
    resolve_quarantines,
    upsert_canonical,
)
from vnalpha.ingestion.canonical_validation import (
    CanonicalCandidate,
    validate_candidate,
)
from vnalpha.observability.audit import log_audit
from vnalpha.observability.context import get_correlation_id, set_correlation_id

logger = get_logger("ingestion.build_canonical")


def build_canonical_ohlcv(
    conn: duckdb.DuckDBPyConnection,
    symbol: str | None = None,
    interval: str = "1D",
) -> dict[str, int]:
    """Promote only validated raw OHLCV observations into canonical storage.

    The highest-ranked raw candidate for each bar is the sole candidate that
    can be promoted. If it violates a severe validation rule, its evidence is
    quarantined and any canonical bar for that key is removed.
    """

    if get_correlation_id() in {"", "unset"}:
        set_correlation_id()
    log_audit(
        "CANONICAL_OHLCV_BUILD_STARTED",
        "Canonical OHLCV validation started.",
        extra={"interval": interval, "symbol": symbol or "ALL"},
    )
    transaction_started = False
    try:
        conn.execute("BEGIN TRANSACTION")
        transaction_started = True
        grouped: defaultdict[tuple[str, datetime, str], list[CanonicalCandidate]] = (
            defaultdict(list)
        )
        for candidate in load_ranked_candidates(conn, symbol, interval):
            grouped[(candidate.symbol, candidate.timestamp, candidate.interval)].append(
                candidate
            )

        rejected = 0
        for candidates in grouped.values():
            selected_candidate = candidates[0]
            rules = validate_candidate(selected_candidate, tuple(candidates[1:]))
            if rules:
                persist_quarantine(conn, selected_candidate, rules)
                delete_canonical_bar(conn, selected_candidate)
                rejected += 1
            else:
                upsert_canonical(
                    conn, replace(selected_candidate, quality_status="pass")
                )
                resolve_quarantines(conn, selected_candidate)

        # Daily bars are keyed by trading date, not by an intraday timestamp.
        # A canonical row with a non-midnight time-of-day is leftover from
        # before candidates were grouped by date (raw providers occasionally
        # report different times-of-day for the same trading session); every
        # current write lands at midnight, so any such row is always stale.
        if interval == "1D":
            delete_stray_intraday_canonical_rows(conn, symbol, interval)

        canonical_count = count_canonical_rows(conn, symbol, interval)
        conn.execute("COMMIT")
        transaction_started = False
        log_audit(
            "CANONICAL_OHLCV_BUILD_COMPLETED",
            "Canonical OHLCV validation completed.",
            extra={
                "canonical_count": canonical_count,
                "interval": interval,
                "rejected_count": rejected,
                "symbol": symbol or "ALL",
            },
        )
        logger.info(
            "Canonical OHLCV built: upserted=%d rejected=%d symbol=%s interval=%s",
            canonical_count,
            rejected,
            symbol or "ALL",
            interval,
        )
        return {"upserted": canonical_count, "rejected": rejected}
    except Exception:  # noqa: BLE001
        if transaction_started:
            conn.execute("ROLLBACK")
        log_audit(
            "CANONICAL_OHLCV_BUILD_FAILED",
            "Canonical OHLCV validation failed.",
            status="FAILED",
            extra={"interval": interval, "symbol": symbol or "ALL"},
        )
        raise

"""Audit-aware orchestration for validation-gated canonical OHLCV promotion."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from datetime import date, datetime

import duckdb

from vnalpha.core.logging import get_logger
from vnalpha.ingestion.canonical_quarantine import persist_quarantine
from vnalpha.ingestion.canonical_storage import (
    delete_canonical_bar,
    delete_stray_intraday_canonical_rows,
    load_ranked_candidates,
    resolve_quarantines,
    upsert_canonical,
)
from vnalpha.ingestion.canonical_validation import (
    CanonicalCandidate,
    validate_candidate,
)
from vnalpha.ingestion.index_provider_policy import resolve_index_provider_conflict
from vnalpha.observability.audit import log_audit
from vnalpha.observability.context import get_correlation_id, set_correlation_id
from vnalpha.warehouse.transaction import warehouse_transaction

logger = get_logger("ingestion.build_canonical")


def build_canonical_ohlcv(
    conn: duckdb.DuckDBPyConnection,
    symbol: str | None = None,
    interval: str = "1D",
    *,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, int]:
    """Promote only validated raw OHLCV observations into canonical storage.

    The highest-ranked raw candidate for each bar is the sole candidate that
    can be promoted. If it violates a severe validation rule, its evidence is
    quarantined and any canonical bar for that key is removed.
    """

    if (start is None) != (end is None):
        raise ValueError("canonical promotion range requires both start and end")
    if start is not None and end is not None:
        if date.fromisoformat(start) > date.fromisoformat(end):
            raise ValueError("canonical promotion range start must not exceed end")
    if get_correlation_id() in {"", "unset"}:
        set_correlation_id()
    log_audit(
        "CANONICAL_OHLCV_BUILD_STARTED",
        "Canonical OHLCV validation started.",
        extra={
            "interval": interval,
            "symbol": symbol or "ALL",
            "start": start,
            "end": end,
        },
    )
    try:
        with warehouse_transaction(conn):
            grouped: defaultdict[
                tuple[str, datetime, str], list[CanonicalCandidate]
            ] = defaultdict(list)
            for candidate in load_ranked_candidates(
                conn, symbol, interval, start=start, end=end
            ):
                grouped[
                    (candidate.symbol, candidate.timestamp, candidate.interval)
                ].append(candidate)

            rejected = 0
            upserted = 0
            for candidates in grouped.values():
                selected_candidate = _select_canonical_candidate(tuple(candidates))
                peer_candidates = tuple(
                    candidate
                    for candidate in candidates
                    if candidate is not selected_candidate
                )
                rules = validate_candidate(selected_candidate, peer_candidates)
                if rules:
                    persist_quarantine(conn, selected_candidate, rules)
                    delete_canonical_bar(conn, selected_candidate)
                    rejected += 1
                else:
                    upsert_canonical(
                        conn, replace(selected_candidate, quality_status="pass")
                    )
                    resolve_quarantines(conn, selected_candidate)
                    upserted += 1

            if interval == "1D" and start is None:
                delete_stray_intraday_canonical_rows(conn, symbol, interval)
        log_audit(
            "CANONICAL_OHLCV_BUILD_COMPLETED",
            "Canonical OHLCV validation completed.",
            extra={
                "canonical_count": upserted,
                "interval": interval,
                "rejected_count": rejected,
                "symbol": symbol or "ALL",
            },
        )
        logger.info(
            "Canonical OHLCV built: upserted=%d rejected=%d symbol=%s interval=%s",
            upserted,
            rejected,
            symbol or "ALL",
            interval,
        )
        return {"upserted": upserted, "rejected": rejected}
    except Exception:  # noqa: BLE001
        log_audit(
            "CANONICAL_OHLCV_BUILD_FAILED",
            "Canonical OHLCV validation failed.",
            status="FAILED",
            extra={
                "interval": interval,
                "symbol": symbol or "ALL",
                "start": start,
                "end": end,
            },
        )
        raise


def _select_canonical_candidate(
    candidates: tuple[CanonicalCandidate, ...],
) -> CanonicalCandidate:
    provider_candidates = tuple(
        candidate.provider for candidate in candidates if candidate.provider
    )
    resolution = resolve_index_provider_conflict(
        candidates[0].symbol, provider_candidates
    )
    if resolution is None:
        return candidates[0]
    return next(
        (
            candidate
            for candidate in candidates
            if candidate.provider
            and candidate.provider.strip().lower() == resolution.selected_provider
        ),
        candidates[0],
    )

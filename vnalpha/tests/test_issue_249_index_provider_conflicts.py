"""Tests for issue #249 index-provider conflict handling and auditability."""

from __future__ import annotations

import json
from datetime import datetime

import duckdb

from vnalpha.ingestion.canonical_storage import upsert_canonical
from vnalpha.ingestion.canonical_validation import (
    CanonicalCandidate,
    CanonicalValidationRule,
    validate_candidate,
)
from vnalpha.ingestion.index_provider_policy import (
    INDEX_PROVIDER_POLICY_VERSION,
    is_index_symbol,
    resolve_index_provider_conflict,
)
from vnalpha.warehouse.migrations import run_migrations


def _candidate(
    symbol: str,
    provider: str,
    *,
    open_value: float,
    high: float = 1803.14,
    low: float = 1780.30,
    close: float = 1787.45,
    volume: float = 436669396.0,
    run_id: str = "test-run",
    timestamp: datetime | None = None,
) -> CanonicalCandidate:
    return CanonicalCandidate(
        symbol=symbol,
        timestamp=timestamp or datetime(2026, 7, 17, 9, 0),
        interval="1D",
        open=open_value,
        high=high,
        low=low,
        close=close,
        volume=volume,
        provider=provider,
        price_basis="RAW_UNADJUSTED",
        quality_status="PASS",
        ingestion_run_id=run_id,
    )


def test_index_recognition_is_explicit() -> None:
    assert is_index_symbol("VNINDEX")
    assert is_index_symbol(" vn30 ")
    assert is_index_symbol("HNXINDEX")
    assert is_index_symbol("UPCOMINDEX")
    assert not is_index_symbol("VCB")


def test_hose_policy_resolves_exact_issue_249_conflict() -> None:
    resolution = resolve_index_provider_conflict("VNINDEX", ("vci", "kbs"))
    assert resolution is not None
    assert resolution.selected_provider == "vci"
    assert resolution.rejected_providers == ("kbs",)
    assert resolution.policy_family == "HOSE"
    assert resolution.policy_version == INDEX_PROVIDER_POLICY_VERSION
    assert "audit" in resolution.rationale.lower()


def test_hose_policy_falls_to_next_registered_candidate() -> None:
    resolution = resolve_index_provider_conflict("VNINDEX", ("kbs", "ssi"))
    assert resolution is not None
    assert resolution.selected_provider == "kbs"
    assert resolution.rejected_providers == ("ssi",)


def test_hnx_and_upcom_do_not_inherit_hose_precedence() -> None:
    assert resolve_index_provider_conflict("HNXINDEX", ("vci", "kbs")) is None
    assert resolve_index_provider_conflict("UPCOMINDEX", ("vci", "kbs")) is None


def test_no_resolution_for_equity_or_unknown_providers() -> None:
    assert resolve_index_provider_conflict("VCB", ("vci", "kbs")) is None
    assert resolve_index_provider_conflict("VNINDEX", ("unknown1", "unknown2")) is None


def test_vnindex_preferred_candidate_passes_and_peer_is_rejected() -> None:
    vci = _candidate("VNINDEX", "vci", open_value=1801.89, run_id="vci-run")
    kbs = _candidate(
        "VNINDEX",
        "kbs",
        open_value=1804.24,
        high=1804.24,
        low=1779.58,
        run_id="kbs-run",
    )
    assert CanonicalValidationRule.PROVIDER_CONSISTENCY not in validate_candidate(
        vci, peer_candidates=(kbs,)
    )
    assert CanonicalValidationRule.PROVIDER_CONSISTENCY in validate_candidate(
        kbs, peer_candidates=(vci,)
    )


def test_regular_equity_still_requires_strict_consistency() -> None:
    vci = _candidate(
        "VCB",
        "vci",
        open_value=100.0,
        high=102.0,
        low=99.0,
        close=101.0,
        volume=1_000_000,
    )
    kbs = _candidate(
        "VCB",
        "kbs",
        open_value=100.5,
        high=102.0,
        low=99.0,
        close=101.0,
        volume=1_000_000,
    )
    assert CanonicalValidationRule.PROVIDER_CONSISTENCY in validate_candidate(
        vci, peer_candidates=(kbs,)
    )
    assert CanonicalValidationRule.PROVIDER_CONSISTENCY in validate_candidate(
        kbs, peer_candidates=(vci,)
    )


def test_agreeing_index_providers_need_no_selection_audit() -> None:
    vci = _candidate("VNINDEX", "vci", open_value=1787.45)
    kbs = _candidate("VNINDEX", "kbs", open_value=1787.45)
    assert CanonicalValidationRule.PROVIDER_CONSISTENCY not in validate_candidate(
        vci, peer_candidates=(kbs,)
    )


def test_canonical_index_conflict_persists_exact_selection_audit() -> None:
    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn, emit_observability=False)
    conn.executemany(
        """
        INSERT INTO market_ohlcv_raw (
            ingestion_run_id, symbol, time, interval, open, high, low, close,
            volume, provider, price_basis, quality_status, fetched_at
        ) VALUES (?, 'VNINDEX', ?, '1D', ?, ?, ?, 1787.45, 436669396,
                  ?, 'RAW_UNADJUSTED', 'PASS', current_timestamp)
        """,
        [
            (
                "vci-run",
                "2026-07-17 09:00:00",
                1801.89,
                1803.14,
                1780.30,
                "VCI",
            ),
            (
                "kbs-run",
                "2026-07-17 10:00:00",
                1804.24,
                1804.24,
                1779.58,
                "KBS",
            ),
        ],
    )
    selected = _candidate(
        "VNINDEX",
        "vci",
        open_value=1801.89,
        run_id="vci-run",
        timestamp=datetime(2026, 7, 17),
    )
    upsert_canonical(conn, selected)

    canonical = conn.execute(
        """
        SELECT selected_provider, selection_audit_id
        FROM canonical_ohlcv WHERE symbol = 'VNINDEX'
        """
    ).fetchone()
    assert canonical[0].lower() == "vci"
    assert canonical[1]

    audit = conn.execute(
        """
        SELECT selected_provider, rejected_providers_json,
               candidate_values_json, policy_version, policy_family,
               evidence_refs_json, content_hash
        FROM canonical_selection_audit WHERE audit_id = ?
        """,
        [canonical[1]],
    ).fetchone()
    assert audit[0] == "vci"
    assert json.loads(audit[1]) == ["kbs"]
    observations = json.loads(audit[2])
    assert {item["provider"] for item in observations} == {"vci", "kbs"}
    assert {item["ingestion_run_id"] for item in observations} == {
        "vci-run",
        "kbs-run",
    }
    assert audit[3] == INDEX_PROVIDER_POLICY_VERSION
    assert audit[4] == "HOSE"
    assert len(json.loads(audit[5])) == 2
    assert len(audit[6]) == 64

    upsert_canonical(conn, selected)
    assert (
        conn.execute("SELECT COUNT(*) FROM canonical_selection_audit").fetchone()[0]
        == 1
    )
    conn.close()


def test_non_index_canonical_bar_has_no_selection_audit() -> None:
    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn, emit_observability=False)
    candidate = _candidate(
        "VCB",
        "vci",
        open_value=100.0,
        high=102.0,
        low=99.0,
        close=101.0,
        volume=1_000_000,
        timestamp=datetime(2026, 7, 17),
    )
    upsert_canonical(conn, candidate)
    assert conn.execute(
        "SELECT selection_audit_id FROM canonical_ohlcv WHERE symbol = 'VCB'"
    ).fetchone() == (None,)
    assert (
        conn.execute("SELECT COUNT(*) FROM canonical_selection_audit").fetchone()[0]
        == 0
    )
    conn.close()

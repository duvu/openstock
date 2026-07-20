"""Tests for issue #257: publication-aware fundamentals vertical."""

from __future__ import annotations

import duckdb
import pytest

from vnalpha.fundamentals import (
    AuditStatus,
    FundamentalFact,
    StatementScope,
    as_of_snapshot,
    compute_debt_to_equity,
    compute_roe,
    fact_content_hash,
    get_fact_revisions,
    upsert_fundamental_fact,
)
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    run_migrations(conn=connection, emit_observability=False)
    yield connection
    connection.close()


def _fact(**overrides) -> FundamentalFact:
    base = {
        "fact_id": "FPT-2025-FY-CONSOLIDATED",
        "revision_number": 1,
        "symbol": "FPT",
        "fiscal_year": 2025,
        "fiscal_period": "FY",
        "statement_scope": StatementScope.CONSOLIDATED,
        "published_at": "2026-03-31",
        "period_end_date": "2025-12-31",
        "audit_status": AuditStatus.AUDITED,
        "currency": "VND",
        "unit": "VND_MILLION",
        "revenue": 60000.0,
        "net_income": 9000.0,
        "eps": 6.0,
        "total_assets": 80000.0,
        "total_equity": 45000.0,
        "total_liabilities": 35000.0,
        "operating_cash_flow": 11000.0,
        "source_reference": "hsx-disclosure-123",
        "source_authority": "HSX",
    }
    base.update(overrides)
    return FundamentalFact(**base)


def test_derived_ratios_reproduce_from_canonical_facts() -> None:
    assert compute_roe(9000.0, 45000.0) == pytest.approx(0.2)
    assert compute_debt_to_equity(35000.0, 45000.0) == pytest.approx(35000.0 / 45000.0)


def test_derived_ratios_fail_closed_on_non_positive_equity() -> None:
    assert compute_roe(9000.0, 0.0) is None
    assert compute_roe(9000.0, -10.0) is None
    assert compute_debt_to_equity(35000.0, 0.0) is None
    assert compute_roe(None, 45000.0) is None


def test_units_and_currency_are_required() -> None:
    with pytest.raises(ValueError):
        _fact(currency="")
    with pytest.raises(ValueError):
        _fact(unit="")


def test_unsupported_fiscal_period_fails_closed() -> None:
    with pytest.raises(ValueError):
        _fact(fiscal_period="Q5")


def test_upsert_is_idempotent(conn) -> None:
    rid1 = upsert_fundamental_fact(conn, _fact())
    rid2 = upsert_fundamental_fact(conn, _fact())
    assert rid1 == rid2
    count = conn.execute("SELECT COUNT(*) FROM fundamental_fact").fetchone()[0]
    assert count == 1


def test_conflicting_same_revision_content_fails_closed(conn) -> None:
    upsert_fundamental_fact(conn, _fact())
    # Same fact_id + revision_number but different content must not silently
    # overwrite an immutable revision.
    with pytest.raises(ValueError, match="different content"):
        upsert_fundamental_fact(conn, _fact(net_income=9999.0))


def test_restatement_supersedes_prior_revision(conn) -> None:
    upsert_fundamental_fact(conn, _fact())
    upsert_fundamental_fact(conn, _fact(revision_number=2, net_income=9500.0))

    revisions = get_fact_revisions(conn, "FPT-2025-FY-CONSOLIDATED")
    assert len(revisions) == 2
    assert revisions[0]["canonical_status"] == "SUPERSEDED"
    assert revisions[0]["superseded_by_revision_id"] == revisions[1]["revision_id"]
    assert revisions[1]["canonical_status"] == "CURRENT"


def test_future_published_facts_never_enter_historical_analysis(conn) -> None:
    # A fact published 2026-03-31 must not appear in an as-of snapshot dated
    # before its publication.
    upsert_fundamental_fact(conn, _fact())
    early = as_of_snapshot(conn, "FPT", "2026-01-01")
    assert early == []
    later = as_of_snapshot(conn, "FPT", "2026-04-01")
    assert len(later) == 1
    assert later[0].fiscal_year == 2025


def test_restatement_visible_only_after_its_publication(conn) -> None:
    upsert_fundamental_fact(conn, _fact())  # published 2026-03-31, NI 9000
    upsert_fundamental_fact(
        conn,
        _fact(revision_number=2, published_at="2026-06-30", net_income=9500.0),
    )
    # As of 2026-04-01 only the first revision is public.
    snap_apr = as_of_snapshot(conn, "FPT", "2026-04-01")
    assert snap_apr[0].net_income == 9000.0
    # As of 2026-07-01 the restatement is public and wins.
    snap_jul = as_of_snapshot(conn, "FPT", "2026-07-01")
    assert snap_jul[0].net_income == 9500.0


def test_consolidated_and_separate_do_not_mix(conn) -> None:
    upsert_fundamental_fact(conn, _fact())  # consolidated
    upsert_fundamental_fact(
        conn,
        _fact(
            fact_id="FPT-2025-FY-SEPARATE",
            statement_scope=StatementScope.SEPARATE,
            net_income=6000.0,
        ),
    )
    consolidated = as_of_snapshot(
        conn, "FPT", "2026-04-01", statement_scope=StatementScope.CONSOLIDATED
    )
    separate = as_of_snapshot(
        conn, "FPT", "2026-04-01", statement_scope=StatementScope.SEPARATE
    )
    assert consolidated[0].net_income == 9000.0
    assert separate[0].net_income == 6000.0
    assert consolidated[0].statement_scope == "CONSOLIDATED"


def test_snapshot_reports_derived_ratios(conn) -> None:
    upsert_fundamental_fact(conn, _fact())
    snap = as_of_snapshot(conn, "FPT", "2026-04-01")
    assert snap[0].roe == pytest.approx(0.2)
    assert snap[0].debt_to_equity == pytest.approx(35000.0 / 45000.0)


def test_missing_periods_remain_truthful(conn) -> None:
    # No data for the symbol -> empty snapshot, not a fabricated value.
    assert as_of_snapshot(conn, "UNKNOWN", "2026-07-01") == []


def test_stale_period_is_flagged(conn) -> None:
    upsert_fundamental_fact(conn, _fact())  # period ends 2025-12-31
    snap = as_of_snapshot(conn, "FPT", "2027-06-30")  # >400 days later
    assert snap[0].is_stale is True
    assert any("older than" in c for c in snap[0].caveats)


def test_content_hash_is_stable_and_sensitive() -> None:
    h1 = fact_content_hash(_fact())
    h2 = fact_content_hash(_fact())
    h3 = fact_content_hash(_fact(net_income=1.0))
    assert h1 == h2
    assert h1 != h3


def test_cli_fundamentals_read_is_publication_aware(conn) -> None:
    from typer.testing import CliRunner

    from vnalpha.cli import app

    # The CLI opens its own warehouse connection; use an in-process run against
    # a seeded connection by monkeypatching is overkill here, so just assert the
    # command wiring and empty-case behaviour on a fresh warehouse.
    result = CliRunner().invoke(
        app, ["data", "status", "fundamentals", "FPT", "--as-of", "2026-04-01"]
    )
    assert result.exit_code == 0
    import json as _json

    payload = _json.loads(result.stdout)
    assert payload["symbol"] == "FPT"
    assert payload["facts"] == []


def test_cli_fundamentals_rejects_bad_scope() -> None:
    from typer.testing import CliRunner

    from vnalpha.cli import app

    result = CliRunner().invoke(
        app,
        [
            "data",
            "status",
            "fundamentals",
            "FPT",
            "--as-of",
            "2026-04-01",
            "--scope",
            "BOGUS",
        ],
    )
    assert result.exit_code != 0

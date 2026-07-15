from dataclasses import dataclass
from datetime import date

import pytest

from vnalpha.data_availability.ohlcv_gap_checks import (
    UnresolvedTrueGapWindow,
    count_unresolved_true_gaps,
)
from vnalpha.warehouse.connection import in_memory_connection
from vnalpha.warehouse.migrations import run_migrations


@pytest.fixture
def conn():
    connection = in_memory_connection()
    run_migrations(conn=connection)
    yield connection
    connection.close()


@dataclass(frozen=True, slots=True)
class GapObservationRow:
    symbol: str
    interval: str
    session_date: date
    gap_kind: str
    resolved_at: str | None


def test_gap_check_counts_only_unresolved_daily_true_gaps_in_window(conn) -> None:
    # Given
    for row in (
        GapObservationRow("FPT", "1D", date(2026, 9, 1), "PROVIDER_EMPTY", None),
        GapObservationRow("FPT", "1D", date(2026, 9, 2), "TRUE_GAP", None),
        GapObservationRow("FPT", "1D", date(2026, 9, 3), "TRUE_GAP", "2026-09-04"),
        GapObservationRow("FPT", "1D", date(2026, 8, 31), "TRUE_GAP", None),
        GapObservationRow("VNM", "1D", date(2026, 9, 2), "TRUE_GAP", None),
        GapObservationRow("FPT", "1H", date(2026, 9, 2), "TRUE_GAP", None),
    ):
        _insert_gap(conn, row)
    window = UnresolvedTrueGapWindow(
        symbol="FPT",
        lookback_start="2026-09-01",
        target_date="2026-09-03",
    )

    # When
    gap_count = count_unresolved_true_gaps(conn, window)

    # Then
    assert gap_count == 1


def _insert_gap(
    conn,
    row: GapObservationRow,
) -> None:
    conn.execute(
        """
        INSERT INTO ohlcv_gap_observation
            (symbol, interval, session_date, gap_kind, calendar_version,
             first_observed_at, last_observed_at, correlation_id, resolved_at)
        VALUES (?, ?, ?, ?, 'vn-session-v1', current_timestamp, current_timestamp,
                'corr-gap-check', ?)
        """,
        [row.symbol, row.interval, row.session_date, row.gap_kind, row.resolved_at],
    )

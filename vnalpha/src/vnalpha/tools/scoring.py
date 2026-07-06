"""candidate.explain and candidate.compare tools."""

from __future__ import annotations

import duckdb

from vnalpha.tools.models import ToolOutput


def explain_candidate(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    date: str,
) -> ToolOutput:
    """Return full persisted candidate score record for a symbol/date."""
    from vnalpha.warehouse.repositories import get_candidate_score

    record = get_candidate_score(conn, symbol, date)
    if record is None:
        return ToolOutput(
            data=None,
            summary=f"No candidate score found for {symbol} on {date}.",
            warnings=[f"Run 'vnalpha score --date {date}' to generate scores."],
        )
    return ToolOutput(
        data=record,
        summary=(
            f"{symbol}: score={record['score']:.3f} "
            f"class={record['candidate_class']} "
            f"setup={record['setup_type']}"
        ),
    )


def compare_candidates(
    conn: duckdb.DuckDBPyConnection,
    symbols: list[str],
    date: str,
) -> ToolOutput:
    """Compare a list of symbols using their persisted candidate scores."""
    from vnalpha.warehouse.repositories import get_candidate_score

    records = []
    missing = []
    for sym in symbols:
        rec = get_candidate_score(conn, sym, date)
        if rec is not None:
            records.append(rec)
        else:
            missing.append(sym)

    warnings = [f"No score for {m} on {date}" for m in missing]
    return ToolOutput(
        data=records,
        summary=f"Compared {len(records)} symbols on {date}.",
        warnings=warnings,
    )

from __future__ import annotations

from typing import Optional

import duckdb

from vnalpha.tools.models import ToolOutput


def fetch_symbol_data(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    interval: str = "1D",
) -> ToolOutput:
    from vnalpha.ingestion.build_canonical import build_canonical_ohlcv
    from vnalpha.ingestion.sync_ohlcv import sync_ohlcv

    sync_result = sync_ohlcv(conn, universe=[symbol], start=start, end=end, interval=interval)
    inserted_raw = sync_result.get("inserted", 0)

    canonical_result = build_canonical_ohlcv(conn, symbol=symbol, interval=interval)
    upserted = canonical_result.get("upserted", 0)
    rejected = canonical_result.get("rejected", 0)

    summary = (
        f"Fetched {symbol}: {inserted_raw} raw rows synced, "
        f"{upserted} canonical rows upserted, {rejected} rejected."
    )
    return ToolOutput(
        data={
            "symbol": symbol,
            "raw_inserted": inserted_raw,
            "canonical_upserted": upserted,
            "canonical_rejected": rejected,
            "run_id": sync_result.get("run_id"),
        },
        summary=summary,
    )

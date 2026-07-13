from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final

import duckdb

from vnalpha.research_automation.models import DatasetRef

_MIN_RESEARCH_ROWS: Final = 2


@dataclass(frozen=True, slots=True)
class DatasetResolution:
    dataset: DatasetRef
    sufficient: bool
    warnings: tuple[str, ...]


class DatasetResolver:
    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn

    def resolve_feature_snapshot(
        self,
        *,
        universe: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        interval: str = "1D",
        benchmark: str | None = None,
    ) -> DatasetResolution:
        clauses = ["1 = 1"]
        parameters: list[object] = []
        if start_date is not None:
            clauses.append("date >= ?")
            parameters.append(start_date)
        if end_date is not None:
            clauses.append("date <= ?")
            parameters.append(end_date)
        where = " AND ".join(clauses)
        row = self._conn.execute(
            "SELECT count(*), min(date), max(date), count(DISTINCT symbol), "
            "count(*) FILTER (WHERE feature_data_status IS NULL OR "
            "lower(feature_data_status) NOT IN ('good', 'ok', 'pass')) "
            f"FROM feature_snapshot WHERE {where}",
            parameters,
        ).fetchone()
        symbols = tuple(
            item[0]
            for item in self._conn.execute(
                f"SELECT DISTINCT symbol FROM feature_snapshot WHERE {where} ORDER BY symbol",
                parameters,
            ).fetchall()
        )
        row_count = int(row[0]) if row else 0
        period_start = row[1] if row else None
        period_end = row[2] if row else None
        symbol_count = int(row[3]) if row else 0
        low_quality_rows = int(row[4]) if row else 0
        warnings: list[str] = []
        if row_count < _MIN_RESEARCH_ROWS:
            warnings.append(
                f"Insufficient dataset coverage: {row_count} rows; at least {_MIN_RESEARCH_ROWS} required."
            )
        if low_quality_rows:
            warnings.append(f"{low_quality_rows} rows have non-good data quality.")
        if universe:
            warnings.append(
                f"Universe {universe.upper()} is recorded as a research scope; warehouse rows are the persisted members available."
            )
        quality_status = {
            "status": "good"
            if not warnings or row_count >= _MIN_RESEARCH_ROWS and not low_quality_rows
            else "warning",
            "warnings": tuple(warnings),
            "symbol_count": symbol_count,
            "period_start": str(period_start) if period_start else None,
            "period_end": str(period_end) if period_end else None,
            "benchmark": benchmark,
        }
        snapshot_id = self._snapshot_id(period_end, row_count)
        return DatasetResolution(
            dataset=DatasetRef(
                dataset_name="feature_snapshot",
                snapshot_id=snapshot_id,
                symbols=symbols,
                start_date=period_start,
                end_date=period_end,
                interval=interval,
                row_count=row_count,
                quality_status=quality_status,
            ),
            sufficient=row_count >= _MIN_RESEARCH_ROWS,
            warnings=tuple(warnings),
        )

    @staticmethod
    def _snapshot_id(period_end: date | None, row_count: int) -> str:
        suffix = period_end.isoformat() if period_end else "empty"
        return f"feature-snapshot-{suffix}-{row_count}"


__all__ = ["DatasetResolution", "DatasetResolver"]

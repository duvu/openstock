from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final

import duckdb

from vnalpha.features.status import (
    FEATURE_STATUS_CONTRACT_VERSION,
    FeatureDataStatus,
    FeatureExclusionReason,
    parse_feature_eligibility,
)
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
            "SELECT count(*), min(date), max(date), count(DISTINCT symbol) "
            f"FROM feature_snapshot WHERE {where}",
            parameters,
        ).fetchone()
        status_rows = self._conn.execute(
            "SELECT feature_data_status, count(*) FROM feature_snapshot "
            f"WHERE {where} GROUP BY feature_data_status",
            parameters,
        ).fetchall()
        symbols = tuple(
            item[0]
            for item in self._conn.execute(
                f"SELECT DISTINCT symbol FROM feature_snapshot WHERE {where} "
                "AND upper(trim(coalesce(feature_data_status, ''))) = ? "
                "ORDER BY symbol",
                [*parameters, FeatureDataStatus.EXACT_DATE.value],
            ).fetchall()
        )
        row_count = int(row[0]) if row else 0
        period_start = row[1] if row else None
        period_end = row[2] if row else None
        symbol_count = int(row[3]) if row else 0
        eligible_rows = 0
        exclusion_counts: dict[str, int] = {}
        for raw_status, count in status_rows:
            eligibility = parse_feature_eligibility(
                str(raw_status) if raw_status is not None else None
            )
            if eligibility.eligible:
                eligible_rows += int(count)
                continue
            reason = (
                eligibility.exclusion_reason
                or FeatureExclusionReason.UNKNOWN_FEATURE_STATUS
            )
            exclusion_counts[reason.value] = exclusion_counts.get(
                reason.value, 0
            ) + int(count)
        warnings: list[str] = []
        if eligible_rows < _MIN_RESEARCH_ROWS:
            warnings.append(
                "Insufficient eligible dataset coverage: "
                f"{eligible_rows} rows; at least {_MIN_RESEARCH_ROWS} required."
            )
        for reason, count in sorted(exclusion_counts.items()):
            warnings.append(f"{count} feature rows excluded: {reason}.")
        if universe:
            warnings.append(
                f"Universe {universe.upper()} is recorded as a research scope; warehouse rows are the persisted members available."
            )
        quality_status = {
            "status": "good"
            if eligible_rows >= _MIN_RESEARCH_ROWS and not exclusion_counts
            else "warning",
            "warnings": tuple(warnings),
            "symbol_count": symbol_count,
            "eligible_row_count": eligible_rows,
            "excluded_row_count": row_count - eligible_rows,
            "exclusion_counts": exclusion_counts,
            "feature_status_contract_version": FEATURE_STATUS_CONTRACT_VERSION,
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
            sufficient=eligible_rows >= _MIN_RESEARCH_ROWS,
            warnings=tuple(warnings),
        )

    @staticmethod
    def _snapshot_id(period_end: date | None, row_count: int) -> str:
        suffix = period_end.isoformat() if period_end else "empty"
        return f"feature-snapshot-{suffix}-{row_count}"


__all__ = ["DatasetResolution", "DatasetResolver"]

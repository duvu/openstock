from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import TypeAlias

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


class SymbolIngestionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    EMPTY = "EMPTY"
    FAILED = "FAILED"
    INVALID = "INVALID"
    SKIPPED = "SKIPPED"


class BatchIngestionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class IngestionErrorCategory(str, Enum):
    CONNECTION = "CONNECTION"
    TIMEOUT = "TIMEOUT"
    HTTP = "HTTP"
    INVALID_JSON = "INVALID_JSON"
    INVALID_DATA = "INVALID_DATA"
    PROVIDER_DATA = "PROVIDER_DATA"
    PROVIDER = "PROVIDER"
    STORAGE = "STORAGE"


class IngestionRemediationAction(str, Enum):
    RETRY_OHLCV = "RETRY_OHLCV"
    VERIFY_RANGE_AND_RETRY = "VERIFY_RANGE_AND_RETRY"
    INSPECT_DIAGNOSTICS_AND_RETRY = "INSPECT_DIAGNOSTICS_AND_RETRY"


@dataclass(frozen=True, slots=True)
class IngestionRemediationStep:
    action: IngestionRemediationAction
    command: tuple[str, ...]
    guidance: str

    def render_command(self) -> str:
        return " ".join(self.command)

    def to_payload(self) -> dict[str, JsonValue]:
        return {
            "action": self.action.value,
            "command": self.render_command(),
            "guidance": self.guidance,
        }


@dataclass(frozen=True, slots=True)
class SymbolIngestionResult:
    symbol: str
    status: SymbolIngestionStatus
    requested_start: str | None
    requested_end: str | None
    provider: str
    rows_received: int = 0
    rows_inserted: int = 0
    error_category: IngestionErrorCategory | None = None
    retryable: bool = False
    diagnostics_ref: str | None = None
    message: str | None = None
    remediation: str | None = None
    remediation_steps: tuple[IngestionRemediationStep, ...] = ()
    attempts: int = 1
    quality_report: dict[str, JsonValue] = field(default_factory=dict)
    diagnostics: dict[str, JsonValue] = field(default_factory=dict)

    def to_payload(self) -> dict[str, JsonValue]:
        return {
            "symbol": self.symbol,
            "status": self.status.value,
            "requested_start": self.requested_start,
            "requested_end": self.requested_end,
            "provider": self.provider,
            "rows_received": self.rows_received,
            "rows_inserted": self.rows_inserted,
            "error_category": (
                self.error_category.value if self.error_category is not None else None
            ),
            "retryable": self.retryable,
            "diagnostics_ref": self.diagnostics_ref,
            "message": self.message,
            "remediation": self.remediation,
            "remediation_steps": [step.to_payload() for step in self.remediation_steps],
            "attempts": self.attempts,
            "quality_report": self.quality_report,
            "diagnostics": self.diagnostics,
        }


@dataclass(frozen=True, slots=True)
class OHLCVBatchResult(Mapping[str, JsonValue]):
    run_id: str
    status: BatchIngestionStatus
    symbol_results: tuple[SymbolIngestionResult, ...]
    terminal_reason: str

    @property
    def requested_count(self) -> int:
        return len(self.symbol_results)

    def count(self, status: SymbolIngestionStatus) -> int:
        return sum(result.status is status for result in self.symbol_results)

    @property
    def rows_inserted(self) -> int:
        return sum(result.rows_inserted for result in self.symbol_results)

    def to_payload(self) -> dict[str, JsonValue]:
        skipped_count = self.count(SymbolIngestionStatus.SKIPPED)
        return {
            "run_id": self.run_id,
            "status": self.status.value,
            "total": self.requested_count,
            "inserted": self.rows_inserted,
            "skipped": skipped_count,
            "requested_count": self.requested_count,
            "success_count": self.count(SymbolIngestionStatus.SUCCESS),
            "empty_count": self.count(SymbolIngestionStatus.EMPTY),
            "failed_count": self.count(SymbolIngestionStatus.FAILED),
            "invalid_count": self.count(SymbolIngestionStatus.INVALID),
            "skipped_count": skipped_count,
            "failed_symbols": [
                result.symbol
                for result in self.symbol_results
                if result.status is SymbolIngestionStatus.FAILED
            ],
            "empty_symbols": [
                result.symbol
                for result in self.symbol_results
                if result.status is SymbolIngestionStatus.EMPTY
            ],
            "invalid_symbols": [
                result.symbol
                for result in self.symbol_results
                if result.status is SymbolIngestionStatus.INVALID
            ],
            "skipped_symbols": [
                result.symbol
                for result in self.symbol_results
                if result.status is SymbolIngestionStatus.SKIPPED
            ],
            "symbol_results": [result.to_payload() for result in self.symbol_results],
            "terminal_reason": self.terminal_reason,
        }

    def __getitem__(self, key: str) -> JsonValue:
        return self.to_payload()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.to_payload())

    def __len__(self) -> int:
        return len(self.to_payload())


def aggregate_ohlcv_results(
    run_id: str, results: tuple[SymbolIngestionResult, ...]
) -> OHLCVBatchResult:
    completed = sum(
        result.status in {SymbolIngestionStatus.SUCCESS, SymbolIngestionStatus.SKIPPED}
        for result in results
    )
    problems = len(results) - completed
    if not results:
        status = BatchIngestionStatus.FAILED
        reason = "no_symbols_requested"
    elif problems == 0:
        status = BatchIngestionStatus.SUCCESS
        reason = "all_required_symbols_completed"
    elif completed > 0:
        status = BatchIngestionStatus.PARTIAL
        reason = "mixed_symbol_outcomes"
    else:
        status = BatchIngestionStatus.FAILED
        reason = "no_required_symbol_completed"
    return OHLCVBatchResult(
        run_id=run_id,
        status=status,
        symbol_results=results,
        terminal_reason=reason,
    )

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from vnalpha.data_availability.artifact_readiness_models import ReadinessCapability
from vnalpha.data_provisioning.current_symbol_application import (
    CurrentSymbolResearchApplication,
    CurrentSymbolResearchRequest,
)
from vnalpha.data_provisioning.current_symbol_queue_wait import (
    CurrentSymbolWaitMode,
    default_current_symbol_wait_timeout_seconds,
)
from vnalpha.data_provisioning.current_symbol_result import (
    CurrentSymbolResearchResult,
    CurrentSymbolResearchStatus,
)
from vnalpha.provisioning_queue import DEFAULT_QUEUE_PATH
from vnalpha.provisioning_queue.models import GoalEnrichment
from vnalpha.tools.errors import ToolExecutionError
from vnalpha.tools.models import ToolOutput
from vnalpha.tools.research_intelligence import deep_symbol_analysis
from vnalpha.warehouse.connection import read_connection


def current_symbol_research(
    *,
    warehouse_path: Path | str | None,
    symbol: str,
    date: str | None = None,
    requested_capability: ReadinessCapability = ReadinessCapability.CANDIDATE_RANKING,
    priority: int = 1,
    force_refresh: bool = False,
    company_context: bool = False,
    historical: bool = False,
    wait_mode: CurrentSymbolWaitMode = CurrentSymbolWaitMode.WAIT_UP_TO,
    wait_timeout_seconds: float | None = None,
    origin: str | None = None,
    correlation_id: str | None = None,
    queue_path: Path | None = DEFAULT_QUEUE_PATH,
) -> ToolOutput:
    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol:
        raise ToolExecutionError("analysis.current_symbol requires 'symbol'.")
    resolved_wait_mode = _wait_mode(wait_mode)
    resolved_timeout_seconds = (
        default_current_symbol_wait_timeout_seconds()
        if wait_timeout_seconds is None
        else wait_timeout_seconds
    )
    result = CurrentSymbolResearchApplication(
        warehouse_path=warehouse_path,
        queue_path=queue_path,
    ).execute(
        CurrentSymbolResearchRequest(
            symbol=normalized_symbol,
            effective_date=date,
            requested_capability=_capability(requested_capability),
            priority=priority,
            force_refresh=force_refresh,
            requested_enrichments=(
                (GoalEnrichment.COMPANY_CONTEXT,) if company_context else ()
            ),
            historical=historical,
            wait_mode=resolved_wait_mode,
            wait_timeout_seconds=resolved_timeout_seconds,
            origin=origin,
            correlation_id=correlation_id,
        )
    )
    payload: dict[str, Any] = {
        "tool": "analysis.current_symbol",
        "status": result.status.value,
        "provisioning": _result_payload(result),
        "wait": {
            "mode": resolved_wait_mode.value,
            "timeout_seconds": resolved_timeout_seconds,
        },
        "analysis": None,
    }
    if result.status in {
        CurrentSymbolResearchStatus.READY,
        CurrentSymbolResearchStatus.DEGRADED,
    }:
        with read_connection(warehouse_path) as connection:
            analysis = deep_symbol_analysis(
                connection,
                normalized_symbol,
                date=result.effective_date,
            )
        analysis_data = dict(analysis.data) if isinstance(analysis.data, dict) else {}
        if result.status is CurrentSymbolResearchStatus.DEGRADED:
            analysis_data = _price_only_payload(analysis_data)
        payload.update(analysis_data)
        payload["tool"] = "analysis.current_symbol"
        payload["analysis"] = analysis_data
        return ToolOutput(
            data=payload,
            summary=analysis.summary,
            warnings=list(analysis.warnings),
        )
    return ToolOutput(
        data=payload,
        summary=f"Current-symbol research status: {result.status.value}.",
        warnings=[
            f"Deterministic analysis is unavailable while status is {result.status.value}."
        ],
    )


def _capability(value: ReadinessCapability | str) -> ReadinessCapability:
    if isinstance(value, ReadinessCapability):
        return value
    try:
        return ReadinessCapability(str(value).strip().upper())
    except ValueError as exc:
        raise ToolExecutionError(f"Unsupported readiness capability: {value}.") from exc


def _wait_mode(value: CurrentSymbolWaitMode | str) -> CurrentSymbolWaitMode:
    if isinstance(value, CurrentSymbolWaitMode):
        return value
    try:
        return CurrentSymbolWaitMode(str(value).strip().upper())
    except ValueError as exc:
        raise ToolExecutionError(f"Unsupported wait mode: {value}.") from exc


def _result_payload(result: CurrentSymbolResearchResult) -> dict[str, Any]:
    data = asdict(result)
    data["status"] = result.status.value
    data["provisioning"] = result.provisioning.value
    data["requested_capability"] = result.requested_capability.value
    data["effective_capability"] = (
        result.effective_capability.value if result.effective_capability else None
    )
    data["company_context"] = (
        result.company_context.to_dict() if result.company_context is not None else None
    )
    return data


def _price_only_payload(data: dict[str, Any]) -> dict[str, Any]:
    for key in ("candidate", "feature_context", "market_context", "sector_context"):
        data.pop(key, None)
    data["claims"] = {
        "candidate_ranking": False,
        "score": False,
        "benchmark": False,
    }
    return data


__all__ = ["current_symbol_research"]

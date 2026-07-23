from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from vnalpha.data_availability.artifact_readiness_models import ReadinessCapability
from vnalpha.data_provisioning.current_symbol_queue_wait import (
    CurrentSymbolWaitMode,
    default_current_symbol_wait_timeout_seconds,
)
from vnalpha.data_provisioning.current_symbol_result import CurrentSymbolResearchStatus
from vnalpha.provisioning_queue import DEFAULT_QUEUE_PATH
from vnalpha.tools.current_symbol_research import current_symbol_research
from vnalpha.tools.errors import ToolExecutionError


def register(app: typer.Typer) -> None:
    @app.command("current-symbol")
    def current_symbol(
        symbol: Annotated[str, typer.Argument(help="Equity symbol.")],
        date: Annotated[str | None, typer.Option("--date")] = None,
        capability: Annotated[
            ReadinessCapability, typer.Option("--capability")
        ] = ReadinessCapability.CANDIDATE_RANKING,
        priority: Annotated[int, typer.Option("--priority", min=0, max=1000)] = 1,
        force_refresh: Annotated[bool, typer.Option("--force-refresh")] = False,
        company_context: Annotated[bool, typer.Option("--company-context")] = False,
        historical: Annotated[bool, typer.Option("--historical")] = False,
        wait: Annotated[bool, typer.Option("--wait")] = False,
        wait_timeout: Annotated[
            float | None, typer.Option("--wait-timeout", min=0)
        ] = None,
        no_wait: Annotated[bool, typer.Option("--no-wait")] = False,
        warehouse_path: Annotated[Path | None, typer.Option("--warehouse-path")] = None,
        queue_path: Annotated[Path, typer.Option("--queue-path")] = DEFAULT_QUEUE_PATH,
        json_output: Annotated[bool, typer.Option("--json")] = False,
    ) -> None:
        wait_mode, timeout_seconds = _wait_policy(
            wait=wait,
            wait_timeout=wait_timeout,
            no_wait=no_wait,
        )
        try:
            output = current_symbol_research(
                warehouse_path=warehouse_path,
                symbol=symbol,
                date=date,
                requested_capability=capability,
                priority=priority,
                force_refresh=force_refresh,
                company_context=company_context,
                historical=historical,
                wait_mode=wait_mode,
                wait_timeout_seconds=timeout_seconds,
                origin="cli",
                queue_path=queue_path,
            )
        except ToolExecutionError as error:
            typer.echo(f"Current-symbol research failed: {error}", err=True)
            raise typer.Exit(code=1) from error
        payload = output.data if isinstance(output.data, dict) else {}
        status = str(payload.get("status", CurrentSymbolResearchStatus.FAILED.value))
        if json_output:
            typer.echo(json.dumps(payload, sort_keys=True, default=str))
        else:
            provisioning = payload.get("provisioning")
            job_id = (
                provisioning.get("job_id") if isinstance(provisioning, dict) else None
            )
            typer.echo(
                f"{status} wait={wait_mode.value} timeout={timeout_seconds:g} "
                f"job_id={job_id or '-'}"
            )
            company_context_result = (
                provisioning.get("company_context")
                if isinstance(provisioning, dict)
                else None
            )
            if isinstance(company_context_result, dict):
                typer.echo(
                    "company_context="
                    f"{company_context_result.get('status', 'UNAVAILABLE')}"
                )
            if output.summary:
                typer.echo(output.summary)
            for warning in output.warnings:
                typer.echo(f"warning={warning}", err=True)
        if status in {
            CurrentSymbolResearchStatus.UNAVAILABLE.value,
            CurrentSymbolResearchStatus.FAILED.value,
        }:
            raise typer.Exit(code=1)


def _wait_policy(
    *, wait: bool, wait_timeout: float | None, no_wait: bool
) -> tuple[CurrentSymbolWaitMode, float]:
    selected = int(wait) + int(wait_timeout is not None) + int(no_wait)
    if selected > 1:
        raise typer.BadParameter(
            "Use only one of --wait, --wait-timeout, or --no-wait."
        )
    if wait:
        return CurrentSymbolWaitMode.WAIT_UNTIL_TERMINAL, 0
    if wait_timeout is not None:
        return CurrentSymbolWaitMode.WAIT_UP_TO, wait_timeout
    if no_wait:
        return CurrentSymbolWaitMode.DETACH, 0
    return (
        CurrentSymbolWaitMode.WAIT_UP_TO,
        default_current_symbol_wait_timeout_seconds(),
    )


__all__ = ["register"]

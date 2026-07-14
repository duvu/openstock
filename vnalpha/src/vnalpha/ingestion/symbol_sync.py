from __future__ import annotations

import duckdb
from pydantic import ValidationError

from vnalpha.clients.vnstock.client import VnstockClient
from vnalpha.clients.vnstock.errors import (
    VnstockConnectionError,
    VnstockDataError,
    VnstockHTTPError,
    VnstockTimeoutError,
)
from vnalpha.core.logging import get_logger
from vnalpha.ingestion.models import (
    IngestionErrorCategory,
    IngestionRemediationAction,
    SymbolIngestionResult,
    SymbolIngestionStatus,
)
from vnalpha.ingestion.persistence import persist_raw_ohlcv_metadata
from vnalpha.ingestion.symbol_outcomes import (
    failed_symbol_result,
    invalid_symbol_result,
    remediation_step,
)
from vnalpha.warehouse.repositories import insert_raw_ohlcv

logger = get_logger("ingestion.sync_ohlcv")
_MAX_ATTEMPTS = 2


def sync_ohlcv_for_symbol(
    conn: duckdb.DuckDBPyConnection,
    client: VnstockClient,
    run_id: str,
    symbol: str,
    start: str | None = None,
    end: str | None = None,
    interval: str = "1D",
    source: str | None = None,
) -> SymbolIngestionResult:
    provider = source or "auto"
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            response = client.get_equity_ohlcv(
                symbol=symbol,
                start=start,
                end=end,
                interval=interval,
                source=source,
            )
        except VnstockHTTPError as exc:
            if exc.status_code == 422:
                return invalid_symbol_result(
                    symbol,
                    start,
                    end,
                    provider,
                    IngestionErrorCategory.PROVIDER_DATA,
                    "Provider rejected invalid OHLCV data.",
                    attempt,
                )
            retryable = exc.status_code in {408, 429} or exc.status_code >= 500
            if retryable and attempt < _MAX_ATTEMPTS:
                logger.warning("Retrying OHLCV provider request for %s", symbol)
                continue
            return failed_symbol_result(
                symbol,
                start,
                end,
                provider,
                IngestionErrorCategory.HTTP,
                retryable,
                "Provider HTTP request failed.",
                attempt,
            )
        except VnstockTimeoutError:
            if attempt < _MAX_ATTEMPTS:
                logger.warning("Retrying OHLCV provider request for %s", symbol)
                continue
            return failed_symbol_result(
                symbol,
                start,
                end,
                provider,
                IngestionErrorCategory.TIMEOUT,
                True,
                "Provider request timed out.",
                attempt,
            )
        except VnstockConnectionError:
            if attempt < _MAX_ATTEMPTS:
                logger.warning("Retrying OHLCV provider request for %s", symbol)
                continue
            return failed_symbol_result(
                symbol,
                start,
                end,
                provider,
                IngestionErrorCategory.CONNECTION,
                True,
                "Provider connection failed.",
                attempt,
            )
        except VnstockDataError:
            return invalid_symbol_result(
                symbol,
                start,
                end,
                provider,
                IngestionErrorCategory.INVALID_JSON,
                "Provider returned invalid JSON.",
                attempt,
            )
        except ValidationError:
            return invalid_symbol_result(
                symbol,
                start,
                end,
                provider,
                IngestionErrorCategory.INVALID_DATA,
                "Provider returned invalid OHLCV data.",
                attempt,
            )
        except RuntimeError:
            return failed_symbol_result(
                symbol,
                start,
                end,
                provider,
                IngestionErrorCategory.PROVIDER,
                False,
                "Provider runtime failed.",
                attempt,
            )

        provider = response.meta.provider
        quality_report = response.meta.quality_report or response.diagnostics.get(
            "quality", {}
        )
        if not isinstance(quality_report, dict):
            quality_report = {}
        quality_status = (response.meta.quality_status or "").lower()
        if quality_status == "skipped":
            return SymbolIngestionResult(
                symbol=symbol,
                status=SymbolIngestionStatus.SKIPPED,
                requested_start=start,
                requested_end=end,
                provider=provider,
                diagnostics_ref=response.meta.request_id,
                quality_report=quality_report,
                diagnostics=response.diagnostics,
                message="Provider marked the OHLCV request as skipped.",
                attempts=attempt,
            )
        if not response.data:
            remediation = remediation_step(
                symbol,
                start,
                end,
                source,
                IngestionRemediationAction.VERIFY_RANGE_AND_RETRY,
                "Verify the requested range and provider, then retry the bounded command.",
            )
            return SymbolIngestionResult(
                symbol=symbol,
                status=SymbolIngestionStatus.EMPTY,
                requested_start=start,
                requested_end=end,
                provider=provider,
                diagnostics_ref=response.meta.request_id,
                quality_report=quality_report,
                diagnostics=response.diagnostics,
                message="Provider returned no rows for the requested range.",
                remediation=f"{remediation.guidance} {remediation.render_command()}",
                remediation_steps=(remediation,),
                attempts=attempt,
            )
        records = response.data
        try:
            inserted = insert_raw_ohlcv(
                conn,
                run_id=run_id,
                symbol=symbol,
                records=records,
                provider=provider,
                quality_status=response.meta.quality_status,
                fetched_at=response.meta.fetched_at,
            )
        except duckdb.Error:
            return failed_symbol_result(
                symbol,
                start,
                end,
                provider,
                IngestionErrorCategory.STORAGE,
                False,
                "Warehouse persistence failed.",
                attempt,
            )
        quality_failed = (response.meta.quality_status or "").upper() in {
            "ERROR",
            "FAIL",
            "FAILED",
            "INVALID",
        }
        remediation = remediation_step(
            symbol,
            start,
            end,
            source,
            IngestionRemediationAction.INSPECT_DIAGNOSTICS_AND_RETRY,
            "Inspect the provider quality report, correct the data, then retry.",
        )
        result = SymbolIngestionResult(
            symbol=symbol,
            status=(
                SymbolIngestionStatus.INVALID
                if quality_failed
                else SymbolIngestionStatus.SUCCESS
            ),
            requested_start=start,
            requested_end=end,
            provider=provider,
            rows_received=len(response.data),
            rows_inserted=inserted,
            error_category=(
                IngestionErrorCategory.PROVIDER_DATA if quality_failed else None
            ),
            diagnostics_ref=response.meta.request_id,
            message=("Provider quality validation failed." if quality_failed else None),
            remediation=(
                f"{remediation.guidance} {remediation.render_command()}"
                if quality_failed
                else None
            ),
            remediation_steps=((remediation,) if quality_failed else ()),
            quality_report=quality_report,
            diagnostics=response.diagnostics,
            attempts=attempt,
        )
        persist_raw_ohlcv_metadata(conn, run_id, result)
        return result
    raise AssertionError("bounded retry loop did not return")

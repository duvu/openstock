#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
# ─── How to run ───
# 1. Install uv (if not installed):
#      curl -LsSf https://astral.sh/uv/install.sh | sh
# 2. Run directly (no venv, no pip install needed):
#      PYTHONPATH=vnstock uv run scripts/probe-fiinquantx.py --output /secure/path/report.json
# 3. Or make executable and run:
#      chmod +x scripts/probe-fiinquantx.py && ./scripts/probe-fiinquantx.py --output /secure/path/report.json
# ──────────────────
"""Write bounded, sanitized FiinQuantX runtime evidence outside this repository."""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import multiprocessing
import platform
import sys
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from vnstock.providers.fiinquantx.bridge import load_fiinquantx_sdk
from vnstock.providers.fiinquantx.exceptions import (
    FiinQuantXProviderError,
    FiinQuantXSchemaError,
    map_fiinquantx_exception,
)
from vnstock.providers.fiinquantx.session import (
    DEFAULT_FIINQUANTX_SESSION_PROVIDER,
    reset_fiinquantx_runtime_state,
)

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_SAFE_ACCOUNT_SCOPES = ("LICENSED_LOCAL_ACCOUNT", "UNSPECIFIED")


@dataclass(frozen=True)
class ProbeCase:
    identifier: str
    dataset: str
    sdk_method: str
    invoke: Callable[[Any], Any]


def _member(session: Any, name: str, dataset: str) -> Callable[..., Any]:
    member = getattr(session, name, None)
    if not callable(member):
        raise FiinQuantXSchemaError(dataset)
    return member


def _instance_method(
    session: Any,
    factory_name: str,
    method_name: str,
    dataset: str,
) -> Callable[..., Any]:
    factory = _member(session, factory_name, dataset)
    instance = factory()
    return _member(instance, method_name, dataset)


def _ticker_list(session: Any) -> Any:
    return _member(session, "TickerList", "reference.index_membership_snapshot")(
        ticker="VN30"
    )


def _basic_info(session: Any) -> Any:
    return _member(session, "BasicInfor", "reference.company_info")(tickers=["VCB"])


def _ohlcv(session: Any) -> Any:
    return _member(session, "Fetch_Trading_Data", "equity.ohlcv")(
        realtime=False,
        tickers=["VCB"],
        fields=["open", "high", "low", "close", "volume", "value"],
        adjusted=False,
        by="1d",
        period=2,
        lasted=False,
    )


def _statistics_overview(session: Any) -> Any:
    return _instance_method(
        session, "PriceStatistics", "get_overview", "market.market_cap_daily"
    )(
        tickers=["VCB"],
        time_filter="Daily",
        from_date="2026-07-01",
        to_date="2026-07-02",
    )


def _statistics_foreign(session: Any) -> Any:
    return _instance_method(
        session, "PriceStatistics", "get_foreign", "foreign_flow.daily"
    )(
        tickers=["VCB"],
        time_filter="Daily",
        from_date="2026-07-01",
        to_date="2026-07-02",
    )


def _statistics_freefloat(session: Any) -> Any:
    return _instance_method(
        session, "PriceStatistics", "get_freefloat", "reference.free_float_observation"
    )(tickers=["VCB"], from_date="2026-07-01", to_date="2026-07-02")


def _statistics_limits(session: Any) -> Any:
    return _instance_method(
        session, "PriceStatistics", "get_ceilingfloor", "market.price_limits_daily"
    )(tickers=["VCB"], from_date="2026-07-01", to_date="2026-07-02")


def _statistics_investor(session: Any) -> Any:
    return _instance_method(
        session, "PriceStatistics", "get_value_by_investor", "investor_flow.daily"
    )(tickers=["VCB"], from_date="2026-07-01", to_date="2026-07-02")


def _breadth(session: Any) -> Any:
    return _instance_method(session, "MarketBreadth", "get", "market.breadth_snapshot")(
        tickers=["VCB"]
    )


def _stock_valuation(session: Any) -> Any:
    return _instance_method(
        session, "MarketDepth", "get_stock_valuation", "valuation.stock_observation"
    )(tickers=["VCB"], from_date="2026-07-01", to_date="2026-07-02")


def _sector_valuation(session: Any) -> Any:
    return _instance_method(
        session, "MarketDepth", "get_sector_valuation", "valuation.sector_observation"
    )(tickers=["BANKS_L2"], level=2, from_date="2026-07-01", to_date="2026-07-02")


def _index_valuation(session: Any) -> Any:
    return _instance_method(
        session, "MarketDepth", "get_index_valuation", "valuation.index_observation"
    )(tickers=["VNINDEX"], from_date="2026-07-01", to_date="2026-07-02")


def _statements(session: Any) -> Any:
    return _instance_method(
        session,
        "FundamentalAnalysis",
        "get_financial_statement",
        "fundamental.balance_sheet",
    )(
        tickers=["VCB"],
        statement="balancesheet",
        years=[2024],
        quarters=[4],
        audited=True,
        type="consolidated",
    )


def _ratios(session: Any) -> Any:
    return _instance_method(
        session,
        "FundamentalAnalysis",
        "get_ratios",
        "fundamental.financial_ratio",
    )(tickers=["VCB"], years=[2024], quarters=[4], type="consolidated")


_PROBE_CASES = (
    ProbeCase(
        "ticker-list", "reference.index_membership_snapshot", "TickerList", _ticker_list
    ),
    ProbeCase("basic-info", "reference.company_info", "BasicInfor", _basic_info),
    ProbeCase("ohlcv", "equity.ohlcv", "Fetch_Trading_Data", _ohlcv),
    ProbeCase(
        "statistics-overview",
        "market.market_cap_daily",
        "PriceStatistics.get_overview",
        _statistics_overview,
    ),
    ProbeCase(
        "statistics-foreign",
        "foreign_flow.daily",
        "PriceStatistics.get_foreign",
        _statistics_foreign,
    ),
    ProbeCase(
        "statistics-freefloat",
        "reference.free_float_observation",
        "PriceStatistics.get_freefloat",
        _statistics_freefloat,
    ),
    ProbeCase(
        "statistics-limits",
        "market.price_limits_daily",
        "PriceStatistics.get_ceilingfloor",
        _statistics_limits,
    ),
    ProbeCase(
        "statistics-investor",
        "investor_flow.daily",
        "PriceStatistics.get_value_by_investor",
        _statistics_investor,
    ),
    ProbeCase("breadth", "market.breadth_snapshot", "MarketBreadth.get", _breadth),
    ProbeCase(
        "stock-valuation",
        "valuation.stock_observation",
        "MarketDepth.get_stock_valuation",
        _stock_valuation,
    ),
    ProbeCase(
        "sector-valuation",
        "valuation.sector_observation",
        "MarketDepth.get_sector_valuation",
        _sector_valuation,
    ),
    ProbeCase(
        "index-valuation",
        "valuation.index_observation",
        "MarketDepth.get_index_valuation",
        _index_valuation,
    ),
    ProbeCase(
        "statements",
        "fundamental.balance_sheet",
        "FundamentalAnalysis.get_financial_statement",
        _statements,
    ),
    ProbeCase(
        "ratios",
        "fundamental.financial_ratio",
        "FundamentalAnalysis.get_ratios",
        _ratios,
    ),
)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument(
        "--account-scope", choices=_SAFE_ACCOUNT_SCOPES, default="UNSPECIFIED"
    )
    parser.add_argument(
        "--probe", choices=[case.identifier for case in _PROBE_CASES], action="append"
    )
    return parser.parse_args()


def _safe_shape(raw: Any) -> dict[str, Any]:
    if hasattr(raw, "get_data"):
        raw = raw.get_data()
    if isinstance(raw, pd.DataFrame):
        columns = [str(column) for column in raw.columns]
        return {
            "kind": "dataframe",
            "row_count": len(raw),
            "columns": columns,
            "column_fingerprint": hashlib.sha256(
                "\x1f".join(columns).encode()
            ).hexdigest()[:12],
            "dtypes": {str(column): str(dtype) for column, dtype in raw.dtypes.items()},
        }
    if isinstance(raw, Iterable) and not isinstance(raw, (str, bytes, dict)):
        return {"kind": type(raw).__name__, "row_count": sum(1 for _ in raw)}
    if isinstance(raw, dict):
        return {"kind": "mapping", "field_count": len(raw)}
    return {"kind": type(raw).__name__}


def _safe_signature(case: ProbeCase) -> str:
    signature = inspect.signature(case.invoke)
    return f"{case.sdk_method} {signature}"


def _probe_once(case: ProbeCase, module: Any) -> dict[str, Any]:
    started = time.monotonic()
    try:
        with DEFAULT_FIINQUANTX_SESSION_PROVIDER.request_session(
            module, case.dataset
        ) as session:
            raw = case.invoke(session)
        shape = _safe_shape(raw)
        return {
            "probe": case.identifier,
            "dataset": case.dataset,
            "sdk_method": case.sdk_method,
            "verified_signature": _safe_signature(case),
            "status": "VALID_EMPTY" if shape.get("row_count") == 0 else "SUCCESS",
            "elapsed_ms": round((time.monotonic() - started) * 1_000),
            "shape": shape,
        }
    except FiinQuantXProviderError as exc:
        return {
            "probe": case.identifier,
            "dataset": case.dataset,
            "sdk_method": case.sdk_method,
            "status": "FAILURE",
            "failure_type": exc.kind.value,
            "elapsed_ms": round((time.monotonic() - started) * 1_000),
        }
    except Exception as exc:  # noqa: BLE001 - vendor call boundary
        mapped = map_fiinquantx_exception(exc, case.dataset)
        return {
            "probe": case.identifier,
            "dataset": case.dataset,
            "sdk_method": case.sdk_method,
            "status": "FAILURE",
            "failure_type": mapped.kind.value,
            "elapsed_ms": round((time.monotonic() - started) * 1_000),
        }


def _probe_worker(case_identifier: str, connection: Any) -> None:
    case = next(case for case in _PROBE_CASES if case.identifier == case_identifier)
    try:
        sdk = load_fiinquantx_sdk()
        if sdk.module is None:
            result = {
                "probe": case.identifier,
                "dataset": case.dataset,
                "sdk_method": case.sdk_method,
                "status": "FAILURE",
                "failure_type": "SDK_UNAVAILABLE",
                "elapsed_ms": 0,
            }
        else:
            result = _probe_once(case, sdk.module)
        connection.send(result)
    finally:
        reset_fiinquantx_runtime_state()
        connection.close()


def _probe(case: ProbeCase, timeout_seconds: float) -> dict[str, Any]:
    if timeout_seconds <= 0:
        raise ValueError("--timeout-seconds must be greater than zero")

    started = time.monotonic()
    context = multiprocessing.get_context("spawn")
    receive_connection, send_connection = context.Pipe(duplex=False)
    worker = context.Process(
        target=_probe_worker, args=(case.identifier, send_connection)
    )
    try:
        worker.start()
        send_connection.close()
        worker.join(timeout_seconds)
        if worker.is_alive():
            worker.terminate()
            worker.join()
            return {
                "probe": case.identifier,
                "dataset": case.dataset,
                "sdk_method": case.sdk_method,
                "status": "FAILURE",
                "failure_type": "TIMEOUT",
                "elapsed_ms": round((time.monotonic() - started) * 1_000),
            }
        if receive_connection.poll():
            return receive_connection.recv()
        return {
            "probe": case.identifier,
            "dataset": case.dataset,
            "sdk_method": case.sdk_method,
            "status": "FAILURE",
            "failure_type": "WORKER_EXITED",
            "elapsed_ms": round((time.monotonic() - started) * 1_000),
        }
    finally:
        receive_connection.close()
        if worker.is_alive():
            worker.terminate()
            worker.join()


def _selected_cases(selected: list[str] | None) -> tuple[ProbeCase, ...]:
    if selected is None:
        return _PROBE_CASES
    selected_identifiers = set(selected)
    return tuple(
        case for case in _PROBE_CASES if case.identifier in selected_identifiers
    )


def _validate_output_path(path: Path) -> Path:
    output_path = path.resolve()
    if output_path.is_relative_to(_REPOSITORY_ROOT):
        raise ValueError("--output must be outside the repository")
    return output_path


def main() -> int:
    args = _args()
    output_path = _validate_output_path(args.output)
    sdk = load_fiinquantx_sdk()
    report: dict[str, Any] = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "account_scope": args.account_scope,
        "sdk_state": sdk.state.value,
        "sdk_version": sdk.version,
        "timeout_seconds": args.timeout_seconds,
        "probes": [],
    }
    try:
        if sdk.module is None:
            report["blocking_reason"] = "exact supported SDK runtime is unavailable"
        else:
            cases = _selected_cases(args.probe)
            report["probes"] = [_probe(case, args.timeout_seconds) for case in cases]
    except FiinQuantXProviderError as exc:
        report["blocking_reason"] = exc.kind.value
    finally:
        reset_fiinquantx_runtime_state()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

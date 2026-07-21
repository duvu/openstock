#!/usr/bin/env python3
"""Probe every advertised provider/dataset pair exposed by vnstock-service.

Writes a local JSON, CSV, and Markdown report. Uses only the Python standard
library and never sends credentials in query parameters.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

ROUTES = {
    "equity.ohlcv": "/v1/equity/ohlcv",
    "equity.quote": "/v1/equity/quote",
    "equity.intraday_trades": "/v1/equity/intraday-trades",
    "index.ohlcv": "/v1/index/ohlcv",
    "reference.symbols": "/v1/reference/symbols",
    "reference.corporate_actions": "/v1/reference/corporate-actions",
    "reference.index_membership_snapshot": "/v1/reference/index-membership",
    "reference.sector_membership_snapshot": "/v1/reference/sector-membership",
    "reference.company_info": "/v1/company/info",
    "fundamental.balance_sheet": "/v1/fundamental/balance-sheet",
    "fundamental.income_statement": "/v1/fundamental/income-statement",
    "fundamental.cash_flow": "/v1/fundamental/cash-flow",
    "fundamental.financial_ratio": "/v1/fundamental/financial-ratio",
    "fund.nav": "/v1/fund/nav",
    "fund.holdings": "/v1/fund/holdings",
}
DISCOVERY = {
    "health": "/healthz",
    "providers": "/v1/providers",
    "capabilities": "/v1/providers/capabilities",
    "provider_health": "/v1/providers/health",
    "auth_status": "/v1/auth/status",
    "auth_providers": "/v1/auth/providers",
}
SENSITIVE = (
    "api_key",
    "authorization",
    "cookie",
    "credential",
    "password",
    "secret",
    "session",
    "token",
    "username",
)
FAILURES = {
    "CAPABILITY_MISMATCH",
    "CONTRACT_ERROR",
    "HTTP_ERROR",
    "NO_HEALTHY_PROVIDER",
    "RATE_LIMITED",
    "ROUTING_MISMATCH",
    "TRANSPORT_ERROR",
}


@dataclass(frozen=True, slots=True)
class Result:
    provider: str
    dataset: str
    advertised: bool
    capability_status: str | None
    auth_required: bool | None
    status: str
    http_status: int | None = None
    row_count: int | None = None
    elapsed_ms: float | None = None
    actual_provider: str | None = None
    quality_status: str | None = None
    runtime_path: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    request_url: str | None = None
    sample_rows: tuple[dict[str, Any], ...] = ()


def arguments(argv: list[str]) -> argparse.Namespace:
    today = date.today()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.getenv("VNSTOCK_SERVICE_URL", "http://127.0.0.1:6900"),
    )
    parser.add_argument("--symbol", default="FPT")
    parser.add_argument("--fundamental-symbol", default="TCB")
    parser.add_argument("--index-symbol", default="VNINDEX")
    parser.add_argument("--membership-index", default="VN30")
    parser.add_argument("--sector-symbol", default="BANKS_L2")
    parser.add_argument("--fund-symbol", default="VCBF")
    parser.add_argument("--start", default=(today - timedelta(days=30)).isoformat())
    parser.add_argument("--end", default=today.isoformat())
    parser.add_argument("--interval", default="1D")
    parser.add_argument("--period", choices=("year", "quarter"), default="year")
    parser.add_argument("--lang", choices=("vi", "en"), default="vi")
    parser.add_argument("--providers", help="Comma-separated provider filter")
    parser.add_argument(
        "--datasets", help="Comma-separated canonical dataset filter"
    )
    parser.add_argument("--include-auto", action="store_true")
    parser.add_argument("--probe-unsupported", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument(
        "--quality-mode", choices=("off", "warn", "strict"), default="warn"
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--delay", type=float, default=0.25)
    parser.add_argument("--sample-rows", type=int, default=2)
    parser.add_argument("--max-requests", type=int, default=200)
    parser.add_argument("--strict-empty", action="store_true")
    parser.add_argument("--allow-auth-missing", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args(argv)


def safe(value: Any, depth: int = 0) -> Any:
    if depth > 8:
        return "[TRUNCATED]"
    if isinstance(value, Mapping):
        return {
            str(key): safe(item, depth + 1)
            for key, item in value.items()
            if not any(fragment in str(key).lower() for fragment in SENSITIVE)
        }
    if isinstance(value, (list, tuple)):
        return [safe(item, depth + 1) for item in value[:100]]
    if isinstance(value, str):
        normalized = " ".join(value.split())
        return normalized if len(normalized) <= 500 else normalized[:499] + "…"
    return value


def url(base: str, path: str, params: Mapping[str, Any] | None = None) -> str:
    value = urljoin(base.rstrip("/") + "/", path.lstrip("/"))
    query = urlencode(
        [(key, item) for key, item in (params or {}).items() if item is not None]
    )
    return f"{value}?{query}" if query else value


def get_json(
    base: str,
    path: str,
    params: Mapping[str, Any] | None,
    timeout: float,
) -> tuple[int | None, Any, float, str | None]:
    target = url(base, path, params)
    request = Request(
        target,
        headers={
            "Accept": "application/json",
            "User-Agent": "openstock-vnstock-audit/1",
            "X-Correlation-ID": f"audit-{uuid.uuid4().hex}",
        },
    )
    started = time.perf_counter()
    try:
        with urlopen(  # noqa: S310 - operator-selected local service
            request, timeout=timeout
        ) as response:
            status, raw = response.status, response.read()
    except HTTPError as exc:
        status, raw = exc.code, exc.read()
    except (URLError, TimeoutError, OSError) as exc:
        return (
            None,
            None,
            (time.perf_counter() - started) * 1000,
            f"{type(exc).__name__}: {exc}",
        )
    elapsed = (time.perf_counter() - started) * 1000
    try:
        payload = json.loads(raw.decode()) if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = {
            "error": "invalid_json",
            "message": raw[:500].decode("utf-8", "replace"),
        }
    return status, safe(payload), elapsed, None


def discover(args: argparse.Namespace) -> dict[str, Any]:
    data = {}
    for name, path in DISCOVERY.items():
        status, payload, elapsed, error = get_json(
            args.base_url, path, None, args.timeout
        )
        data[name] = {
            "http_status": status,
            "elapsed_ms": round(elapsed, 3),
            "transport_error": error,
            "payload": payload,
        }
    return data


def capability_matrix(
    discovery: Mapping[str, Any],
) -> dict[str, dict[str, dict[str, Any]]]:
    raw = (
        discovery.get("capabilities", {})
        .get("payload", {})
        .get("capabilities", {})
    )
    matrix = {}
    if not isinstance(raw, Mapping):
        return matrix
    for provider, datasets in raw.items():
        if not isinstance(datasets, Mapping):
            continue
        provider_name = str(provider).upper()
        matrix[provider_name] = {}
        for dataset, spec in datasets.items():
            item = dict(spec) if isinstance(spec, Mapping) else {"supported": bool(spec)}
            item["supported"] = bool(item.get("supported", False))
            matrix[provider_name][str(dataset).lower()] = safe(item)
    return matrix


def selected(value: str | None, upper: bool) -> set[str] | None:
    if not value:
        return None
    items = {item.strip() for item in value.split(",") if item.strip()}
    return {item.upper() if upper else item.lower() for item in items} or None


def probe_params(dataset: str, args: argparse.Namespace) -> dict[str, Any]:
    historical = {
        "start": args.start,
        "end": args.end,
        "interval": args.interval,
    }
    return {
        "equity.ohlcv": {"symbol": args.symbol, **historical},
        "equity.quote": {"symbol": args.symbol},
        "equity.intraday_trades": {
            "symbol": args.symbol,
            "page": 0,
            "size": 100,
        },
        "index.ohlcv": {"symbol": args.index_symbol, **historical},
        "reference.symbols": {},
        "reference.corporate_actions": {
            "symbol": args.symbol,
            "start": args.start,
            "end": args.end,
            "page": 1,
            "page_size": 50,
        },
        "reference.index_membership_snapshot": {"symbol": args.membership_index},
        "reference.sector_membership_snapshot": {"symbol": args.sector_symbol},
        "reference.company_info": {"symbol": args.symbol},
        "fundamental.balance_sheet": {
            "symbol": args.fundamental_symbol,
            "period": args.period,
            "lang": args.lang,
        },
        "fundamental.income_statement": {
            "symbol": args.fundamental_symbol,
            "period": args.period,
            "lang": args.lang,
        },
        "fundamental.cash_flow": {
            "symbol": args.fundamental_symbol,
            "period": args.period,
            "lang": args.lang,
        },
        "fundamental.financial_ratio": {
            "symbol": args.fundamental_symbol,
            "period": args.period,
            "lang": args.lang,
        },
        "fund.nav": {"symbol": args.fund_symbol},
        "fund.holdings": {"symbol": args.fund_symbol},
    }[dataset]


def text(value: Any) -> str | None:
    result = "" if value is None else str(value).strip()
    return result or None


def boolean(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def skipped(
    provider: str,
    dataset: str,
    capability: Mapping[str, Any],
    status: str,
    message: str,
) -> Result:
    return Result(
        provider,
        dataset,
        False,
        text(capability.get("status")),
        boolean(capability.get("auth_required")),
        status,
        error_message=message,
    )


def classify(
    provider: str,
    dataset: str,
    advertised: bool,
    capability: Mapping[str, Any],
    request_url: str,
    response: tuple[int | None, Any, float, str | None],
    samples: int,
) -> Result:
    status_code, raw, elapsed, transport = response
    common = {
        "provider": provider,
        "dataset": dataset,
        "advertised": advertised,
        "capability_status": text(capability.get("status")),
        "auth_required": boolean(capability.get("auth_required")),
        "http_status": status_code,
        "elapsed_ms": round(elapsed, 3),
        "request_url": request_url,
    }
    if transport:
        return Result(
            **common,
            status="TRANSPORT_ERROR",
            error_code="transport_error",
            error_message=transport,
        )
    payload = raw if isinstance(raw, Mapping) else {}
    if status_code is not None and 200 <= status_code < 300:
        rows = payload.get("data")
        meta = payload.get("meta")
        diagnostics = payload.get("diagnostics")
        if (
            not isinstance(rows, list)
            or not isinstance(meta, Mapping)
            or not isinstance(diagnostics, Mapping)
        ):
            return Result(
                **common,
                status="CONTRACT_ERROR",
                error_code="invalid_service_envelope",
                error_message="Expected data:list, meta:object and diagnostics:object",
            )
        actual_provider = text(meta.get("provider"))
        actual_dataset = text(meta.get("dataset"))
        result_status = "PASS" if rows else "EMPTY"
        error_code = None
        error_message = None
        if actual_dataset != dataset:
            result_status = "CONTRACT_ERROR"
            error_code = "dataset_identity_mismatch"
            error_message = f"Returned {actual_dataset!r}"
        elif provider != "AUTO" and (actual_provider or "").upper() != provider:
            result_status = "ROUTING_MISMATCH"
            error_code = "provider_identity_mismatch"
            error_message = f"Returned {actual_provider!r}"
        sample = (
            tuple(
                safe(dict(row))
                for row in rows[:samples]
                if isinstance(row, Mapping)
            )
            if samples
            else ()
        )
        return Result(
            **common,
            status=result_status,
            row_count=len(rows),
            actual_provider=actual_provider,
            quality_status=text(meta.get("quality_status")),
            runtime_path=text(meta.get("runtime_path")),
            error_code=error_code,
            error_message=error_message,
            sample_rows=sample,
        )
    code = text(payload.get("error")) or "http_error"
    message = text(payload.get("message")) or f"HTTP {status_code}"
    if status_code == 429:
        outcome = "RATE_LIMITED"
    elif status_code in (401, 403) or "auth" in code:
        outcome = "AUTH_REQUIRED"
    elif status_code == 503 or code == "no_healthy_provider":
        outcome = "NO_HEALTHY_PROVIDER"
    elif code in {"unsupported_dataset", "unsupported_dataset_for_provider"}:
        outcome = "CAPABILITY_MISMATCH" if advertised else "EXPECTED_UNSUPPORTED"
    else:
        outcome = "HTTP_ERROR"
    return Result(
        **common,
        status=outcome,
        error_code=code,
        error_message=message,
    )


def is_failure(result: Result, args: argparse.Namespace) -> bool:
    return (
        result.status in FAILURES
        or (result.status == "AUTH_REQUIRED" and not args.allow_auth_missing)
        or (result.status == "EMPTY" and args.strict_empty)
    )


def run_probes(
    args: argparse.Namespace, discovery: Mapping[str, Any]
) -> tuple[list[Result], dict[str, Any]]:
    capabilities = capability_matrix(discovery)
    provider_filter = selected(args.providers, True)
    dataset_filter = selected(args.datasets, False)
    raw_providers = (
        discovery.get("providers", {}).get("payload", {}).get("providers", [])
    )
    providers = sorted(
        {str(item).upper() for item in raw_providers} | set(capabilities)
    )
    providers = [
        provider
        for provider in providers
        if not provider_filter or provider in provider_filter
    ]
    datasets = [
        dataset for dataset in ROUTES if not dataset_filter or dataset in dataset_filter
    ]
    if dataset_filter and dataset_filter - ROUTES.keys():
        raise SystemExit(
            f"Unknown datasets: {', '.join(sorted(dataset_filter - ROUTES.keys()))}"
        )
    if provider_filter and provider_filter - set(providers):
        raise SystemExit(
            f"Providers not discovered: {', '.join(sorted(provider_filter - set(providers)))}"
        )
    pairs = [
        (provider, dataset, capabilities.get(provider, {}).get(dataset, {}))
        for provider in providers
        for dataset in datasets
    ]
    if args.include_auto:
        pairs += [("AUTO", dataset, {}) for dataset in datasets]
    results = []
    live_requests = 0
    for index, (provider, dataset, capability) in enumerate(pairs, 1):
        advertised = (
            bool(capability.get("supported"))
            if provider != "AUTO"
            else any(
                bool(provider_caps.get(dataset, {}).get("supported"))
                for provider_caps in capabilities.values()
            )
        )
        if not advertised and provider != "AUTO" and not args.probe_unsupported:
            results.append(
                skipped(
                    provider,
                    dataset,
                    capability,
                    "NOT_ADVERTISED",
                    "Capability matrix does not advertise this dataset",
                )
            )
            continue
        if provider == "AUTO" and not advertised:
            results.append(
                skipped(
                    provider,
                    dataset,
                    capability,
                    "NO_ADVERTISED_PROVIDER",
                    "No provider advertises this route",
                )
            )
            continue
        params = dict(probe_params(dataset, args))
        if provider != "AUTO":
            params["source"] = provider
        if args.validate:
            params.update(validate="true", quality_mode=args.quality_mode)
        target = url(args.base_url, ROUTES[dataset], params)
        prefix = f"[{index:03d}/{len(pairs):03d}] {provider:<12} {dataset:<42}"
        if args.dry_run:
            print(f"{prefix} DRY_RUN")
            results.append(
                Result(
                    provider,
                    dataset,
                    advertised,
                    text(capability.get("status")),
                    boolean(capability.get("auth_required")),
                    "DRY_RUN",
                    request_url=target,
                )
            )
            continue
        live_requests += 1
        if live_requests > args.max_requests:
            raise SystemExit(f"Exceeded --max-requests={args.max_requests}")
        result = classify(
            provider,
            dataset,
            advertised,
            capability,
            target,
            get_json(args.base_url, ROUTES[dataset], params, args.timeout),
            args.sample_rows,
        )
        results.append(result)
        print(
            f"{prefix} {result.status:<24} "
            f"http={result.http_status or '-'} "
            f"rows={result.row_count if result.row_count is not None else '-'} "
            f"ms={result.elapsed_ms or '-'}"
        )
        if args.fail_fast and is_failure(result, args):
            break
        if args.delay:
            time.sleep(args.delay)
    return results, {
        "providers": providers,
        "datasets": datasets,
        "capabilities": capabilities,
        "live_requests": live_requests,
    }


def summary(results: list[Result]) -> dict[str, int]:
    values = {}
    for result in results:
        values[result.status] = values.get(result.status, 0) + 1
    return dict(sorted(values.items()))


def output_dir(args: argparse.Namespace, stamp: str) -> Path:
    return (
        args.output_dir.expanduser().resolve()
        if args.output_dir
        else Path("/tmp/openstock-vnstock-audit") / stamp
    )


def write_reports(
    path: Path,
    args: argparse.Namespace,
    discovery: Mapping[str, Any],
    context: Mapping[str, Any],
    results: list[Result],
    started: str,
    completed: str,
) -> None:
    path.mkdir(parents=True, exist_ok=True)
    report = {
        "contract_version": "vnstock-service-provider-audit-v1",
        "started_at": started,
        "completed_at": completed,
        "base_url": args.base_url,
        "inputs": {
            key: getattr(args, key)
            for key in (
                "symbol",
                "fundamental_symbol",
                "index_symbol",
                "membership_index",
                "sector_symbol",
                "fund_symbol",
                "start",
                "end",
                "interval",
                "period",
                "validate",
                "quality_mode",
                "include_auto",
                "probe_unsupported",
            )
        },
        "discovery": discovery,
        "context": context,
        "summary": summary(results),
        "results": [asdict(result) for result in results],
        "warning": (
            "Reports may contain bounded market-data samples. Keep them local and "
            "review provider licence terms before sharing."
        ),
    }
    (path / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    fields = [
        "provider",
        "dataset",
        "advertised",
        "capability_status",
        "auth_required",
        "status",
        "http_status",
        "row_count",
        "elapsed_ms",
        "actual_provider",
        "quality_status",
        "runtime_path",
        "error_code",
        "error_message",
        "request_url",
    ]
    with (path / "matrix.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in results:
            row = asdict(result)
            writer.writerow({key: row.get(key) for key in fields})
    lines = [
        "# vnstock-service provider/data audit",
        "",
        f"- Base URL: `{args.base_url}`",
        f"- Summary: `{json.dumps(summary(results), sort_keys=True)}`",
        "",
        "> Reports may contain bounded market-data samples. Keep them local.",
        "",
        "| Provider | Dataset | Advertised | Status | HTTP | Rows | Actual | Quality | ms | Error |",
        "|---|---|---:|---|---:|---:|---|---|---:|---|",
    ]

    def cell(value: Any) -> str:
        if value is None:
            return "—"
        return str(value).replace("|", "\\|").replace("\n", " ")

    for result in results:
        lines.append(
            "| "
            + " | ".join(
                cell(value)
                for value in (
                    result.provider,
                    result.dataset,
                    result.advertised,
                    result.status,
                    result.http_status,
                    result.row_count,
                    result.actual_provider,
                    result.quality_status,
                    result.elapsed_ms,
                    result.error_code or result.error_message,
                )
            )
            + " |"
        )
    lines += ["", "## Bounded samples", ""]
    for result in results:
        if result.sample_rows:
            lines += [
                f"### {result.provider} / {result.dataset}",
                "",
                "```json",
                json.dumps(
                    result.sample_rows,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                ),
                "```",
                "",
            ]
    (path / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = arguments(sys.argv[1:] if argv is None else argv)
    if (
        args.timeout <= 0
        or args.delay < 0
        or args.sample_rows < 0
        or args.max_requests < 1
    ):
        raise SystemExit("Invalid timeout, delay, sample-rows, or max-requests")
    started = datetime.now(UTC)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    print(f"Discovering vnstock-service at {args.base_url} ...")
    discovery = discover(args)
    capabilities = capability_matrix(discovery)
    health = discovery.get("health", {})
    capability_probe = discovery.get("capabilities", {})
    if (
        health.get("http_status") != 200
        or health.get("transport_error")
        or capability_probe.get("http_status") != 200
        or capability_probe.get("transport_error")
        or not capabilities
    ):
        path = output_dir(args, stamp)
        write_reports(
            path,
            args,
            discovery,
            {"capabilities": capabilities},
            [],
            started.isoformat(),
            datetime.now(UTC).isoformat(),
        )
        print(f"Service discovery failed. Report: {path}", file=sys.stderr)
        return 2
    results, context = run_probes(args, discovery)
    path = output_dir(args, stamp)
    write_reports(
        path,
        args,
        discovery,
        context,
        results,
        started.isoformat(),
        datetime.now(UTC).isoformat(),
    )
    failures = [result for result in results if is_failure(result, args)]
    print(f"Reports written to: {path}")
    print(f"Summary: {json.dumps(summary(results), sort_keys=True)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

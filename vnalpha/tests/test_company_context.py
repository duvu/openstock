from __future__ import annotations

from copy import deepcopy

import duckdb
import httpx
import respx

from vnalpha.clients.vnstock.client import VnstockClient
from vnalpha.company_context import (
    CompanyContextStatus,
    get_current_company_context,
    refresh_company_context,
)
from vnalpha.warehouse.migrations import run_migrations

MOCK_BASE = "http://127.0.0.1:6900"
_COMPANY_RESPONSE = {
    "data": [
        {
            "symbol": "FPT",
            "exchange": "HOSE",
            "short_name": "FPT",
            "full_name": "FPT Corporation",
            "industry": "Technology",
            "employees": 50000,
        }
    ],
    "meta": {
        "dataset": "reference.company_info",
        "provider": "kbs",
        "quality_status": "pass",
        "fetched_at": "2024-01-02T09:00:00Z",
    },
    "diagnostics": {},
}


@respx.mock(base_url=MOCK_BASE)
def test_company_context_preserves_current_revision_contract(respx_mock) -> None:
    fpt_requests = 0

    def company_info(request: httpx.Request) -> httpx.Response:
        nonlocal fpt_requests
        symbol = request.url.params["symbol"]
        if symbol == "VCB":
            return httpx.Response(200, json={**_COMPANY_RESPONSE, "data": []})
        if symbol == "VNM":
            return httpx.Response(404, json={"error": "NOT_FOUND"})
        if symbol == "SSI":
            return httpx.Response(503, json={"error": "UPSTREAM_UNAVAILABLE"})
        fpt_requests += 1
        if fpt_requests == 4:
            return httpx.Response(503, json={"error": "UPSTREAM_UNAVAILABLE"})
        response = deepcopy(_COMPANY_RESPONSE)
        if fpt_requests == 3:
            response["data"][0]["employees"] = 60000
            response["meta"]["fetched_at"] = "2024-01-03T09:00:00Z"
        return httpx.Response(200, json=response)

    respx_mock.get("/v1/company/info").mock(side_effect=company_info)
    connection = duckdb.connect(":memory:")
    run_migrations(conn=connection, emit_observability=False)

    with VnstockClient(base_url=MOCK_BASE) as client:
        first = refresh_company_context(connection, "fpt", client)
        repeated = refresh_company_context(connection, "FPT", client)
        changed = refresh_company_context(connection, "FPT", client)
        empty = refresh_company_context(connection, "VCB", client)
        unsupported = refresh_company_context(connection, "VNM", client)
        provider_failure = refresh_company_context(connection, "SSI", client)
        latest_failure = refresh_company_context(connection, "FPT", client)

    current = get_current_company_context(connection, "FPT", historical=False)
    historical = get_current_company_context(connection, "FPT", historical=True)
    revision_count = connection.execute(
        "SELECT COUNT(*) FROM company_context_revision "
        "WHERE symbol = 'FPT' AND status = 'AVAILABLE'"
    ).fetchone()[0]

    assert first.status is CompanyContextStatus.AVAILABLE
    assert repeated.snapshot is not None
    assert first.snapshot is not None
    assert repeated.snapshot.content_hash == first.snapshot.content_hash
    assert changed.snapshot is not None
    assert changed.snapshot.content_hash != first.snapshot.content_hash
    assert changed.snapshot.employees == 60000
    rehydrated = changed.from_dict(changed.to_dict())
    assert rehydrated is not None
    assert changed.to_dict() == rehydrated.to_dict()
    assert revision_count == 2
    assert empty.status is CompanyContextStatus.EMPTY
    assert unsupported.status is CompanyContextStatus.UNSUPPORTED
    assert provider_failure.status is CompanyContextStatus.PROVIDER_FAILURE
    assert latest_failure.status is CompanyContextStatus.PROVIDER_FAILURE
    assert current.status is CompanyContextStatus.AVAILABLE
    assert current.snapshot is not None
    assert current.snapshot.employees == 60000
    assert historical.status is CompanyContextStatus.HISTORICAL_UNAVAILABLE
    assert respx_mock.calls.last.request.url.params["validate"] == "true"
    assert respx_mock.calls.last.request.url.params["quality_mode"] == "strict"

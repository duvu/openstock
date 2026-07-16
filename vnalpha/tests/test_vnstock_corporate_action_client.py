from __future__ import annotations

import httpx

from vnalpha.clients.vnstock.client import VnstockClient


def test_get_corporate_actions_uses_canonical_bounded_endpoint(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_get(self, url):
        captured["url"] = str(url)
        return httpx.Response(
            200,
            request=httpx.Request("GET", str(url)),
            json={
                "data": [],
                "meta": {
                    "dataset": "reference.corporate_actions",
                    "provider": "VCI",
                },
                "diagnostics": {},
            },
        )

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    client = VnstockClient(base_url="http://vnstock.test")
    response = client.get_corporate_actions(
        "SSI", start="2024-01-01", end="2024-12-31", source="VCI"
    )
    client.close()

    assert response.meta.dataset == "reference.corporate_actions"
    assert captured["url"] == (
        "/v1/reference/corporate-actions?symbol=SSI&start=2024-01-01"
        "&end=2024-12-31&source=VCI"
    )

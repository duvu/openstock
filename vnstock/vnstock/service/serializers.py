"""DataResult serializer for the vnstock local HTTP service.

Converts :class:`~vnstock.core.result.DataResult` to a stable JSON envelope::

    {
        "data": [...],
        "meta": {
            "request_id": "req_...",
            "dataset": "equity.ohlcv",
            "provider": "KBS",
            "quality_status": "PASS",
            "fetched_at": "2026-07-03T00:00:00Z",
            "source_requested": "auto",
            "runtime_path": "plugin_runtime"
        },
        "diagnostics": {
            "routing": {},
            "provider_diagnostics": {},
            "quality": {},
            "warnings": []
        }
    }

Sensitive fields (passwords, tokens, API keys, cookies) are never included.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vnstock.core.result import DataResult

# Credential-related keys that must never appear in a service response
_REDACT_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "api_key",
        "access_token",
        "refresh_token",
        "cookie",
        "session_id",
        "authorization",
        "authorization_header",
        "token",
        "secret",
        "credential",
        "credentials",
    }
)


def _redact(obj: Any, _depth: int = 0) -> Any:
    """Recursively remove credential-related keys from dicts.

    Args:
        obj: Any JSON-serialisable object.
        _depth: Current recursion depth (guards against pathological inputs).

    Returns:
        A copy of *obj* with credential keys removed.
    """
    if _depth > 10:
        return obj
    if isinstance(obj, dict):
        return {
            k: _redact(v, _depth + 1)
            for k, v in obj.items()
            if k.lower() not in _REDACT_KEYS
        }
    if isinstance(obj, list):
        return [_redact(item, _depth + 1) for item in obj]
    return obj


def _fmt_dt(dt: datetime | None) -> str | None:
    """Format a datetime as an ISO-8601 UTC string, or None."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


class RequestContext:
    """Minimal context associated with an HTTP request.

    Args:
        dataset: Canonical dataset name.
        source_requested: Source explicitly requested by the caller, or
            ``"auto"`` when none was specified.
        request_id: Optional caller-supplied or auto-generated request ID.
    """

    def __init__(
        self,
        dataset: str,
        source_requested: str | None = None,
        request_id: str | None = None,
    ) -> None:
        self.dataset = dataset
        self.source_requested = source_requested or "auto"
        self.request_id = request_id or f"req_{uuid.uuid4().hex[:12]}"


def serialize_data_result(
    result: "DataResult",
    request_context: RequestContext,
) -> dict[str, Any]:
    """Convert a :class:`~vnstock.core.result.DataResult` to a service envelope.

    Args:
        result: The :class:`~vnstock.core.result.DataResult` from
            :meth:`~vnstock.core.runtime.plugin_runtime.PluginRuntime.fetch`.
        request_context: A :class:`RequestContext` describing the originating
            HTTP request.

    Returns:
        A JSON-serialisable dict with ``data``, ``meta``, and
        ``diagnostics`` keys.
    """
    import pandas as pd

    # ── data ──────────────────────────────────────────────────────────────
    df = result.data
    if isinstance(df, pd.DataFrame):
        records = df.to_dict(orient="records")
    else:
        records = []

    # ── meta ──────────────────────────────────────────────────────────────
    diagnostics = result.diagnostics or {}
    runtime_path: str = diagnostics.get("runtime_path", "plugin_runtime")

    meta: dict[str, Any] = {
        "request_id": request_context.request_id,
        "dataset": request_context.dataset,
        "provider": result.provider,
        "quality_status": result.quality_status,
        "fetched_at": _fmt_dt(result.fetched_at),
        "source_requested": request_context.source_requested,
        "runtime_path": runtime_path,
    }

    # ── diagnostics ───────────────────────────────────────────────────────
    safe_diag = _redact(diagnostics)

    # Reshape into stable sub-keys
    diag_out: dict[str, Any] = {
        "routing": safe_diag.get("routing", {}),
        "provider_diagnostics": safe_diag.get("provider_diagnostics", {}),
        "quality": result.quality_report or {},
        "warnings": safe_diag.get("warnings", []),
    }
    # Pass through any extra keys that aren't already mapped
    for k, v in safe_diag.items():
        if k not in {
            "routing",
            "provider_diagnostics",
            "warnings",
            "runtime_path",
        }:
            diag_out[k] = v

    return {
        "data": records,
        "meta": meta,
        "diagnostics": diag_out,
    }

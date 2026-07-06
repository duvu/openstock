"""
DataResult: structured internal result envelope for vnstock platform.

DataResult wraps a DataFrame with metadata from the data pipeline:
provider, quality status, diagnostics, fetch timestamp, etc.

It MUST NOT contain auth secrets (passwords, tokens, API keys, cookies).

Usage::

    from vnstock.core.result import DataResult
    from datetime import datetime

    result = DataResult(
        dataset="equity.ohlcv",
        provider="KBS",
        data=df,
        quality_status="PASS",
        quality_report={"checks": []},
        diagnostics={"routing_reason": "default priority"},
        fetched_at=datetime.utcnow(),
    )

    df_with_meta = result.to_dataframe()
    # df_with_meta.attrs["provider"] == "KBS"
    # df_with_meta.attrs["quality_status"] == "PASS"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

#: Metadata keys that MUST NOT appear in DataResult or DataFrame.attrs.
_FORBIDDEN_METADATA_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "api_key",
        "access_token",
        "refresh_token",
        "cookie",
        "session_id",
        "authorization",
        "authorization_header",
    }
)


@dataclass
class DataResult:
    """Structured internal result envelope from the data pipeline.

    Attributes:
        dataset: Dotted dataset name, e.g. ``"equity.ohlcv"``.
        provider: Provider name that produced the data, e.g. ``"KBS"``.
        data: The raw result :class:`pandas.DataFrame`.
        quality_status: Summary quality gate result (``"PASS"`` / ``"FAIL"``
            / ``None`` if not validated).
        quality_report: Detailed quality validation report.
        diagnostics: Routing and pipeline diagnostics dict.
        fetched_at: UTC timestamp when data was fetched.
        ingestion_run_id: Optional ingestion run identifier for batch use.
    """

    dataset: str
    provider: str
    data: pd.DataFrame
    quality_status: str | None = None
    quality_report: dict[str, Any] | None = field(default_factory=dict)
    diagnostics: dict[str, Any] | None = field(default_factory=dict)
    fetched_at: datetime | None = None
    ingestion_run_id: str | None = None

    def to_dataframe(self) -> pd.DataFrame:
        """Return ``data`` with metadata attached to ``DataFrame.attrs``.

        The following keys are set on ``df.attrs``:

        - ``dataset``
        - ``provider``
        - ``quality_status``
        - ``quality``  (same as quality_report, for backward compatibility)
        - ``diagnostics``
        - ``fetched_at``
        - ``ingestion_run_id``

        Auth secrets are never written to attrs.

        Returns:
            The underlying :class:`pandas.DataFrame` with attrs populated.
        """
        df = self.data
        df.attrs["dataset"] = self.dataset
        df.attrs["provider"] = self.provider
        df.attrs["quality_status"] = self.quality_status
        # "quality" key for backward compatibility with existing df.attrs usage
        df.attrs["quality"] = self.quality_report
        df.attrs["diagnostics"] = self.diagnostics
        df.attrs["fetched_at"] = self.fetched_at
        df.attrs["ingestion_run_id"] = self.ingestion_run_id
        return df

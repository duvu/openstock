from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol

import duckdb

from vnalpha.data_provisioning.service import (
    DataProvisioningRequest,
    DataProvisioningResult,
    DataProvisioningService,
)
from vnalpha.data_provisioning.source_policy import (
    ResolvedSource,
    SourcePolicyResolver,
    get_default_resolver,
)


class ProvisioningExecutor(Protocol):
    def execute(self, request: DataProvisioningRequest) -> DataProvisioningResult: ...


@dataclass(frozen=True, slots=True)
class MaintenanceSourcePolicy:
    reference_symbols: ResolvedSource
    equity_ohlcv: ResolvedSource
    index_ohlcv: ResolvedSource
    index_membership: ResolvedSource
    sector_membership: ResolvedSource

    def source_for_request(self, request: DataProvisioningRequest) -> ResolvedSource | None:
        operation = request.operation.strip().lower()
        artifact = request.artifact.strip().lower()
        if operation == "download" and artifact == "symbols":
            return self.reference_symbols
        if artifact in {"daily", "ohlcv"} and operation in {
            "download",
            "sync",
            "repair",
        }:
            return self.equity_ohlcv
        if operation == "download" and artifact == "index":
            return self.index_ohlcv
        if artifact in {"index-membership", "index_membership"}:
            return self.index_membership
        if artifact in {"sector-membership", "sector_membership"}:
            return self.sector_membership
        return None

    def to_dict(self) -> dict[str, object]:
        return {
            "reference.symbols": _resolved_dict(self.reference_symbols),
            "equity.ohlcv": _resolved_dict(self.equity_ohlcv),
            "index.ohlcv": _resolved_dict(self.index_ohlcv),
            "reference.index_membership_snapshot": _resolved_dict(
                self.index_membership
            ),
            "reference.sector_membership_snapshot": _resolved_dict(
                self.sector_membership
            ),
        }


def resolve_maintenance_source_policy(
    *,
    resolver: SourcePolicyResolver | None = None,
    legacy_ohlcv_source: str | None = None,
    reference_source: str | None = None,
    equity_source: str | None = None,
    index_source: str | None = None,
    membership_source: str | None = None,
) -> MaintenanceSourcePolicy:
    """Resolve independent sources for every acquired maintenance dataset.

    The legacy ``--source`` value applies only to equity/index OHLCV. It never
    overrides reference symbols or membership, preventing an explicit-only
    FiinQuantX OHLCV choice from being reused for unsupported symbol bootstrap.
    """
    policy_resolver = resolver or get_default_resolver()
    legacy = _normalize(legacy_ohlcv_source)
    return MaintenanceSourcePolicy(
        reference_symbols=policy_resolver.resolve(
            "reference.symbols",
            requested_source=_normalize(reference_source),
        ),
        equity_ohlcv=policy_resolver.resolve(
            "equity.ohlcv",
            requested_source=_normalize(equity_source) or legacy,
        ),
        index_ohlcv=policy_resolver.resolve(
            "index.ohlcv",
            requested_source=_normalize(index_source) or legacy,
        ),
        index_membership=policy_resolver.resolve(
            "reference.index_membership_snapshot",
            requested_source=_normalize(membership_source),
        ),
        sector_membership=policy_resolver.resolve(
            "reference.sector_membership_snapshot",
            requested_source=_normalize(membership_source),
        ),
    )


class RoutedDataProvisioningService:
    """A thin application adapter that applies per-dataset source ownership."""

    def __init__(
        self,
        conn: duckdb.DuckDBPyConnection,
        policy: MaintenanceSourcePolicy,
        *,
        delegate: ProvisioningExecutor | None = None,
    ) -> None:
        self.policy = policy
        self.delegate = delegate or DataProvisioningService(conn)

    def execute(self, request: DataProvisioningRequest) -> DataProvisioningResult:
        resolved = self.policy.source_for_request(request)
        routed = request if resolved is None else replace(request, source=resolved.source)
        return self.delegate.execute(routed)


def _normalize(value: str | None) -> str | None:
    normalized = value.strip().lower() if value else ""
    return normalized or None


def _resolved_dict(value: ResolvedSource) -> dict[str, object]:
    return {
        "source": value.source,
        "mode": value.mode.value,
        "fallback_allowed": value.fallback_allowed,
        "rationale": value.rationale,
    }


__all__ = [
    "MaintenanceSourcePolicy",
    "RoutedDataProvisioningService",
    "resolve_maintenance_source_policy",
]

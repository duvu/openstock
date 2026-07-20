"""Explicit per-dataset provider source policy (issue #253).

Resolves source selection independently for each canonical dataset instead of
using one ambiguous global source. Explicit source requests never fall back
silently. Provider validity is checked against the real registered provider
set: free auto-route providers plus the licensed explicit-only FiinQuantX SDK.
There is no SSI provider in the registry, so it is never treated as valid.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum


class SourceSelectionMode(str, Enum):
    AUTO = "AUTO"
    EXPLICIT = "EXPLICIT"
    CONFIGURED = "CONFIGURED"


# Free providers that auto-route Vietnamese reference/OHLCV data. These match
# the plugins registered in vnstock's runtime bootstrap; SSI is intentionally
# absent because no SSI provider is registered.
_FREE_PROVIDERS = ("vci", "kbs", "dnse", "tcbs")
_EXPLICIT_ONLY_PROVIDER = "fiinquantx"

_DATASET_ALIASES = {
    "index.membership": "reference.index_membership_snapshot",
    "sector.membership": "reference.sector_membership_snapshot",
}

_DATASET_CONFIG_KEYS = {
    "reference.symbols": "OPENSTOCK_REFERENCE_SOURCE",
    "equity.ohlcv": "OPENSTOCK_EQUITY_OHLCV_SOURCE",
    "index.ohlcv": "OPENSTOCK_INDEX_OHLCV_SOURCE",
    "reference.index_membership_snapshot": "OPENSTOCK_MEMBERSHIP_SOURCE",
    "reference.sector_membership_snapshot": "OPENSTOCK_MEMBERSHIP_SOURCE",
}

# Datasets that accept a global ``default_source`` override. Reference universe
# and membership never take the global default: reference always auto-routes
# across free providers and membership is owned by the configured reference
# provider.
_DEFAULTABLE_DATASETS = ("equity.ohlcv", "index.ohlcv")


@dataclass(frozen=True, slots=True)
class ResolvedSource:
    dataset: str
    source: str | None
    mode: SourceSelectionMode
    fallback_allowed: bool
    rationale: str


class InvalidSourceForDataset(ValueError):
    pass


class SourcePolicyResolver:
    """Resolve one provider policy independently for each canonical dataset."""

    def __init__(
        self,
        *,
        default_source: str | None = None,
        configured_sources: dict[str, str] | None = None,
        allow_auto_fallback: bool = True,
    ) -> None:
        self.default_source = (
            default_source.strip().lower()
            if default_source and default_source.strip()
            else None
        )
        self.configured_sources = {
            _canonical_dataset(dataset): source.strip().lower()
            for dataset, source in (configured_sources or {}).items()
            if source and source.strip()
        }
        self.allow_auto_fallback = allow_auto_fallback

    def resolve(
        self,
        dataset: str,
        requested_source: str | None = None,
    ) -> ResolvedSource:
        canonical_dataset = _canonical_dataset(dataset)

        if requested_source is not None:
            source = requested_source.strip().lower()
            valid, reason = self.validate_source_for_dataset(canonical_dataset, source)
            if not valid:
                raise InvalidSourceForDataset(reason)
            return ResolvedSource(
                dataset=canonical_dataset,
                source=source,
                mode=SourceSelectionMode.EXPLICIT,
                fallback_allowed=False,
                rationale=f"Source {source} was explicitly requested: {reason}",
            )

        configured = self.configured_sources.get(canonical_dataset)
        if configured is None and canonical_dataset in _DEFAULTABLE_DATASETS:
            configured = self.default_source
        if configured:
            valid, reason = self.validate_source_for_dataset(
                canonical_dataset, configured
            )
            if not valid:
                raise InvalidSourceForDataset(
                    f"Configured source {configured!r} is invalid for "
                    f"{canonical_dataset}: {reason}"
                )
            return ResolvedSource(
                dataset=canonical_dataset,
                source=configured,
                mode=SourceSelectionMode.CONFIGURED,
                fallback_allowed=(
                    self.allow_auto_fallback and configured != _EXPLICIT_ONLY_PROVIDER
                ),
                rationale=f"Configured source {configured}: {reason}",
            )

        if canonical_dataset == "reference.symbols":
            return ResolvedSource(
                dataset=canonical_dataset,
                source=None,
                mode=SourceSelectionMode.AUTO,
                fallback_allowed=True,
                rationale=(
                    "Reference universe uses auto-routing only across supported "
                    "free providers; the global default is ignored here"
                ),
            )

        if canonical_dataset in {"equity.ohlcv", "index.ohlcv"}:
            return ResolvedSource(
                dataset=canonical_dataset,
                source=None,
                mode=SourceSelectionMode.AUTO,
                fallback_allowed=True,
                rationale=(
                    "OHLCV uses runtime auto-routing; licensed providers remain "
                    "explicit-only"
                ),
            )

        if canonical_dataset in {
            "reference.index_membership_snapshot",
            "reference.sector_membership_snapshot",
        }:
            return ResolvedSource(
                dataset=canonical_dataset,
                source="vci",
                mode=SourceSelectionMode.CONFIGURED,
                fallback_allowed=False,
                rationale="Membership defaults to the configured reference provider",
            )

        raise InvalidSourceForDataset(f"Unsupported canonical dataset {dataset!r}")

    def validate_source_for_dataset(
        self,
        dataset: str,
        source: str,
    ) -> tuple[bool, str]:
        canonical_dataset = _canonical_dataset(dataset)
        normalized_source = source.strip().lower()

        if normalized_source == _EXPLICIT_ONLY_PROVIDER:
            if canonical_dataset == "reference.symbols":
                return (
                    False,
                    "FiinQuantX cannot be used for the reference symbol universe",
                )
            if canonical_dataset in {
                "equity.ohlcv",
                "index.ohlcv",
                "reference.index_membership_snapshot",
                "reference.sector_membership_snapshot",
            }:
                return True, "FiinQuantX supports this dataset as explicit-only"
            return False, f"FiinQuantX does not support {canonical_dataset}"

        if normalized_source in _FREE_PROVIDERS:
            return True, f"{normalized_source} is an allowed runtime provider"

        return False, f"Unknown source {source!r}"


def _canonical_dataset(dataset: str) -> str:
    normalized = dataset.strip().lower()
    return _DATASET_ALIASES.get(normalized, normalized)


def get_default_resolver() -> SourcePolicyResolver:
    configured = {
        dataset: value
        for dataset, env_name in _DATASET_CONFIG_KEYS.items()
        if (value := os.getenv(env_name, "").strip())
    }
    return SourcePolicyResolver(configured_sources=configured)


__all__ = [
    "InvalidSourceForDataset",
    "ResolvedSource",
    "SourcePolicyResolver",
    "SourceSelectionMode",
    "get_default_resolver",
]

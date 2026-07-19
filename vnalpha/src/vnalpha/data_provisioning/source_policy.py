"""Per-dataset source policy resolver for issue #253.

Resolves source selection per dataset rather than using one ambiguous global
source. Explicit source requests never fall back silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SourceSelectionMode(str, Enum):
    """How a source was selected."""

    AUTO = "AUTO"  # Automatic provider selection
    EXPLICIT = "EXPLICIT"  # User-specified source
    CONFIGURED = "CONFIGURED"  # Configuration file default


@dataclass(frozen=True, slots=True)
class ResolvedSource:
    """Result of source policy resolution."""

    dataset: str
    source: str | None
    mode: SourceSelectionMode
    fallback_allowed: bool
    rationale: str


class SourcePolicyResolver:
    """Resolves source selection per dataset with explicit policy."""

    def __init__(
        self,
        *,
        default_source: str | None = None,
        allow_auto_fallback: bool = True,
    ) -> None:
        """Initialize resolver with global defaults.

        Args:
            default_source: Global default source if any
            allow_auto_fallback: Whether to allow automatic provider fallback
        """
        self.default_source = default_source
        self.allow_auto_fallback = allow_auto_fallback

    def resolve(
        self,
        dataset: str,
        requested_source: str | None = None,
    ) -> ResolvedSource:
        """Resolve source for a specific dataset.

        Args:
            dataset: Dataset identifier (e.g., 'equity.ohlcv')
            requested_source: User-requested source, if any

        Returns:
            ResolvedSource with selection mode and fallback policy
        """
        # Explicit source request - no fallback
        if requested_source is not None:
            return ResolvedSource(
                dataset=dataset,
                source=requested_source,
                mode=SourceSelectionMode.EXPLICIT,
                fallback_allowed=False,
                rationale=f"User requested {requested_source} explicitly",
            )

        # Dataset-specific policy
        if dataset == "reference.symbols":
            # Reference data: auto-route only, never FiinQuantX
            return ResolvedSource(
                dataset=dataset,
                source=None,
                mode=SourceSelectionMode.AUTO,
                fallback_allowed=True,
                rationale="Reference data uses auto-routing across free providers",
            )

        elif dataset in ("equity.ohlcv", "index.ohlcv"):
            # OHLCV: auto-route or use default
            if self.default_source:
                return ResolvedSource(
                    dataset=dataset,
                    source=self.default_source,
                    mode=SourceSelectionMode.CONFIGURED,
                    fallback_allowed=self.allow_auto_fallback,
                    rationale=f"Default source {self.default_source} with fallback={self.allow_auto_fallback}",
                )
            return ResolvedSource(
                dataset=dataset,
                source=None,
                mode=SourceSelectionMode.AUTO,
                fallback_allowed=True,
                rationale="Auto-routing enabled for OHLCV",
            )

        elif dataset in ("index.membership", "sector.membership"):
            # Membership: VCI only (official exchange data)
            return ResolvedSource(
                dataset=dataset,
                source="vci",
                mode=SourceSelectionMode.CONFIGURED,
                fallback_allowed=False,
                rationale="Membership data requires official VCI source",
            )

        # Unknown dataset: auto with fallback
        return ResolvedSource(
            dataset=dataset,
            source=self.default_source,
            mode=SourceSelectionMode.AUTO if not self.default_source else SourceSelectionMode.CONFIGURED,
            fallback_allowed=True,
            rationale="No specific policy, using defaults",
        )

    def validate_source_for_dataset(
        self,
        dataset: str,
        source: str,
    ) -> tuple[bool, str]:
        """Validate if a source is allowed for a dataset.

        Returns:
            (is_valid, reason)
        """
        # FiinQuantX restrictions
        if source == "fiinquantx":
            if dataset == "reference.symbols":
                return (
                    False,
                    "FiinQuantX cannot be used for reference.symbols",
                )
            if dataset in ("equity.ohlcv", "index.ohlcv"):
                return (True, "FiinQuantX supports OHLCV as explicit-only")
            return (
                False,
                f"FiinQuantX does not support dataset {dataset}",
            )

        # Free providers (vci, kbs, ssi) support all current datasets
        if source in ("vci", "kbs", "ssi"):
            return (True, f"{source} supports {dataset}")

        # Unknown source
        return (False, f"Unknown source {source}")


def get_default_resolver() -> SourcePolicyResolver:
    """Return the default production source policy resolver."""
    return SourcePolicyResolver(
        default_source=None,  # Auto-routing by default
        allow_auto_fallback=True,
    )

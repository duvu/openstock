"""Provider capability matrix rendering and validation.

Produces a human-readable or structured matrix of which providers support
which (asset_class, dataset_type) combinations, derived from CAPABILITIES.
"""

from __future__ import annotations

from typing import Any

from vnstock.core.provider.capabilities import CAPABILITIES, query_capabilities


def build_matrix(
    providers: list[str] | None = None,
    dataset_types: list[str] | None = None,
    asset_classes: list[str] | None = None,
) -> dict[str, Any]:
    """Build a capability matrix dict.

    Returns a dict with:
    - providers: sorted list of provider names
    - dataset_types: sorted list of dataset types
    - asset_classes: sorted list of asset classes
    - matrix: {provider: {dataset_type: {asset_class: bool}}}
    - summary: {provider: {"total": int, "dataset_types": list}}
    """
    all_providers = sorted({c.provider for c in CAPABILITIES})
    all_dataset_types = sorted({c.dataset_type for c in CAPABILITIES})
    all_asset_classes = sorted({c.asset_class for c in CAPABILITIES})

    # Apply optional filters
    if providers is not None:
        lower_filter = {p.lower() for p in providers}
        all_providers = [p for p in all_providers if p.lower() in lower_filter]
    if dataset_types is not None:
        all_dataset_types = [d for d in all_dataset_types if d in dataset_types]
    if asset_classes is not None:
        all_asset_classes = [a for a in all_asset_classes if a in asset_classes]

    matrix: dict[str, dict[str, dict[str, bool]]] = {}
    summary: dict[str, Any] = {}

    for provider in all_providers:
        matrix[provider] = {}
        supported_dataset_types: set[str] = set()

        for dt in all_dataset_types:
            matrix[provider][dt] = {}
            for ac in all_asset_classes:
                caps = query_capabilities(
                    provider=provider, dataset_type=dt, asset_class=ac
                )
                supported = len(caps) > 0
                matrix[provider][dt][ac] = supported
                if supported:
                    supported_dataset_types.add(dt)

        summary[provider] = {
            "total": sum(
                1
                for dt in matrix[provider]
                for ac in matrix[provider][dt]
                if matrix[provider][dt][ac]
            ),
            "dataset_types": sorted(supported_dataset_types),
        }

    return {
        "providers": all_providers,
        "dataset_types": all_dataset_types,
        "asset_classes": all_asset_classes,
        "matrix": matrix,
        "summary": summary,
    }


def render_matrix_text(matrix_dict: dict[str, Any]) -> str:
    """Render the capability matrix as a plain-text table."""
    providers = matrix_dict["providers"]
    dataset_types = matrix_dict["dataset_types"]
    asset_classes = matrix_dict["asset_classes"]
    matrix = matrix_dict["matrix"]

    # Header row
    col_headers = [f"{dt}/{ac}" for dt in dataset_types for ac in asset_classes]
    col_width = max(len(h) for h in col_headers + providers + ["Provider"]) + 2

    header = "Provider".ljust(col_width) + "".join(
        h.ljust(col_width) for h in col_headers
    )
    sep = "-" * len(header)
    lines = [header, sep]

    for provider in providers:
        row = provider.ljust(col_width)
        for dt in dataset_types:
            for ac in asset_classes:
                supported = matrix.get(provider, {}).get(dt, {}).get(ac, False)
                cell = "✓" if supported else "·"
                row += cell.ljust(col_width)
        lines.append(row)

    return "\n".join(lines)

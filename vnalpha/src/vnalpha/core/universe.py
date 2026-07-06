"""Named universe resolver for vnalpha.

Resolves named universes (e.g. VN30) to lists of symbols.
For Phase 5, VN30 is resolved from static config (universe.yaml).

Resolution order for sync ohlcv:
1. if --symbols is supplied, use explicit symbols.
2. else if --universe is supplied, resolve named universe.
3. else use active symbols from symbol_master.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml  # type: ignore[import-untyped]

from vnalpha.core.logging import get_logger

logger = get_logger("core.universe")

# ---------------------------------------------------------------------------
# Static VN30 constituent list (Phase 5 default)
# These are the VN30 constituents as of 2024. Update as needed.
# ---------------------------------------------------------------------------
VN30_SYMBOLS: list[str] = [
    "ACB",
    "BCM",
    "BID",
    "BVH",
    "CTG",
    "FPT",
    "GAS",
    "GVR",
    "HDB",
    "HPG",
    "MBB",
    "MSN",
    "MWG",
    "NVL",
    "PDR",
    "PLX",
    "POW",
    "SAB",
    "SHB",
    "SSB",
    "SSI",
    "STB",
    "TCB",
    "TPB",
    "VCB",
    "VHM",
    "VIB",
    "VIC",
    "VJC",
    "VNM",
    "VPB",
    "VRE",
]

# Known named universes (Phase 5 static config)
_STATIC_UNIVERSES: dict[str, list[str]] = {
    "VN30": VN30_SYMBOLS,
}


def _load_yaml_universe(name: str) -> Optional[list[str]]:
    """Try to load a universe from the configs/universe.yaml file."""
    configs_path = Path(os.environ.get("VNALPHA_CONFIGS", "configs")) / "universe.yaml"
    if not configs_path.exists():
        # Try relative to package root
        pkg_root = Path(__file__).parent.parent.parent.parent.parent
        configs_path = pkg_root / "configs" / "universe.yaml"

    if not configs_path.exists():
        return None

    try:
        with open(configs_path) as f:
            data = yaml.safe_load(f)
        universes = data.get("universes", {})
        if name in universes:
            # For Phase 5, universe.yaml defines filter-based resolution;
            # fall back to static list for VN30 since we don't have a live resolver.
            return None
    except Exception as e:
        logger.warning("Failed to load universe.yaml: %s", e)
    return None


def resolve_universe(name: str) -> list[str]:
    """Resolve a named universe to a list of symbols.

    Supported named universes for Phase 5:
        VN30 — static list of VN30 index constituents

    Raises:
        ValueError: if the named universe is unknown.
    """
    upper = name.strip().upper()

    # Check static universes first
    if upper in _STATIC_UNIVERSES:
        symbols = _STATIC_UNIVERSES[upper]
        logger.info("Resolved universe %s: %d symbols (static)", upper, len(symbols))
        return list(symbols)

    # Try YAML-based resolution (Phase 5.8+ extension point)
    yaml_result = _load_yaml_universe(upper)
    if yaml_result is not None:
        logger.info("Resolved universe %s: %d symbols (yaml)", upper, len(yaml_result))
        return yaml_result

    raise ValueError(
        f"Unknown universe '{name}'. "
        f"Supported universes for Phase 5: {list(_STATIC_UNIVERSES.keys())}. "
        "Add custom universes in configs/universe.yaml."
    )


def parse_symbols_or_universe(
    symbols: Optional[str],
    universe: Optional[str],
) -> Optional[list[str]]:
    """Resolve CLI options to a concrete symbol list or None (all active).

    Resolution order:
        1. --symbols takes precedence over --universe
        2. --universe resolves named universe
        3. None → caller should use active symbols from warehouse
    """
    if symbols:
        return [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if universe:
        return resolve_universe(universe)
    return None

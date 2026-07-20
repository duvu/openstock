"""Stable failure classification for current-symbol data preparation (#305).

Maps a failed provisioning action plus its raised exception to a stable,
sanitized failure category, the affected dataset/symbol, and a bounded
root-cause message. This preserves the first actionable root cause instead of
collapsing every failure into a generic "could not be made ready" wrapper.

No vendor response bodies, credentials or unbounded prose are surfaced: the
root cause is a truncated, single-line exception message and the category is
drawn from a fixed vocabulary.
"""

from __future__ import annotations

from vnalpha.data_availability.models import EnsureDataAction

_MAX_ROOT_CAUSE_CHARS = 240

# Which canonical dataset each action operates on.
_ACTION_DATASET = {
    EnsureDataAction.SYMBOLS_SYNCED: "reference.symbols",
    EnsureDataAction.OHLCV_SYNCED: "equity.ohlcv",
    EnsureDataAction.CANONICAL_BUILT: "equity.canonical_ohlcv",
    EnsureDataAction.BENCHMARK_SYNCED: "index.ohlcv",
    EnsureDataAction.BENCHMARK_CANONICAL_BUILT: "index.canonical_ohlcv",
    EnsureDataAction.FEATURES_BUILT: "feature_snapshot",
    EnsureDataAction.SCORED: "candidate_score",
}

# The benchmark actions concern VNINDEX rather than the requested symbol.
_BENCHMARK_ACTIONS = frozenset(
    {
        EnsureDataAction.BENCHMARK_SYNCED,
        EnsureDataAction.BENCHMARK_CANONICAL_BUILT,
    }
)

# Marker phrases → stable failure category. Checked case-insensitively against
# the exception message; falls back to a per-action default when nothing hits.
_MESSAGE_MARKERS: tuple[tuple[str, str], ...] = (
    ("no raw", "NO_RAW_ROWS"),
    ("does not support", "PROVIDER_UNSUPPORTED_DATASET"),
    ("not support index", "PROVIDER_UNSUPPORTED_DATASET"),
    ("schema", "CANONICAL_SCHEMA_INVALID"),
    ("quarantine", "CANONICAL_SCHEMA_INVALID"),
    ("benchmark", "BENCHMARK_JOIN_EMPTY"),
    ("lookback", "INSUFFICIENT_LOOKBACK"),
    ("insufficient", "INSUFFICIENT_LOOKBACK"),
    ("no row", "SCORE_INPUT_MISSING"),
    ("produced no", "SCORE_INPUT_MISSING"),
    ("postcondition", "POSTCONDITION_UNSATISFIED"),
    ("credential", "PROVIDER_AUTH_MISSING"),
    ("auth", "PROVIDER_AUTH_MISSING"),
    ("not a completed", "SESSION_NOT_COMPLETED"),
    ("calendar", "SESSION_NOT_COMPLETED"),
)

_ACTION_DEFAULT_CATEGORY = {
    EnsureDataAction.SYMBOLS_SYNCED: "SYMBOL_SYNC_FAILED",
    EnsureDataAction.OHLCV_SYNCED: "OHLCV_SYNC_FAILED",
    EnsureDataAction.CANONICAL_BUILT: "CANONICAL_BUILD_FAILED",
    EnsureDataAction.BENCHMARK_SYNCED: "BENCHMARK_SYNC_FAILED",
    EnsureDataAction.BENCHMARK_CANONICAL_BUILT: "BENCHMARK_CANONICAL_BUILD_FAILED",
    EnsureDataAction.FEATURES_BUILT: "FEATURE_BUILD_FAILED",
    EnsureDataAction.SCORED: "SCORE_BUILD_FAILED",
}


def dataset_for_action(action: EnsureDataAction) -> str:
    return _ACTION_DATASET.get(action, action.value.lower())


def subject_symbol(action: EnsureDataAction, symbol: str, benchmark: str) -> str:
    return benchmark if action in _BENCHMARK_ACTIONS else symbol


def sanitize_root_cause(error: BaseException) -> str:
    """Return a bounded, single-line, prose-free root-cause message."""
    message = str(error).strip() or type(error).__name__
    # Collapse to one line and bound length; never leak multi-line vendor prose.
    message = " ".join(message.split())
    if len(message) > _MAX_ROOT_CAUSE_CHARS:
        message = message[: _MAX_ROOT_CAUSE_CHARS - 1].rstrip() + "…"
    return f"{type(error).__name__}: {message}"


def classify_failure(action: EnsureDataAction, error: BaseException) -> str:
    """Map an action failure to a stable failure category."""
    lowered = str(error).casefold()
    for marker, category in _MESSAGE_MARKERS:
        if marker in lowered:
            return category
    return _ACTION_DEFAULT_CATEGORY.get(action, "PROVISIONING_FAILED")


__all__ = [
    "classify_failure",
    "dataset_for_action",
    "sanitize_root_cause",
    "subject_symbol",
]

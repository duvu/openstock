"""vnalpha top-level logging facade.

Re-exports the full logging API from vnalpha.core.logging so callers can use either:
    from vnalpha.logging import configure_logging, get_logger, set_correlation_id
    from vnalpha.core.logging import configure_logging, get_logger, set_correlation_id
"""

from __future__ import annotations

from vnalpha.core.logging import (
    configure_logging,
    get_correlation_id,
    get_logger,
    set_correlation_id,
)

__all__ = [
    "configure_logging",
    "get_correlation_id",
    "get_logger",
    "set_correlation_id",
]

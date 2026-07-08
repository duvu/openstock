"""vnalpha structured logging — async-safe, rotating file + colored stderr.

Public surface:
    configure_logging(level, log_path)  — idempotent setup, called once at CLI entry.
    get_logger(name)                    — returns a structlog BoundLogger.
    set_correlation_id()                — generates UUID4 and stores in ContextVar.

Correlation ID unification (task 1.2-1.3):
    The single source-of-truth for the correlation ID is
    ``vnalpha.observability.context``.  Both structlog events and file-based
    observability events therefore carry the same value.  ``set_correlation_id``
    and ``get_correlation_id`` below delegate to that module.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import queue
from pathlib import Path
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger

# ---------------------------------------------------------------------------
# Correlation ID — unified with observability.context
# ---------------------------------------------------------------------------


def set_correlation_id() -> str:
    """Generate a new UUID4 correlation ID, bind it, and return it.

    Delegates to ``vnalpha.observability.context`` so that structlog events and
    file-based observability events always share the same value.
    """
    from vnalpha.observability.context import (
        set_correlation_id as _obs_set,  # noqa: PLC0415
    )

    return _obs_set()


def get_correlation_id() -> str:
    """Return the current correlation ID (empty string if not set).

    Delegates to ``vnalpha.observability.context`` — the single source of truth.
    """
    from vnalpha.observability.context import (
        get_correlation_id as _obs_get,  # noqa: PLC0415
    )

    cid = _obs_get()
    # observability defaults to "unset"; normalise to "" for backwards compat
    return "" if cid == "unset" else cid


# ---------------------------------------------------------------------------
# structlog processor: inject correlation_id into every event dict
# ---------------------------------------------------------------------------


def _inject_correlation_id(
    _logger: WrappedLogger, _method: str, event_dict: EventDict
) -> EventDict:
    cid = get_correlation_id()
    if cid:
        event_dict["correlation_id"] = cid
    return event_dict


# ---------------------------------------------------------------------------
# Internal state
# ---------------------------------------------------------------------------

_CONFIGURED = False
_QUEUE_LISTENER: logging.handlers.QueueListener | None = None

_DEFAULT_LOG_PATH = (
    Path.home() / ".local" / "share" / "openstock" / "logs" / "vnalpha.log"
)
_DEFAULT_LEVEL = "INFO"


# ---------------------------------------------------------------------------
# configure_logging
# ---------------------------------------------------------------------------


def configure_logging(
    level: str | None = None,
    log_path: Path | str | None = None,
) -> None:
    """Configure the vnalpha logging subsystem.  Idempotent: safe to call multiple times.

    Architecture:
    - Root logger → QueueHandler (async)
    - QueueHandler has a ProcessorFormatter(JSONRenderer) so QueueHandler.prepare()
      stores a JSON string in record.msg.
    - QueueListener → RotatingFileHandler(%(message)s) writes those JSON strings.
    - Root logger → StreamHandler (direct, colored console via ProcessorFormatter).
    - The two handlers use separate ProcessorFormatter instances so they never share
      a mutated LogRecord.

    Reads env vars:
    - VNALPHA_LOG_LEVEL (default INFO)
    - VNALPHA_LOG_PATH  (default ~/.local/share/openstock/logs/vnalpha.log)
    """
    global _CONFIGURED, _QUEUE_LISTENER  # noqa: PLW0603

    if _CONFIGURED:
        return

    resolved_level_str = (
        level or os.environ.get("VNALPHA_LOG_LEVEL", _DEFAULT_LEVEL)
    ).upper()
    resolved_level = getattr(logging, resolved_level_str, logging.INFO)

    resolved_path = Path(
        log_path or os.environ.get("VNALPHA_LOG_PATH", str(_DEFAULT_LOG_PATH))
    )
    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    pre_chain = _shared_pre_chain()

    # --- File handler: plain %(message)s — JSON string was rendered by QueueHandler ---
    file_handler = logging.handlers.RotatingFileHandler(
        resolved_path,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(resolved_level)
    file_handler.setFormatter(logging.Formatter("%(message)s"))

    # --- QueueHandler with JSON formatter so prepare() stores JSON in record.msg ---
    log_queue: queue.Queue[Any] = queue.Queue(maxsize=0)  # unbounded
    queue_handler = logging.handlers.QueueHandler(log_queue)
    queue_handler.setLevel(resolved_level)
    queue_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
            foreign_pre_chain=pre_chain,
        )
    )

    _QUEUE_LISTENER = logging.handlers.QueueListener(
        log_queue, file_handler, respect_handler_level=True
    )
    _QUEUE_LISTENER.start()

    # --- Stderr handler: colored console, direct (separate LogRecord copy) ---
    stderr_handler = logging.StreamHandler()
    stderr_handler.setLevel(resolved_level)
    stderr_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            foreign_pre_chain=pre_chain,
        )
    )

    # --- Root logger ---
    root_logger = logging.getLogger()
    existing_types = {type(h) for h in root_logger.handlers}
    if logging.handlers.QueueHandler not in existing_types:
        root_logger.addHandler(queue_handler)
    has_stream = any(
        isinstance(h, logging.StreamHandler)
        and not isinstance(h, (logging.FileHandler, logging.handlers.QueueHandler))
        for h in root_logger.handlers
    )
    if not has_stream:
        root_logger.addHandler(stderr_handler)
    root_logger.setLevel(resolved_level)

    # --- structlog configuration ---
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            _inject_correlation_id,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    _CONFIGURED = True


def _shared_pre_chain() -> list[Any]:
    """Processors applied by ProcessorFormatter before the final renderer."""
    return [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        _inject_correlation_id,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]


# ---------------------------------------------------------------------------
# Public logger factory
# ---------------------------------------------------------------------------


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog BoundLogger bound to *name*."""
    return structlog.get_logger(name)

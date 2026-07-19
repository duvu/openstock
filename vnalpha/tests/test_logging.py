"""Tests for vnalpha.core.logging — configure_logging, get_logger, correlation ID."""

from __future__ import annotations

import asyncio
import json
import logging
import logging.handlers
import time
from pathlib import Path

import pytest

import vnalpha.core.logging as _log_module

# ---------------------------------------------------------------------------
# Helpers to reset module state between tests
# ---------------------------------------------------------------------------


def _reset_logging_state() -> None:
    """Reset the module-level singleton so configure_logging() can run again."""
    # Stop any running listener
    if _log_module._QUEUE_LISTENER is not None:
        try:
            _log_module._QUEUE_LISTENER.stop()
        except Exception:
            pass
    _log_module._QUEUE_LISTENER = None
    _log_module._CONFIGURED = False

    # Remove all handlers from root logger
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass

    # Reset structlog so it is not cached
    import structlog

    structlog.reset_defaults()


@pytest.fixture(autouse=True)
def reset_state() -> None:
    """Ensure a clean logging state for each test."""
    _reset_logging_state()
    yield
    _reset_logging_state()


# ---------------------------------------------------------------------------
# Task 1.2 — configure_logging: creates file, sets up handlers
# ---------------------------------------------------------------------------


def test_configure_logging_creates_log_file(tmp_path: Path) -> None:
    """Given a tmp log_path, configure_logging must create the file."""
    from vnalpha.core.logging import configure_logging, get_logger

    log_path = tmp_path / "logs" / "test.log"
    configure_logging(level="DEBUG", log_path=log_path)

    logger = get_logger("test")
    logger.info("probe message")
    time.sleep(0.3)

    assert log_path.exists(), "log file was not created"


def test_configure_logging_idempotent(tmp_path: Path) -> None:
    """Calling configure_logging() twice must not add duplicate handlers."""
    from vnalpha.core.logging import configure_logging

    log_path = tmp_path / "test.log"
    configure_logging(level="INFO", log_path=log_path)

    root = logging.getLogger()
    handler_count_after_first = len(root.handlers)

    # Second call must be a no-op
    configure_logging(level="INFO", log_path=log_path)

    assert len(root.handlers) == handler_count_after_first, (
        "configure_logging added handlers on second call"
    )


# ---------------------------------------------------------------------------
# Task 1.3 — get_logger: JSON output has required fields
# ---------------------------------------------------------------------------


def test_get_logger_json_fields(tmp_path: Path) -> None:
    """Log records written to file must contain timestamp, level, logger, event."""
    from vnalpha.core.logging import configure_logging, get_logger

    log_path = tmp_path / "test.log"
    configure_logging(level="DEBUG", log_path=log_path)

    logger = get_logger("mymodule")
    logger.info("structured info", extra_key="extra_value")
    time.sleep(0.3)

    lines = [ln for ln in log_path.read_text().strip().split("\n") if ln]
    assert lines, "No log lines written"
    rec = json.loads(lines[0])

    assert "timestamp" in rec, f"Missing timestamp. Keys: {list(rec.keys())}"
    assert "level" in rec, f"Missing level. Keys: {list(rec.keys())}"
    assert "logger" in rec, f"Missing logger. Keys: {list(rec.keys())}"
    assert "event" in rec, f"Missing event. Keys: {list(rec.keys())}"
    assert rec["event"] == "structured info"
    assert rec["level"] == "info"


def test_structlog_pipeline_redacts_dynamic_keys_and_values(tmp_path: Path) -> None:
    from vnalpha.core.logging import configure_logging, get_logger

    log_path = tmp_path / "redacted.log"
    private_fragment = "STRUCTLOG_PRIVATE_88"
    configure_logging(level="DEBUG", log_path=log_path)

    get_logger("security").warning(
        f"provider password={private_fragment}",
        **{"pass\x1b[31mword": private_fragment},
    )
    time.sleep(0.3)

    serialized = log_path.read_text()
    assert private_fragment not in serialized
    assert "\x1b[31m" not in serialized
    assert "[REDACTED]" in serialized


# ---------------------------------------------------------------------------
# Task 1.4 — correlation ID: set_correlation_id / get_correlation_id
# ---------------------------------------------------------------------------


def test_set_correlation_id_generates_uuid(tmp_path: Path) -> None:
    """set_correlation_id must return a non-empty hex string."""
    from vnalpha.core.logging import configure_logging, set_correlation_id

    configure_logging(level="INFO", log_path=tmp_path / "test.log")
    cid = set_correlation_id()
    assert cid, "correlation_id is empty"
    assert len(cid) == 32, f"Expected 32-char hex, got {len(cid)}: {cid!r}"


def test_correlation_id_in_log_record(tmp_path: Path) -> None:
    """Log records written after set_correlation_id must include correlation_id field."""
    from vnalpha.core.logging import configure_logging, get_logger, set_correlation_id

    log_path = tmp_path / "test.log"
    configure_logging(level="DEBUG", log_path=log_path)
    cid = set_correlation_id()

    logger = get_logger("test")
    logger.info("with cid")
    time.sleep(0.3)

    lines = [ln for ln in log_path.read_text().strip().split("\n") if ln]
    rec = json.loads(lines[0])
    assert rec.get("correlation_id") == cid, (
        f"correlation_id mismatch: {rec.get('correlation_id')!r} != {cid!r}"
    )


def test_correlation_id_propagates_across_asyncio_tasks(tmp_path: Path) -> None:
    """ContextVar propagates into child asyncio tasks spawned in the same context."""
    from vnalpha.core.logging import (
        configure_logging,
        get_correlation_id,
        set_correlation_id,
    )

    log_path = tmp_path / "test.log"
    configure_logging(level="DEBUG", log_path=log_path)

    async def _run() -> tuple[str, str]:
        cid = set_correlation_id()

        # Spawn a child task — it should inherit the same ContextVar
        async def _child() -> str:
            return get_correlation_id()

        child_cid = await asyncio.create_task(_child())
        return cid, child_cid

    parent_cid, child_cid = asyncio.run(_run())
    assert parent_cid == child_cid, (
        f"Child task did not inherit correlation_id: {parent_cid!r} != {child_cid!r}"
    )


def test_correlation_id_different_per_invocation(tmp_path: Path) -> None:
    """Each call to set_correlation_id generates a unique ID."""
    from vnalpha.core.logging import configure_logging, set_correlation_id

    configure_logging(level="INFO", log_path=tmp_path / "test.log")
    ids = {set_correlation_id() for _ in range(10)}
    assert len(ids) == 10, "set_correlation_id produced duplicate IDs"


# ---------------------------------------------------------------------------
# Task 1.8 — correlation ID unification: core and observability share one value
# ---------------------------------------------------------------------------


def test_correlation_id_shared_between_core_and_observability(tmp_path: Path) -> None:
    from vnalpha.core.logging import configure_logging
    from vnalpha.core.logging import get_correlation_id as core_get
    from vnalpha.core.logging import set_correlation_id as core_set
    from vnalpha.observability.context import get_correlation_id as obs_get

    configure_logging(level="INFO", log_path=tmp_path / "test.log")
    cid = core_set()
    assert core_get() == cid
    assert obs_get() == cid, (
        f"observability get_correlation_id={obs_get()!r} != core {cid!r}"
    )


def test_observability_set_visible_to_core(tmp_path: Path) -> None:
    from vnalpha.core.logging import configure_logging
    from vnalpha.core.logging import get_correlation_id as core_get
    from vnalpha.observability.context import set_correlation_id as obs_set

    configure_logging(level="INFO", log_path=tmp_path / "test.log")
    cid = obs_set()
    assert core_get() == cid, (
        f"core get_correlation_id={core_get()!r} != observability {cid!r}"
    )


# ---------------------------------------------------------------------------
# Task 1.9 — regression: no "unset" correlation IDs in instrumented commands
# ---------------------------------------------------------------------------


def test_no_unset_correlation_id_after_set(tmp_path: Path) -> None:
    from vnalpha.core.logging import (
        configure_logging,
        get_correlation_id,
        set_correlation_id,
    )

    configure_logging(level="INFO", log_path=tmp_path / "test.log")
    set_correlation_id()
    cid = get_correlation_id()
    assert cid != "unset", (
        "correlation_id must not be 'unset' after set_correlation_id()"
    )
    assert cid != "", "correlation_id must not be empty after set_correlation_id()"

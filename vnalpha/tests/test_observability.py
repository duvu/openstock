"""Tests for observability: context, jsonl, redaction, correlation, commands, errors."""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def isolated_run_ctx(tmp_path):
    """Return a fresh RunContext writing to tmp_path."""
    from vnalpha.observability.context import RunContext, reset_run_context

    reset_run_context()
    ctx = RunContext(
        run_id="test_run_abc12345",
        surface="cli",
        actor="test",
        log_root=tmp_path,
    )
    yield ctx
    reset_run_context()


@pytest.fixture(autouse=True)
def reset_run_ctx():
    from vnalpha.observability.context import reset_run_context

    reset_run_context()
    yield
    reset_run_context()


# ===========================================================================
# Section 1: Run directory and context
# ===========================================================================


class TestRunContext:
    def test_run_dir_is_created(self, tmp_path):
        from vnalpha.observability.context import RunContext

        ctx = RunContext(
            run_id="run_test_001",
            surface="cli",
            actor="test",
            log_root=tmp_path,
        )
        assert ctx.run_dir.exists()
        assert ctx.run_dir.is_dir()


# ===========================================================================
# Section 2: JSONL writer
# ===========================================================================


# ===========================================================================
# Section 3: Redaction
# ===========================================================================


# ===========================================================================
# Section 4: Correlation context
# ===========================================================================


# ===========================================================================
# Section 5: Command logging
# ===========================================================================


# ===========================================================================
# Section 6: Error capture
# ===========================================================================


# ===========================================================================
# Section 7: Chat logging
# ===========================================================================


# ===========================================================================
# Section 8: Tool trace logging
# ===========================================================================


# ===========================================================================
# Section 11: Summary generation
# ===========================================================================


# ===========================================================================
# Section 12: Bundle creation
# ===========================================================================


# ===========================================================================
# Section 12: Logs CLI commands
# ===========================================================================


# ===========================================================================
# Section 2 (additional): log_audit extended fields + event coverage
# ===========================================================================


# ===========================================================================
# Section 3 (additional): CLI lifecycle wrapper integration tests
# ===========================================================================

"""Tests for repair bundle generation and repair/deploy tracking (sections 13-16)."""

from __future__ import annotations

import json

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def isolated_run_ctx(tmp_path):
    """Fresh RunContext writing to tmp_path."""
    from vnalpha.observability.context import RunContext, reset_run_context

    reset_run_context()
    ctx = RunContext(
        run_id="test_run_repair",
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


@pytest.fixture()
def sample_run_dir(tmp_path):
    """Create a minimal fake run directory with JSONL files and a failed command."""
    run_dir = tmp_path / "runs" / "run_test_001"
    run_dir.mkdir(parents=True)

    # audit.jsonl with some events
    audit_events = [
        {
            "event_id": "e1",
            "run_id": "run_test_001",
            "created_at": "2024-01-01T00:00:00Z",
            "level": "INFO",
            "event_type": "COMMAND_STARTED",
            "surface": "cli",
            "correlation_id": "corr_abc",
            "summary": "Started pipeline",
            "redaction_status": "redacted",
            "metadata": {},
        },
        {
            "event_id": "e2",
            "run_id": "run_test_001",
            "created_at": "2024-01-01T00:01:00Z",
            "level": "ERROR",
            "event_type": "COMMAND_FAILED",
            "surface": "cli",
            "correlation_id": "corr_abc",
            "summary": "Pipeline step failed: DivisionByZero",
            "redaction_status": "redacted",
            "metadata": {},
        },
    ]
    (run_dir / "audit.jsonl").write_text(
        "\n".join(json.dumps(e) for e in audit_events) + "\n"
    )

    # errors.jsonl
    error_events = [
        {
            "event_id": "err1",
            "run_id": "run_test_001",
            "created_at": "2024-01-01T00:01:00Z",
            "level": "ERROR",
            "event_type": "EXCEPTION_CAPTURED",
            "surface": "cli",
            "correlation_id": "corr_abc",
            "summary": "ZeroDivisionError in compute_features",
            "error_type": "ZeroDivisionError",
            "error_message": "division by zero",
            "module": "vnalpha.features.compute",
            "function": "compute_features",
            "redaction_status": "redacted",
            "metadata": {},
        }
    ]
    (run_dir / "errors.jsonl").write_text(
        "\n".join(json.dumps(e) for e in error_events) + "\n"
    )

    # commands.jsonl with a failed command
    cmd_events = [
        {
            "event_id": "cmd1",
            "run_id": "run_test_001",
            "created_at": "2024-01-01T00:01:00Z",
            "level": "INFO",
            "event_type": "COMMAND_FAILED",
            "surface": "cli",
            "correlation_id": "corr_abc",
            "summary": "make build-features exited with code 1",
            "exit_code": 1,
            "redaction_status": "redacted",
            "metadata": {},
        }
    ]
    (run_dir / "commands.jsonl").write_text(
        "\n".join(json.dumps(e) for e in cmd_events) + "\n"
    )

    # environment.json
    (run_dir / "environment.json").write_text(
        json.dumps({"python": "3.12.0", "commit": "abc1234", "branch": "main"})
    )

    # A fake secret file that MUST be excluded
    (run_dir / "secrets.env").write_text("API_KEY=supersecret123")
    (run_dir / "some.pem").write_text("-----BEGIN PRIVATE KEY-----")

    return run_dir


# ===========================================================================
# Section 13: Repair bundle generation
# ===========================================================================


class TestRepairBundleGeneration:
    """13.1-13.8: Bundle structure, content, guardrails."""

    def test_bundle_dir_created(self, sample_run_dir, tmp_path):
        """13.2 Bundle dir created under bundles/<bundle-id>/."""
        from vnalpha.observability.repair import create_repair_bundle

        bundles_root = tmp_path / "bundles"
        bundle_dir = create_repair_bundle(sample_run_dir, bundles_root=bundles_root)

        assert bundle_dir.exists()
        assert bundle_dir.is_dir()
        assert bundle_dir.parent == bundles_root

    # -----------------------------------------------------------------------
    # 13.9-13.10: Unsafe file exclusion
    # -----------------------------------------------------------------------


# ===========================================================================
# Section 14: Repair tracking events
# ===========================================================================

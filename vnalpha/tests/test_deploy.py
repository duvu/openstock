"""Tests for deploy event generation and end-to-end repair→deploy scenario (S15.12, S16)."""

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
        run_id="test_run_deploy",
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
def failed_run_dir(tmp_path):
    """Fixture: a run directory with a failed command — simulates a runtime failure."""
    run_dir = tmp_path / "runs" / "run_failed_001"
    run_dir.mkdir(parents=True)

    # Simulated error event (16.2: fixture-based failed command)
    events = [
        {
            "event_id": "err1",
            "run_id": "run_failed_001",
            "created_at": "2024-01-01T00:01:00Z",
            "level": "ERROR",
            "event_type": "EXCEPTION_CAPTURED",
            "surface": "cli",
            "correlation_id": "corr_fail",
            "summary": "ValueError in compute_features",
            "error_type": "ValueError",
            "error_message": "invalid feature input",
            "module": "vnalpha.features",
            "function": "compute",
            "redaction_status": "redacted",
            "metadata": {},
        }
    ]
    (run_dir / "errors.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events) + "\n"
    )
    (run_dir / "audit.jsonl").write_text(
        json.dumps(
            {
                "event_id": "cmd_fail",
                "run_id": "run_failed_001",
                "created_at": "2024-01-01T00:01:00Z",
                "level": "INFO",
                "event_type": "COMMAND_FAILED",
                "surface": "cli",
                "correlation_id": "corr_fail",
                "summary": "make build-features exited with code 1",
                "redaction_status": "redacted",
                "metadata": {},
            }
        )
        + "\n"
    )

    return run_dir


# ===========================================================================
# Section 15: Deploy event generation (S15.12: static validation)
# ===========================================================================


class TestDeployEvents:
    """15.1-15.12: deploy.jsonl / audit.jsonl events."""

    def test_verify_started_event_written(self, tmp_path, isolated_run_ctx):
        """15.2 DEPLOY_VERIFY_STARTED written to deploy.jsonl."""
        from vnalpha.observability.deploy import log_deploy_event

        log_deploy_event(
            "DEPLOY_VERIFY_STARTED",
            "Verifying v1.2.3",
            deployment_id="dep001",
            run_ctx=isolated_run_ctx,
            extra={"candidate_version": "v1.2.3"},
        )

        deploy_path = isolated_run_ctx.run_dir / "deploy.jsonl"
        assert deploy_path.exists()
        events = [
            json.loads(line)
            for line in deploy_path.read_text().splitlines()
            if line.strip()
        ]
        assert any(e["event_type"] == "DEPLOY_VERIFY_STARTED" for e in events)


# ===========================================================================
# Section 16: End-to-end scenario tests
# ===========================================================================

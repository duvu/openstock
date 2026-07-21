"""Closed-loop e2e fixture tests: RUN -> FAIL -> OBSERVE -> REPAIR -> VALIDATE -> DEPLOY gate (S13)."""

from __future__ import annotations

import json

import pytest


@pytest.fixture()
def isolated_run_ctx(tmp_path):
    from vnalpha.observability.context import RunContext, reset_run_context

    reset_run_context()
    ctx = RunContext(
        run_id="e2e_run_001",
        surface="cli",
        actor="test",
        log_root=tmp_path,
    )
    yield ctx
    reset_run_context()


@pytest.fixture(autouse=True)
def _reset():
    from vnalpha.observability.context import reset_run_context

    reset_run_context()
    yield
    reset_run_context()


@pytest.fixture()
def failed_run_dir(tmp_path):
    run_dir = tmp_path / "runs" / "run_e2e_fail_001"
    run_dir.mkdir(parents=True)

    errors = [
        {
            "event_id": "err1",
            "run_id": "run_e2e_fail_001",
            "created_at": "2024-01-01T00:00:01Z",
            "level": "ERROR",
            "event_type": "EXCEPTION_CAPTURED",
            "surface": "cli",
            "correlation_id": "corr_e2e",
            "summary": "KeyError: missing symbol in build_features",
            "error_type": "KeyError",
            "error_message": "missing_symbol",
            "module": "vnalpha.features.builder",
        }
    ]
    (run_dir / "errors.jsonl").write_text(
        "\n".join(json.dumps(e) for e in errors) + "\n"
    )
    (run_dir / "commands.jsonl").write_text(
        json.dumps(
            {
                "event_type": "COMMAND_FAILED",
                "run_id": "run_e2e_fail_001",
                "correlation_id": "corr_e2e",
                "summary": "build features failed",
                "status": "FAILED",
                "exit_code": 1,
            }
        )
        + "\n"
    )
    return run_dir


class TestClosedLoopE2E:
    def test_13_1_fixture_command_produces_failed_run_dir(self, failed_run_dir):
        assert failed_run_dir.exists()
        assert (failed_run_dir / "errors.jsonl").exists()
        assert (failed_run_dir / "commands.jsonl").exists()

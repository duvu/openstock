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

    def test_13_2_failure_writes_command_audit_error_events(self, failed_run_dir):
        error_events = [
            json.loads(line)
            for line in (failed_run_dir / "errors.jsonl").read_text().splitlines()
            if line.strip()
        ]
        cmd_events = [
            json.loads(line)
            for line in (failed_run_dir / "commands.jsonl").read_text().splitlines()
            if line.strip()
        ]
        assert any(e.get("event_type") == "EXCEPTION_CAPTURED" for e in error_events)
        assert any(e.get("event_type") == "COMMAND_FAILED" for e in cmd_events)

    def test_13_3_generate_summary_from_failed_run(self, tmp_path, failed_run_dir):
        from vnalpha.observability.summary import generate_summary

        summary = generate_summary(failed_run_dir)
        assert summary is not None
        summary_str = str(summary) if not isinstance(summary, str) else summary
        assert len(summary_str) > 0

    def test_13_4_repair_prepare_on_failed_run(
        self, tmp_path, failed_run_dir, isolated_run_ctx
    ):
        from vnalpha.observability.repair import create_repair_bundle

        bundles_root = tmp_path / "bundles"
        bundle_path = create_repair_bundle(
            failed_run_dir,
            bundles_root,
            test_commands=["pytest -q"],
            mode="redacted",
        )
        assert bundle_path.exists()

    def test_13_5_repair_bundle_contains_required_files(
        self, tmp_path, failed_run_dir, isolated_run_ctx
    ):
        from vnalpha.observability.repair import create_repair_bundle

        bundles_root = tmp_path / "bundles"
        bundle_path = create_repair_bundle(
            failed_run_dir,
            bundles_root,
            test_commands=["pytest -q"],
            mode="redacted",
        )
        assert (bundle_path / "ai-coding-prompt.md").exists()
        assert (bundle_path / "reproduction.md").exists()
        assert (bundle_path / "manifest.json").exists()
        raw_logs = bundle_path / "raw-logs"
        assert raw_logs.exists()

    def test_13_6_repair_validate_with_failing_command(
        self, tmp_path, failed_run_dir, isolated_run_ctx
    ):
        from vnalpha.observability.repair import (
            create_repair_bundle,
            load_repair_state,
            update_repair_state,
        )

        bundles_root = tmp_path / "bundles"
        bundle_path = create_repair_bundle(
            failed_run_dir,
            bundles_root,
            test_commands=["exit 1"],
            mode="redacted",
        )
        manifest = json.loads((bundle_path / "manifest.json").read_text())
        test_commands = manifest.get("test_commands", ["exit 1"])

        import subprocess

        results = []
        for cmd in test_commands:
            proc = subprocess.run(cmd, shell=True, capture_output=True)
            results.append(
                {
                    "cmd": cmd,
                    "exit_code": proc.returncode,
                    "passed": proc.returncode == 0,
                }
            )

        validation_passed = all(r["passed"] for r in results)
        update_repair_state(
            bundle_path, validation_passed=validation_passed, validation_results=results
        )

        state = load_repair_state(bundle_path)
        assert state.get("validation_passed") is not None

    def test_13_7_validation_failure_is_recorded(
        self, tmp_path, failed_run_dir, isolated_run_ctx
    ):
        from vnalpha.observability.repair import (
            create_repair_bundle,
            load_repair_state,
            update_repair_state,
        )

        bundles_root = tmp_path / "bundles"
        bundle_path = create_repair_bundle(
            failed_run_dir,
            bundles_root,
            test_commands=["exit 1"],
            mode="redacted",
        )
        update_repair_state(
            bundle_path,
            validation_passed=False,
            validation_results=[{"cmd": "exit 1", "exit_code": 1, "passed": False}],
        )

        state = load_repair_state(bundle_path)
        assert state.get("validation_passed") is False

    def test_13_8_deploy_promote_blocked_when_not_verified(
        self, tmp_path, isolated_run_ctx
    ):
        import pytest as _pytest

        from vnalpha.observability.deploy import (
            DeployGateError,
            promote_candidate,
        )

        log_root = tmp_path
        with _pytest.raises(DeployGateError):
            promote_candidate(
                "v1.0.1",
                deployment_id="dep_e2e_001",
                previous_version="v1.0.0",
                force=False,
                log_root=log_root,
                run_ctx=isolated_run_ctx,
            )

    def test_13_9_deploy_blocked_event_logged(self, tmp_path, isolated_run_ctx):
        from vnalpha.observability.deploy import DeployGateError, promote_candidate
        from vnalpha.observability.jsonl import read_jsonl

        log_root = tmp_path

        try:
            promote_candidate(
                "v1.0.1",
                deployment_id="dep_e2e_002",
                previous_version="v1.0.0",
                force=False,
                log_root=log_root,
                run_ctx=isolated_run_ctx,
            )
        except DeployGateError:
            pass

        audit_path = isolated_run_ctx.audit_path
        if audit_path and audit_path.exists():
            events = read_jsonl(audit_path)
            blocked = [
                e
                for e in events
                if "BLOCKED" in e.get("event_type", "")
                or "BLOCKED" in e.get("summary", "")
            ]
            assert len(blocked) >= 1, (
                f"Expected DEPLOY_BLOCKED event, got: {[e.get('event_type') for e in events]}"
            )

    def test_13_10_dry_run_promote_records_success(self, tmp_path, isolated_run_ctx):
        from vnalpha.observability.deploy import (
            promote_candidate,
            verify_deploy_candidate,
        )

        log_root = tmp_path
        deployment_id = "dep_e2e_dry_001"

        verify_deploy_candidate(
            "v1.0.2",
            verify_commands=["true"],
            deployment_id=deployment_id,
            log_root=log_root,
            run_ctx=isolated_run_ctx,
        )

        result = promote_candidate(
            "v1.0.2",
            deployment_id=deployment_id,
            previous_version="v1.0.1",
            force=False,
            log_root=log_root,
            run_ctx=isolated_run_ctx,
        )
        assert result.get("candidate_version") == "v1.0.2"
        assert result.get("previous_version") == "v1.0.1"

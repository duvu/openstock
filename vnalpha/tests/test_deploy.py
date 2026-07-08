"""Tests for deploy event generation and end-to-end repair→deploy scenario (S15.12, S16)."""

from __future__ import annotations

import json
from pathlib import Path

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
        json.dumps({
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
        }) + "\n"
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
        events = [json.loads(l) for l in deploy_path.read_text().splitlines() if l.strip()]
        assert any(e["event_type"] == "DEPLOY_VERIFY_STARTED" for e in events)

    def test_deploy_event_also_in_audit(self, tmp_path, isolated_run_ctx):
        """15.1 Deploy events appear in audit.jsonl as well."""
        from vnalpha.observability.deploy import log_deploy_event

        log_deploy_event(
            "DEPLOY_VERIFY_STARTED",
            "Verify candidate",
            deployment_id="dep002",
            run_ctx=isolated_run_ctx,
        )

        audit_path = isolated_run_ctx.audit_path
        events = [json.loads(l) for l in audit_path.read_text().splitlines() if l.strip()]
        assert any(e["event_type"] == "DEPLOY_VERIFY_STARTED" for e in events)

    def test_deploy_verify_completed_event(self, tmp_path, isolated_run_ctx):
        """15.2 DEPLOY_VERIFY_COMPLETED event written."""
        from vnalpha.observability.deploy import log_deploy_event

        log_deploy_event(
            "DEPLOY_VERIFY_COMPLETED",
            "Verification PASSED",
            deployment_id="dep003",
            status="PASSED",
            run_ctx=isolated_run_ctx,
        )

        deploy_path = isolated_run_ctx.run_dir / "deploy.jsonl"
        events = [json.loads(l) for l in deploy_path.read_text().splitlines() if l.strip()]
        assert any(e["event_type"] == "DEPLOY_VERIFY_COMPLETED" for e in events)

    def test_deploy_promoted_event(self, tmp_path, isolated_run_ctx):
        """15.3 DEPLOY_PROMOTED event written + previous/candidate versions logged."""
        from vnalpha.observability.deploy import log_deploy_event

        log_deploy_event(
            "DEPLOY_PROMOTED",
            "Promoted v2 (prev=v1)",
            deployment_id="dep004",
            status="PROMOTED",
            run_ctx=isolated_run_ctx,
            extra={"candidate_version": "v2", "previous_version": "v1"},
        )

        deploy_path = isolated_run_ctx.run_dir / "deploy.jsonl"
        events = [json.loads(l) for l in deploy_path.read_text().splitlines() if l.strip()]
        promoted = [e for e in events if e["event_type"] == "DEPLOY_PROMOTED"]
        assert promoted[0]["metadata"]["previous_version"] == "v1"  # 15.5
        assert promoted[0]["metadata"]["candidate_version"] == "v2"  # 15.6

    def test_deploy_smoke_event(self, tmp_path, isolated_run_ctx):
        """15.9 DEPLOY_SMOKE_COMPLETED event written."""
        from vnalpha.observability.deploy import log_deploy_event

        log_deploy_event(
            "DEPLOY_SMOKE_COMPLETED",
            "Smoke PASSED",
            deployment_id="dep005",
            status="PASSED",
            run_ctx=isolated_run_ctx,
        )

        deploy_path = isolated_run_ctx.run_dir / "deploy.jsonl"
        events = [json.loads(l) for l in deploy_path.read_text().splitlines() if l.strip()]
        assert any(e["event_type"] == "DEPLOY_SMOKE_COMPLETED" for e in events)

    def test_rollback_events(self, tmp_path, isolated_run_ctx):
        """15.10-15.11 DEPLOY_ROLLBACK_STARTED and DEPLOY_ROLLED_BACK events."""
        from vnalpha.observability.deploy import log_deploy_event

        log_deploy_event(
            "DEPLOY_ROLLBACK_STARTED",
            "Rolling back dep006",
            deployment_id="dep006",
            status="ROLLING_BACK",
            run_ctx=isolated_run_ctx,
            extra={"previous_version": "v1"},
        )
        log_deploy_event(
            "DEPLOY_ROLLED_BACK",
            "Rolled back to v1",
            deployment_id="dep006",
            status="ROLLED_BACK",
            run_ctx=isolated_run_ctx,
            extra={"previous_version": "v1"},
        )

        deploy_path = isolated_run_ctx.run_dir / "deploy.jsonl"
        events = [json.loads(l) for l in deploy_path.read_text().splitlines() if l.strip()]
        types = {e["event_type"] for e in events}
        assert "DEPLOY_ROLLBACK_STARTED" in types  # 15.10
        assert "DEPLOY_ROLLED_BACK" in types  # 15.11

    def test_promotion_blocked_when_unverified(self, tmp_path):
        """15.7 Promotion is blocked when verification has not passed."""
        from vnalpha.observability.deploy import (
            DeployGateError,
            promote_candidate,
            save_deploy_state,
        )

        dep_id = "dep_blocked"
        # Simulate a failed verification state
        state_dir = tmp_path / "deployments"
        state_dir.mkdir(parents=True)
        (state_dir / f"{dep_id}.json").write_text(json.dumps({
            "deployment_id": dep_id,
            "candidate_version": "v2",
            "verification_status": "FAILED",
            "deploy_status": "PENDING",
        }))

        with pytest.raises(DeployGateError):
            promote_candidate("v2", deployment_id=dep_id, log_root=tmp_path)

    def test_promotion_succeeds_when_verified(self, tmp_path):
        """15.7 Promotion proceeds when verification passed."""
        from vnalpha.observability.deploy import promote_candidate

        dep_id = "dep_ok"
        state_dir = tmp_path / "deployments"
        state_dir.mkdir(parents=True)
        (state_dir / f"{dep_id}.json").write_text(json.dumps({
            "deployment_id": dep_id,
            "candidate_version": "v2",
            "verification_status": "PASSED",
            "deploy_status": "PENDING",
        }))

        result = promote_candidate(
            "v2",
            deployment_id=dep_id,
            previous_version="v1",
            log_root=tmp_path,
        )
        assert result["deploy_status"] == "PROMOTED"
        assert result["previous_version"] == "v1"

    def test_deploy_event_required_fields(self, tmp_path, isolated_run_ctx):
        """15.12 Deploy events have required schema fields."""
        from vnalpha.observability.deploy import log_deploy_event

        log_deploy_event(
            "DEPLOY_VERIFY_STARTED",
            "Verifying",
            deployment_id="dep_fields",
            run_ctx=isolated_run_ctx,
        )

        deploy_path = isolated_run_ctx.run_dir / "deploy.jsonl"
        events = [json.loads(l) for l in deploy_path.read_text().splitlines() if l.strip()]
        event = events[0]

        required = ["event_id", "run_id", "created_at", "event_type", "deployment_id", "summary"]
        for field in required:
            assert field in event, f"Missing field: {field}"

    def test_rollback_state_persisted(self, tmp_path):
        """15.11 Rollback state is saved with rollback_status, rollback_at, rollback_reason."""
        from vnalpha.observability.deploy import load_deploy_state, rollback_deployment

        dep_id = "dep_rb"
        state_dir = tmp_path / "deployments"
        state_dir.mkdir(parents=True)
        (state_dir / f"{dep_id}.json").write_text(json.dumps({
            "deployment_id": dep_id,
            "candidate_version": "v3",
            "previous_version": "v2",
            "verification_status": "PASSED",
            "deploy_status": "PROMOTED",
        }))

        rollback_deployment(dep_id, reason="smoke failed", log_root=tmp_path)
        state = load_deploy_state(dep_id, tmp_path)
        assert state["rollback_status"] == "ROLLED_BACK"
        assert state["rollback_reason"] == "smoke failed"
        assert "rollback_at" in state


# ===========================================================================
# Section 16: End-to-end scenario tests
# ===========================================================================


class TestEndToEndScenario:
    """16.1-16.5: Full failure → bundle → repair → deploy loop."""

    def test_failed_run_generates_repair_bundle(self, failed_run_dir, tmp_path):
        """16.2-16.3 repair prepare can consume a failed run and generate a usable bundle."""
        from vnalpha.observability.repair import create_repair_bundle

        bundles_root = tmp_path / "bundles"
        bundle_dir = create_repair_bundle(failed_run_dir, bundles_root=bundles_root)

        assert bundle_dir.exists()
        assert (bundle_dir / "ai-coding-prompt.md").exists()
        assert (bundle_dir / "manifest.json").exists()

        manifest = json.loads((bundle_dir / "manifest.json").read_text())
        # Source run ID should reference the failed run
        assert "run_failed_001" in manifest.get("source_run_ids", [])

    def test_bundle_contains_error_summary(self, failed_run_dir, tmp_path):
        """16.3 Bundle manifest captures errors from failed run."""
        from vnalpha.observability.repair import create_repair_bundle

        bundle_dir = create_repair_bundle(failed_run_dir, bundles_root=tmp_path / "b")
        manifest = json.loads((bundle_dir / "manifest.json").read_text())

        assert manifest.get("error_count", 0) >= 1

    def test_promotion_blocked_without_verification(self, tmp_path):
        """16.4 Promotion is blocked when verification failed — no bypass allowed."""
        from vnalpha.observability.deploy import DeployGateError, promote_candidate

        dep_id = "e2e_dep_fail"
        state_dir = tmp_path / "deployments"
        state_dir.mkdir(parents=True)
        (state_dir / f"{dep_id}.json").write_text(json.dumps({
            "deployment_id": dep_id,
            "candidate_version": "v5",
            "verification_status": "FAILED",
            "deploy_status": "PENDING",
        }))

        with pytest.raises(DeployGateError) as exc_info:
            promote_candidate("v5", deployment_id=dep_id, log_root=tmp_path)

        assert "FAILED" in str(exc_info.value)

    def test_promotion_records_result_when_verified(self, tmp_path):
        """16.5 Promotion records result when verification passes."""
        from vnalpha.observability.deploy import load_deploy_state, promote_candidate

        dep_id = "e2e_dep_pass"
        state_dir = tmp_path / "deployments"
        state_dir.mkdir(parents=True)
        (state_dir / f"{dep_id}.json").write_text(json.dumps({
            "deployment_id": dep_id,
            "candidate_version": "v6",
            "verification_status": "PASSED",
            "deploy_status": "PENDING",
        }))

        promote_candidate("v6", deployment_id=dep_id, previous_version="v5", log_root=tmp_path)
        state = load_deploy_state(dep_id, tmp_path)

        assert state["deploy_status"] == "PROMOTED"
        assert state["candidate_version"] == "v6"
        assert state["previous_version"] == "v5"
        assert "promoted_at" in state

    def test_full_scenario_repair_to_deploy(self, failed_run_dir, tmp_path):
        """16.1 Full scenario: failure → bundle → repair events → deploy verify → promote → smoke."""
        from vnalpha.observability.context import RunContext, reset_run_context
        from vnalpha.observability.deploy import (
            log_deploy_event,
            promote_candidate,
            record_post_deploy_smoke,
            save_deploy_state,
        )
        from vnalpha.observability.repair import (
            create_repair_bundle,
            log_repair_event,
            update_repair_state,
        )

        reset_run_context()
        ctx = RunContext(
            run_id="e2e_run_001",
            surface="cli",
            actor="test",
            log_root=tmp_path,
        )

        # Step 1: Runtime failure captured → create repair bundle
        bundle_dir = create_repair_bundle(failed_run_dir, bundles_root=tmp_path / "bundles")
        assert bundle_dir.exists()

        # Step 2: Log REPAIR_PREPARED
        log_repair_event(
            "REPAIR_PREPARED", "Bundle created", repair_id=bundle_dir.name, run_ctx=ctx
        )

        # Step 3: AI agent starts work
        log_repair_event(
            "REPAIR_STARTED", "Agent started", repair_id=bundle_dir.name,
            status="STARTED", run_ctx=ctx
        )

        # Step 4: Fix branch created
        log_repair_event(
            "REPAIR_UPDATED", "Fix branch", repair_id=bundle_dir.name, run_ctx=ctx,
            extra={"fix_branch": "fix/e2e-test"}
        )

        # Step 5: Validation
        log_repair_event(
            "REPAIR_VALIDATED", "Validation PASSED", repair_id=bundle_dir.name,
            status="PASSED", run_ctx=ctx,
            extra={"validation_status": "PASSED", "commands_passed": 1}
        )

        # Step 6: Deploy verify
        dep_id = "e2e_dep_001"
        state_dir = tmp_path / "deployments"
        state_dir.mkdir(parents=True)
        (state_dir / f"{dep_id}.json").write_text(json.dumps({
            "deployment_id": dep_id,
            "candidate_version": "v2",
            "verification_status": "PASSED",
            "deploy_status": "PENDING",
        }))

        # Step 7: Promote
        promote_candidate("v2", deployment_id=dep_id, previous_version="v1", log_root=tmp_path)

        # Step 8: Post-deploy smoke
        smoke_state = record_post_deploy_smoke(
            dep_id, smoke_passed=True, details="health check OK", log_root=tmp_path
        )

        assert smoke_state["smoke_status"] == "PASSED"
        assert smoke_state["deploy_status"] == "PROMOTED"

        # Repair events written
        repair_path = ctx.run_dir / "repair.jsonl"
        repair_events = [json.loads(l) for l in repair_path.read_text().splitlines() if l.strip()]
        repair_types = {e["event_type"] for e in repair_events}
        assert "REPAIR_PREPARED" in repair_types
        assert "REPAIR_STARTED" in repair_types
        assert "REPAIR_VALIDATED" in repair_types

        reset_run_context()

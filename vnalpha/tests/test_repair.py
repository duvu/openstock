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

    def test_required_files_present(self, sample_run_dir, tmp_path):
        """13.2-13.5 Required files are generated."""
        from vnalpha.observability.repair import create_repair_bundle

        bundle_dir = create_repair_bundle(sample_run_dir, bundles_root=tmp_path / "b")

        assert (bundle_dir / "ai-coding-prompt.md").exists()
        assert (bundle_dir / "reproduction.md").exists()
        assert (bundle_dir / "manifest.json").exists()

    def test_manifest_required_fields(self, sample_run_dir, tmp_path):
        """13.5 manifest.json has all required fields."""
        from vnalpha.observability.repair import create_repair_bundle

        bundle_dir = create_repair_bundle(sample_run_dir, bundles_root=tmp_path / "b")
        manifest = json.loads((bundle_dir / "manifest.json").read_text())

        for field in [
            "bundle_id",
            "source_run_ids",
            "redaction_mode",
            "included_files",
            "generated_at",
        ]:
            assert field in manifest, f"Missing field: {field}"

    def test_manifest_has_error_count(self, sample_run_dir, tmp_path):
        """13.6 Manifest includes error_count, failed_command_count."""
        from vnalpha.observability.repair import create_repair_bundle

        bundle_dir = create_repair_bundle(sample_run_dir, bundles_root=tmp_path / "b")
        manifest = json.loads((bundle_dir / "manifest.json").read_text())

        assert "error_count" in manifest
        assert "failed_command_count" in manifest

    def test_manifest_has_test_commands(self, sample_run_dir, tmp_path):
        """13.7 Manifest includes test_commands."""
        from vnalpha.observability.repair import create_repair_bundle

        bundle_dir = create_repair_bundle(
            sample_run_dir,
            bundles_root=tmp_path / "b",
            test_commands=["pytest", "make lint"],
        )
        manifest = json.loads((bundle_dir / "manifest.json").read_text())
        assert "test_commands" in manifest
        assert "pytest" in manifest["test_commands"]

    def test_manifest_has_guardrails(self, sample_run_dir, tmp_path):
        """13.8 Manifest has guardrails field (no broker/trading execution)."""
        from vnalpha.observability.repair import create_repair_bundle

        bundle_dir = create_repair_bundle(sample_run_dir, bundles_root=tmp_path / "b")
        manifest = json.loads((bundle_dir / "manifest.json").read_text())

        assert "guardrails" in manifest
        guardrails = manifest["guardrails"]
        assert "broker" in guardrails.lower() or "trading" in guardrails.lower()

    def test_ai_coding_prompt_contains_guardrails(self, sample_run_dir, tmp_path):
        """13.8 ai-coding-prompt.md contains explicit guardrails."""
        from vnalpha.observability.repair import create_repair_bundle

        bundle_dir = create_repair_bundle(sample_run_dir, bundles_root=tmp_path / "b")
        prompt_text = (bundle_dir / "ai-coding-prompt.md").read_text()

        # Must explicitly mention that trading/broker features are off-limits
        lower = prompt_text.lower()
        assert "broker" in lower or "trading" in lower, (
            "ai-coding-prompt.md must mention broker/trading guardrails"
        )

    def test_reproduction_md_present(self, sample_run_dir, tmp_path):
        """13.4 reproduction.md is generated."""
        from vnalpha.observability.repair import create_repair_bundle

        bundle_dir = create_repair_bundle(sample_run_dir, bundles_root=tmp_path / "b")
        repro = (bundle_dir / "reproduction.md").read_text()
        assert len(repro) > 10  # not empty

    def test_raw_logs_dir_contains_jsonl(self, sample_run_dir, tmp_path):
        """13.2 raw-logs/ directory is populated with safe JSONL files."""
        from vnalpha.observability.repair import create_repair_bundle

        bundle_dir = create_repair_bundle(sample_run_dir, bundles_root=tmp_path / "b")
        raw_logs = bundle_dir / "raw-logs"

        # raw-logs dir may exist if there are JSONL files
        if raw_logs.exists():
            jsonl_files = list(raw_logs.glob("*.jsonl"))
            # Each file should contain valid JSON lines
            for jf in jsonl_files:
                for line in jf.read_text().splitlines():
                    line = line.strip()
                    if line:
                        json.loads(line)  # should not raise

    # -----------------------------------------------------------------------
    # 13.9-13.10: Unsafe file exclusion
    # -----------------------------------------------------------------------

    def test_secrets_env_excluded(self, sample_run_dir, tmp_path):
        """13.10 secrets.env must not appear in raw-logs/."""
        from vnalpha.observability.repair import create_repair_bundle

        bundle_dir = create_repair_bundle(sample_run_dir, bundles_root=tmp_path / "b")
        raw_logs = bundle_dir / "raw-logs"

        if raw_logs.exists():
            for f in raw_logs.iterdir():
                assert "secrets" not in f.name.lower(), (
                    f"Secrets file found in raw-logs: {f.name}"
                )

    def test_pem_excluded(self, sample_run_dir, tmp_path):
        """13.10 .pem files must not appear in raw-logs/."""
        from vnalpha.observability.repair import create_repair_bundle

        bundle_dir = create_repair_bundle(sample_run_dir, bundles_root=tmp_path / "b")
        raw_logs = bundle_dir / "raw-logs"

        if raw_logs.exists():
            for f in raw_logs.iterdir():
                assert not f.name.endswith(".pem"), (
                    f".pem file found in raw-logs: {f.name}"
                )

    def test_manifest_included_files_do_not_have_secrets(
        self, sample_run_dir, tmp_path
    ):
        """13.10 manifest.json included_files list does not contain secret file names."""
        from vnalpha.observability.repair import create_repair_bundle

        bundle_dir = create_repair_bundle(sample_run_dir, bundles_root=tmp_path / "b")
        manifest = json.loads((bundle_dir / "manifest.json").read_text())

        included = manifest.get("included_files", [])
        for fname in included:
            assert "secrets" not in fname.lower()
            assert not fname.endswith(".pem")
            assert not fname.endswith(".key")


# ===========================================================================
# Section 14: Repair tracking events
# ===========================================================================


class TestRepairEvents:
    """14.1-14.12: repair.jsonl / audit.jsonl event logging."""

    def test_repair_prepared_event_written(self, tmp_path, isolated_run_ctx):
        """14.2 REPAIR_PREPARED event is written to repair.jsonl."""
        from vnalpha.observability.repair import log_repair_event

        log_repair_event(
            "REPAIR_PREPARED",
            "Bundle repair_001 created",
            repair_id="repair_001",
            run_ctx=isolated_run_ctx,
        )

        repair_path = isolated_run_ctx.run_dir / "repair.jsonl"
        assert repair_path.exists()
        events = [
            json.loads(line)
            for line in repair_path.read_text().splitlines()
            if line.strip()
        ]
        assert any(e["event_type"] == "REPAIR_PREPARED" for e in events)

    def test_repair_event_also_written_to_audit(self, tmp_path, isolated_run_ctx):
        """14.1 Repair events appear in audit.jsonl too."""
        from vnalpha.observability.repair import log_repair_event

        log_repair_event(
            "REPAIR_PREPARED",
            "Bundle created",
            repair_id="r001",
            run_ctx=isolated_run_ctx,
        )

        audit_path = isolated_run_ctx.audit_path
        assert audit_path.exists()
        events = [
            json.loads(line)
            for line in audit_path.read_text().splitlines()
            if line.strip()
        ]
        assert any(e["event_type"] == "REPAIR_PREPARED" for e in events)

    def test_repair_started_event(self, tmp_path, isolated_run_ctx):
        """14.3 REPAIR_STARTED event is written."""
        from vnalpha.observability.repair import log_repair_event

        log_repair_event(
            "REPAIR_STARTED",
            "AI agent started repair on repair_002",
            repair_id="repair_002",
            status="STARTED",
            run_ctx=isolated_run_ctx,
            extra={"agent": "claude"},
        )

        repair_path = isolated_run_ctx.run_dir / "repair.jsonl"
        events = [
            json.loads(line)
            for line in repair_path.read_text().splitlines()
            if line.strip()
        ]
        started = [e for e in events if e["event_type"] == "REPAIR_STARTED"]
        assert len(started) == 1
        assert started[0]["metadata"].get("agent") == "claude"

    def test_repair_updated_fix_branch(self, tmp_path, isolated_run_ctx):
        """14.4 Fix branch name logged in REPAIR_UPDATED event."""
        from vnalpha.observability.repair import log_repair_event

        log_repair_event(
            "REPAIR_UPDATED",
            "Repair r003 updated: fix_branch",
            repair_id="r003",
            run_ctx=isolated_run_ctx,
            extra={"fix_branch": "fix/zero-div-error"},
        )

        repair_path = isolated_run_ctx.run_dir / "repair.jsonl"
        events = [
            json.loads(line)
            for line in repair_path.read_text().splitlines()
            if line.strip()
        ]
        updated = [e for e in events if e["event_type"] == "REPAIR_UPDATED"]
        assert updated[0]["metadata"]["fix_branch"] == "fix/zero-div-error"

    def test_repair_updated_pr_number(self, tmp_path, isolated_run_ctx):
        """14.5 PR number logged in REPAIR_UPDATED event."""
        from vnalpha.observability.repair import log_repair_event

        log_repair_event(
            "REPAIR_UPDATED",
            "Repair r004 PR opened",
            repair_id="r004",
            run_ctx=isolated_run_ctx,
            extra={"pr_number": "42"},
        )

        repair_path = isolated_run_ctx.run_dir / "repair.jsonl"
        events = [
            json.loads(line)
            for line in repair_path.read_text().splitlines()
            if line.strip()
        ]
        assert any(e["metadata"].get("pr_number") == "42" for e in events)

    def test_repair_updated_commit_sha(self, tmp_path, isolated_run_ctx):
        """14.6 Commit SHA logged in REPAIR_UPDATED event."""
        from vnalpha.observability.repair import log_repair_event

        log_repair_event(
            "REPAIR_UPDATED",
            "Repair r005 commit merged",
            repair_id="r005",
            run_ctx=isolated_run_ctx,
            extra={"commit_sha": "abc1234def"},
        )

        repair_path = isolated_run_ctx.run_dir / "repair.jsonl"
        events = [
            json.loads(line)
            for line in repair_path.read_text().splitlines()
            if line.strip()
        ]
        assert any(e["metadata"].get("commit_sha") == "abc1234def" for e in events)

    def test_repair_validated_event(self, tmp_path, isolated_run_ctx):
        """14.7-14.8 REPAIR_VALIDATED event logs commands and results."""
        from vnalpha.observability.repair import log_repair_event

        log_repair_event(
            "REPAIR_VALIDATED",
            "Validation PASSED for r006",
            repair_id="r006",
            status="PASSED",
            run_ctx=isolated_run_ctx,
            extra={
                "validation_status": "PASSED",
                "validation_commands": ["pytest", "make lint"],
                "commands_passed": 2,
            },
        )

        repair_path = isolated_run_ctx.run_dir / "repair.jsonl"
        events = [
            json.loads(line)
            for line in repair_path.read_text().splitlines()
            if line.strip()
        ]
        validated = [e for e in events if e["event_type"] == "REPAIR_VALIDATED"]
        assert len(validated) == 1
        assert validated[0]["metadata"]["validation_commands"] == [
            "pytest",
            "make lint",
        ]

    def test_repair_outcome_accepted(self, tmp_path, isolated_run_ctx):
        """14.9 Outcome accepted/rejected/deferred logged."""
        from vnalpha.observability.repair import log_repair_event

        log_repair_event(
            "REPAIR_UPDATED",
            "Repair r007 accepted",
            repair_id="r007",
            status="ACCEPTED",
            run_ctx=isolated_run_ctx,
            extra={"outcome": "accepted"},
        )

        repair_path = isolated_run_ctx.run_dir / "repair.jsonl"
        events = [
            json.loads(line)
            for line in repair_path.read_text().splitlines()
            if line.strip()
        ]
        assert any(e["metadata"].get("outcome") == "accepted" for e in events)

    def test_repair_state_persistence(self, tmp_path):
        """14.10-14.11 Repair state can be saved and loaded."""
        from vnalpha.observability.repair import (
            load_repair_state,
            save_repair_state,
            update_repair_state,
        )

        bundle_dir = tmp_path / "bundles" / "repair_test"
        bundle_dir.mkdir(parents=True)

        save_repair_state(bundle_dir, {"repair_status": "STARTED"})
        state = load_repair_state(bundle_dir)
        assert state["repair_status"] == "STARTED"

        update_repair_state(bundle_dir, fix_branch="fix/foo", pr_number="99")
        state2 = load_repair_state(bundle_dir)
        assert state2["fix_branch"] == "fix/foo"
        assert state2["pr_number"] == "99"

    def test_repair_event_fields(self, tmp_path, isolated_run_ctx):
        """14.12 Repair event has required fields."""
        from vnalpha.observability.repair import log_repair_event

        log_repair_event(
            "REPAIR_PREPARED",
            "Test event",
            repair_id="r_field_test",
            run_ctx=isolated_run_ctx,
        )

        repair_path = isolated_run_ctx.run_dir / "repair.jsonl"
        events = [
            json.loads(line)
            for line in repair_path.read_text().splitlines()
            if line.strip()
        ]
        event = events[0]

        required = [
            "event_id",
            "run_id",
            "created_at",
            "event_type",
            "repair_id",
            "summary",
        ]
        for field in required:
            assert field in event, f"Missing field: {field}"

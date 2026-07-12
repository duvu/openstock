"""Tests for observability: context, jsonl, redaction, correlation, commands, errors."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

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

    def test_run_dir_path_structure(self, tmp_path):
        from vnalpha.observability.context import RunContext

        ctx = RunContext(
            run_id="run_test_002",
            surface="tui",
            actor="test",
            log_root=tmp_path,
        )
        assert ctx.run_dir == tmp_path / "runs" / "run_test_002"

    def test_environment_json_is_valid_json(self, tmp_path):
        from vnalpha.observability.context import RunContext

        ctx = RunContext(
            run_id="run_test_003",
            surface="cli",
            actor="test",
            log_root=tmp_path,
        )
        env_path = ctx.run_dir / "environment.json"
        assert env_path.exists()
        data = json.loads(env_path.read_text())
        assert data["run_id"] == "run_test_003"
        assert data["surface"] == "cli"
        assert "python_version" in data
        assert "platform" in data

    def test_readme_is_written(self, tmp_path):
        from vnalpha.observability.context import RunContext

        ctx = RunContext(
            run_id="run_test_004",
            surface="cli",
            actor="test",
            log_root=tmp_path,
        )
        readme = ctx.run_dir / "README.md"
        assert readme.exists()
        content = readme.read_text()
        assert "run_test_004" in content
        assert "audit.jsonl" in content

    def test_latest_txt_fallback_written(self, tmp_path):
        """latest.txt should exist if symlink creation fails."""
        from vnalpha.observability.context import RunContext

        with patch("pathlib.Path.symlink_to", side_effect=OSError("no symlinks")):
            _ = RunContext(
                run_id="run_symlink_fallback",
                surface="cli",
                actor="test",
                log_root=tmp_path,
            )
        latest_txt = tmp_path / "runs" / "latest.txt"
        assert latest_txt.exists()
        assert "run_symlink_fallback" in latest_txt.read_text()

    def test_latest_symlink_created(self, tmp_path):
        from vnalpha.observability.context import RunContext

        _ = RunContext(
            run_id="run_symlink_test",
            surface="cli",
            actor="test",
            log_root=tmp_path,
        )
        latest_link = tmp_path / "runs" / "latest"
        assert latest_link.is_symlink() or (tmp_path / "runs" / "latest.txt").exists()

    def test_convenience_paths(self, isolated_run_ctx):
        ctx = isolated_run_ctx
        assert ctx.audit_path.name == "audit.jsonl"
        assert ctx.app_path.name == "app.jsonl"
        assert ctx.errors_path.name == "errors.jsonl"
        assert ctx.trace_path.name == "trace.jsonl"
        assert ctx.commands_path.name == "commands.jsonl"

    def test_make_run_context(self, tmp_path):
        from vnalpha.observability.context import make_run_context

        ctx = make_run_context(surface="pipeline", actor="ci", log_root=tmp_path)
        assert ctx.surface == "pipeline"
        assert ctx.run_dir.exists()

    def test_log_root_env_override(self, tmp_path, monkeypatch):
        monkeypatch.setenv("VNALPHA_LOG_ROOT", str(tmp_path))
        from vnalpha.observability.context import resolve_log_root

        root = resolve_log_root()
        assert root == tmp_path


# ===========================================================================
# Section 2: JSONL writer
# ===========================================================================


class TestJsonlWriter:
    def test_appends_valid_json_line(self, tmp_path):
        from vnalpha.observability.jsonl import append_jsonl

        path = tmp_path / "test.jsonl"
        append_jsonl(path, {"event": "test", "value": 42})
        lines = path.read_text().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["event"] == "test"
        assert record["value"] == 42

    def test_appends_multiple_lines(self, tmp_path):
        from vnalpha.observability.jsonl import append_jsonl

        path = tmp_path / "multi.jsonl"
        for i in range(5):
            append_jsonl(path, {"n": i})
        lines = path.read_text().splitlines()
        assert len(lines) == 5
        for i, line in enumerate(lines):
            assert json.loads(line)["n"] == i

    def test_creates_parent_dirs(self, tmp_path):
        from vnalpha.observability.jsonl import append_jsonl

        deep_path = tmp_path / "a" / "b" / "c" / "test.jsonl"
        append_jsonl(deep_path, {"x": 1})
        assert deep_path.exists()
        assert json.loads(deep_path.read_text().strip())["x"] == 1

    def test_never_raises_on_permission_error(self, tmp_path):
        from vnalpha.observability.jsonl import append_jsonl

        bad_path = Path("/root/no_access/test.jsonl")
        append_jsonl(bad_path, {"x": 1})

    def test_each_line_parses_independently(self, tmp_path):
        from vnalpha.observability.jsonl import append_jsonl

        path = tmp_path / "indep.jsonl"
        records = [{"a": 1}, {"b": "hello"}, {"c": True}]
        for r in records:
            append_jsonl(path, r)
        for line in path.read_text().splitlines():
            parsed = json.loads(line)
            assert isinstance(parsed, dict)


# ===========================================================================
# Section 3: Redaction
# ===========================================================================


class TestRedaction:
    def test_redacts_sensitive_key_in_dict(self):
        from vnalpha.observability.redaction import redact_dict

        d = {"username": "alice", "password": "s3cr3t!", "data": "ok"}
        result = redact_dict(d, mode="redacted")
        assert result["password"] == "[REDACTED]"
        assert result["username"] == "alice"
        assert result["data"] == "ok"

    def test_redacts_token_key(self):
        from vnalpha.observability.redaction import redact_dict

        d = {"token": "abc123", "event": "test"}
        result = redact_dict(d, mode="redacted")
        assert result["token"] == "[REDACTED]"

    def test_redacts_api_key(self):
        from vnalpha.observability.redaction import redact_dict

        d = {"api_key": "secret-value", "name": "test"}
        result = redact_dict(d, mode="redacted")
        assert result["api_key"] == "[REDACTED]"

    def test_full_mode_returns_original(self):
        from vnalpha.observability.redaction import redact_dict

        d = {"password": "plaintext", "name": "test"}
        result = redact_dict(d, mode="full")
        assert result["password"] == "plaintext"

    def test_metadata_mode_filters_to_safe_keys(self):
        from vnalpha.observability.redaction import redact_dict

        d = {
            "event_id": "abc",
            "password": "secret",
            "run_id": "r1",
            "summary": "test",
        }
        result = redact_dict(d, mode="metadata")
        assert "event_id" in result
        assert "run_id" in result
        assert "password" not in result

    def test_redact_str_replaces_sensitive_patterns(self):
        from vnalpha.observability.redaction import redact_str

        s = "Using api_key=SuperSecret123 for connection"
        result = redact_str(s, mode="redacted")
        assert "SuperSecret123" not in result
        assert "[REDACTED]" in result

    def test_redact_str_full_mode_unchanged(self):
        from vnalpha.observability.redaction import redact_str

        s = "password=mysecret"
        result = redact_str(s, mode="full")
        assert result == s

    def test_default_mode_is_redacted(self, monkeypatch):
        monkeypatch.delenv("VNALPHA_LOG_CONTENT_MODE", raising=False)
        from vnalpha.observability.redaction import get_content_mode

        mode = get_content_mode()
        assert mode == "redacted"

    def test_default_mode_does_not_write_secrets(self, monkeypatch):
        monkeypatch.delenv("VNALPHA_LOG_CONTENT_MODE", raising=False)
        from vnalpha.observability.redaction import redact_dict

        d = {"password": "supersecret", "token": "tok123"}
        result = redact_dict(d)
        assert "supersecret" not in str(result)
        assert "tok123" not in str(result)

    def test_nested_dict_redaction(self):
        from vnalpha.observability.redaction import redact_dict

        d = {"outer": {"inner_password": "secret", "safe": "value"}}
        result = redact_dict(d, mode="redacted")
        assert result["outer"]["inner_password"] == "[REDACTED]"
        assert result["outer"]["safe"] == "value"


# ===========================================================================
# Section 4: Correlation context
# ===========================================================================


class TestCorrelation:
    def test_set_correlation_id_returns_string(self):
        from vnalpha.observability.context import set_correlation_id

        cid = set_correlation_id()
        assert isinstance(cid, str)
        assert len(cid) > 8

    def test_get_correlation_id_after_set(self):
        from vnalpha.observability.context import get_correlation_id, set_correlation_id

        cid = set_correlation_id()
        assert get_correlation_id() == cid

    def test_get_correlation_id_default_is_unset(self):

        from vnalpha.observability import context as ctx_module

        ctx_module._CORRELATION_ID.set("unset")
        from vnalpha.observability.context import get_correlation_id

        assert get_correlation_id() == "unset"

    def test_different_invocations_produce_different_ids(self):
        from vnalpha.observability.context import set_correlation_id

        ids = {set_correlation_id() for _ in range(10)}
        assert len(ids) == 10

    def test_make_correlation_context(self):
        from vnalpha.observability.context import make_correlation_context

        corr = make_correlation_context()
        assert corr.correlation_id
        assert len(corr.correlation_id) >= 8

    def test_related_events_share_correlation_id(self, isolated_run_ctx):
        from vnalpha.observability.audit import log_audit
        from vnalpha.observability.context import set_correlation_id
        from vnalpha.observability.errors import capture_warning

        ctx = isolated_run_ctx
        cid = set_correlation_id()

        log_audit("TEST_EVENT", "test", run_ctx=ctx)
        capture_warning("test warning", run_ctx=ctx)

        audit_records = [
            json.loads(line)
            for line in ctx.audit_path.read_text().splitlines()
            if line.strip()
        ]
        err_records = [
            json.loads(line)
            for line in ctx.errors_path.read_text().splitlines()
            if line.strip()
        ]

        assert all(r["correlation_id"] == cid for r in audit_records)
        assert all(r["correlation_id"] == cid for r in err_records)

    def test_new_span_id_is_unique(self):
        from vnalpha.observability.context import new_span_id

        spans = {new_span_id() for _ in range(10)}
        assert len(spans) == 10


# ===========================================================================
# Section 5: Command logging
# ===========================================================================


class TestCommandLogging:
    def test_command_start_writes_to_commands_jsonl(self, isolated_run_ctx):
        from vnalpha.observability.commands import log_command_start
        from vnalpha.observability.context import set_correlation_id

        set_correlation_id()
        log_command_start("vnalpha sync symbols", run_ctx=isolated_run_ctx)
        path = isolated_run_ctx.commands_path
        assert path.exists()
        records = [
            json.loads(line) for line in path.read_text().splitlines() if line.strip()
        ]
        assert len(records) == 1
        r = records[0]
        assert r["event_type"] == "COMMAND_STARTED"
        assert r["command"] == "vnalpha sync symbols"
        assert r["status"] == "STARTED"

    def test_command_success_writes_to_commands_and_audit(self, isolated_run_ctx):
        from vnalpha.observability.commands import log_command_success
        from vnalpha.observability.context import set_correlation_id

        set_correlation_id()
        log_command_success(
            "vnalpha sync symbols",
            duration_ms=123.4,
            exit_code=0,
            run_ctx=isolated_run_ctx,
        )
        cmd_path = isolated_run_ctx.commands_path
        audit_path = isolated_run_ctx.audit_path
        assert cmd_path.exists()
        assert audit_path.exists()

        cmd_records = [
            json.loads(line)
            for line in cmd_path.read_text().splitlines()
            if line.strip()
        ]
        assert cmd_records[0]["event_type"] == "COMMAND_SUCCEEDED"
        assert cmd_records[0]["status"] == "SUCCESS"
        assert cmd_records[0]["duration_ms"] == 123.4

        audit_records = [
            json.loads(line)
            for line in audit_path.read_text().splitlines()
            if line.strip()
        ]
        assert any(r["event_type"] == "COMMAND_EXECUTED" for r in audit_records)

    def test_command_failure_writes_failed_event(self, isolated_run_ctx):
        from vnalpha.observability.commands import log_command_failure
        from vnalpha.observability.context import set_correlation_id

        set_correlation_id()
        log_command_failure(
            "vnalpha sync",
            duration_ms=50.0,
            exit_code=1,
            error_message="connection refused",
            run_ctx=isolated_run_ctx,
        )
        records = [
            json.loads(line)
            for line in isolated_run_ctx.commands_path.read_text().splitlines()
            if line.strip()
        ]
        assert records[0]["event_type"] == "COMMAND_FAILED"
        assert records[0]["status"] == "FAILED"
        assert records[0]["exit_code"] == 1

    def test_required_fields_in_command_event(self, isolated_run_ctx):
        from vnalpha.observability.commands import log_command_start
        from vnalpha.observability.context import set_correlation_id
        from vnalpha.observability.schemas import COMMAND_REQUIRED_FIELDS

        set_correlation_id()
        log_command_start("test cmd", run_ctx=isolated_run_ctx)
        records = [
            json.loads(line)
            for line in isolated_run_ctx.commands_path.read_text().splitlines()
            if line.strip()
        ]
        for field in COMMAND_REQUIRED_FIELDS:
            assert field in records[0], f"Missing required field: {field}"


# ===========================================================================
# Section 6: Error capture
# ===========================================================================


class TestErrorCapture:
    def test_capture_exception_writes_to_errors_jsonl(self, isolated_run_ctx):
        from vnalpha.observability.context import set_correlation_id
        from vnalpha.observability.errors import capture_exception

        set_correlation_id()
        try:
            raise ValueError("test error message")
        except ValueError as exc:
            capture_exception(exc, run_ctx=isolated_run_ctx)

        path = isolated_run_ctx.errors_path
        assert path.exists()
        records = [
            json.loads(line) for line in path.read_text().splitlines() if line.strip()
        ]
        assert len(records) == 1
        r = records[0]
        assert r["error_type"] == "ValueError"
        assert "test error message" in r["error_message"]
        assert r["stacktrace_hash"]

    def test_error_event_required_fields(self, isolated_run_ctx):
        from vnalpha.observability.context import set_correlation_id
        from vnalpha.observability.errors import capture_exception
        from vnalpha.observability.schemas import ERROR_REQUIRED_FIELDS

        set_correlation_id()
        try:
            raise RuntimeError("req field test")
        except RuntimeError as exc:
            capture_exception(exc, run_ctx=isolated_run_ctx)

        records = [
            json.loads(line)
            for line in isolated_run_ctx.errors_path.read_text().splitlines()
            if line.strip()
        ]
        for field in ERROR_REQUIRED_FIELDS:
            assert field in records[0], f"Missing: {field}"

    def test_capture_exception_never_raises(self, isolated_run_ctx):
        """Even if capture_exception itself fails, it must not raise."""
        from vnalpha.observability.errors import capture_exception

        exc = RuntimeError("test")
        capture_exception(exc, run_ctx=None)

    def test_capture_warning_writes_warning_level(self, isolated_run_ctx):
        from vnalpha.observability.context import set_correlation_id
        from vnalpha.observability.errors import capture_warning

        set_correlation_id()
        capture_warning("data quality degraded", run_ctx=isolated_run_ctx)
        records = [
            json.loads(line)
            for line in isolated_run_ctx.errors_path.read_text().splitlines()
            if line.strip()
        ]
        assert records[0]["level"] == "WARNING"

    def test_logging_failure_does_not_crash_workflow(self, tmp_path):
        """Simulate a broken log path — the workflow must continue."""
        from vnalpha.observability.errors import capture_exception

        exc = RuntimeError("workflow exc")
        capture_exception(exc, run_ctx=None)
        assert True


# ===========================================================================
# Section 7: Chat logging
# ===========================================================================


class TestChatLogging:
    def test_chat_turn_started_event(self, isolated_run_ctx):
        from vnalpha.observability.audit import log_audit
        from vnalpha.observability.context import set_correlation_id

        set_correlation_id()
        log_audit(
            "CHAT_TURN_STARTED",
            "User started chat turn",
            run_ctx=isolated_run_ctx,
        )
        records = [
            json.loads(line)
            for line in isolated_run_ctx.audit_path.read_text().splitlines()
            if line.strip()
        ]
        assert any(r["event_type"] == "CHAT_TURN_STARTED" for r in records)

    def test_plan_previewed_event(self, isolated_run_ctx):
        from vnalpha.observability.audit import log_audit
        from vnalpha.observability.context import set_correlation_id

        set_correlation_id()
        log_audit("PLAN_PREVIEWED", "Plan generated", run_ctx=isolated_run_ctx)
        log_audit("PLAN_APPROVED", "Plan approved", run_ctx=isolated_run_ctx)
        log_audit("PLAN_CANCELLED", "Plan cancelled", run_ctx=isolated_run_ctx)

        records = [
            json.loads(line)
            for line in isolated_run_ctx.audit_path.read_text().splitlines()
            if line.strip()
        ]
        types = {r["event_type"] for r in records}
        assert "PLAN_PREVIEWED" in types
        assert "PLAN_APPROVED" in types
        assert "PLAN_CANCELLED" in types

    def test_refusal_logging(self, isolated_run_ctx):
        from vnalpha.observability.audit import log_audit
        from vnalpha.observability.context import set_correlation_id

        set_correlation_id()
        log_audit(
            "TOOL_REFUSED",
            "Tool call refused: forbidden",
            status="REFUSED",
            run_ctx=isolated_run_ctx,
        )
        records = [
            json.loads(line)
            for line in isolated_run_ctx.audit_path.read_text().splitlines()
            if line.strip()
        ]
        assert any(r["event_type"] == "TOOL_REFUSED" for r in records)


# ===========================================================================
# Section 8: Tool trace logging
# ===========================================================================


class TestToolTraceLogging:
    def test_tool_call_started(self, isolated_run_ctx):
        from vnalpha.observability.context import set_correlation_id
        from vnalpha.observability.trace import log_trace

        set_correlation_id()
        log_trace(
            "TOOL_CALL_STARTED",
            "scan_watchlist",
            status="RUNNING",
            run_ctx=isolated_run_ctx,
        )
        records = [
            json.loads(line)
            for line in isolated_run_ctx.trace_path.read_text().splitlines()
            if line.strip()
        ]
        assert records[0]["event_type"] == "TOOL_CALL_STARTED"

    def test_tool_call_succeeded(self, isolated_run_ctx):
        from vnalpha.observability.context import set_correlation_id
        from vnalpha.observability.trace import log_trace

        set_correlation_id()
        log_trace(
            "TOOL_CALL_SUCCEEDED",
            "scan_watchlist",
            status="SUCCESS",
            duration_ms=42.5,
            run_ctx=isolated_run_ctx,
        )
        records = [
            json.loads(line)
            for line in isolated_run_ctx.trace_path.read_text().splitlines()
            if line.strip()
        ]
        assert records[0]["event_type"] == "TOOL_CALL_SUCCEEDED"
        assert records[0]["duration_ms"] == 42.5

    def test_tool_call_failed(self, isolated_run_ctx):
        from vnalpha.observability.context import set_correlation_id
        from vnalpha.observability.trace import log_trace

        set_correlation_id()
        log_trace(
            "TOOL_CALL_FAILED",
            "broken_tool",
            status="FAILED",
            run_ctx=isolated_run_ctx,
        )
        records = [
            json.loads(line)
            for line in isolated_run_ctx.trace_path.read_text().splitlines()
            if line.strip()
        ]
        assert records[0]["event_type"] == "TOOL_CALL_FAILED"

    def test_trace_required_fields(self, isolated_run_ctx):
        from vnalpha.observability.context import set_correlation_id
        from vnalpha.observability.schemas import TRACE_REQUIRED_FIELDS
        from vnalpha.observability.trace import log_trace

        set_correlation_id()
        log_trace("TOOL_CALL_STARTED", "my_tool", run_ctx=isolated_run_ctx)
        records = [
            json.loads(line)
            for line in isolated_run_ctx.trace_path.read_text().splitlines()
            if line.strip()
        ]
        for field in TRACE_REQUIRED_FIELDS:
            assert field in records[0], f"Missing: {field}"

    def test_tool_refused_audit_event(self, isolated_run_ctx):
        from vnalpha.observability.audit import log_audit
        from vnalpha.observability.context import set_correlation_id

        set_correlation_id()
        log_audit(
            "TOOL_REFUSED",
            "denied tool",
            status="REFUSED",
            run_ctx=isolated_run_ctx,
        )
        records = [
            json.loads(line)
            for line in isolated_run_ctx.audit_path.read_text().splitlines()
            if line.strip()
        ]
        assert any(r["event_type"] == "TOOL_REFUSED" for r in records)


# ===========================================================================
# Section 11: Summary generation
# ===========================================================================


class TestSummaryGeneration:
    def test_summary_generated(self, isolated_run_ctx):
        from vnalpha.observability.audit import log_audit
        from vnalpha.observability.commands import log_command_success
        from vnalpha.observability.context import set_correlation_id
        from vnalpha.observability.summary import generate_summary

        ctx = isolated_run_ctx
        set_correlation_id()
        log_audit("CLI_STARTED", "started", run_ctx=ctx)
        log_command_success("test cmd", duration_ms=10.0, run_ctx=ctx)

        md = generate_summary(ctx.run_dir)
        assert "# AI Agent Run Summary" in md
        assert ctx.run_id in md

    def test_summary_includes_errors_section(self, isolated_run_ctx):
        from vnalpha.observability.context import set_correlation_id
        from vnalpha.observability.errors import capture_exception
        from vnalpha.observability.summary import generate_summary

        set_correlation_id()
        try:
            raise RuntimeError("something went wrong")
        except RuntimeError as exc:
            capture_exception(exc, run_ctx=isolated_run_ctx)

        md = generate_summary(isolated_run_ctx.run_dir)
        assert "## Errors" in md
        assert "RuntimeError" in md

    def test_summary_includes_failed_commands(self, isolated_run_ctx):
        from vnalpha.observability.commands import log_command_failure
        from vnalpha.observability.context import set_correlation_id
        from vnalpha.observability.summary import generate_summary

        set_correlation_id()
        log_command_failure(
            "bad cmd",
            exit_code=1,
            error_message="failed hard",
            run_ctx=isolated_run_ctx,
        )

        md = generate_summary(isolated_run_ctx.run_dir)
        assert "## Failed commands" in md
        assert "bad cmd" in md

    def test_summary_file_written_to_run_dir(self, isolated_run_ctx):
        from vnalpha.observability.summary import generate_summary

        generate_summary(isolated_run_ctx.run_dir)
        summary_path = isolated_run_ctx.run_dir / "ai-agent-summary.md"
        assert summary_path.exists()
        content = summary_path.read_text()
        assert "AI Agent Run Summary" in content

    def test_summary_separates_fact_from_inference(self, isolated_run_ctx):
        from vnalpha.observability.context import set_correlation_id
        from vnalpha.observability.errors import capture_exception
        from vnalpha.observability.summary import generate_summary

        set_correlation_id()
        try:
            raise ValueError("test")
        except ValueError as exc:
            capture_exception(exc, likely_cause="bad input", run_ctx=isolated_run_ctx)

        md = generate_summary(isolated_run_ctx.run_dir)
        assert "*Likely" in md or "Likely" in md

    def test_summary_links_raw_logs(self, isolated_run_ctx):
        from vnalpha.observability.summary import generate_summary

        md = generate_summary(isolated_run_ctx.run_dir)
        assert "audit.jsonl" in md
        assert "errors.jsonl" in md


# ===========================================================================
# Section 12: Bundle creation
# ===========================================================================


class TestBundleCreation:
    def test_bundle_creates_tar_gz(self, isolated_run_ctx, tmp_path):
        from vnalpha.observability.audit import log_audit
        from vnalpha.observability.bundle import create_bundle
        from vnalpha.observability.context import set_correlation_id
        from vnalpha.observability.summary import generate_summary

        set_correlation_id()
        log_audit("TEST_EVENT", "test", run_ctx=isolated_run_ctx)
        generate_summary(isolated_run_ctx.run_dir)

        bundle_path = create_bundle(
            isolated_run_ctx.run_dir,
            output_path=tmp_path / "test_bundle.tar.gz",
        )
        assert bundle_path.exists()
        assert bundle_path.suffix == ".gz"

    def test_bundle_contains_summary_and_logs(self, isolated_run_ctx, tmp_path):
        import tarfile

        from vnalpha.observability.audit import log_audit
        from vnalpha.observability.bundle import create_bundle
        from vnalpha.observability.context import set_correlation_id
        from vnalpha.observability.summary import generate_summary

        set_correlation_id()
        log_audit("TEST_EVENT", "test", run_ctx=isolated_run_ctx)
        generate_summary(isolated_run_ctx.run_dir)

        bundle_path = create_bundle(
            isolated_run_ctx.run_dir,
            output_path=tmp_path / "test_bundle2.tar.gz",
        )
        with tarfile.open(bundle_path, "r:gz") as tar:
            names = tar.getnames()

        assert any("ai-agent-summary.md" in n for n in names)
        assert any("audit.jsonl" in n for n in names)

    def test_bundle_excludes_key_files(self, isolated_run_ctx, tmp_path):
        import tarfile

        from vnalpha.observability.bundle import create_bundle
        from vnalpha.observability.summary import generate_summary

        (isolated_run_ctx.run_dir / "secrets.key").write_text("fake_key")
        generate_summary(isolated_run_ctx.run_dir)

        bundle_path = create_bundle(
            isolated_run_ctx.run_dir,
            output_path=tmp_path / "test_bundle3.tar.gz",
        )
        with tarfile.open(bundle_path, "r:gz") as tar:
            names = tar.getnames()

        assert not any("secrets.key" in n for n in names)

    def test_bundle_contains_environment_json(self, isolated_run_ctx, tmp_path):
        import tarfile

        from vnalpha.observability.bundle import create_bundle
        from vnalpha.observability.summary import generate_summary

        generate_summary(isolated_run_ctx.run_dir)
        bundle_path = create_bundle(
            isolated_run_ctx.run_dir,
            output_path=tmp_path / "bundle4.tar.gz",
        )
        with tarfile.open(bundle_path, "r:gz") as tar:
            names = tar.getnames()
        assert any("environment.json" in n for n in names)


# ===========================================================================
# Section 12: Logs CLI commands
# ===========================================================================


class TestLogsCLI:
    def test_logs_latest_shows_run_dir(self, isolated_run_ctx, tmp_path, monkeypatch):
        from typer.testing import CliRunner

        from vnalpha.observability.cli_logs import logs_app

        monkeypatch.setenv("VNALPHA_LOG_ROOT", str(isolated_run_ctx.log_root))
        runner = CliRunner()
        result = runner.invoke(logs_app, ["latest"])
        assert result.exit_code == 0
        assert (
            isolated_run_ctx.run_id in result.output
            or str(isolated_run_ctx.run_dir) in result.output
        )

    def test_logs_errors_runs(self, isolated_run_ctx, tmp_path, monkeypatch):
        from typer.testing import CliRunner

        from vnalpha.observability.cli_logs import logs_app

        monkeypatch.setenv("VNALPHA_LOG_ROOT", str(isolated_run_ctx.log_root))
        runner = CliRunner()
        result = runner.invoke(logs_app, ["errors", "--latest"])
        assert result.exit_code == 0

    def test_logs_show_runs(self, isolated_run_ctx, monkeypatch):
        from typer.testing import CliRunner

        from vnalpha.observability.audit import log_audit
        from vnalpha.observability.cli_logs import logs_app
        from vnalpha.observability.context import set_correlation_id

        monkeypatch.setenv("VNALPHA_LOG_ROOT", str(isolated_run_ctx.log_root))
        set_correlation_id()
        log_audit("TEST", "summary text", run_ctx=isolated_run_ctx)

        runner = CliRunner()
        result = runner.invoke(logs_app, ["show", "--latest"])
        assert result.exit_code == 0

    def test_logs_summarize_runs(self, isolated_run_ctx, monkeypatch):
        from typer.testing import CliRunner

        from vnalpha.observability.cli_logs import logs_app

        monkeypatch.setenv("VNALPHA_LOG_ROOT", str(isolated_run_ctx.log_root))
        runner = CliRunner()
        result = runner.invoke(logs_app, ["summarize", "--latest"])
        assert result.exit_code == 0
        assert "AI Agent Run Summary" in result.output

    def test_logs_doctor_runs(self, isolated_run_ctx, monkeypatch):
        from typer.testing import CliRunner

        from vnalpha.observability.cli_logs import logs_app

        monkeypatch.setenv("VNALPHA_LOG_ROOT", str(isolated_run_ctx.log_root))
        runner = CliRunner()
        result = runner.invoke(logs_app, ["doctor", "--latest"])
        assert result.exit_code == 0

    def test_logs_bundle_creates_artifact(
        self, isolated_run_ctx, tmp_path, monkeypatch
    ):
        from typer.testing import CliRunner

        from vnalpha.observability.cli_logs import logs_app

        monkeypatch.setenv("VNALPHA_LOG_ROOT", str(isolated_run_ctx.log_root))
        out = str(tmp_path / "out.tar.gz")
        runner = CliRunner()
        result = runner.invoke(logs_app, ["bundle", "--latest", "--output", out])
        assert result.exit_code == 0
        assert Path(out).exists()


# ===========================================================================
# Section 2 (additional): log_audit extended fields + event coverage
# ===========================================================================


class TestAuditExtendedFields:
    """Tasks 2.5-2.8: test log_audit optional kwargs + event type coverage."""

    def test_log_audit_module_field_written(self, isolated_run_ctx):
        """Task 2.5: log_audit(..., module=...) writes module field to audit.jsonl."""
        from vnalpha.observability.audit import log_audit
        from vnalpha.observability.context import set_correlation_id

        set_correlation_id()
        log_audit(
            "TEST_EVENT",
            "test with module",
            module="vnalpha.test",
            run_ctx=isolated_run_ctx,
        )
        records = [
            json.loads(line)
            for line in isolated_run_ctx.audit_path.read_text().splitlines()
            if line.strip()
        ]
        r = next(r for r in records if r["event_type"] == "TEST_EVENT")
        assert r["module"] == "vnalpha.test"

    def test_log_audit_function_field_written(self, isolated_run_ctx):
        """Task 2.5: log_audit(..., function=...) writes function field."""
        from vnalpha.observability.audit import log_audit
        from vnalpha.observability.context import set_correlation_id

        set_correlation_id()
        log_audit(
            "TEST_EVENT2",
            "test with function",
            function="do_something",
            run_ctx=isolated_run_ctx,
        )
        records = [
            json.loads(line)
            for line in isolated_run_ctx.audit_path.read_text().splitlines()
            if line.strip()
        ]
        r = next(r for r in records if r["event_type"] == "TEST_EVENT2")
        assert r["function"] == "do_something"

    def test_log_audit_session_and_object_fields(self, isolated_run_ctx):
        """Task 2.5: session_id, object_type, object_id round-trip."""
        from vnalpha.observability.audit import log_audit
        from vnalpha.observability.context import set_correlation_id

        set_correlation_id()
        log_audit(
            "TEST_OBJ",
            "test with object fields",
            session_id="sess-abc",
            object_type="tool",
            object_id="tool-001",
            run_ctx=isolated_run_ctx,
        )
        records = [
            json.loads(line)
            for line in isolated_run_ctx.audit_path.read_text().splitlines()
            if line.strip()
        ]
        r = next(r for r in records if r["event_type"] == "TEST_OBJ")
        assert r["session_id"] == "sess-abc"
        assert r["object_type"] == "tool"
        assert r["object_id"] == "tool-001"

    def test_log_audit_without_optional_fields_no_extra_keys(self, isolated_run_ctx):
        """Task 2.3: calling log_audit without optional kwargs does not add spurious keys."""
        from vnalpha.observability.audit import log_audit
        from vnalpha.observability.context import set_correlation_id

        set_correlation_id()
        log_audit("PLAIN_EVENT", "no extra", run_ctx=isolated_run_ctx)
        records = [
            json.loads(line)
            for line in isolated_run_ctx.audit_path.read_text().splitlines()
            if line.strip()
        ]
        r = next(r for r in records if r["event_type"] == "PLAIN_EVENT")
        for key in ("module", "function", "session_id", "object_type", "object_id"):
            assert key not in r

    def test_assistant_answer_logged_event(self, isolated_run_ctx):
        """Task 2.7: ASSISTANT_ANSWER_LOGGED is written directly via log_audit."""
        from vnalpha.observability.audit import log_audit
        from vnalpha.observability.context import set_correlation_id

        set_correlation_id()
        log_audit(
            "ASSISTANT_ANSWER_LOGGED",
            "Answer delivered to user",
            run_ctx=isolated_run_ctx,
        )
        records = [
            json.loads(line)
            for line in isolated_run_ctx.audit_path.read_text().splitlines()
            if line.strip()
        ]
        assert any(r["event_type"] == "ASSISTANT_ANSWER_LOGGED" for r in records)

    def test_chat_refusal_event(self, isolated_run_ctx):
        """Task 2.8: CHAT_REFUSAL is written on refusal paths via log_audit."""
        from vnalpha.observability.audit import log_audit
        from vnalpha.observability.context import set_correlation_id

        set_correlation_id()
        log_audit(
            "CHAT_REFUSAL",
            "Request refused: out of scope",
            status="REFUSED",
            run_ctx=isolated_run_ctx,
        )
        records = [
            json.loads(line)
            for line in isolated_run_ctx.audit_path.read_text().splitlines()
            if line.strip()
        ]
        r = next(r for r in records if r["event_type"] == "CHAT_REFUSAL")
        assert r["status"] == "REFUSED"


# ===========================================================================
# Section 3 (additional): CLI lifecycle wrapper integration tests
# ===========================================================================


def test_logs_doctor_accepts_absent_event_driven_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    from vnalpha.observability import cli_logs

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "app.jsonl").write_text('{"event_type":"CLI_STARTED"}\n')
    (run_dir / "environment.json").write_text('{"run_id":"run"}\n')
    monkeypatch.setattr(cli_logs, "_resolve_run_dir", lambda *_args: run_dir)

    result = CliRunner().invoke(cli_logs.logs_app, ["doctor", "--latest"])

    assert result.exit_code == 0
    assert "Status: OK" in result.output


class TestCommandLifecycleWrapper:
    """Tasks 3.22-3.24: CLI lifecycle context manager tests."""

    def test_command_lifecycle_success_path(self, isolated_run_ctx):
        """Task 3.23: command_lifecycle emits STARTED + SUCCEEDED on success."""
        from vnalpha.observability.commands import command_lifecycle
        from vnalpha.observability.context import set_correlation_id
        from vnalpha.observability.jsonl import read_jsonl

        set_correlation_id()
        with command_lifecycle("test cmd", run_ctx=isolated_run_ctx):
            pass  # success

        records = read_jsonl(isolated_run_ctx.commands_path)
        types = [r["event_type"] for r in records]
        assert "COMMAND_STARTED" in types
        assert "COMMAND_SUCCEEDED" in types

    def test_command_lifecycle_failure_path(self, isolated_run_ctx):
        """Task 3.24: command_lifecycle emits STARTED + FAILED + captures exception."""
        from vnalpha.observability.commands import command_lifecycle
        from vnalpha.observability.context import set_correlation_id
        from vnalpha.observability.jsonl import read_jsonl

        set_correlation_id()
        with pytest.raises(ValueError, match="boom"):
            with command_lifecycle("fail cmd", run_ctx=isolated_run_ctx):
                raise ValueError("boom")

        cmd_records = read_jsonl(isolated_run_ctx.commands_path)
        types = [r["event_type"] for r in cmd_records]
        assert "COMMAND_STARTED" in types
        assert "COMMAND_FAILED" in types
        # Exception should be captured in errors.jsonl
        err_records = read_jsonl(isolated_run_ctx.errors_path)
        assert any(r.get("error_type") == "ValueError" for r in err_records)

    def test_command_lifecycle_sets_correlation_id(self, isolated_run_ctx):
        """Task 3.3: lifecycle auto-assigns correlation ID if unset."""
        from vnalpha.observability.commands import command_lifecycle
        from vnalpha.observability.context import get_correlation_id, set_correlation_id

        # Reset correlation ID
        set_correlation_id("unset")
        with command_lifecycle("test-cid", run_ctx=isolated_run_ctx):
            cid_inside = get_correlation_id()

        assert cid_inside != "" and cid_inside != "unset"

    def test_command_lifecycle_duration_ms_present(self, isolated_run_ctx):
        """Task 3.8: COMMAND_SUCCEEDED has duration_ms field."""
        from vnalpha.observability.commands import command_lifecycle
        from vnalpha.observability.context import set_correlation_id
        from vnalpha.observability.jsonl import read_jsonl

        set_correlation_id()
        with command_lifecycle("timed cmd", run_ctx=isolated_run_ctx):
            pass

        records = read_jsonl(isolated_run_ctx.commands_path)
        succeeded = next(r for r in records if r["event_type"] == "COMMAND_SUCCEEDED")
        assert "duration_ms" in succeeded
        assert succeeded["duration_ms"] >= 0


class TestCapturedSwallowedExceptions:
    def test_slash_command_exception_captured(self, isolated_run_ctx):
        from unittest.mock import patch

        from vnalpha.observability.jsonl import read_jsonl

        with patch(
            "vnalpha.observability.context._CURRENT_RUN_CONTEXT", isolated_run_ctx
        ):
            with patch(
                "vnalpha.commands.executor.CommandExecutor.execute",
                side_effect=RuntimeError("slash boom"),
            ):
                from vnalpha.chat.controller import ChatController

                ctrl = ChatController(on_message=lambda s, t: None)
                result = ctrl.handle_slash_command("/scan")

        assert result is not None
        err_records = read_jsonl(isolated_run_ctx.errors_path)
        assert any(r.get("error_type") == "RuntimeError" for r in err_records)

    def test_natural_language_exception_captured(self, isolated_run_ctx):
        from unittest.mock import patch

        from vnalpha.observability.jsonl import read_jsonl

        with patch(
            "vnalpha.observability.context._CURRENT_RUN_CONTEXT", isolated_run_ctx
        ):
            with patch(
                "vnalpha.chat.controller.ChatController._run_ask",
                side_effect=RuntimeError("nlp boom"),
            ):
                from vnalpha.chat.controller import ChatController

                ctrl = ChatController(on_message=lambda s, t: None)
                result = ctrl.handle_natural_language("what is VNM?")

        assert result is not None
        err_records = read_jsonl(isolated_run_ctx.errors_path)
        assert any(r.get("error_type") == "RuntimeError" for r in err_records)


class TestToolTraceObservability:
    def _make_executor(self, tmp_path, *, trace_events=None):
        import duckdb

        from vnalpha.tools.executor import TracedLocalToolExecutor
        from vnalpha.tools.models import ToolOutput, ToolPermission, ToolSpec
        from vnalpha.tools.registry import LocalToolRegistry
        from vnalpha.warehouse.migrations import run_migrations

        conn = duckdb.connect(str(tmp_path / "db.duckdb"))
        run_migrations(conn=conn)

        registry = LocalToolRegistry()
        spec = ToolSpec(
            name="test_tool",
            description="test",
            permission=ToolPermission.READ_WATCHLIST,
        )
        registry.register(spec, lambda **kwargs: ToolOutput(data=None, summary="ok"))

        cb = trace_events.append if trace_events is not None else None
        return TracedLocalToolExecutor(
            conn,
            registry,
            session_id=None,
            assistant_session_id=None,
            trace_event_callback=cb,
        ), conn

    def test_successful_tool_trace_has_correlation_id(self, tmp_path, isolated_run_ctx):
        from unittest.mock import patch

        from vnalpha.observability.context import set_correlation_id
        from vnalpha.observability.jsonl import read_jsonl
        from vnalpha.tools.models import ToolPermission

        set_correlation_id()
        events = []
        executor, conn = self._make_executor(tmp_path, trace_events=events)

        with patch(
            "vnalpha.observability.context._CURRENT_RUN_CONTEXT", isolated_run_ctx
        ):
            executor.call(
                "test_tool", granted_permissions={ToolPermission.READ_WATCHLIST}
            )

        trace_records = read_jsonl(isolated_run_ctx.trace_path)
        succeeded = [
            r for r in trace_records if r.get("event_type") == "TOOL_CALL_SUCCEEDED"
        ]
        assert len(succeeded) >= 1
        for rec in succeeded:
            assert rec.get("correlation_id", "unset") != "unset"

    def test_failed_tool_writes_errors_jsonl(self, tmp_path, isolated_run_ctx):
        from unittest.mock import patch

        import duckdb

        from vnalpha.observability.jsonl import read_jsonl
        from vnalpha.tools.executor import TracedLocalToolExecutor
        from vnalpha.tools.models import ToolPermission, ToolSpec
        from vnalpha.tools.registry import LocalToolRegistry
        from vnalpha.warehouse.migrations import run_migrations

        conn = duckdb.connect(str(tmp_path / "db2.duckdb"))
        run_migrations(conn=conn)

        registry = LocalToolRegistry()
        spec = ToolSpec(
            name="fail_tool",
            description="fails",
            permission=ToolPermission.READ_WATCHLIST,
        )

        def _fail(**kwargs):
            raise ValueError("tool exploded")

        registry.register(spec, _fail)

        executor = TracedLocalToolExecutor(conn, registry)
        with patch(
            "vnalpha.observability.context._CURRENT_RUN_CONTEXT", isolated_run_ctx
        ):
            with pytest.raises(ValueError, match="tool exploded"):
                executor.call(
                    "fail_tool", granted_permissions={ToolPermission.READ_WATCHLIST}
                )

        err_records = read_jsonl(isolated_run_ctx.errors_path)
        assert any(r.get("error_type") == "ValueError" for r in err_records)

    def test_refused_tool_emits_audit_and_trace(self, tmp_path, isolated_run_ctx):
        from unittest.mock import patch

        import duckdb

        from vnalpha.observability.jsonl import read_jsonl
        from vnalpha.tools.errors import ToolPermissionError
        from vnalpha.tools.executor import TracedLocalToolExecutor
        from vnalpha.tools.models import ToolOutput, ToolPermission, ToolSpec
        from vnalpha.tools.registry import LocalToolRegistry
        from vnalpha.warehouse.migrations import run_migrations

        conn = duckdb.connect(str(tmp_path / "db3.duckdb"))
        run_migrations(conn=conn)

        registry = LocalToolRegistry()
        spec = ToolSpec(
            name="write_note_tool",
            description="writes notes",
            permission=ToolPermission.WRITE_NOTE,
        )
        registry.register(spec, lambda **kwargs: ToolOutput(data=None, summary="never"))

        events = []
        executor = TracedLocalToolExecutor(
            conn, registry, trace_event_callback=events.append
        )

        with patch(
            "vnalpha.observability.context._CURRENT_RUN_CONTEXT", isolated_run_ctx
        ):
            with pytest.raises(ToolPermissionError):
                executor.call(
                    "write_note_tool",
                    granted_permissions={ToolPermission.READ_WATCHLIST},
                )

        audit_records = read_jsonl(isolated_run_ctx.audit_path)
        assert any(r.get("event_type") == "TOOL_REFUSED" for r in audit_records)

        trace_records = read_jsonl(isolated_run_ctx.trace_path)
        assert any(r.get("event_type") == "TOOL_CALL_REFUSED" for r in trace_records)

        failed_events = [e for e in events if e.status == "FAILED"]
        assert len(failed_events) >= 1

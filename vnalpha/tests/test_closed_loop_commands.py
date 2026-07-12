from __future__ import annotations

import json
from pathlib import Path

import duckdb

from vnalpha.commands.parser import parse
from vnalpha.commands.setup import build_default_registry
from vnalpha.warehouse.migrations import run_migrations


def _failed_run(root: Path) -> None:
    run_dir = root / "runs" / "latest-run"
    run_dir.mkdir(parents=True)
    (run_dir / "environment.json").write_text("{}", encoding="utf-8")
    (run_dir / "errors.jsonl").write_text(
        json.dumps(
            {
                "event_type": "EXCEPTION_CAPTURED",
                "correlation_id": "corr-command",
                "job_id": "job-command",
                "error_type": "RuntimeError",
                "error_message": "failed",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "commands.jsonl").write_text(
        json.dumps(
            {
                "event_type": "COMMAND_FAILED",
                "correlation_id": "corr-command",
                "status": "FAILED",
                "command": "/sandbox run test",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "runs" / "latest.txt").write_text("latest-run\n", encoding="utf-8")


def test_closed_loop_commands_are_registered_and_render_inline_errors(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("VNALPHA_LOG_ROOT", str(tmp_path))
    _failed_run(tmp_path)
    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn)

    registry = build_default_registry()
    prepared = registry.execute(parse("/repair prepare --latest"), conn=conn)
    unsupported = registry.execute(parse("/repair unsupported"), conn=conn)

    assert {"repair", "validate", "deploy"}.issubset(registry.names())
    assert prepared.status.value == "SUCCESS"
    assert prepared.panels
    assert unsupported.status.value == "VALIDATION_ERROR"
    assert "Unsupported" in (unsupported.summary or "")
    conn.close()


def test_deploy_force_option_is_rejected_inline(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VNALPHA_LOG_ROOT", str(tmp_path))
    conn = duckdb.connect(":memory:")
    run_migrations(conn=conn)

    result = build_default_registry().execute(
        parse("/deploy promote artifact-1 --deployment-id deployment-1 --force"),
        conn=conn,
    )

    assert result.status.value == "VALIDATION_ERROR"
    assert "Unsupported" in (result.summary or "")
    conn.close()

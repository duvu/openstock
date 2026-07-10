"""Non-CLI operational command bridge for the Textual TUI."""

from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Protocol


class UnsupportedOperationalCommand(Exception):
    """Raised when an operational command is outside the documented TUI forms."""


class OperationalActions(Protocol):
    """Domain actions exposed through the seven supported TUI commands."""

    def logs_errors(self) -> str: ...

    def logs_summarize(self) -> str: ...

    def repair_prepare(self) -> str: ...

    def repair_status(self, repair_id: str) -> str: ...

    def deploy_verify(self, candidate: str) -> str: ...

    def deploy_promote(self, candidate: str, deployment_id: str) -> str: ...

    def deploy_rollback(self, deployment_id: str) -> str: ...


class OperationalCommandBridge:
    """Parse and execute only documented operational commands without Typer."""

    def __init__(self, actions: OperationalActions | None = None) -> None:
        self._actions = actions or ObservabilityActions()

    def is_supported(self, raw: str) -> bool:
        try:
            parts = self._parse(raw)
        except ValueError:
            return False
        match parts:
            case ["/logs", "errors", "--latest"]:
                return True
            case ["/logs", "summarize", "--latest"]:
                return True
            case ["/repair", "prepare", "--latest"]:
                return True
            case ["/repair", "status", repair_id] if repair_id:
                return True
            case ["/deploy", "verify", candidate] if candidate:
                return True
            case [
                "/deploy",
                "promote",
                candidate,
                "--deployment-id",
                deployment_id,
            ] if candidate and deployment_id:
                return True
            case ["/deploy", "rollback", deployment_id] if deployment_id:
                return True
            case _:
                return False

    def execute(self, raw: str) -> str:
        try:
            parts = self._parse(raw)
        except ValueError as exc:
            raise UnsupportedOperationalCommand(
                "Unsupported operational command. Use /logs, /repair, or /deploy help."
            ) from exc

        match parts:
            case ["/logs", "errors", "--latest"]:
                return self._actions.logs_errors()
            case ["/logs", "summarize", "--latest"]:
                return self._actions.logs_summarize()
            case ["/repair", "prepare", "--latest"]:
                return self._actions.repair_prepare()
            case ["/repair", "status", repair_id] if repair_id:
                return self._actions.repair_status(repair_id)
            case ["/deploy", "verify", candidate] if candidate:
                return self._actions.deploy_verify(candidate)
            case [
                "/deploy",
                "promote",
                candidate,
                "--deployment-id",
                deployment_id,
            ] if candidate and deployment_id:
                return self._actions.deploy_promote(candidate, deployment_id)
            case ["/deploy", "rollback", deployment_id] if deployment_id:
                return self._actions.deploy_rollback(deployment_id)
            case _:
                raise UnsupportedOperationalCommand(
                    "Unsupported operational command. Supported: "
                    "/logs errors --latest, /logs summarize --latest, "
                    "/repair prepare --latest, /repair status <repair-id>, "
                    "/deploy verify <candidate>, "
                    "/deploy promote <candidate> --deployment-id <id>, "
                    "/deploy rollback <deployment-id>."
                )

    def _parse(self, raw: str) -> list[str]:
        return shlex.split(raw)


class ObservabilityActions:
    """Invoke existing observability-domain functions without CLI entrypoints."""

    def logs_errors(self) -> str:
        errors_path = self._latest_run_dir() / "errors.jsonl"
        if not errors_path.exists():
            return "No errors recorded."

        lines = [
            line
            for line in errors_path.read_text(encoding="utf-8").splitlines()
            if line
        ]
        if not lines:
            return "No errors recorded."
        return "\n".join(self._format_error_line(line) for line in lines)

    def logs_summarize(self) -> str:
        from vnalpha.observability.summary import generate_summary

        return generate_summary(self._latest_run_dir())

    def repair_prepare(self) -> str:
        from vnalpha.observability.repair import create_repair_bundle, log_repair_event

        run_dir = self._latest_run_dir()
        bundle_dir = create_repair_bundle(run_dir)
        log_repair_event(
            "REPAIR_PREPARED",
            f"Repair bundle created: {bundle_dir.name}",
            repair_id=bundle_dir.name,
            extra={"bundle_dir": str(bundle_dir), "source_run_id": run_dir.name},
        )
        return f"Repair bundle created: {bundle_dir}"

    def repair_status(self, repair_id: str) -> str:
        from vnalpha.observability.repair import load_repair_state, resolve_bundles_root

        bundle_dir = resolve_bundles_root() / repair_id
        if not bundle_dir.exists():
            raise UnsupportedOperationalCommand(f"Repair bundle not found: {repair_id}")
        return json.dumps(load_repair_state(bundle_dir), indent=2, default=str)

    def deploy_verify(self, candidate: str) -> str:
        from vnalpha.observability.deploy import verify_deploy_candidate

        result = verify_deploy_candidate(candidate)
        return self._format_deployment_result(result)

    def deploy_promote(self, candidate: str, deployment_id: str) -> str:
        from vnalpha.observability.deploy import promote_candidate

        result = promote_candidate(candidate, deployment_id=deployment_id)
        return self._format_deployment_result(result)

    def deploy_rollback(self, deployment_id: str) -> str:
        from vnalpha.observability.deploy import rollback_deployment

        result = rollback_deployment(deployment_id)
        return self._format_deployment_result(result)

    def _latest_run_dir(self) -> Path:
        from vnalpha.observability.context import resolve_log_root

        runs_root = resolve_log_root() / "runs"
        latest = runs_root / "latest"
        if latest.exists():
            return latest.resolve()
        latest_txt = runs_root / "latest.txt"
        if latest_txt.exists():
            return runs_root / latest_txt.read_text(encoding="utf-8").strip()
        runs = sorted(path for path in runs_root.iterdir() if path.is_dir())
        if runs:
            return runs[-1]
        raise UnsupportedOperationalCommand("No observability runs are available.")

    def _format_error_line(self, line: str) -> str:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            return line
        timestamp = str(record.get("created_at", ""))[:19]
        level = record.get("level", "ERROR")
        error_type = record.get("error_type", "")
        message = record.get("error_message", "")
        return f"[{timestamp}] [{level}] {error_type}: {message}"

    def _format_deployment_result(self, result) -> str:
        return json.dumps(result, indent=2, default=str)

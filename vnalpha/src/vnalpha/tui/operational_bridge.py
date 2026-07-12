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

    def repair_apply(self, repair_id: str, attempt: str) -> str: ...

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
            case ["/repair", "apply", repair_id, "--attempt", attempt] if (
                repair_id and attempt.isdigit()
            ):
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
            case ["/repair", "apply", repair_id, "--attempt", attempt] if (
                repair_id and attempt.isdigit()
            ):
                return self._actions.repair_apply(repair_id, attempt)
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
                    "/repair apply <repair-id> --attempt <n>, "
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
        from vnalpha.closed_loop.bundle import latest_failed_run
        from vnalpha.closed_loop.service import ClosedLoopService
        from vnalpha.closed_loop.store import ClosedLoopStore
        from vnalpha.observability.context import resolve_log_root

        root = resolve_log_root()
        run_dir = latest_failed_run(root)
        if run_dir is None:
            raise UnsupportedOperationalCommand("No failed research run is available.")
        bundle = ClosedLoopService(ClosedLoopStore(root)).prepare_failed_run(run_dir)
        return f"Repair bundle created: {root / 'bundles' / bundle.repair_id}"

    def repair_status(self, repair_id: str) -> str:
        from vnalpha.closed_loop.service import ClosedLoopService
        from vnalpha.closed_loop.store import ClosedLoopStore
        from vnalpha.observability.context import resolve_log_root

        service = ClosedLoopService(ClosedLoopStore(resolve_log_root()))
        try:
            bundle = service.store.load_bundle(repair_id)
            lifecycle = service.store.current_lifecycle(repair_id)
        except RuntimeError as exc:
            raise UnsupportedOperationalCommand(str(exc)) from exc
        return json.dumps(
            {
                "repair_id": bundle.repair_id,
                "correlation_id": bundle.correlation_id,
                "state": lifecycle.state.value,
                "attempts": len(service.store.list_attempts(repair_id)),
            },
            indent=2,
        )

    def repair_apply(self, repair_id: str, attempt: str) -> str:
        raise UnsupportedOperationalCommand(
            f"Repair {repair_id} attempt {attempt} requires an approved sandbox runner; "
            "no local execution started."
        )

    def deploy_verify(self, candidate: str) -> str:
        from vnalpha.closed_loop.service import ClosedLoopService
        from vnalpha.closed_loop.store import ClosedLoopStore
        from vnalpha.closed_loop.validation import resolve_artifact_root
        from vnalpha.observability.context import resolve_log_root

        root = resolve_log_root()
        result = ClosedLoopService(ClosedLoopStore(root)).verify(
            candidate, artifact_root=resolve_artifact_root(root, candidate)
        )
        return self._format_deployment_result(result.model_dump(mode="json"))

    def deploy_promote(self, candidate: str, deployment_id: str) -> str:
        from vnalpha.closed_loop.service import ClosedLoopService
        from vnalpha.closed_loop.store import ClosedLoopStore
        from vnalpha.observability.context import resolve_log_root

        result = ClosedLoopService(ClosedLoopStore(resolve_log_root())).promote(
            candidate, deployment_id=deployment_id
        )
        return self._format_deployment_result(result.model_dump(mode="json"))

    def deploy_rollback(self, deployment_id: str) -> str:
        from vnalpha.closed_loop.service import ClosedLoopService
        from vnalpha.closed_loop.store import ClosedLoopStore
        from vnalpha.observability.context import resolve_log_root

        result = ClosedLoopService(ClosedLoopStore(resolve_log_root())).rollback(
            deployment_id
        )
        return self._format_deployment_result(result.model_dump(mode="json"))

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

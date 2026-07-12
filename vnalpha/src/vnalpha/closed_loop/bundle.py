from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from vnalpha.closed_loop.errors import ClosedLoopBoundaryError
from vnalpha.closed_loop.models import JsonObject, RepairBundle
from vnalpha.closed_loop.paths import (
    ensure_tree_confined,
    resolve_component,
    resolve_under,
    validate_identifier,
)
from vnalpha.closed_loop.store import ClosedLoopStore
from vnalpha.observability.context import get_correlation_id
from vnalpha.observability.jsonl import read_jsonl
from vnalpha.observability.redaction import get_content_mode, redact_dict, redact_str


@dataclass(frozen=True, slots=True)
class RepairPreparation:
    run_dir: Path
    failed_job_id: str | None = None
    user_request: str = ""
    plan_summary: str = ""


def latest_failed_run(root: Path) -> Path | None:
    runs_root = resolve_under(root, Path("runs"), "runs root")
    ensure_tree_confined(root, runs_root, "runs root")
    if not runs_root.exists():
        return None
    latest_link = runs_root / "latest"
    if latest_link.is_symlink():
        try:
            latest_run = resolve_under(runs_root, latest_link.resolve(), "latest run")
            ensure_tree_confined(latest_run, latest_run, "latest run")
        except ClosedLoopBoundaryError:
            latest_run = None
        if latest_run is not None and _is_failed_run(latest_run):
            return latest_run
    latest_text = runs_root / "latest.txt"
    if latest_text.exists():
        run_id = latest_text.read_text(encoding="utf-8").strip()
        try:
            candidate = resolve_component(root, "runs", run_id, "run_id")
            ensure_tree_confined(candidate, candidate, "run directory")
        except ClosedLoopBoundaryError:
            candidate = None
        if candidate is not None and _is_failed_run(candidate):
            return candidate
    candidates: list[Path] = []
    for path in runs_root.iterdir():
        if not path.is_dir() or path.name == "latest":
            continue
        try:
            confined = resolve_under(runs_root, path, "run directory")
            ensure_tree_confined(confined, confined, "run directory")
        except ClosedLoopBoundaryError:
            continue
        if _is_failed_run(confined):
            candidates.append(confined)
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def run_for_job(root: Path, job_id: str) -> Path | None:
    job_id = validate_identifier(job_id, "job_id")
    direct = resolve_component(root, "runs", job_id, "job_id")
    if direct.is_dir():
        ensure_tree_confined(direct, direct, "run directory")
        return direct
    runs_root = resolve_under(root, Path("runs"), "runs root")
    ensure_tree_confined(root, runs_root, "runs root")
    if not runs_root.exists():
        return None
    for run_dir in runs_root.iterdir():
        try:
            confined_run_dir = resolve_under(runs_root, run_dir, "run directory")
            ensure_tree_confined(confined_run_dir, confined_run_dir, "run directory")
        except ClosedLoopBoundaryError:
            continue
        sandbox_job = resolve_under(
            confined_run_dir / "sandbox", Path(job_id), "sandbox job"
        )
        if sandbox_job.exists() and _is_failed_run(confined_run_dir):
            return confined_run_dir
    return None


def package_repair(
    preparation: RepairPreparation, store: ClosedLoopStore
) -> RepairBundle:
    run_dir = store.run_directory(preparation.run_dir)
    errors = read_jsonl(run_dir / "errors.jsonl")
    commands = read_jsonl(run_dir / "commands.jsonl")
    audit = read_jsonl(run_dir / "audit.jsonl")
    events = (*errors, *commands, *audit)
    environment = _read_json(run_dir / "environment.json")
    manifest = _read_json(run_dir / "manifest.json")
    validation = _read_json(run_dir / "validation.json")
    output_state = _read_json(run_dir / "execution.json")
    guard = _read_json(run_dir / "guard.json")
    input_references = _read_json(run_dir / "input_references.json")
    correlation_id = _first_text(events, "correlation_id") or get_correlation_id()
    if correlation_id in {"", "unset"}:
        correlation_id = uuid4().hex
    failed_job_id = (
        preparation.failed_job_id or _first_text(events, "job_id") or run_dir.name
    )
    failed_session_id = _first_text(events, "session_id")
    user_request = (
        preparation.user_request
        or _first_text(events, "user_request")
        or _text_value(environment, "request")
        or _first_text(commands, "command")
    )
    plan_summary = (
        preparation.plan_summary
        or _first_text(events, "plan_summary")
        or _read_text(run_dir / "ai-agent-summary.md")
    )
    generated_code = _read_text(run_dir / "generated_code.py")
    stdout = _read_text(run_dir / "stdout.txt") or _first_text(commands, "stdout_tail")
    stderr = _read_text(run_dir / "stderr.txt") or _first_text(commands, "stderr_tail")
    error_trace = "\n".join(
        value
        for event in errors
        for value in (
            _text_value(event, "stacktrace"),
            _text_value(event, "error_message"),
        )
        if value
    )
    dataset_refs = _dataset_refs(input_references, manifest)
    redaction_mode = get_content_mode()
    bundle = RepairBundle(
        repair_id=f"repair-{uuid4().hex}",
        correlation_id=redact_str(correlation_id, redaction_mode),
        failed_job_id=redact_str(failed_job_id, redaction_mode),
        failed_session_id=(
            redact_str(failed_session_id, redaction_mode) if failed_session_id else None
        ),
        user_request=redact_str(user_request, redaction_mode),
        plan_summary=redact_str(plan_summary, redaction_mode),
        generated_code=redact_str(generated_code, redaction_mode),
        static_guard_result=_redact(guard, redaction_mode),
        stdout=redact_str(stdout, redaction_mode),
        stderr=redact_str(stderr, redaction_mode),
        error_trace=redact_str(error_trace, redaction_mode),
        input_dataset_references=tuple(
            redact_str(value, redaction_mode) for value in dataset_refs
        ),
        artifact_manifest=_redact(manifest, redaction_mode),
        output_state=_redact(output_state, redaction_mode),
        validation_result=_redact(validation, redaction_mode),
        environment_summary=_redact(environment, redaction_mode),
        redaction_status=redaction_mode,
        run_id=run_dir.name,
        artifact_id=_text_value(manifest, "artifact_id") or None,
        experiment_id=_text_value(manifest, "experiment_id") or None,
        feature_id=_text_value(manifest, "feature_id") or None,
        hypothesis_id=_text_value(manifest, "hypothesis_id") or None,
        pattern_id=_text_value(manifest, "pattern_id") or None,
    )
    store.save_bundle(bundle)
    store.emit(
        "REPAIR_BUNDLE_CREATED",
        correlation_id=bundle.correlation_id,
        repair_id=bundle.repair_id,
        run_id=bundle.run_id or "",
        detail="repair bundle created from failed research run",
        metadata={"failed_job_id": bundle.failed_job_id},
    )
    return bundle


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _read_json(path: Path) -> JsonObject:
    text = _read_text(path)
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _text_value(payload: dict, key: str) -> str:
    value = payload.get(key)
    return value.strip() if isinstance(value, str) else ""


def _first_text(events: tuple[dict, ...] | list[dict], key: str) -> str:
    for event in events:
        value = _text_value(event, key)
        if value:
            return value
    return ""


def _dataset_refs(
    input_references: JsonObject, manifest: JsonObject
) -> tuple[str, ...]:
    values = (
        input_references.get("datasets")
        or manifest.get("input_dataset_references")
        or []
    )
    if not isinstance(values, list):
        return ()
    return tuple(str(value) for value in values if isinstance(value, str) and value)


def _redact(payload: JsonObject, mode: str) -> JsonObject:
    return redact_dict(payload, mode)


def _is_failed_run(run_dir: Path) -> bool:
    if not run_dir.is_dir():
        return False
    errors = read_jsonl(run_dir / "errors.jsonl")
    commands = read_jsonl(run_dir / "commands.jsonl")
    return any(
        event.get("level") == "ERROR"
        or event.get("event_type") in {"COMMAND_FAILED", "EXCEPTION_CAPTURED"}
        for event in (*errors, *commands)
    )

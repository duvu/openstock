from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from vnalpha.closed_loop.errors import ClosedLoopPersistenceError
from vnalpha.closed_loop.models import JsonObject, now_iso
from vnalpha.closed_loop.paths import (
    resolve_component,
    resolve_file,
    validate_identifier,
)
from vnalpha.observability.redaction import redact_dict, redact_str, redaction_status


@dataclass(frozen=True, slots=True)
class EventInput:
    event_type: str
    correlation_id: str
    repair_id: str = ""
    artifact_id: str = ""
    run_id: str = ""
    status: str = "OK"
    detail: str = ""
    metadata: JsonObject | None = None


def emit_event(root: Path, event: EventInput) -> None:
    payload = {
        "event_id": uuid4().hex,
        "created_at": now_iso(),
        "event_type": redact_str(event.event_type),
        "correlation_id": redact_str(event.correlation_id),
        "repair_id": redact_str(event.repair_id),
        "artifact_id": redact_str(event.artifact_id),
        "run_id": redact_str(event.run_id),
        "status": redact_str(event.status),
        "detail": redact_str(event.detail),
        "redaction_status": redaction_status(),
        "metadata": redact_dict(event.metadata or {}),
    }
    if event.repair_id:
        path = (
            resolve_component(root, "bundles", event.repair_id, "repair_id")
            / "closed-loop.jsonl"
        )
    elif event.artifact_id:
        path = resolve_file(
            root, "closed-loop", event.artifact_id, ".jsonl", "artifact_id"
        )
    else:
        path = resolve_file(root, "closed-loop", "events", ".jsonl", "events")
    _append(path, payload)


def event_types(root: Path, identifier: str) -> list[str]:
    identifier = validate_identifier(identifier, "event identifier")
    paths = (
        resolve_component(root, "bundles", identifier, "event identifier")
        / "closed-loop.jsonl",
        resolve_file(root, "closed-loop", identifier, ".jsonl", "event identifier"),
    )
    return [
        str(record["event_type"])
        for path in paths
        for record in _read_lines(path)
        if "event_type" in record
    ]


def _append(path: Path, payload: JsonObject) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
    except OSError as exc:
        raise ClosedLoopPersistenceError(f"could not append {path}") from exc


def _read_lines(path: Path) -> list[JsonObject]:
    if not path.exists():
        return []
    try:
        return [
            payload
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and isinstance((payload := json.loads(line)), dict)
        ]
    except (OSError, json.JSONDecodeError) as exc:
        raise ClosedLoopPersistenceError(f"could not read {path}") from exc

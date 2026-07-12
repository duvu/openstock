from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from vnalpha.closed_loop.errors import (
    ClosedLoopNotFoundError,
    ClosedLoopPersistenceError,
)
from vnalpha.closed_loop.models import JsonObject

ModelT = TypeVar("ModelT", bound=BaseModel)


def write_model(path: Path, model: BaseModel) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(model.model_dump_json(indent=2), encoding="utf-8")
    except OSError as exc:
        raise ClosedLoopPersistenceError(f"could not write {path}") from exc


def write_json(path: Path, payload: JsonObject) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    except OSError as exc:
        raise ClosedLoopPersistenceError(f"could not write {path}") from exc


def append_json(path: Path, payload: JsonObject) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
    except OSError as exc:
        raise ClosedLoopPersistenceError(f"could not append {path}") from exc


def load_model(path: Path, model_type: type[ModelT]) -> ModelT:
    if not path.exists():
        raise ClosedLoopNotFoundError(f"closed-loop record not found: {path}")
    try:
        return model_type.model_validate_json(path.read_bytes())
    except (OSError, ValidationError, ValueError) as exc:
        raise ClosedLoopPersistenceError(f"could not load {path}") from exc


def read_json_lines(path: Path) -> list[JsonObject]:
    if not path.exists():
        return []
    try:
        values: list[JsonObject] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                payload = json.loads(line)
                if isinstance(payload, dict):
                    values.append(payload)
        return values
    except (OSError, json.JSONDecodeError) as exc:
        raise ClosedLoopPersistenceError(f"could not read {path}") from exc

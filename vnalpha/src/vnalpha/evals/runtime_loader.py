from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from vnalpha.evals.runtime_models import (
    RuntimeReplayCase,
    RuntimeReplayLoadError,
    RuntimeReplayValidationError,
)


def load_runtime_replay_case(path: Path) -> RuntimeReplayCase:
    try:
        document = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise RuntimeReplayLoadError(path=path, detail=str(error)) from error
    try:
        return RuntimeReplayCase.model_validate_json(document)
    except ValidationError as error:
        raise RuntimeReplayValidationError(path=path, detail=str(error)) from error

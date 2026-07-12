"""Best-effort JSONL append helper.

Never raises. On failure, writes diagnostic to stderr and returns silently.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Mapping, TypeVar

_RecordValue = TypeVar("_RecordValue")


def read_jsonl(path: Path) -> list[dict]:
    """Read all JSON lines from *path* and return as a list of dicts.

    Returns an empty list if the file does not exist or any line fails to parse.
    """
    if not path.exists():
        return []
    records: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    except Exception:  # noqa: BLE001
        pass
    return records


def append_jsonl(path: Path, record: Mapping[str, _RecordValue]) -> None:  # noqa: C901
    """Append *record* as one JSON line to *path*.

    - Creates parent directories if needed.
    - Never raises: any exception is swallowed after logging to stderr.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, default=str) + "\n"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line)
    except Exception as exc:  # noqa: BLE001
        try:
            sys.stderr.write(f"[observability] append_jsonl failed for {path}: {exc}\n")
        except Exception:  # noqa: BLE001
            pass

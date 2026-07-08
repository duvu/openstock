"""Best-effort JSONL append helper.

Never raises. On failure, writes diagnostic to stderr and returns silently.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def append_jsonl(path: Path, record: dict) -> None:  # noqa: C901
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

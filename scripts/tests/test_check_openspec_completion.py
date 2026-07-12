from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _module():
    path = Path(__file__).parents[1] / "check-openspec-completion.py"
    spec = importlib.util.spec_from_file_location("check_openspec_completion", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_change(tmp_path: Path, tasks: str, validation: str) -> Path:
    change = tmp_path / "change"
    change.mkdir()
    (change / "tasks.md").write_text(tasks, encoding="utf-8")
    (change / "validation.md").write_text(validation, encoding="utf-8")
    return change


def _validation(status: str = "Pass", command: str = "make repo-hygiene") -> str:
    return f"""# Validation

## Status
Phase gates: {status}

## Baseline

| UTC timestamp | Commit SHA | Phase/task | Command | Exit | Result summary | Evidence artifact |
|---|---|---|---|---:|---|---|
| 2026-07-12T00:00:00Z | abc123 | 1.1 | {command} | 0 | passed | local transcript |

## Phase 1 validation matrix

| Gate | Required evidence | Status |
|---|---|---|
| Gate | command | {status} |

## Final command matrix

```bash
{command}
```
"""


def test_complete_change_returns_zero(tmp_path: Path) -> None:
    module = _module()
    change = _write_change(
        tmp_path,
        "- [x] **1.1 Do the thing.**\n",
        _validation(),
    )
    result = module.verify_change(change)
    assert result.exit_code == 0


def test_unchecked_completion_ready_change_returns_one(tmp_path: Path) -> None:
    module = _module()
    (tmp_path.parent / "active-changes.yaml").write_text(
        "changes:\n  change:\n    status: ready\n", encoding="utf-8"
    )
    change = _write_change(
        tmp_path,
        "- [ ] **1.1 Do the thing.**\n",
        _validation(),
    )
    result = module.verify_change(change)
    assert result.exit_code == 1
    assert "completion-ready" in " ".join(result.messages)


def test_checked_task_with_pending_validation_returns_one(tmp_path: Path) -> None:
    module = _module()
    change = _write_change(
        tmp_path,
        "- [x] **1.1 Do the thing.**\n",
        _validation(status="Pending"),
    )
    result = module.verify_change(change)
    assert result.exit_code == 1
    assert "pending" in " ".join(result.messages)


def test_malformed_evidence_returns_two(tmp_path: Path) -> None:
    module = _module()
    validation = _validation().replace("2026-07-12T00:00:00Z", "not-a-timestamp")
    change = _write_change(tmp_path, "- [x] **1.1 Do the thing.**\n", validation)
    result = module.verify_change(change)
    assert result.exit_code == 2
    assert "timestamp" in " ".join(result.messages)


def test_deferred_task_requires_structured_record(tmp_path: Path) -> None:
    module = _module()
    validation = _validation() + "\n## Deferred work register\nTask ID: 1.1\n"
    change = _write_change(
        tmp_path,
        "- [ ] **1.1 Deferred task.** [deferred]\n",
        validation,
    )
    result = module.verify_change(change)
    assert result.exit_code == 2
    assert "Owner" in " ".join(result.messages)


def test_missing_required_command_evidence_returns_one(tmp_path: Path) -> None:
    module = _module()
    validation = _validation().replace(
        "```bash\nmake repo-hygiene\n```",
        "```bash\nmake lint-vnalpha\n```",
    )
    change = _write_change(tmp_path, "- [x] **1.1 Do the thing.**\n", validation)
    result = module.verify_change(change)
    assert result.exit_code == 1
    assert "required command" in " ".join(result.messages)


def test_archived_change_without_required_evidence_returns_one(tmp_path: Path) -> None:
    module = _module()
    archive = tmp_path / "archive"
    archive.mkdir()
    change = _write_change(archive, "- [x] **1.1 Do the thing.**\n", _validation())
    validation_path = change / "validation.md"
    validation_path.write_text(
        validation_path.read_text(encoding="utf-8").replace(
            "```bash\nmake repo-hygiene\n```",
            "```bash\nmake lint-vnalpha\n```",
        ),
        encoding="utf-8",
    )
    result = module.verify_change(change)
    assert result.exit_code == 1
    assert "required command" in " ".join(result.messages)

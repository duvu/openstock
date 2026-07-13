from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_FINAL_SHA = "a" * 40


def _module():
    path = Path(__file__).parents[1] / "check-openspec-completion.py"
    spec = importlib.util.spec_from_file_location("check_openspec_completion", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_change(tmp_path: Path, tasks: str, validation: str) -> Path:
    if not (tmp_path / ".git").exists():
        _ = subprocess.run(
            ("git", "init", "-q", str(tmp_path)), check=True, capture_output=True
        )
        _ = subprocess.run(
            ("git", "-C", str(tmp_path), "config", "user.email", "test@example.com"),
            check=True,
            capture_output=True,
        )
        _ = subprocess.run(
            ("git", "-C", str(tmp_path), "config", "user.name", "OpenSpec Test"),
            check=True,
            capture_output=True,
        )
        (tmp_path / "sentinel").write_text("fixture\n", encoding="utf-8")
        _ = subprocess.run(
            ("git", "-C", str(tmp_path), "add", "sentinel"),
            check=True,
            capture_output=True,
        )
        _ = subprocess.run(
            ("git", "-C", str(tmp_path), "commit", "-q", "-m", "fixture"),
            check=True,
            capture_output=True,
        )
    commit = subprocess.run(
        ("git", "-C", str(tmp_path), "rev-parse", "HEAD"),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    change = tmp_path / "change"
    change.mkdir()
    (change / "tasks.md").write_text(tasks, encoding="utf-8")
    (change / "validation.md").write_text(
        validation.replace(_FINAL_SHA, commit), encoding="utf-8"
    )
    return change


def _validation(status: str = "Pass", command: str = "make repo-hygiene") -> str:
    return f"""# Validation

## Status
Phase gates: {status}

## Baseline

| UTC timestamp | Commit SHA | Phase/task | Command | Exit | Result summary | Evidence artifact |
|---|---|---|---|---:|---|---|
| 2026-07-12T00:00:00Z | {_FINAL_SHA} | 1.1 | {command} | 0 | passed | local transcript |

## Phase 1 validation matrix

| Gate | Required evidence | Status |
|---|---|---|
| Gate | command | {status} |

## Final command matrix

```bash
{command}
```

Final implementation SHA: {_FINAL_SHA}
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


def test_complete_change_rejects_working_tree_required_command_evidence(
    tmp_path: Path,
) -> None:
    module = _module()
    validation = _validation().replace(
        f"| {_FINAL_SHA} | 1.1 |", f"| {_FINAL_SHA} + working tree | 1.1 |"
    )
    change = _write_change(tmp_path, "- [x] **1.1 Do the thing.**\n", validation)

    result = module.verify_change(change)

    assert result.exit_code == 1
    assert "exact final implementation SHA" in " ".join(result.messages)


def test_complete_change_rejects_abbreviated_final_sha(tmp_path: Path) -> None:
    module = _module()
    validation = _validation().replace(
        f"Final implementation SHA: {_FINAL_SHA}", "Final implementation SHA: abc123"
    )
    change = _write_change(tmp_path, "- [x] **1.1 Do the thing.**\n", validation)

    result = module.verify_change(change)

    assert result.exit_code == 1
    assert "Final implementation SHA" in " ".join(result.messages)


def test_complete_change_rejects_nonexistent_full_sha(tmp_path: Path) -> None:
    module = _module()
    validation = _validation().replace(_FINAL_SHA, "b" * 40)
    change = _write_change(tmp_path, "- [x] **1.1 Do the thing.**\n", validation)
    validation_path = change / "validation.md"
    validation_path.write_text(
        validation_path.read_text(encoding="utf-8").replace(
            subprocess.run(
                ("git", "-C", str(tmp_path), "rev-parse", "HEAD"),
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip(),
            "b" * 40,
        ),
        encoding="utf-8",
    )

    result = module.verify_change(change)

    assert result.exit_code == 1
    assert "does not name a commit" in " ".join(result.messages)


def test_complete_change_rejects_nonexistent_evidence_row_commit(
    tmp_path: Path,
) -> None:
    module = _module()
    validation = _validation().replace(
        "\n## Phase 1 validation matrix",
        f"\n| 2026-07-12T00:01:00Z | {'b' * 40} | 1.2 | manual review | 0 | passed | local transcript |\n\n## Phase 1 validation matrix",
    )
    change = _write_change(
        tmp_path,
        "- [x] **1.1 First task.**\n- [x] **1.2 Second task.**\n",
        validation,
    )

    result = module.verify_change(change)

    assert result.exit_code == 1
    assert "evidence commit does not name a commit" in " ".join(result.messages)


def test_required_command_must_match_exactly(tmp_path: Path) -> None:
    module = _module()
    validation = _validation().replace(
        "| make repo-hygiene | 0 |", "| make repo-hygiene --keep-going | 0 |"
    )
    change = _write_change(tmp_path, "- [x] **1.1 Do the thing.**\n", validation)

    result = module.verify_change(change)

    assert result.exit_code == 1
    assert "required command" in " ".join(result.messages)


def test_plain_task_format_is_supported(tmp_path: Path) -> None:
    module = _module()
    change = _write_change(
        tmp_path,
        "- [x] 1.1 Do the thing.\n",
        _validation(),
    )

    assert module.verify_change(change).exit_code == 0


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


def test_checked_task_without_matching_evidence_returns_one(tmp_path: Path) -> None:
    module = _module()
    change = _write_change(
        tmp_path,
        "- [x] **1.1 First task.**\n- [x] **1.2 Second task.**\n",
        _validation(),
    )

    result = module.verify_change(change)

    assert result.exit_code == 1
    assert "checked tasks without evidence: 1.2" in " ".join(result.messages)


def test_evidence_range_covers_each_checked_task(tmp_path: Path) -> None:
    module = _module()
    change = _write_change(
        tmp_path,
        "- [x] **1.1 First task.**\n- [x] **1.2 Second task.**\n",
        _validation().replace("| 1.1 |", "| 1.1–1.2 |"),
    )

    result = module.verify_change(change)

    assert result.exit_code == 0


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

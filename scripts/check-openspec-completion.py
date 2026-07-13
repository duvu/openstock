#!/usr/bin/env python3
"""Check OpenSpec task and validation consistency."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


TASK_RE = re.compile(r"^\s*-\s+\[([ xX])\]\s+(?:\*\*)?([0-9]+(?:\.[0-9A-Z]+)?)\b")
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
SIBLING_RE = re.compile(r"^  \S.*:$")
REQUIRED_DEFER_FIELDS = (
    "Task ID",
    "Reason",
    "Owner",
    "Dependency",
    "Risk accepted until",
    "Approval reference",
)


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    checked: bool
    deferred: bool


@dataclass(frozen=True)
class EvidenceRow:
    timestamp: str
    commit: str
    task: str
    command: str
    exit_code: str
    summary: str
    artifact: str


@dataclass(frozen=True)
class VerificationResult:
    exit_code: int
    messages: tuple[str, ...]


def _tasks(text: str) -> tuple[TaskRecord, ...]:
    records: list[TaskRecord] = []
    for line in text.splitlines():
        match = TASK_RE.match(line)
        if match is None:
            continue
        records.append(
            TaskRecord(
                task_id=match.group(2),
                checked=match.group(1).lower() == "x",
                deferred=bool(
                    re.search(r"\[(?:defer|deferred)\]", line, re.IGNORECASE)
                ),
            )
        )
    return tuple(records)


def _evidence_rows(text: str) -> tuple[tuple[EvidenceRow, ...], tuple[str, ...]]:
    lines = text.splitlines()
    header_index = next(
        (
            index
            for index, line in enumerate(lines)
            if line.startswith("| UTC timestamp")
        ),
        None,
    )
    if header_index is None:
        return (), ("validation.md is missing the evidence table header",)

    rows: list[EvidenceRow] = []
    errors: list[str] = []
    for line in lines[header_index + 2 :]:
        if line.startswith("## "):
            break
        if not line.startswith("|"):
            continue
        parts = tuple(part.strip() for part in line.strip().strip("|").split("|"))
        if len(parts) != 7 or parts[0].lower() == "pending":
            continue
        row = EvidenceRow(*parts)
        if not TIMESTAMP_RE.fullmatch(row.timestamp):
            errors.append(f"invalid evidence timestamp: {row.timestamp}")
        if not row.commit or row.commit.lower() == "pending":
            errors.append(f"invalid evidence commit for {row.task}")
        if not row.command or row.command.lower() == "pending":
            errors.append(f"invalid evidence command for {row.task}")
        if row.exit_code not in {"0", "1", "2"}:
            errors.append(f"invalid evidence exit code for {row.task}: {row.exit_code}")
        if not row.summary or row.summary.lower() == "not executed":
            errors.append(f"invalid evidence summary for {row.task}")
        if not row.artifact or row.artifact == "—":
            errors.append(f"invalid evidence artifact for {row.task}")
        rows.append(row)
    return tuple(rows), tuple(errors)


def _required_commands(text: str) -> tuple[str, ...]:
    lines = text.splitlines()
    try:
        start = next(index for index, line in enumerate(lines) if line == "```bash")
    except StopIteration:
        return ()
    commands: list[str] = []
    current = ""
    for line in lines[start + 1 :]:
        value = line.strip()
        if value == "```":
            break
        if not value:
            continue
        if current:
            current = f"{current} {value.rstrip(chr(92)).strip()}"
        else:
            current = value.rstrip(chr(92)).strip()
        if not value.endswith(chr(92)):
            commands.append(" ".join(current.split()))
            current = ""
    if current:
        commands.append(" ".join(current.split()))
    return tuple(commands)


def _evidence_task_ids(value: str) -> frozenset[str]:
    task_ids: set[str] = set()
    for token in re.split(r"\s*,\s*", value):
        normalized = token.strip().replace("-", "–")
        range_match = re.fullmatch(
            r"([0-9]+)\.([0-9]+)\s*–\s*(?:(\1)\.)?([0-9]+)",
            normalized,
        )
        if range_match is not None:
            section = range_match.group(1)
            start = int(range_match.group(2))
            end = int(range_match.group(4))
            if start <= end:
                task_ids.update(f"{section}.{index}" for index in range(start, end + 1))
            continue
        task_ids.update(re.findall(r"\b[0-9]+\.(?:[0-9]+|[A-Z][0-9]+)\b", normalized))
    return frozenset(task_ids)


def _pending_validation(text: str) -> bool:
    relevant = text.split("## Evidence row format", 1)[0]
    relevant += text.split("## Phase 1 validation matrix", 1)[-1]
    return bool(
        re.search(r"\|[^|]+\|\s*Pending\s*\|", relevant, re.IGNORECASE)
        or re.search(
            r"(?:Phase gates|Ready to archive):\s*pending", relevant, re.IGNORECASE
        )
    )


def _registry_status(change_dir: Path) -> str | None:
    registry = change_dir.parents[1] / "active-changes.yaml"
    if not registry.is_file():
        return None
    lines = registry.read_text(encoding="utf-8").splitlines()
    marker = f"  {change_dir.name}:"
    inside = False
    for line in lines:
        if line == marker:
            inside = True
            continue
        if inside and SIBLING_RE.match(line):
            break
        if inside:
            match = re.match(r"\s+status:\s*(\S+)", line)
            if match:
                return match.group(1).lower()
    return None


def _defer_errors(text: str, tasks: tuple[TaskRecord, ...]) -> tuple[str, ...]:
    if not any(task.deferred for task in tasks):
        return ()
    register = text.split("## Deferred work register", 1)[-1]
    if register.startswith("\nNo tasks are deferred"):
        return ("deferred task exists but the deferred work register is empty",)
    errors = []
    for field in REQUIRED_DEFER_FIELDS:
        if re.search(rf"^\s*{re.escape(field)}:\s*\S", register, re.MULTILINE) is None:
            errors.append(f"deferred work register is missing {field}")
    return tuple(errors)


def verify_change(change_dir: Path) -> VerificationResult:
    tasks_path = change_dir / "tasks.md"
    validation_path = change_dir / "validation.md"
    if not tasks_path.is_file() or not validation_path.is_file():
        return VerificationResult(2, ("change requires tasks.md and validation.md",))

    tasks_text = tasks_path.read_text(encoding="utf-8")
    validation_text = validation_path.read_text(encoding="utf-8")
    tasks = _tasks(tasks_text)
    if not tasks:
        return VerificationResult(2, ("tasks.md contains no parseable task records",))
    rows, format_errors = _evidence_rows(validation_text)
    if format_errors:
        return VerificationResult(2, format_errors)

    messages: list[str] = []
    unchecked = tuple(
        task.task_id for task in tasks if not task.checked and not task.deferred
    )
    if unchecked:
        status = _registry_status(change_dir)
        qualifier = "completion-ready " if status in {"ready", "complete"} else ""
        messages.append(
            f"{qualifier}change has unchecked tasks: {', '.join(unchecked)}"
        )
    if _pending_validation(validation_text):
        messages.append(
            "validation.md still contains pending phase or completion gates"
        )

    evidenced_task_ids = frozenset(
        task_id
        for row in rows
        if row.exit_code == "0"
        for task_id in _evidence_task_ids(row.task)
    )
    missing_evidence = tuple(
        task.task_id
        for task in tasks
        if task.checked and task.task_id not in evidenced_task_ids
    )
    if missing_evidence:
        messages.append(
            "checked tasks without evidence: " + ", ".join(missing_evidence)
        )

    commands = _required_commands(validation_text)
    evidence_commands = tuple(row.command for row in rows if row.exit_code == "0")
    for command in commands:
        if not any(command in evidence for evidence in evidence_commands):
            messages.append(
                f"required command has no successful evidence row: {command}"
            )
    defer_errors = _defer_errors(tasks_text, tasks)
    if defer_errors:
        return VerificationResult(2, defer_errors)
    if messages:
        return VerificationResult(1, tuple(messages))
    if change_dir.parent.name == "archive" and any(not task.checked for task in tasks):
        return VerificationResult(1, ("archived change contains unchecked tasks",))
    return VerificationResult(
        0, (f"verified {len(tasks)} tasks and {len(rows)} evidence rows",)
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("change", type=Path)
    args = parser.parse_args(argv)
    result = verify_change(args.change)
    label = {0: "PASS", 1: "INCOMPLETE", 2: "INVALID"}[result.exit_code]
    print(f"{label}: {args.change}")
    for message in result.messages:
        print(f"- {message}")
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())

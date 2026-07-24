#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

# ─── How to run ───
# 1. Install uv (if not installed):
#      curl -LsSf https://astral.sh/uv/install.sh | sh
# 2. Run directly:
#      uv run scripts/openstock-log-triage.py [--path LOG] [--github-run RUN]
# 3. Or make executable and run:
#      chmod +x scripts/openstock-log-triage.py && ./scripts/openstock-log-triage.py
# ──────────────────
from __future__ import annotations

import argparse
import json
import os
import re
import selectors
import signal
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Sequence

MAX_TAIL_BYTES = 256 * 1024
MAX_DISCOVERED_RUNS = 5
MAX_EVIDENCE_CHARS = 500
DESCRIPTION = "Read-only, bounded triage for local OpenStock and failed CI logs."
SENSITIVE_VALUE = re.compile(
    r"(?i)(?<![A-Za-z0-9_-])"
    r"(?P<quote>[\"']?)(?P<key>(?:[A-Za-z0-9]+[_-])*(?:authorization|api[_-]?key|apikey|"
    r"access[_-]?tokens?|accesstokens?|refresh[_-]?tokens?|refreshtokens?|"
    r"client[_-]?secret|clientsecret|tokens?|passwords?|secrets?|private[_-]?key|"
    r"privatekey|cookies?|signatures?))"
    r"(?P=quote)(?![A-Za-z0-9_-])\s*[:=]\s*"
    r"(\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|[^\s,;&]+)"
)
BEARER_VALUE = re.compile(r"(?i)\b(bearer|basic)\s+[^\s,;&]+")
URL_CREDENTIALS = re.compile(r"(?i)([A-Za-z][A-Za-z0-9+.-]*://)[^/@\s]+@")
LOG_PREFIX = re.compile(
    r"^(?:\[[^\]]+\]\s*)?(?:\d{4}[-/]\d{2}[-/]\d{2}[ T]"
    r"\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z)?[:\s]+)?"
)


class FindingSeverity(str, Enum):
    ERROR = "ERROR"
    WARN = "WARN"


class FindingCategory(str, Enum):
    AUTHENTICATION = "AUTHENTICATION"
    CI_STATIC = "CI_STATIC"
    INPUT = "INPUT"
    NETWORK = "NETWORK"
    RUNTIME = "RUNTIME"
    TEST = "TEST"


@dataclass(frozen=True, slots=True)
class Finding:
    severity: FindingSeverity
    category: FindingCategory
    evidence: str
    source: str
    locations: tuple[str, ...]
    occurrences: int
    next_step: str


def arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--path", action="append", type=Path, default=[])
    parser.add_argument("--github-run", type=_run_id)
    parser.add_argument("--max-lines", type=_positive_int, default=200)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--fail-on-findings", action="store_true")
    return parser.parse_args(argv)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _run_id(value: str) -> int:
    if not value.isdecimal() or int(value) < 1:
        raise argparse.ArgumentTypeError("must be a positive numeric run ID")
    return int(value)


def sanitize(value: str) -> str:
    redacted = BEARER_VALUE.sub(lambda match: f"{match.group(1)} [REDACTED]", value)
    redacted = SENSITIVE_VALUE.sub(r"\g<key>=[REDACTED]", redacted)
    redacted = URL_CREDENTIALS.sub(r"\1[REDACTED]@", redacted)
    normalized = " ".join(redacted.split())
    return normalized[:MAX_EVIDENCE_CHARS]


def discover_paths(repo_root: Path) -> tuple[Path, ...]:
    paths = sorted((repo_root / "ya-router" / "logs").glob("*.log"))
    log_root = Path(
        os.environ.get("VNALPHA_LOG_ROOT", Path.home() / ".local/state/openstock/logs")
    )
    run_logs = log_root / "runs"
    paths.extend(
        sorted(
            run_logs.glob("*/errors.jsonl"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )[:MAX_DISCOVERED_RUNS]
    )
    return tuple(paths)


def tail_lines(path: Path, max_lines: int) -> tuple[str, ...]:
    with path.open("rb") as source:
        source.seek(0, 2)
        start = max(0, source.tell() - MAX_TAIL_BYTES)
        source.seek(start)
        text = source.read().decode("utf-8", "replace")
    lines = text.splitlines()
    if start:
        lines = lines[1:]
    return tuple(lines[-max_lines:])


def analyze_lines(source: str, lines: Sequence[str]) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    consistency_failure = False
    for number, raw_line in enumerate(lines, start=1):
        text, severity = _record_text(raw_line)
        continuation = consistency_failure and raw_line.lstrip().startswith("- ")
        consistency_failure = "repository consistency check failed" in text.casefold()
        if (
            not text
            or _is_noise(text)
            or not (_is_signal(text, severity) or continuation)
        ):
            continue
        if continuation:
            severity = FindingSeverity.ERROR
        category = _category(text)
        findings.append(
            Finding(
                severity=severity,
                category=category,
                evidence=sanitize(LOG_PREFIX.sub("", text)),
                source=sanitize(source),
                locations=(f"tail:{number}",),
                occurrences=1,
                next_step=_next_step(category),
            )
        )
    return tuple(findings)


def _record_text(raw_line: str) -> tuple[str, FindingSeverity]:
    try:
        record = json.loads(raw_line)
    except json.JSONDecodeError:
        return raw_line, _severity(raw_line)
    if not isinstance(record, dict):
        return raw_line, _severity(raw_line)
    values = [
        str(record[key])
        for key in (
            "event_type",
            "summary",
            "error_type",
            "error_message",
            "likely_cause",
            "suggested_next_step",
        )
        if record.get(key)
    ]
    text = ". ".join(values) or raw_line
    level = str(record.get("level", ""))
    return text, _severity(level or text)


def _severity(text: str) -> FindingSeverity:
    lowered = text.casefold()
    if any(marker in lowered for marker in ("warning", "warn", "degraded")):
        if not any(marker in lowered for marker in ("error", "failed", "fatal")):
            return FindingSeverity.WARN
    return FindingSeverity.ERROR


def _is_signal(text: str, severity: FindingSeverity) -> bool:
    markers = (
        "error",
        "exception",
        "traceback",
        "failed",
        "fatal",
        "warning",
        "degraded",
        "unavailable",
        "would reformat",
        "f821",
    )
    return severity is FindingSeverity.WARN or any(
        marker in text.casefold() for marker in markers
    )


def _is_noise(text: str) -> bool:
    lowered = text.casefold()
    return any(
        marker in lowered
        for marker in (
            "deprecationwarning",
            "node.js 20 is deprecated",
            "hint: to use in all of your repositories",
            "process completed with exit code",
            "required merge gate",
        )
    )


def _category(text: str) -> FindingCategory:
    lowered = text.casefold()
    if any(marker in lowered for marker in ("auth", "credential", "login", "token")):
        return FindingCategory.AUTHENTICATION
    if any(
        marker in lowered
        for marker in (
            "ruff",
            "would reformat",
            "f821",
            "make: ***",
            "found ",
            "repository consistency",
            "test suite manifest",
            "invalid `# noqa`",
        )
    ):
        return FindingCategory.CI_STATIC
    if any(marker in lowered for marker in ("pytest", "assertionerror", " failed")):
        return FindingCategory.TEST
    if any(
        marker in lowered
        for marker in ("timeout", "connection", "network", "transport")
    ):
        return FindingCategory.NETWORK
    return FindingCategory.RUNTIME


def _next_step(category: FindingCategory) -> str:
    match category:
        case FindingCategory.AUTHENTICATION:
            return "Reconnect the affected provider account, then retry its request."
        case FindingCategory.CI_STATIC:
            return "Run make lint-vnalpha to reproduce the repository static check."
        case FindingCategory.INPUT:
            return "Verify the selected --path or --github-run value and retry."
        case FindingCategory.NETWORK:
            return "Check the affected local service health before retrying."
        case FindingCategory.RUNTIME:
            return "Inspect the cited evidence and reproduce the owning operation."
        case FindingCategory.TEST:
            return "Run the owning focused test with make test-loop."
        case unreachable:
            raise AssertionError(f"Unhandled finding category: {unreachable}")


def github_lines(run_id: int, max_lines: int) -> tuple[tuple[str, ...], Finding | None]:
    source = f"github-actions:{run_id}"
    try:
        result = _bounded_command(
            ("gh", "run", "view", str(run_id), "--log-failed"),
        )
    except OSError as exc:
        return (), _input_finding(source, f"gh failed-log retrieval unavailable: {exc}")
    if result.timed_out:
        return (), _input_finding(source, "gh failed-log retrieval timed out")
    if result.returncode:
        return (), _input_finding(
            source, result.output or "gh failed-log retrieval failed"
        )
    return tuple(result.output.splitlines()[-max_lines:]), None


@dataclass(frozen=True, slots=True)
class _BoundedCommandResult:
    returncode: int
    output: str
    timed_out: bool


def _bounded_command(command: tuple[str, ...]) -> _BoundedCommandResult:
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    if process.stdout is None:
        raise OSError("gh output pipe was not created")
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    output = bytearray()
    deadline = time.monotonic() + 30
    timed_out = False
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                _kill_process_group(process)
                selector.unregister(process.stdout)
                process.stdout.close()
                break
            for key, _ in selector.select(remaining):
                chunk = os.read(key.fileobj.fileno(), 8192)
                if not chunk:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
                    continue
                output.extend(chunk)
                if len(output) > MAX_TAIL_BYTES:
                    del output[:-MAX_TAIL_BYTES]
    finally:
        selector.close()
    if process.poll() is None:
        try:
            process.wait(timeout=max(0.0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_process_group(process)
            process.wait()
    return _BoundedCommandResult(
        returncode=process.returncode,
        output=bytes(output).decode("utf-8", "replace"),
        timed_out=timed_out,
    )


def _kill_process_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _input_finding(source: str, evidence: str) -> Finding:
    return Finding(
        severity=FindingSeverity.ERROR,
        category=FindingCategory.INPUT,
        evidence=sanitize(evidence),
        source=sanitize(source),
        locations=(),
        occurrences=1,
        next_step=_next_step(FindingCategory.INPUT),
    )


def deduplicate(findings: Sequence[Finding]) -> tuple[Finding, ...]:
    unique: dict[tuple[FindingSeverity, FindingCategory, str, str], Finding] = {}
    for finding in findings:
        key = (finding.severity, finding.category, finding.evidence, finding.source)
        previous = unique.get(key)
        if previous is None:
            unique[key] = finding
            continue
        unique[key] = replace(
            previous,
            locations=(previous.locations + finding.locations)[:5],
            occurrences=previous.occurrences + finding.occurrences,
        )
    return tuple(
        sorted(
            unique.values(),
            key=lambda finding: (
                finding.severity.value,
                finding.category.value,
                finding.source,
                finding.evidence,
            ),
        )
    )


def render_markdown(sources: Sequence[str], findings: Sequence[Finding]) -> str:
    lines = ["# OpenStock log triage", "", f"Sources analyzed: {len(sources)}"]
    if not findings:
        return "\n".join(lines + ["", "No matching warnings or errors found."])
    lines.extend(["", "## Findings"])
    for finding in findings:
        location = ", ".join(finding.locations) or "source"
        lines.extend(
            [
                "",
                f"- [{finding.severity.value}] {finding.category.value} "
                f"({finding.source}, {location}; occurrences={finding.occurrences})",
                f"  Evidence: {finding.evidence}",
                f"  Next: {finding.next_step}",
            ]
        )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = arguments(sys.argv[1:] if argv is None else argv)
    selected_paths = tuple(args.path) or discover_paths(Path.cwd())
    findings: list[Finding] = []
    sources: list[str] = []
    for path in selected_paths:
        source = str(path)
        try:
            lines = tail_lines(path, args.max_lines)
        except OSError as exc:
            findings.append(_input_finding(source, f"cannot read selected path: {exc}"))
            continue
        sources.append(source)
        findings.extend(analyze_lines(source, lines))
    if args.github_run is not None:
        source = f"github-actions:{args.github_run}"
        lines, input_finding = github_lines(args.github_run, args.max_lines)
        if input_finding is not None:
            findings.append(input_finding)
        else:
            sources.append(source)
            findings.extend(analyze_lines(source, lines))
    normalized = deduplicate(findings)
    if args.as_json:
        print(
            json.dumps(
                {
                    "sources": [sanitize(source) for source in sources],
                    "findings": [asdict(finding) for finding in normalized],
                },
                indent=2,
                default=lambda value: value.value if isinstance(value, Enum) else value,
            )
        )
    else:
        print(render_markdown(sources, normalized))
    has_error = any(finding.severity is FindingSeverity.ERROR for finding in normalized)
    return 1 if args.fail_on_findings and has_error else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Inventory DuckDB/SQLite coupling for the PostgreSQL migration program."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

SCHEMA_VERSION = 1
MAX_EVIDENCE_CHARS = 240
MAX_TEXT_FILE_BYTES = 2_000_000

CLASSIFICATIONS = frozenset(
    {
        "portable SQL",
        "adapter-only change",
        "query rewrite",
        "schema redesign",
        "behavior/invariant redesign",
    }
)

SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "site-packages",
    }
)
SKIP_PREFIXES = (
    "openspec/changes/archive/",
    "openspec/changes/postgresql-authoritative-storage/",
)
SKIP_FILES = frozenset(
    {
        "scripts/postgresql_storage_inventory.py",
        "scripts/tests/test_postgresql_storage_inventory.py",
    }
)


@dataclass(frozen=True, slots=True)
class PatternRule:
    kind: str
    expression: re.Pattern[str]
    description: str


@dataclass(frozen=True, slots=True)
class InventoryFinding:
    path: str
    line: int
    kind: str
    classification: str
    owner_issue: int
    domain: str
    evidence: str


PATTERNS: tuple[PatternRule, ...] = (
    PatternRule(
        "duckdb_api",
        re.compile(
            r"(?:^|\s)(?:import\s+duckdb\b|from\s+duckdb\b|"
            r"DuckDBPyConnection\b|duckdb\.connect\s*\()"
        ),
        "DuckDB imports, driver types, or connection creation",
    ),
    PatternRule(
        "sqlite_api",
        re.compile(
            r"(?:^|\s)(?:import\s+sqlite3\b|from\s+sqlite3\b|"
            r"sqlite3\.connect\s*\(|PRAGMA\s+(?:journal_mode|busy_timeout|"
            r"foreign_keys|synchronous|integrity_check|wal_checkpoint)\b)",
            re.IGNORECASE,
        ),
        "SQLite imports, connections, or runtime pragmas",
    ),
    PatternRule(
        "direct_sql",
        re.compile(r"\.(?:execute|executemany|sql)\s*\("),
        "Direct SQL execution call site",
    ),
    PatternRule(
        "schema_ddl",
        re.compile(
            r"\b(?:CREATE\s+(?:TABLE|INDEX|SCHEMA|VIEW)|ALTER\s+TABLE|"
            r"DROP\s+(?:TABLE|INDEX|VIEW)|COMMENT\s+ON)\b",
            re.IGNORECASE,
        ),
        "DDL or implicit schema migration",
    ),
    PatternRule(
        "duckdb_specific_sql",
        re.compile(
            r"\b(?:QUALIFY|PIVOT|UNPIVOT|read_parquet|read_csv_auto|"
            r"information_schema\.columns|duckdb_|EXPORT\s+DATABASE|"
            r"IMPORT\s+DATABASE)\b",
            re.IGNORECASE,
        ),
        "DuckDB-specific SQL, catalog, or table function",
    ),
    PatternRule(
        "file_database_path",
        re.compile(
            r"(?:warehouse\.duckdb|provisioning\.sqlite3|"
            r"VNALPHA_WAREHOUSE_PATH|VNALPHA_PROVISIONING_QUEUE_PATH|"
            r"OPENSTOCK_WAREHOUSE_DIR)"
        ),
        "File-database path, environment variable, or mounted-volume assumption",
    ),
    PatternRule(
        "file_lock",
        re.compile(r"(?:\bfcntl\b|\bflock\b|LOCK_EX|LOCK_UN|\.vnalpha-locks)"),
        "Filesystem lock or single-writer coordination",
    ),
    PatternRule(
        "in_memory_database",
        re.compile(
            r"(?:[\"']?:memory:[\"']?|TemporaryDirectory|"
            r"tmp_path.*(?:duckdb|sqlite))"
        ),
        "In-memory or temporary file-database test fixture",
    ),
    PatternRule(
        "backup_or_volume",
        re.compile(
            r"(?:backup.*(?:duckdb|sqlite|warehouse|queue)|"
            r"restore.*(?:duckdb|sqlite|warehouse|queue)|"
            r"warehouse.*volume|volume.*warehouse)",
            re.IGNORECASE,
        ),
        "Backup, restore, or volume ownership tied to file databases",
    ),
)

REQUIRED_KINDS = frozenset(
    {
        "duckdb_api",
        "sqlite_api",
        "direct_sql",
        "schema_ddl",
        "file_database_path",
        "file_lock",
        "in_memory_database",
    }
)


def _relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _should_skip(path: Path, root: Path) -> bool:
    relative = _relative_path(path, root)
    if relative in SKIP_FILES or relative.startswith(SKIP_PREFIXES):
        return True
    return any(part in SKIP_DIR_NAMES for part in path.relative_to(root).parts)


def _candidate_paths(root: Path) -> tuple[str, tuple[Path, ...]]:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            check=False,
            capture_output=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        result = None
    if result is not None and result.returncode == 0:
        tracked = tuple(
            root / value.decode("utf-8", errors="surrogateescape")
            for value in result.stdout.split(b"\0")
            if value
        )
        return "git tracked files", tuple(sorted(tracked))
    return "bounded filesystem fallback", tuple(sorted(root.rglob("*")))


def _iter_text_files(root: Path) -> tuple[str, tuple[Path, ...]]:
    source, candidates = _candidate_paths(root)
    text_files: list[Path] = []
    for path in candidates:
        if path.is_symlink() or not path.is_file() or _should_skip(path, root):
            continue
        try:
            if path.stat().st_size > MAX_TEXT_FILE_BYTES:
                continue
            path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        text_files.append(path)
    return source, tuple(text_files)


def _domain_and_owner(path: str, kind: str) -> tuple[str, int]:
    if path.startswith("vnalpha/src/vnalpha/provisioning_queue/"):
        return "queue", 395
    if path.startswith("vnalpha/src/vnalpha/warehouse/"):
        if (
            kind in {"schema_ddl", "duckdb_specific_sql"}
            or "schema" in path
            or "migration" in path
        ):
            return "schema", 393
        if path.endswith(("connection.py", "transaction.py", "write_coordinator.py")):
            return "runtime", 392
        return "repositories", 394
    if path == "vnalpha/src/vnalpha/core/config.py":
        return "runtime", 392
    if path.startswith("vnalpha/src/vnalpha/"):
        return "repositories", 394
    if path.startswith("vnalpha/tests/"):
        return "tests", 397
    if path.startswith("scripts/"):
        return "migration", 396
    if path.startswith("packaging/") or path in {
        "docker-compose.yml",
        ".env.example",
        "Makefile",
    }:
        return "operations", 399
    if path.startswith("openspec/") or "/docs/" in path or path.endswith("README.md"):
        return "architecture", 391
    if path.startswith("vnstock/"):
        return "provider-boundary", 391
    return "repository-policy", 391


def _classification(path: str, kind: str, domain: str) -> str:
    if domain == "queue":
        return "behavior/invariant redesign"
    if domain == "schema":
        return "schema redesign"
    if domain == "runtime":
        return (
            "behavior/invariant redesign"
            if kind == "file_lock"
            else "adapter-only change"
        )
    if domain == "repositories":
        return (
            "query rewrite"
            if kind in {"direct_sql", "duckdb_specific_sql", "schema_ddl"}
            else "adapter-only change"
        )
    if domain == "tests":
        return "behavior/invariant redesign"
    if domain == "migration":
        return (
            "query rewrite"
            if kind in {"direct_sql", "duckdb_specific_sql", "schema_ddl"}
            else "behavior/invariant redesign"
        )
    if domain == "operations":
        return "adapter-only change"
    if domain in {"architecture", "provider-boundary", "repository-policy"}:
        return "adapter-only change"
    return "portable SQL"


def _safe_evidence(line: str) -> str:
    compact = " ".join(line.strip().split())
    compact = re.sub(
        r"(?i)([a-z][a-z0-9+.-]*://[^\s/:@]+:)[^@\s/]+(@)",
        r"\1[REDACTED]\2",
        compact,
    )
    compact = re.sub(
        r"(?i)(authorization\s*[:=]\s*(?:bearer|basic)\s+)[^\s,;]+",
        r"\1[REDACTED]",
        compact,
    )
    secret_pattern = (
        r"(?ix)(\b(?:password|passwd|secret|token|api[_-]?key|access[_-]?key|"
        r"private[_-]?key)\b\s*[:=]\s*)"
        r"(?:[\"'][^\"']*[\"']|[^\s,;]+)"
    )
    compact = re.sub(secret_pattern, r"\1[REDACTED]", compact)
    return compact[:MAX_EVIDENCE_CHARS]


def scan_repository(root: Path) -> dict[str, object]:
    root = root.resolve()
    findings: list[InventoryFinding] = []
    scan_source, text_files = _iter_text_files(root)
    scanned_files = 0
    for path in text_files:
        scanned_files += 1
        relative = _relative_path(path, root)
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for rule in PATTERNS:
                if rule.expression.search(line) is None:
                    continue
                domain, owner_issue = _domain_and_owner(relative, rule.kind)
                findings.append(
                    InventoryFinding(
                        path=relative,
                        line=line_number,
                        kind=rule.kind,
                        classification=_classification(relative, rule.kind, domain),
                        owner_issue=owner_issue,
                        domain=domain,
                        evidence=_safe_evidence(line),
                    )
                )

    findings.sort(key=lambda item: (item.path, item.line, item.kind))
    by_kind = Counter(item.kind for item in findings)
    by_classification = Counter(item.classification for item in findings)
    by_owner = Counter(str(item.owner_issue) for item in findings)
    files_with_findings = {item.path for item in findings}
    return {
        "schema_version": SCHEMA_VERSION,
        "root": ".",
        "scan_policy": {
            "source": scan_source,
            "max_text_file_bytes": MAX_TEXT_FILE_BYTES,
            "skipped_directories": sorted(SKIP_DIR_NAMES),
            "skipped_prefixes": list(SKIP_PREFIXES),
            "patterns": [
                {"kind": rule.kind, "description": rule.description}
                for rule in PATTERNS
            ],
        },
        "summary": {
            "scanned_files": scanned_files,
            "files_with_findings": len(files_with_findings),
            "findings": len(findings),
            "by_kind": dict(sorted(by_kind.items())),
            "by_classification": dict(sorted(by_classification.items())),
            "by_owner_issue": dict(sorted(by_owner.items())),
        },
        "findings": [asdict(item) for item in findings],
    }


def validate_report(report: dict[str, object]) -> tuple[str, ...]:
    errors: list[str] = []
    if report.get("schema_version") != SCHEMA_VERSION:
        errors.append("unsupported inventory schema version")
    raw_findings = report.get("findings")
    if not isinstance(raw_findings, list) or not raw_findings:
        return (*errors, "storage inventory contains no findings")

    seen: set[tuple[object, object, object]] = set()
    found_kinds: set[str] = set()
    for index, finding in enumerate(raw_findings):
        if not isinstance(finding, dict):
            errors.append(f"finding {index} is not an object")
            continue
        key = (finding.get("path"), finding.get("line"), finding.get("kind"))
        if key in seen:
            errors.append(f"duplicate finding: {key}")
        seen.add(key)
        kind = finding.get("kind")
        if isinstance(kind, str):
            found_kinds.add(kind)
        classification = finding.get("classification")
        if classification not in CLASSIFICATIONS:
            errors.append(
                f"finding {index} has invalid classification {classification!r}"
            )
        owner_issue = finding.get("owner_issue")
        if not isinstance(owner_issue, int) or not 391 <= owner_issue <= 400:
            errors.append(f"finding {index} has invalid owner issue {owner_issue!r}")
        path = finding.get("path")
        if not isinstance(path, str) or path.startswith(("/", "../")):
            errors.append(f"finding {index} has unsafe path {path!r}")
        evidence = finding.get("evidence")
        if not isinstance(evidence, str) or len(evidence) > MAX_EVIDENCE_CHARS:
            errors.append(f"finding {index} has invalid evidence")

    missing_kinds = sorted(REQUIRED_KINDS - found_kinds)
    if missing_kinds:
        errors.append(
            "inventory is missing required coupling kinds: "
            + ", ".join(missing_kinds)
        )
    return tuple(errors)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root to scan",
    )
    parser.add_argument(
        "--json", action="store_true", help="print the full JSON report"
    )
    parser.add_argument("--output", type=Path, help="write the full JSON report")
    parser.add_argument(
        "--check", action="store_true", help="fail on an incomplete inventory"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    report = scan_repository(args.root)
    errors = validate_report(report)
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    if args.json:
        sys.stdout.write(payload)
    else:
        summary = report["summary"]
        assert isinstance(summary, dict)
        print(
            "PostgreSQL storage inventory: "
            f"{summary['findings']} findings across "
            f"{summary['files_with_findings']} files "
            f"({summary['scanned_files']} text files scanned)."
        )
    if errors:
        for error in errors:
            print(f"storage inventory error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

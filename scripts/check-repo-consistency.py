#!/usr/bin/env python3
"""Fail when repository documentation and runtime contracts drift apart."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_WAREHOUSE = "/var/lib/openstock/warehouse/warehouse.duckdb"


class ConsistencyError(RuntimeError):
    """Raised when one or more repository invariants are violated."""


def _read(relative_path: str) -> str:
    path = ROOT / relative_path
    if not path.is_file():
        raise ConsistencyError(f"missing required file: {relative_path}")
    return path.read_text(encoding="utf-8")


def _require(errors: list[str], path: str, *needles: str) -> None:
    text = _read(path)
    for needle in needles:
        if needle not in text:
            errors.append(f"{path}: missing required contract {needle!r}")


def _forbid(errors: list[str], path: str, *needles: str) -> None:
    text = _read(path)
    for needle in needles:
        if needle in text:
            errors.append(f"{path}: contains stale or unsafe contract {needle!r}")


def _check_active_changes(errors: list[str]) -> None:
    registry_path = "openspec/active-changes.yaml"
    registry = _read(registry_path)
    names = re.findall(r"^  ([a-z0-9][a-z0-9-]+):$", registry, re.MULTILINE)
    for name in names:
        change_dir = ROOT / "openspec" / "changes" / name
        if not change_dir.is_dir():
            errors.append(
                f"{registry_path}: active entry {name!r} has no matching directory"
            )

    marker = "  feature-completeness-profiles:"
    if marker in registry:
        section = registry.split(marker, 1)[1]
        sibling = re.search(r"^  [a-z0-9][a-z0-9-]+:$", section, re.MULTILINE)
        if sibling:
            section = section[: sibling.start()]
        for required in (
            "status: partial",
            "github_issues: [83, 131]",
            "roadmap_state: review_required",
        ):
            if required not in section:
                errors.append(
                    "openspec/active-changes.yaml: feature completeness lifecycle "
                    f"must include {required!r} until residual validation is closed"
                )
        change_root = ROOT / "openspec" / "changes" / "feature-completeness-profiles"
        if not (change_root / "validation.md").is_file():
            errors.append(
                "feature-completeness-profiles requires validation.md while active"
            )


def check() -> tuple[str, ...]:
    errors: list[str] = []

    _require(
        errors,
        "docker-compose.yml",
        "device: ${OPENSTOCK_WAREHOUSE_DIR:-/var/lib/openstock/warehouse}",
        "VNALPHA_WAREHOUSE_PATH: /warehouse/warehouse.duckdb",
        "VNALPHA_LLM_MODEL: ${VNALPHA_LLM_MODEL:-}",
    )
    _forbid(
        errors,
        "docker-compose.yml",
        "/home/beou",
        "provider/default-model",
    )
    _require(
        errors,
        ".env.example",
        f"VNALPHA_WAREHOUSE_PATH={CANONICAL_WAREHOUSE}",
        "VNALPHA_LLM_MODEL=",
    )
    _require(
        errors,
        "packaging/config/vnalpha.env",
        f"VNALPHA_WAREHOUSE_PATH={CANONICAL_WAREHOUSE}",
        "VNALPHA_LLM_MODEL=",
    )
    _forbid(errors, "Makefile", "-f vnstock/docker-compose.yml")
    _require(
        errors,
        "Makefile",
        "docker compose up -d vnstock-service",
        "verify-repo-consistency:",
    )

    _require(
        errors,
        "vnstock/pyproject.toml",
        'Source = "https://github.com/duvu/openstock"',
        'IssueTracker = "https://github.com/duvu/openstock/issues"',
    )
    _forbid(
        errors,
        "vnstock/pyproject.toml",
        'Source = "https://github.com/duvu/vnstock"',
    )

    current_docs = (
        "vnalpha/docs/02-system-architecture.md",
        "vnalpha/docs/03-data-pipeline.md",
        "vnalpha/docs/06-ai-layer.md",
        "vnalpha/docs/09-workspace-service-design.md",
        "vnalpha/docs/11-deployment-architecture.md",
    )
    for path in current_docs:
        _forbid(
            errors,
            path,
            "Streamlit MVP",
            "vnalpha-dashboard",
            "python -m vnalpha.ingestion.sync_ohlcv",
            "provider/default-model",
            "/home/beou",
        )

    _check_active_changes(errors)
    return tuple(errors)


def main() -> int:
    try:
        errors = check()
    except ConsistencyError as exc:
        print(f"repository consistency check failed: {exc}", file=sys.stderr)
        return 2

    if errors:
        print("repository consistency check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("repository consistency check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

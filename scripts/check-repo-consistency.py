#!/usr/bin/env python3
"""Fail when repository documentation and runtime contracts drift apart."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_WAREHOUSE = "/var/lib/openstock/warehouse/warehouse.duckdb"
LIVE_ROADMAP_ISSUE_ID = 238
LIVE_ROADMAP_URL = "https://github.com/duvu/openstock/issues/238"
CURRENT_ROADMAP_DOCS = (
    "README.md",
    "ROADMAP.md",
    "vnalpha/docs/02-system-architecture.md",
    "vnalpha/docs/03-data-pipeline.md",
    "vnalpha/docs/05-backtest-and-outcome.md",
    "vnalpha/docs/README.md",
    "vnalpha/docs/RUNBOOK.md",
    "vnalpha/docs/07-implementation-roadmap.md",
    "vnalpha/docs/10-roadmap-phases.md",
    "vnalpha/README.md",
    "vnstock/README.md",
    "vnstock/roadmap.md",
    "openspec/README.md",
)


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


def _extract_issue_id(value: str) -> int | None:
    match = re.search(r"/issues/(\d+)", value)
    if match is not None:
        return int(match.group(1))
    match = re.search(r"#(\d+)", value)
    if match is not None:
        return int(match.group(1))
    return None


def _parse_issue_ids(text: str) -> tuple[int, ...]:
    return tuple(int(value) for value in re.findall(r"\d+", text))


def _iter_active_change_blocks(
    registry: str,
) -> tuple[tuple[str, str], ...]:
    # match only active change names such as `  validate-daily-equity-ranking:`
    entries = tuple(re.finditer(r"(?m)^  ([a-z0-9][a-z0-9-]+):$", registry))
    if not entries:
        return ()
    blocks: list[tuple[str, str]] = []
    for index, match in enumerate(entries):
        start = match.end() + 1
        end = entries[index + 1].start() if index + 1 < len(entries) else len(registry)
        name = match.group(1)
        blocks.append((name, registry[start:end]))
    return tuple(blocks)


def _check_active_changes(errors: list[str]) -> None:
    registry_path = "openspec/active-changes.yaml"
    registry = _read(registry_path)
    blocks = _iter_active_change_blocks(registry)
    names = tuple(name for name, _ in blocks)
    roadmap_source = re.search(r"^  roadmap_source:\s*(.+)$", registry, re.MULTILINE)
    if roadmap_source is None:
        errors.append(f"{registry_path}: missing roadmap_source")
    else:
        issue_id = _extract_issue_id(roadmap_source.group(1).strip())
        if issue_id != LIVE_ROADMAP_ISSUE_ID:
            errors.append(
                f"{registry_path}: roadmap_source must reference issue #{LIVE_ROADMAP_ISSUE_ID}"
            )

    issue_to_changes: dict[int, list[str]] = {}
    for name, entry_text in blocks:
        # Skip the compatibility section name if someone removes it in the future.
        if name == "feature-completeness-profiles":
            continue

        status_match = re.search(r"^    status:\s*(\S+)", entry_text, re.MULTILINE)
        roadmap_state_match = re.search(
            r"^    roadmap_state:\s*(\S+)", entry_text, re.MULTILINE
        )
        issues_match = re.search(
            r"^    github_issues:\s*\[(.*?)\]", entry_text, re.MULTILINE
        )

        if status_match is None:
            errors.append(f"{registry_path}: active entry {name!r} missing status")
        if roadmap_state_match is None:
            errors.append(
                f"{registry_path}: active entry {name!r} missing roadmap_state"
            )
        if issues_match is None:
            errors.append(
                f"{registry_path}: active entry {name!r} missing github_issues list"
            )
            continue

        for issue_id in _parse_issue_ids(issues_match.group(1)):
            issue_to_changes.setdefault(issue_id, []).append(name)

    duplicated_issue_lines = [
        f"{issue} referenced by {', '.join(names)}"
        for issue, names in issue_to_changes.items()
        if len(names) > 1
    ]
    for duplicate in duplicated_issue_lines:
        errors.append(
            f"{registry_path}: duplicate live github issue owner across active entries: {duplicate}"
        )

    for name in names:
        change_dir = ROOT / "openspec" / "changes" / name
        if not change_dir.is_dir():
            errors.append(
                f"{registry_path}: active entry {name!r} has no matching directory"
            )

    if len(blocks) == 0:
        errors.append(f"{registry_path}: no active change entries could be parsed")

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


def _check_live_roadmap_contract(errors: list[str]) -> None:
    for path in CURRENT_ROADMAP_DOCS:
        text = _read(path)
        if LIVE_ROADMAP_URL not in text:
            errors.append(
                f"{path}: missing canonical live roadmap URL {LIVE_ROADMAP_URL}"
            )
        if "#90" in text or "issues/90" in text:
            errors.append(f"{path}: contains stale live-roadmap reference to issue #90")
        if "#209" in text or "issues/209" in text:
            errors.append(
                f"{path}: contains superseded live-roadmap reference to issue #209"
            )
        if "#162" in text or "issues/162" in text:
            errors.append(
                f"{path}: contains stale live-roadmap reference to issue #162"
            )


def _check_ci_gate_contract(errors: list[str]) -> None:
    workflow_path = ".github/workflows/openstock-ci.yml"
    workflow = _read(workflow_path)
    if re.search(r"(?m)^  pull_request:\s*\n    paths:", workflow):
        errors.append(
            f"{workflow_path}: pull_request path filters can hide required checks"
        )
    if re.search(
        r"(?m)^  push:\s*\n    branches:\s*\n      - main\s*\n    paths:",
        workflow,
    ):
        errors.append(
            f"{workflow_path}: main push validation must not be path-filtered"
        )
    for required in (
        "name: Repository consistency",
        "name: vnalpha lint and tests",
        "name: vnstock contracts and package",
        "name: Required merge gate",
        "if: always()",
    ):
        if required not in workflow:
            errors.append(
                f"{workflow_path}: missing required merge-gate contract {required!r}"
            )
    for result_name in (
        "CONSISTENCY_RESULT",
        "VNALPHA_RESULT",
        "VNSTOCK_RESULT",
    ):
        required = f'test "${result_name}" = success'
        if required not in workflow:
            errors.append(
                f"{workflow_path}: required gate must require {result_name} success"
            )

    doc_path = "vnalpha/docs/branch-protection.md"
    document = _read(doc_path)
    for required in (
        "openstock-ci / Repository consistency",
        "openstock-ci / vnalpha lint and tests",
        "openstock-ci / vnstock contracts and package",
        "openstock-ci / Required merge gate",
        "Require branches to be up to date before merging",
        "Do not allow bypassing the above settings",
    ):
        if required not in document:
            errors.append(
                f"{doc_path}: missing required branch-protection contract {required!r}"
            )
    for stale in (
        ".github/workflows/vnalpha-ci.yml",
        "vnalpha-ci / validate",
    ):
        if stale in document:
            errors.append(
                f"{doc_path}: contains stale branch-protection contract {stale!r}"
            )


def _check_suite_manifest(errors: list[str]) -> None:
    module_path = Path(__file__).with_name("test_suite_manifest.py")
    spec = importlib.util.spec_from_file_location(
        "_openstock_test_suite_manifest", module_path
    )
    if spec is None or spec.loader is None:
        errors.append("cannot load test suite manifest validator")
        return
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    manifest_path = ROOT / "vnalpha" / "tests" / "suites" / "authoritative.toml"
    tests_root = ROOT / "vnalpha" / "tests"
    try:
        manifest = module.load_manifest(manifest_path)
        manifest_errors = module.validate_manifest(manifest, tests_root)
    except module.ManifestError as exc:
        errors.append(f"vnalpha test suite manifest: {exc}")
        return
    errors.extend(f"vnalpha test suite manifest: {error}" for error in manifest_errors)


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

    # Issue #254: FiinQuantX docs must route canonical endpoints and the default
    # provider registry inventory must agree with what it actually registers.
    _forbid(
        errors,
        "vnstock/docs/providers/FIINQUANTX.md",
        "/v1/data?dataset=",
    )
    _require(
        errors,
        "vnstock/docs/providers/FIINQUANTX.md",
        "/v1/equity/ohlcv?symbol=",
    )
    _forbid(
        errors,
        "vnstock/vnstock/core/runtime/bootstrap.py",
        "seven built-in",
        "all seven providers registered",
    )
    _require(
        errors,
        "vnstock/vnstock/core/runtime/bootstrap.py",
        "all eight providers registered",
        "**FIINQUANTX**",
    )

    _check_active_changes(errors)
    _check_ci_gate_contract(errors)
    _check_live_roadmap_contract(errors)
    _check_suite_manifest(errors)
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

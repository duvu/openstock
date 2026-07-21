from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
from typing import Sequence


class ImpactError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ImpactDecision:
    classes: tuple[str, ...]
    consistency: bool
    smoke: bool
    domains: tuple[str, ...]
    full: bool
    package: bool


ALL_DOMAINS = (
    "vnalpha-application",
    "vnalpha-data",
    "vnalpha-research",
    "vnstock-contracts",
)
INFRASTRUCTURE = "test_or_workflow_infrastructure"
DOCS = "docs_openspec_only"


def _classify_path(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts:
        raise ImpactError(f"changed path must be repository-relative: {value!r}")
    normalized = path.as_posix()
    if normalized in {"docker-compose.yml", "compose.yaml", ".env.example"}:
        return "shared_contract"
    if normalized in {"Makefile", "pyproject.toml", "uv.lock"}:
        return INFRASTRUCTURE
    if normalized.startswith(
        (".github/", "scripts/", "vnalpha/tests/", "vnstock/tests/")
    ):
        return INFRASTRUCTURE
    if normalized.startswith(("packaging/", "debian/")):
        return "packaging"
    if normalized.startswith("vnalpha/"):
        return "vnalpha"
    if normalized.startswith("vnstock/"):
        return "vnstock"
    if normalized in {"README.md", "AGENTS.md"} or normalized.startswith(
        ("docs/", "openspec/")
    ):
        return DOCS
    raise ImpactError(f"unknown changed path; routing fails closed: {value!r}")


def classify_paths(paths: tuple[str, ...]) -> ImpactDecision:
    if not paths:
        raise ImpactError("at least one changed path is required")
    classes = {_classify_path(path) for path in paths}
    if INFRASTRUCTURE in classes:
        return ImpactDecision(
            classes=(INFRASTRUCTURE,),
            consistency=True,
            smoke=True,
            domains=ALL_DOMAINS,
            full=True,
            package=False,
        )
    ordered_classes = tuple(
        name
        for name in (DOCS, "packaging", "shared_contract", "vnalpha", "vnstock")
        if name in classes
    )
    has_runtime = bool(classes - {DOCS})
    return ImpactDecision(
        classes=ordered_classes,
        consistency=True,
        smoke=has_runtime,
        domains=tuple(
            domain
            for domain in ALL_DOMAINS
            if (domain.startswith("vnalpha") and "vnalpha" in classes)
            or (domain == "vnstock-contracts" and "vnstock" in classes)
            or bool(classes & {"packaging", "shared_contract"})
        ),
        full=bool(classes & {"packaging", "shared_contract"}),
        package="packaging" in classes,
    )


def _write_github_output(decision: ImpactDecision, output_path: str) -> None:
    values = asdict(decision)
    with open(output_path, "a", encoding="utf-8") as output:
        for name, value in values.items():
            output.write(f"{name}={json.dumps(value)}\n")


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Classify changed paths into fail-closed test impacts"
    )
    parser.add_argument("--path", action="append", required=True)
    parser.add_argument("--github-output", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        decision = classify_paths(tuple(args.path))
    except ImpactError as exc:
        print(f"impact classification failed: {exc}", file=sys.stderr)
        return 2
    if args.github_output:
        output_path = os.environ.get("GITHUB_OUTPUT")
        if not output_path:
            print(
                "impact classification failed: GITHUB_OUTPUT is not set",
                file=sys.stderr,
            )
            return 2
        _write_github_output(decision, output_path)
    print(json.dumps(asdict(decision), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from test_suite_manifest import ManifestError, load_manifest, resolve_tests, validate_manifest

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "vnalpha" / "tests" / "suites" / "authoritative.toml"
DEFAULT_TESTS_ROOT = ROOT / "vnalpha" / "tests"


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve and run the bounded authoritative pytest inventory"
    )
    parser.add_argument("--domain", action="append", default=[])
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--tests-root", type=Path, default=DEFAULT_TESTS_ROOT)
    parser.add_argument("--plan", action="store_true")
    return parser.parse_args(argv)


def _nodes_or_error(args: argparse.Namespace) -> tuple[str, ...] | None:
    try:
        inventory = load_manifest(args.manifest)
        errors = validate_manifest(inventory, args.tests_root)
        if errors:
            raise ManifestError("; ".join(errors))
        return resolve_tests(inventory, tuple(args.domain))
    except ManifestError as exc:
        print(f"authoritative inventory validation failed: {exc}", file=sys.stderr)
        return None


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    nodes = _nodes_or_error(args)
    if nodes is None:
        return 2
    if args.plan:
        print("\n".join(nodes))
        return 0
    completed = subprocess.run(
        (sys.executable, "-m", "pytest", "-q", *nodes),
        cwd=args.tests_root.parent,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())

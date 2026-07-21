from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from test_suite_manifest import (
    ManifestError,
    load_manifest,
    resolve_paths,
    validate_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "vnalpha" / "tests" / "suites" / "manifest.toml"
DEFAULT_TESTS_ROOT = ROOT / "vnalpha" / "tests"

PytestRunner = Callable[[tuple[str, ...]], int]


def _run_pytest(paths: tuple[str, ...]) -> int:
    completed = subprocess.run(
        (sys.executable, "-m", "pytest", *paths),
        cwd=DEFAULT_TESTS_ROOT.parent,
        check=False,
    )
    return completed.returncode


def run_suites(
    *,
    manifest_path: Path,
    tests_root: Path,
    suite_names: tuple[str, ...],
    pytest_runner: PytestRunner,
) -> int:
    try:
        manifest = load_manifest(manifest_path, tests_root)
        errors = validate_manifest(manifest, tests_root)
        if errors:
            print("suite manifest validation failed:", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            return 2
        paths = resolve_paths(manifest, suite_names)
    except ManifestError as exc:
        print(f"suite manifest validation failed: {exc}", file=sys.stderr)
        return 2
    return pytest_runner(paths)


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve and run canonical pytest suites"
    )
    parser.add_argument("--suite", action="append", required=True)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--tests-root", type=Path, default=DEFAULT_TESTS_ROOT)
    parser.add_argument("--plan", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    suite_names = tuple(args.suite)
    if args.plan:
        try:
            manifest = load_manifest(args.manifest, args.tests_root)
            errors = validate_manifest(manifest, args.tests_root)
            if errors:
                raise ManifestError("; ".join(errors))
            print("\n".join(resolve_paths(manifest, suite_names)))
        except ManifestError as exc:
            print(f"suite manifest validation failed: {exc}", file=sys.stderr)
            return 2
        return 0
    return run_suites(
        manifest_path=args.manifest,
        tests_root=args.tests_root,
        suite_names=suite_names,
        pytest_runner=_run_pytest,
    )


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_checker():
    path = Path(__file__).resolve().parents[1] / "check-repo-consistency.py"
    spec = importlib.util.spec_from_file_location("check_repo_consistency", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _valid_workflow() -> str:
    return """on:
  pull_request:
  push:
    branches:
      - main
jobs:
  consistency:
    name: Repository consistency
  vnalpha:
    name: vnalpha lint and tests
  vnstock:
    name: vnstock contracts and package
  required:
    name: Required merge gate
    if: always()
    run: |
      test \"$CONSISTENCY_RESULT\" = success
      test \"$VNALPHA_RESULT\" = success
      test \"$VNSTOCK_RESULT\" = success
"""


def _valid_document() -> str:
    return """openstock-ci / Repository consistency
openstock-ci / vnalpha lint and tests
openstock-ci / vnstock contracts and package
openstock-ci / Required merge gate
Require branches to be up to date before merging
Do not allow bypassing the above settings
"""


def test_ci_gate_contract_accepts_stable_required_checks(monkeypatch) -> None:
    module = _load_checker()
    files = {
        ".github/workflows/openstock-ci.yml": _valid_workflow(),
        "vnalpha/docs/branch-protection.md": _valid_document(),
    }
    monkeypatch.setattr(module, "_read", files.__getitem__)
    errors: list[str] = []

    module._check_ci_gate_contract(errors)

    assert errors == []


def test_ci_gate_contract_rejects_path_filtered_pull_requests(monkeypatch) -> None:
    module = _load_checker()
    files = {
        ".github/workflows/openstock-ci.yml": _valid_workflow().replace(
            "  pull_request:\n", '  pull_request:\n    paths:\n      - "vnalpha/**"\n'
        ),
        "vnalpha/docs/branch-protection.md": _valid_document(),
    }
    monkeypatch.setattr(module, "_read", files.__getitem__)
    errors: list[str] = []

    module._check_ci_gate_contract(errors)

    assert any("path filters can hide required checks" in error for error in errors)


def test_ci_gate_contract_rejects_stale_documentation(monkeypatch) -> None:
    module = _load_checker()
    files = {
        ".github/workflows/openstock-ci.yml": _valid_workflow(),
        "vnalpha/docs/branch-protection.md": (
            _valid_document() + "vnalpha-ci / validate\n.github/workflows/vnalpha-ci.yml\n"
        ),
    }
    monkeypatch.setattr(module, "_read", files.__getitem__)
    errors: list[str] = []

    module._check_ci_gate_contract(errors)

    assert any("stale branch-protection contract" in error for error in errors)

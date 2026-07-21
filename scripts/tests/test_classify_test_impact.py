from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _load_module():
    path = Path(__file__).resolve().parents[1] / "classify_test_impact.py"
    spec = importlib.util.spec_from_file_location("classify_test_impact", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_docs_only_paths_select_only_consistency() -> None:
    module = _load_module()

    decision = module.classify_paths(("README.md", "openspec/README.md"))

    assert decision.classes == ("docs_openspec_only",)
    assert decision.consistency is True
    assert decision.smoke is False
    assert decision.domains == ()
    assert decision.full is False
    assert decision.package is False


def test_component_paths_select_owning_domains_and_smoke() -> None:
    module = _load_module()

    decision = module.classify_paths(
        ("vnalpha/src/vnalpha/commands.py", "vnstock/vnstock/core/provider.py")
    )

    assert decision.classes == ("vnalpha", "vnstock")
    assert decision.smoke is True
    assert decision.domains == (
        "vnalpha-application",
        "vnalpha-data",
        "vnalpha-research",
        "vnstock-contracts",
    )
    assert decision.full is False
    assert decision.package is False


def test_infrastructure_paths_escalate_to_full_regression() -> None:
    module = _load_module()

    decision = module.classify_paths(
        ("vnalpha/tests/conftest.py", ".github/workflows/openstock-ci.yml")
    )

    assert decision.classes == ("test_or_workflow_infrastructure",)
    assert decision.smoke is True
    assert decision.domains == (
        "vnalpha-application",
        "vnalpha-data",
        "vnalpha-research",
        "vnstock-contracts",
    )
    assert decision.full is True


def test_packaging_and_shared_contract_paths_escalate_to_full_regression() -> None:
    module = _load_module()

    packaging = module.classify_paths(("./packaging/debian/control",))
    shared = module.classify_paths(("docker-compose.yml",))

    assert packaging.classes == ("packaging",)
    assert packaging.domains == (
        "vnalpha-application",
        "vnalpha-data",
        "vnalpha-research",
        "vnstock-contracts",
    )
    assert packaging.full is True
    assert packaging.package is True
    assert shared.classes == ("shared_contract",)
    assert shared.full is True
    assert shared.package is False


def test_github_output_is_deterministic(monkeypatch, tmp_path, capsys) -> None:
    module = _load_module()
    output = tmp_path / "github-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))

    result = module.main(("--path", "README.md", "--github-output"))

    assert result == 0
    assert json.loads(capsys.readouterr().out) == {
        "classes": ["docs_openspec_only"],
        "consistency": True,
        "domains": [],
        "full": False,
        "package": False,
        "smoke": False,
    }
    assert output.read_text(encoding="utf-8").splitlines() == [
        'classes=["docs_openspec_only"]',
        "consistency=true",
        "smoke=false",
        "domains=[]",
        "full=false",
        "package=false",
    ]


def test_unknown_and_parent_paths_fail_closed() -> None:
    module = _load_module()

    with pytest.raises(module.ImpactError, match="unknown changed path"):
        module.classify_paths(("notes/unclassified.txt",))
    with pytest.raises(module.ImpactError, match="repository-relative"):
        module.classify_paths(("../README.md",))

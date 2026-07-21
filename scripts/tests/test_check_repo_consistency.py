from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


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
  impact:
    name: Change impact routing
    run: python scripts/classify-test-impact.py --github-output
  consistency:
    name: Repository consistency
  vnalpha:
    name: vnalpha lint and tests
    if: needs.impact.outputs.full == 'true'
  vnalpha-smoke:
    if: needs.impact.outputs.smoke == 'true'
  vnalpha-domains:
    if: contains(fromJSON(needs.impact.outputs.domains), 'vnalpha-application')
  vnstock:
    name: vnstock contracts and package
  required:
    name: Required merge gate
    if: always()
    run: |
      case \"$IMPACT_RESULT\" in success|skipped) ;; *) exit 1 ;; esac
      case \"$CONSISTENCY_RESULT\" in success|skipped) ;; *) exit 1 ;; esac
      case \"$VNALPHA_RESULT\" in success|skipped) ;; *) exit 1 ;; esac
      case \"$VNALPHA_SMOKE_RESULT\" in success|skipped) ;; *) exit 1 ;; esac
      case \"$VNALPHA_DOMAINS_RESULT\" in success|skipped) ;; *) exit 1 ;; esac
      case \"$VNSTOCK_RESULT\" in success|skipped) ;; *) exit 1 ;; esac
"""


def _valid_document() -> str:
    return """openstock-ci / Repository consistency
openstock-ci / vnalpha lint and tests
openstock-ci / vnstock contracts and package
openstock-ci / Required merge gate
Require branches to be up to date before merging
Do not allow bypassing the above settings
"""


def _active_changes_registry(roadmap_issue: int = 238) -> str:
    return f"""policy:
  active_directory: openspec/changes
  archive_directory: openspec/changes/archive
  roadmap_source: https://github.com/duvu/openstock/issues/{roadmap_issue}
  priorities_owned_by: github_issues
  dependencies_owned_by: github_issues
  require_github_issue_for_scheduled_work: true
  research_only_boundary: true

changes:

  alpha-change:
    status: partial
    github_issues: [101, 201]
    roadmap_state: review_required
    summary: fixture
    evidence: PR #1 merged.

  beta-change:
    status: partial
    github_issues: [102]
    roadmap_state: review_required
    summary: fixture
    evidence: PR #2 merged.

  feature-completeness-profiles:
    status: partial
    github_issues: [83, 131]
    roadmap_state: review_required
    summary: fixture
    evidence: PR #3 merged.
"""


def _active_changes_registry_with_duplicate_issue(roadmap_issue: int = 238) -> str:
    return f"""policy:
  roadmap_source: https://github.com/duvu/openstock/issues/{roadmap_issue}

changes:

  alpha-change:
    status: partial
    github_issues: [101, 201]
    roadmap_state: review_required

  beta-change:
    status: partial
    github_issues: [101]
    roadmap_state: review_required

  feature-completeness-profiles:
    status: partial
    github_issues: [83, 131]
    roadmap_state: review_required
"""


def _roadmap_docs_containing(needle: str) -> dict[str, str]:
    reference = f"https://github.com/duvu/openstock/issues/{needle}"
    return {
        path: reference
        for path in (
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
    }


def _create_change_dirs(module: Any, tmp_root: Path) -> None:
    for name in ("alpha-change", "beta-change", "feature-completeness-profiles"):
        (tmp_root / "openspec" / "changes" / name).mkdir(parents=True)


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


def test_ci_gate_contract_accepts_deliberate_skips(monkeypatch) -> None:
    module = _load_checker()
    files = {
        ".github/workflows/openstock-ci.yml": _valid_workflow(),
        "vnalpha/docs/branch-protection.md": _valid_document(),
    }
    monkeypatch.setattr(module, "_read", files.__getitem__)
    errors: list[str] = []

    module._check_ci_gate_contract(errors)

    assert errors == []


def test_ci_gate_contract_rejects_unchecked_routed_lane(monkeypatch) -> None:
    module = _load_checker()
    files = {
        ".github/workflows/openstock-ci.yml": _valid_workflow().replace(
            '      case "$VNALPHA_SMOKE_RESULT" in success|skipped) ;; *) exit 1 ;; esac\n',
            "",
        ),
        "vnalpha/docs/branch-protection.md": _valid_document(),
    }
    monkeypatch.setattr(module, "_read", files.__getitem__)
    errors: list[str] = []

    module._check_ci_gate_contract(errors)

    assert any("VNALPHA_SMOKE_RESULT" in error for error in errors)


def test_ci_gate_contract_rejects_missing_impact_router(monkeypatch) -> None:
    module = _load_checker()
    files = {
        ".github/workflows/openstock-ci.yml": _valid_workflow().replace(
            "python scripts/classify-test-impact.py --github-output", "true"
        ),
        "vnalpha/docs/branch-protection.md": _valid_document(),
    }
    monkeypatch.setattr(module, "_read", files.__getitem__)
    errors: list[str] = []

    module._check_ci_gate_contract(errors)

    assert any("classifier" in error for error in errors)


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
            _valid_document()
            + "vnalpha-ci / validate\n.github/workflows/vnalpha-ci.yml\n"
        ),
    }
    monkeypatch.setattr(module, "_read", files.__getitem__)
    errors: list[str] = []

    module._check_ci_gate_contract(errors)

    assert any("stale branch-protection contract" in error for error in errors)


def test_active_changes_rejects_noncanonical_roadmap_source(
    monkeypatch, tmp_path
) -> None:
    module = _load_checker()
    _create_change_dirs(module, tmp_path)
    files: dict[str, str] = {
        "openspec/active-changes.yaml": _active_changes_registry(roadmap_issue=90),
    }
    files.update(_roadmap_docs_containing("238"))
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "_read", files.__getitem__)
    errors: list[str] = []

    module._check_active_changes(errors)
    module._check_live_roadmap_contract(errors)

    assert any("roadmap_source must reference issue #238" in error for error in errors)


def test_active_changes_rejects_duplicate_owners(monkeypatch, tmp_path) -> None:
    module = _load_checker()
    _create_change_dirs(module, tmp_path)
    files: dict[str, str] = {
        "openspec/active-changes.yaml": _active_changes_registry_with_duplicate_issue(),
        "README.md": "issue #238",
        "ROADMAP.md": "issue #238",
        "vnalpha/docs/02-system-architecture.md": "issue #238",
        "vnalpha/docs/03-data-pipeline.md": "issue #238",
        "vnalpha/docs/05-backtest-and-outcome.md": "issue #238",
        "vnalpha/docs/README.md": "issue #238",
    }
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "_read", files.__getitem__)
    errors: list[str] = []

    module._check_active_changes(errors)

    assert any("duplicate live github issue owner" in error for error in errors)


def test_live_roadmap_docs_reject_stale_reference(monkeypatch) -> None:
    module = _load_checker()
    files = _roadmap_docs_containing("238")
    files["README.md"] = "live roadmap is #90"
    files[".github/workflows/openstock-ci.yml"] = _valid_workflow()
    files["vnalpha/docs/branch-protection.md"] = _valid_document()
    monkeypatch.setattr(module, "_read", files.__getitem__)
    errors: list[str] = []

    module._check_live_roadmap_contract(errors)

    assert any("stale live-roadmap reference to issue #90" in error for error in errors)


def test_live_roadmap_docs_reject_superseded_issue_209(monkeypatch) -> None:
    module = _load_checker()
    files = _roadmap_docs_containing("238")
    files["README.md"] = "live roadmap is #238 but old queue is #209"
    monkeypatch.setattr(module, "_read", files.__getitem__)
    errors: list[str] = []

    module._check_live_roadmap_contract(errors)

    assert any(
        "superseded live-roadmap reference to issue #209" in error for error in errors
    )


def test_suite_manifest_consistency_reports_unassigned_test_file(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_checker()
    manifest = tmp_path / "vnalpha" / "tests" / "suites" / "manifest.toml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        "\n".join(
            (
                "version = 1",
                "[[suite]]",
                'name = "vnalpha-data"',
                'paths = ["tests/test_assigned.py"]',
                "[[suite.contract]]",
                'name = "data"',
                'happy = "tests/test_assigned.py::test_happy"',
                'plus_one = "tests/test_assigned.py::test_failure"',
            )
        ),
        encoding="utf-8",
    )
    tests_root = manifest.parents[1]
    (tests_root / "test_assigned.py").write_text("", encoding="utf-8")
    (tests_root / "test_unassigned.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    errors: list[str] = []

    module._check_suite_manifest(errors)

    assert any("test_unassigned.py" in error for error in errors)

from __future__ import annotations

import importlib.util
from pathlib import Path

_MODULE_PATH = Path(__file__).parents[1] / "check_issue_closure_contract.py"
_SPEC = importlib.util.spec_from_file_location("closure_contract", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
module = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(module)

IssueSnapshot = module.IssueSnapshot
extract_closing_issue_numbers = module.extract_closing_issue_numbers
extract_dependencies = module.extract_dependencies
validate_closure = module.validate_closure


def _issue(number: int, body: str, *, state: str = "closed") -> IssueSnapshot:
    return IssueSnapshot(number, f"Issue {number}", body, state)


def _evidence_body(extra: str = "") -> str:
    return f"""
## Acceptance evidence

| Acceptance criterion | Implementation | Test | Evidence |
|---|---|---|---|
| exact criterion | src/module.py:run | test_negative | CI run 123 |

{extra}
"""


def test_extracts_only_github_closing_keywords() -> None:
    assert extract_closing_issue_numbers(
        "Fixes #12", "Refs #11\nResolves: #13\nDoes not close #14"
    ) == (12, 13)


def test_extracts_dependencies_only_from_depends_section() -> None:
    body = """
## Parent
- #1
## Depends on
- #2
- #3 — prerequisite
## Context
See #4.
"""
    assert extract_dependencies(body) == (2, 3)


def test_foundation_pr_cannot_close_implementation_issue() -> None:
    errors = validate_closure(
        pr_title="feat: foundation for issue #10",
        pr_body=_evidence_body("Closes #10"),
        issues={10: _issue(10, "## Acceptance\n- real implementation")},
    )
    assert any("foundation" in error.lower() for error in errors)


def test_closing_pr_requires_acceptance_matrix() -> None:
    errors = validate_closure(
        pr_title="feat: implementation",
        pr_body="Closes #10\nTests pass.",
        issues={10: _issue(10, "## Acceptance")},
    )
    assert any("acceptance evidence" in error.lower() for error in errors)


def test_open_dependency_blocks_closure() -> None:
    errors = validate_closure(
        pr_title="feat: implementation",
        pr_body=_evidence_body("Closes #10"),
        issues={
            10: _issue(10, "## Depends on\n- #9\n## Acceptance"),
            9: _issue(9, "dependency", state="open"),
        },
    )
    assert any("depends on open issue #9" in error for error in errors)


def test_live_issue_requires_explicit_completed_evidence() -> None:
    errors = validate_closure(
        pr_title="ops: proof tooling",
        pr_body=_evidence_body("Closes #10\nRemaining acceptance is pending."),
        issues={
            10: _issue(
                10,
                "Prove 10 consecutive live daily sessions on a supported host.",
            )
        },
    )
    assert any("live/installed-host evidence" in error for error in errors)


def test_live_issue_passes_only_with_exact_completed_evidence() -> None:
    body = _evidence_body(
        """
Closes #10
## Live evidence
EXTERNAL_EVIDENCE_COMPLETE: true
- Commit SHA: abcdef
- Run ID: 12345
- Session dates: 2026-07-01 through 2026-07-14
"""
    )
    errors = validate_closure(
        pr_title="ops: complete live proof",
        pr_body=body,
        issues={10: _issue(10, "10 consecutive live daily sessions")},
    )
    assert errors == []


def test_regular_issue_with_closed_dependencies_and_matrix_passes() -> None:
    errors = validate_closure(
        pr_title="feat: complete implementation",
        pr_body=_evidence_body("Closes #10"),
        issues={
            10: _issue(10, "## Depends on\n- #9\n## Acceptance"),
            9: _issue(9, "dependency", state="closed"),
        },
    )
    assert errors == []

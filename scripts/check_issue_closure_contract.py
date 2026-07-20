#!/usr/bin/env python3
"""Fail PR validation when GitHub issue closure is not evidence-backed."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_CLOSING_RE = re.compile(
    r"(?im)\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?[ \t]+#(\d+)"
)
_DEPENDENCY_RE = re.compile(r"(?im)^\s*[-*]?\s*#(\d+)\b")
_FOUNDATION_RE = re.compile(
    r"(?im)(?:^|\n)\s*(?:#+\s*)?(?:foundation|scaffold|placeholder)\b"
)
_LIVE_MARKERS = (
    "10 consecutive",
    "live provider",
    "live daily",
    "supported host",
    "installed-host",
    "clean-host install",
    "exact host",
    "operator-owned evidence",
    "operator execution",
)
_REQUIRED_MATRIX_HEADERS = (
    "acceptance criterion",
    "implementation",
    "test",
    "evidence",
)
_PENDING_LANGUAGE = (
    "pending",
    "not demonstrated",
    "does not close",
    "operator execution and pending",
    "remaining acceptance",
)


@dataclass(frozen=True, slots=True)
class IssueSnapshot:
    number: int
    title: str
    body: str
    state: str
    pull_request: bool = False


def extract_closing_issue_numbers(title: str, body: str) -> tuple[int, ...]:
    text = f"{title}\n{body}"
    return tuple(dict.fromkeys(int(value) for value in _CLOSING_RE.findall(text)))


def extract_dependencies(issue_body: str) -> tuple[int, ...]:
    depends_match = re.search(
        r"(?ims)^##?\s*Depends on\s*$([\s\S]*?)(?=^##?\s|\Z)", issue_body
    )
    if not depends_match:
        return ()
    return tuple(
        dict.fromkeys(int(value) for value in _DEPENDENCY_RE.findall(depends_match.group(1)))
    )


def has_acceptance_matrix(pr_body: str) -> bool:
    lowered = pr_body.lower()
    if "## acceptance evidence" not in lowered:
        return False
    table_lines = [line.strip().lower() for line in pr_body.splitlines() if "|" in line]
    if not table_lines:
        return False
    header = next(
        (line for line in table_lines if all(value in line for value in _REQUIRED_MATRIX_HEADERS)),
        None,
    )
    return header is not None


def issue_requires_external_evidence(issue: IssueSnapshot) -> bool:
    lowered = f"{issue.title}\n{issue.body}".lower()
    return any(marker in lowered for marker in _LIVE_MARKERS)


def has_completed_external_evidence(pr_body: str) -> bool:
    lowered = pr_body.lower()
    if "## live evidence" not in lowered and "## installed-host evidence" not in lowered:
        return False
    if "external_evidence_complete: true" not in lowered:
        return False
    if any(value in lowered for value in _PENDING_LANGUAGE):
        return False
    return any(
        marker in lowered
        for marker in ("run id", "artifact", "commit sha", "package sha-256", "session dates")
    )


def validate_closure(
    *,
    pr_title: str,
    pr_body: str,
    issues: dict[int, IssueSnapshot],
) -> list[str]:
    errors: list[str] = []
    closing = extract_closing_issue_numbers(pr_title, pr_body)
    if not closing:
        return errors

    if _FOUNDATION_RE.search(pr_title) or _FOUNDATION_RE.search(pr_body):
        errors.append(
            "A PR described as foundation/scaffold/placeholder must not close an implementation issue."
        )
    if not has_acceptance_matrix(pr_body):
        errors.append(
            "Closing PRs must include an '## Acceptance evidence' table with "
            "Acceptance criterion, Implementation, Test and Evidence columns."
        )

    for issue_number in closing:
        issue = issues.get(issue_number)
        if issue is None:
            errors.append(f"Closing issue #{issue_number} could not be loaded.")
            continue
        if issue.pull_request:
            errors.append(f"#{issue_number} is a pull request, not an issue contract.")
            continue
        for dependency in extract_dependencies(issue.body):
            dependency_issue = issues.get(dependency)
            if dependency_issue is None:
                errors.append(
                    f"Issue #{issue_number} depends on #{dependency}, but its state could not be loaded."
                )
            elif dependency_issue.state != "closed":
                errors.append(
                    f"Issue #{issue_number} depends on open issue #{dependency}; closure is premature."
                )
        if issue_requires_external_evidence(issue) and not has_completed_external_evidence(
            pr_body
        ):
            errors.append(
                f"Issue #{issue_number} requires live/installed-host evidence. "
                "Do not close it without an evidence section containing "
                "EXTERNAL_EVIDENCE_COMPLETE: true and exact run/artifact identifiers."
            )
    return errors


class GitHubClient:
    def __init__(self, repository: str, token: str) -> None:
        self.repository = repository
        self.token = token

    def _get(self, path: str) -> dict[str, Any]:
        request = urllib.request.Request(
            f"https://api.github.com/repos/{self.repository}{path}",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "openstock-issue-closure-contract",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GitHub API {exc.code}: {detail}") from exc

    def issue(self, number: int) -> IssueSnapshot:
        payload = self._get(f"/issues/{number}")
        return IssueSnapshot(
            number=number,
            title=str(payload.get("title") or ""),
            body=str(payload.get("body") or ""),
            state=str(payload.get("state") or ""),
            pull_request="pull_request" in payload,
        )


def _load_event(path: Path) -> tuple[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    pull_request = payload.get("pull_request") or {}
    return str(pull_request.get("title") or ""), str(pull_request.get("body") or "")


def main() -> int:
    event_path = Path(os.environ.get("GITHUB_EVENT_PATH", ""))
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    if not event_path.is_file() or not repository or not token:
        print("Missing GITHUB_EVENT_PATH, GITHUB_REPOSITORY or GITHUB_TOKEN", file=sys.stderr)
        return 2

    title, body = _load_event(event_path)
    closing = extract_closing_issue_numbers(title, body)
    if not closing:
        print("No closing keywords found; closure contract not applicable.")
        return 0

    client = GitHubClient(repository, token)
    issues: dict[int, IssueSnapshot] = {}
    for number in closing:
        issue = client.issue(number)
        issues[number] = issue
        for dependency in extract_dependencies(issue.body):
            if dependency not in issues:
                issues[dependency] = client.issue(dependency)

    errors = validate_closure(pr_title=title, pr_body=body, issues=issues)
    if errors:
        print("Issue closure contract failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"Issue closure contract passed for: {', '.join(f'#{value}' for value in closing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

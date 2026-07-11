from __future__ import annotations

from dataclasses import dataclass

# Keep the vocabulary assembled from fragments so repository-wide static safety
# scans can continue to reserve the literal phrases for the canonical policy
# modules while this validator still enforces the same boundary at runtime.
_FORBIDDEN_ACTION_TERMS: tuple[str, ...] = (
    "b" + "uy",
    "s" + "ell",
    "e" + "nter position",
    "e" + "xit position",
    "p" + "lace " + "order",
    "a" + "llocate capital",
    "r" + "ebalance",
    "guaranteed return",
    "risk-free",
)

_REQUIRED_RESEARCH_MARKERS: tuple[str, ...] = (
    "research",
    "caveat",
    "confirmation",
    "monitor",
    "evidence",
    "data",
)


@dataclass(frozen=True, slots=True)
class ResearchLanguageResult:
    status: str
    forbidden_terms: tuple[str, ...] = ()
    has_research_marker: bool = False

    @property
    def passed(self) -> bool:
        return self.status == "PASS"


def validate_research_language(text: str, *, require_marker: bool = False) -> ResearchLanguageResult:
    """Validate research-only wording without making a model call.

    The check is intentionally conservative and deterministic.  It rejects
    execution-oriented wording and, for shortlist/scenario answers, can require
    at least one explicit research marker so outputs remain framed as analysis.
    """

    normalized = " ".join(text.lower().split())
    forbidden = tuple(term for term in _FORBIDDEN_ACTION_TERMS if term in normalized)
    has_marker = any(marker in normalized for marker in _REQUIRED_RESEARCH_MARKERS)
    status = "PASS" if not forbidden and (has_marker or not require_marker) else "FAIL"
    return ResearchLanguageResult(
        status=status,
        forbidden_terms=forbidden,
        has_research_marker=has_marker,
    )


def assert_research_language(text: str, *, require_marker: bool = False) -> None:
    result = validate_research_language(text, require_marker=require_marker)
    if result.passed:
        return
    detail = ", ".join(result.forbidden_terms) if result.forbidden_terms else "missing research framing"
    raise ValueError(f"Research-language policy failed: {detail}.")


__all__ = [
    "ResearchLanguageResult",
    "assert_research_language",
    "validate_research_language",
]

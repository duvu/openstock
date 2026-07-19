from __future__ import annotations

from datetime import date

import duckdb

from vnalpha.assistant.executor import _normalize_tool_arguments
from vnalpha.data_availability.deep_context_artifacts import (
    _evidence_float,
    _evidence_int,
    context_artifact,
    market_remediation_steps,
    sector_remediation_steps,
)
from vnalpha.data_availability.deep_context_readiness import (
    ContextReadinessInput,
    evaluate_context_readiness,
)
from vnalpha.data_availability.deep_readiness_models import (
    ContextIssue,
    ContextRequirement,
)
from vnalpha.data_availability.models import EnsureDataResult, EnsureDataStatus


def test_tool_arguments_normalize_requirement_strings_before_tool_call() -> None:
    arguments = _normalize_tool_arguments(
        {
            "symbol": "FPT",
            "market_regime_requirement": " required ",
            "sector_strength_requirement": "NOT_REQUESTED",
        }
    )

    assert arguments == {
        "symbol": "FPT",
        "market_regime_requirement": ContextRequirement.REQUIRED,
    }


def test_legacy_evidence_conversion_is_null_and_malformed_safe() -> None:
    evidence = (
        ("missing", None),
        ("legacy_none", "None"),
        ("bad_int", "not-an-int"),
        ("bad_float", "not-a-float"),
    )

    assert _evidence_int(evidence, "missing") is None
    assert _evidence_int(evidence, "legacy_none") is None
    assert _evidence_int(evidence, "bad_int") is None
    assert _evidence_float(evidence, "bad_float") is None


def test_root_cause_remediation_orders_upstream_repairs() -> None:
    target = date(2026, 7, 10)

    market = market_remediation_steps(
        target, (ContextIssue.MARKET_REGIME_INPUT_COVERAGE_INSUFFICIENT,)
    )
    metadata = sector_remediation_steps(
        target, (ContextIssue.SYMBOL_SECTOR_UNCLASSIFIED,)
    )
    coverage = sector_remediation_steps(target, (ContextIssue.SECTOR_NOT_RANKABLE,))

    assert [step.command for step in market] == [
        "vnalpha build features --date 2026-07-10",
        "vnalpha build market-regime --date 2026-07-10",
    ]
    assert [step.command for step in metadata] == [
        "vnalpha sync symbols",
        "vnalpha build sector-strength --date 2026-07-10",
    ]
    assert [step.command for step in coverage] == [
        "vnalpha build features --date 2026-07-10",
        "vnalpha build sector-strength --date 2026-07-10",
    ]


def test_context_artifact_exposes_complete_decision_evidence() -> None:
    artifact = context_artifact(
        name="sector_strength_snapshot",
        requirement=ContextRequirement.REQUIRED,
        requested_date="2026-07-10",
        issues=(),
        actions=(),
        freshness="exact",
        observed_as_of_date="2026-07-10",
        row_count=4,
        quality_status="OK",
        methodology_version="sector-strength-v1",
        lineage=("input",),
        remediation_steps=(),
        generated_at="2026-07-10T10:00:00+00:00",
        evidence=(
            ("ranked_sector_count", 4),
            ("member_count", 12),
            ("eligible_count", 10),
            ("excluded_count", 2),
            ("metadata_coverage", 0.9),
            ("rank", 1),
            ("score", 1.5),
            ("rotation", "LEADING"),
        ),
    )

    assert artifact.ranked_sector_count == 4
    assert artifact.member_count == 12
    assert artifact.eligible_count == 10
    assert artifact.excluded_count == 2
    assert artifact.metadata_coverage == 0.9
    assert artifact.generated_at == "2026-07-10T10:00:00+00:00"


def test_unexpected_context_evaluation_failure_returns_structured_result(
    monkeypatch,
) -> None:
    from vnalpha.data_availability import deep_readiness_service

    monkeypatch.setattr(
        deep_readiness_service,
        "resolve_market_session_date",
        lambda _value: "2026-07-10",
    )
    monkeypatch.setattr(deep_readiness_service, "build_artifacts", lambda **_kwargs: ())
    monkeypatch.setattr(
        deep_readiness_service,
        "evaluate_context_readiness",
        lambda _context: (_ for _ in ()).throw(TypeError("legacy shape")),
    )
    service = deep_readiness_service.DeepAnalysisReadinessService(
        ensure=lambda _conn, _symbol, _date: EnsureDataResult(
            symbol="FPT",
            target_date="2026-07-10",
            status=EnsureDataStatus.READY,
            core_evidence_evaluated=True,
        )
    )

    result = service.ensure_ready(
        deep_readiness_service.DeepAnalysisReadinessRequest(
            duckdb.connect(),
            "FPT",
            "2026-07-10",
            market_regime_requirement=ContextRequirement.REQUIRED,
        )
    )

    assert result.is_ready is False
    market = next(
        artifact
        for artifact in result.artifacts
        if artifact.name == "market_regime_snapshot"
    )
    assert market.error_code == ContextIssue.CONTEXT_BUILD_FAILED.value


def test_unexpected_builder_failure_is_fail_closed(monkeypatch) -> None:
    from vnalpha.data_availability import deep_context_readiness

    monkeypatch.setattr(
        deep_context_readiness, "get_market_regime_as_of", lambda *_args: None
    )
    monkeypatch.setattr(
        deep_context_readiness, "get_latest_market_regime", lambda *_args: None
    )
    monkeypatch.setattr(
        deep_context_readiness,
        "build_market_regime",
        lambda *_args: (_ for _ in ()).throw(TypeError("unexpected")),
    )

    artifacts = evaluate_context_readiness(
        ContextReadinessInput(
            conn=duckdb.connect(),
            symbol="FPT",
            resolved_date="2026-07-10",
            market_regime_requirement=ContextRequirement.REQUIRED,
            sector_strength_requirement=ContextRequirement.NOT_REQUESTED,
        )
    )

    assert artifacts[0].error_code == ContextIssue.CONTEXT_BUILD_FAILED.value


def test_invalid_requirement_does_not_query_or_build_context(monkeypatch) -> None:
    from vnalpha.data_availability import deep_context_readiness

    def unexpected(*_args):
        raise AssertionError("invalid requirements must fail before context access")

    monkeypatch.setattr(deep_context_readiness, "get_market_regime_as_of", unexpected)
    monkeypatch.setattr(deep_context_readiness, "build_market_regime", unexpected)

    artifacts = evaluate_context_readiness(
        ContextReadinessInput(
            conn=duckdb.connect(),
            symbol="FPT",
            resolved_date="2026-07-10",
            market_regime_requirement=ContextRequirement.INVALID,
            sector_strength_requirement=ContextRequirement.NOT_REQUESTED,
        )
    )

    assert artifacts[0].error_code == ContextIssue.INVALID_CONTEXT_REQUIREMENT.value

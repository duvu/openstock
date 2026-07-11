from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner


def test_eval_research_answers_when_help_requested_is_registered_at_root() -> None:
    # Given: the public vnalpha CLI shim
    from vnalpha.cli import app

    # When: a user requests the eval command help
    result = CliRunner().invoke(app, ["eval", "research-answers", "--help"])

    # Then: the grouped evaluator namespace is reachable from the real entry point
    assert result.exit_code == 0
    assert "--ci" in result.output


def test_eval_research_answers_when_ci_has_failures_exits_one(
    monkeypatch,
) -> None:
    # Given: the CLI module's imported runner returns a deterministic failure report
    from vnalpha.evals.report import EvaluationRunReport, RunFailure

    def _failed_report() -> EvaluationRunReport:
        return EvaluationRunReport(
            source_count=0,
            evaluations=(),
            failures=(
                RunFailure(
                    path=Path("research_answers/fail.yaml"),
                    case_id="fail_case",
                    check_name="policy",
                    expected="safe answer",
                    actual="buy now",
                ),
            ),
        )

    monkeypatch.setattr("vnalpha.cli_app.eval.run_golden_corpus", _failed_report)
    from vnalpha.cli import app

    # When: CI invokes the fixed corpus command
    result = CliRunner().invoke(app, ["eval", "research-answers", "--ci"])

    # Then: output is rendered and CI receives an explicit failure status
    assert result.exit_code == 1
    assert "case=fail_case" in result.output
    assert "failures=1" in result.output


def test_eval_research_answers_when_standard_run_has_failures_does_not_force_exit(
    monkeypatch,
) -> None:
    # Given: the same failed report at the command's runner import location
    from vnalpha.evals.report import EvaluationRunReport, RunFailure

    def _failed_report() -> EvaluationRunReport:
        return EvaluationRunReport(
            source_count=0,
            evaluations=(),
            failures=(
                RunFailure(
                    path=Path("research_answers/fail.yaml"),
                    case_id="fail_case",
                    check_name="policy",
                    expected="safe answer",
                    actual="buy now",
                ),
            ),
        )

    monkeypatch.setattr("vnalpha.cli_app.eval.run_golden_corpus", _failed_report)
    from vnalpha.cli import app

    # When: a human runs the same fixed corpus without CI mode
    result = CliRunner().invoke(app, ["eval", "research-answers"])

    # Then: the report remains visible without a forced nonzero exit
    assert result.exit_code == 0
    assert "case=fail_case" in result.output

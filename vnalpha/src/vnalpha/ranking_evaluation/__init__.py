"""RankingRun baseline evaluation (issue #261).

Produces reproducible evidence about whether the packaged RankingPolicy adds
information beyond simple baselines (momentum-only, equal-weight, unfiltered)
over the identical point-in-time eligible population, without changing policy
weights automatically.
"""

from vnalpha.ranking_evaluation.evaluator import (
    MIN_SUFFICIENT_SAMPLE,
    RankingEvaluationResult,
    StrategyMetrics,
    evaluate_ranking_run,
    get_ranking_evaluation,
)

__all__ = [
    "MIN_SUFFICIENT_SAMPLE",
    "RankingEvaluationResult",
    "StrategyMetrics",
    "evaluate_ranking_run",
    "get_ranking_evaluation",
]

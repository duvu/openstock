from __future__ import annotations

from typing import TypeAlias

from vnalpha.research_models.models import (
    MarketRegimeSnapshot,
    ResearchAnswerAudit,
    ResearchScenarioPlan,
    SectorStrengthSnapshot,
    SetupAnalysis,
    SetupEvidenceSnapshot,
    ShortlistCandidate,
    ShortlistDecisionReport,
    SymbolLevelSnapshot,
)

ResearchModel: TypeAlias = (
    MarketRegimeSnapshot
    | SectorStrengthSnapshot
    | SymbolLevelSnapshot
    | SetupAnalysis
    | ShortlistCandidate
    | ShortlistDecisionReport
    | ResearchScenarioPlan
    | SetupEvidenceSnapshot
    | ResearchAnswerAudit
)

PERSISTED_RESEARCH_MODEL_TYPES = (
    MarketRegimeSnapshot,
    SectorStrengthSnapshot,
    SymbolLevelSnapshot,
    SetupAnalysis,
    ShortlistCandidate,
    ShortlistDecisionReport,
    ResearchScenarioPlan,
    SetupEvidenceSnapshot,
    ResearchAnswerAudit,
)

__all__ = ["PERSISTED_RESEARCH_MODEL_TYPES", "ResearchModel"]

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any, cast

import duckdb

from vnalpha.research_models.contracts import ResearchModel
from vnalpha.research_models.models import (
    MarketRegimeSnapshot,
    ResearchAnswerAudit,
    ResearchScenarioPlan,
    SectorStrengthSnapshot,
    SetupAnalysis,
    SetupEvidenceSnapshot,
    ShortlistCandidate,
    SymbolLevelSnapshot,
)
from vnalpha.research_models.validators import validate_research_model


@dataclass(frozen=True, slots=True)
class _RecordSpec:
    model_type: type[ResearchModel]
    table_name: str
    identifier: str
    symbol_attribute: str | None = None
    scope_attribute: str | None = None


_RECORD_SPECS = {
    MarketRegimeSnapshot: _RecordSpec(
        MarketRegimeSnapshot,
        "research_market_regime_snapshot",
        "market_regime_snapshot_id",
    ),
    SectorStrengthSnapshot: _RecordSpec(
        SectorStrengthSnapshot,
        "research_sector_strength_snapshot",
        "sector_strength_snapshot_id",
    ),
    SymbolLevelSnapshot: _RecordSpec(
        SymbolLevelSnapshot,
        "research_symbol_level_snapshot",
        "symbol_level_snapshot_id",
        "symbol",
    ),
    SetupAnalysis: _RecordSpec(
        SetupAnalysis,
        "research_setup_analysis",
        "setup_analysis_id",
        "symbol",
    ),
    ShortlistCandidate: _RecordSpec(
        ShortlistCandidate,
        "research_shortlist_candidate",
        "shortlist_candidate_id",
        "symbol",
        "shortlist_run_id",
    ),
    ResearchScenarioPlan: _RecordSpec(
        ResearchScenarioPlan,
        "research_scenario_plan",
        "scenario_plan_id",
        "symbol",
    ),
    SetupEvidenceSnapshot: _RecordSpec(
        SetupEvidenceSnapshot,
        "research_setup_evidence_snapshot",
        "setup_evidence_snapshot_id",
        None,
        "setup_type",
    ),
}

_TUPLE_FIELDS = {
    MarketRegimeSnapshot: ("caveats",),
    SectorStrengthSnapshot: ("caveats",),
    SymbolLevelSnapshot: (
        "support_levels",
        "resistance_levels",
        "pivot_levels",
        "source_bar_refs",
        "caveats",
    ),
    SetupAnalysis: ("caveats",),
    ShortlistCandidate: (
        "why_shortlisted",
        "why_restrained",
        "confirmation_conditions",
        "invalidation_conditions",
        "caveats",
    ),
    ResearchScenarioPlan: (
        "confirmation_conditions",
        "invalidation_conditions",
        "checklist",
        "caveats",
    ),
    SetupEvidenceSnapshot: ("caveats",),
    ResearchAnswerAudit: (
        "tools_used",
        "artifact_refs",
        "missing_data",
        "caveats",
    ),
}

_AUDIT_SELECT = (
    "SELECT research_answer_audit_id, assistant_session_id, "
    "COALESCE(research_session_id, 'legacy:unknown'), created_at::VARCHAR, "
    "intent, tools_json, artifact_refs_json, dataset_freshness_json, "
    "groundedness_json, policy_json, COALESCE(missing_data_json, '[]'), "
    "caveats_json, correlation_id FROM research_answer_audit"
)


class ResearchModelsRepository:
    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn

    @staticmethod
    def validate(model: ResearchModel) -> None:
        validate_research_model(model)

    @staticmethod
    def record_id(model: ResearchModel) -> str:
        if isinstance(model, ResearchAnswerAudit):
            return model.answer_audit_id
        spec = _spec_for(type(model))
        return str(getattr(model, spec.identifier))

    def create(self, model: ResearchModel) -> None:
        self.validate(model)
        if isinstance(model, ResearchAnswerAudit):
            self._upsert_answer_audit(model)
            return
        spec = _spec_for(type(model))
        self._upsert_record(spec, model)

    def get(
        self, model_type: type[ResearchModel], record_id: str
    ) -> ResearchModel | None:
        if model_type is ResearchAnswerAudit:
            return self.get_research_answer_audit(record_id)
        spec = _spec_for(model_type)
        row = self._conn.execute(
            f"SELECT payload_json FROM {spec.table_name} WHERE {spec.identifier} = ?",
            [record_id],
        ).fetchone()
        return None if row is None else _model_from_payload(spec.model_type, row[0])

    def list(
        self, model_type: type[ResearchModel], *, limit: int = 100
    ) -> list[ResearchModel]:
        if model_type is ResearchAnswerAudit:
            return self.list_research_answer_audits(limit=limit)
        spec = _spec_for(model_type)
        rows = self._conn.execute(
            f"SELECT payload_json FROM {spec.table_name} "
            "ORDER BY as_of_date DESC, created_at DESC LIMIT ?",
            [max(1, min(limit, 500))],
        ).fetchall()
        return [_model_from_payload(spec.model_type, row[0]) for row in rows]

    def create_market_regime_snapshot(self, model: MarketRegimeSnapshot) -> None:
        self.create(model)

    def get_market_regime_snapshot(self, record_id: str) -> MarketRegimeSnapshot | None:
        return cast(
            MarketRegimeSnapshot | None, self.get(MarketRegimeSnapshot, record_id)
        )

    def list_market_regime_snapshots(
        self, *, limit: int = 100
    ) -> list[MarketRegimeSnapshot]:
        return cast(
            list[MarketRegimeSnapshot], self.list(MarketRegimeSnapshot, limit=limit)
        )

    def create_sector_strength_snapshot(self, model: SectorStrengthSnapshot) -> None:
        self.create(model)

    def get_sector_strength_snapshot(
        self, record_id: str
    ) -> SectorStrengthSnapshot | None:
        return cast(
            SectorStrengthSnapshot | None, self.get(SectorStrengthSnapshot, record_id)
        )

    def list_sector_strength_snapshots(
        self, *, limit: int = 100
    ) -> list[SectorStrengthSnapshot]:
        return cast(
            list[SectorStrengthSnapshot], self.list(SectorStrengthSnapshot, limit=limit)
        )

    def create_symbol_level_snapshot(self, model: SymbolLevelSnapshot) -> None:
        self.create(model)

    def get_symbol_level_snapshot(self, record_id: str) -> SymbolLevelSnapshot | None:
        return cast(
            SymbolLevelSnapshot | None, self.get(SymbolLevelSnapshot, record_id)
        )

    def list_symbol_level_snapshots(
        self, *, limit: int = 100
    ) -> list[SymbolLevelSnapshot]:
        return cast(
            list[SymbolLevelSnapshot], self.list(SymbolLevelSnapshot, limit=limit)
        )

    def create_setup_analysis(self, model: SetupAnalysis) -> None:
        self.create(model)

    def get_setup_analysis(self, record_id: str) -> SetupAnalysis | None:
        return cast(SetupAnalysis | None, self.get(SetupAnalysis, record_id))

    def list_setup_analyses(self, *, limit: int = 100) -> list[SetupAnalysis]:
        return cast(list[SetupAnalysis], self.list(SetupAnalysis, limit=limit))

    def create_shortlist_candidate(self, model: ShortlistCandidate) -> None:
        self.create(model)

    def get_shortlist_candidate(self, record_id: str) -> ShortlistCandidate | None:
        return cast(ShortlistCandidate | None, self.get(ShortlistCandidate, record_id))

    def list_shortlist_candidates(
        self, *, limit: int = 100
    ) -> list[ShortlistCandidate]:
        return cast(
            list[ShortlistCandidate], self.list(ShortlistCandidate, limit=limit)
        )

    def create_research_scenario_plan(self, model: ResearchScenarioPlan) -> None:
        self.create(model)

    def get_research_scenario_plan(self, record_id: str) -> ResearchScenarioPlan | None:
        return cast(
            ResearchScenarioPlan | None, self.get(ResearchScenarioPlan, record_id)
        )

    def list_research_scenario_plans(
        self, *, limit: int = 100
    ) -> list[ResearchScenarioPlan]:
        return cast(
            list[ResearchScenarioPlan], self.list(ResearchScenarioPlan, limit=limit)
        )

    def create_setup_evidence_snapshot(self, model: SetupEvidenceSnapshot) -> None:
        self.create(model)

    def get_setup_evidence_snapshot(
        self, record_id: str
    ) -> SetupEvidenceSnapshot | None:
        return cast(
            SetupEvidenceSnapshot | None, self.get(SetupEvidenceSnapshot, record_id)
        )

    def list_setup_evidence_snapshots(
        self, *, limit: int = 100
    ) -> list[SetupEvidenceSnapshot]:
        return cast(
            list[SetupEvidenceSnapshot], self.list(SetupEvidenceSnapshot, limit=limit)
        )

    def create_research_answer_audit(self, model: ResearchAnswerAudit) -> None:
        self.create(model)

    def get_research_answer_audit(self, record_id: str) -> ResearchAnswerAudit | None:
        row = self._conn.execute(
            f"{_AUDIT_SELECT} WHERE research_answer_audit_id = ?",
            [record_id],
        ).fetchone()
        return None if row is None else _answer_audit_from_row(row)

    def list_research_answer_audits(
        self, *, limit: int = 100
    ) -> list[ResearchAnswerAudit]:
        rows = self._conn.execute(
            f"{_AUDIT_SELECT} ORDER BY created_at DESC LIMIT ?",
            [max(1, min(limit, 500))],
        ).fetchall()
        return [_answer_audit_from_row(row) for row in rows]

    def _upsert_record(self, spec: _RecordSpec, model: ResearchModel) -> None:
        payload = _model_payload(model)
        values = [
            getattr(model, spec.identifier),
            model.as_of_date,
            getattr(model, spec.symbol_attribute) if spec.symbol_attribute else None,
            getattr(model, spec.scope_attribute) if spec.scope_attribute else None,
            model.correlation_id,
            model.quality_status,
            model.created_at,
            payload,
        ]
        self._conn.execute(
            (
                f"INSERT INTO {spec.table_name} ({spec.identifier}, as_of_date, symbol, "
                "scope_id, correlation_id, quality_status, created_at, payload_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                f"ON CONFLICT ({spec.identifier}) DO UPDATE SET "
                "as_of_date = excluded.as_of_date, symbol = excluded.symbol, "
                "scope_id = excluded.scope_id, correlation_id = excluded.correlation_id, "
                "quality_status = excluded.quality_status, created_at = excluded.created_at, "
                "payload_json = excluded.payload_json"
            ),
            values,
        )

    def _upsert_answer_audit(self, model: ResearchAnswerAudit) -> None:
        self._conn.execute(
            (
                "INSERT INTO research_answer_audit (research_answer_audit_id, "
                "assistant_session_id, research_session_id, created_at, intent, tools_json, "
                "artifact_refs_json, dataset_freshness_json, groundedness_status, "
                "groundedness_json, policy_status, policy_json, missing_data_json, "
                "caveats_json, correlation_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (research_answer_audit_id) DO UPDATE SET "
                "assistant_session_id = excluded.assistant_session_id, "
                "research_session_id = excluded.research_session_id, "
                "created_at = excluded.created_at, intent = excluded.intent, "
                "tools_json = excluded.tools_json, artifact_refs_json = excluded.artifact_refs_json, "
                "dataset_freshness_json = excluded.dataset_freshness_json, "
                "groundedness_status = excluded.groundedness_status, "
                "groundedness_json = excluded.groundedness_json, "
                "policy_status = excluded.policy_status, policy_json = excluded.policy_json, "
                "missing_data_json = excluded.missing_data_json, "
                "caveats_json = excluded.caveats_json, correlation_id = excluded.correlation_id"
            ),
            [
                model.answer_audit_id,
                model.assistant_session_id,
                model.research_session_id,
                model.created_at,
                model.intent,
                _dump(model.tools_used),
                _dump(model.artifact_refs),
                _dump(model.dataset_freshness),
                str(model.groundedness_result.get("status", "UNKNOWN")),
                _dump(model.groundedness_result),
                str(model.policy_result.get("status", "UNKNOWN")),
                _dump(model.policy_result),
                _dump(model.missing_data),
                _dump(model.caveats),
                model.correlation_id,
            ],
        )


def _spec_for(model_type: type[ResearchModel]) -> _RecordSpec:
    try:
        return _RECORD_SPECS[model_type]
    except KeyError as exc:
        raise TypeError(f"Unsupported research model: {model_type!r}") from exc


def _model_payload(model: ResearchModel) -> str:
    return _dump(asdict(model))


def _model_from_payload(model_type: type[ResearchModel], payload: str) -> ResearchModel:
    values: dict[str, Any] = json.loads(payload)
    values["as_of_date"] = date.fromisoformat(values["as_of_date"])
    values["created_at"] = datetime.fromisoformat(values["created_at"])
    for field_name in _TUPLE_FIELDS[model_type]:
        values[field_name] = tuple(values[field_name])
    return model_type(**values)


def _answer_audit_from_row(row: tuple[Any, ...]) -> ResearchAnswerAudit:
    return ResearchAnswerAudit(
        answer_audit_id=row[0],
        assistant_session_id=row[1],
        research_session_id=row[2],
        created_at=datetime.fromisoformat(row[3]),
        intent=row[4],
        tools_used=tuple(_load(row[5])),
        artifact_refs=tuple(_load(row[6])),
        dataset_freshness=_load(row[7]),
        groundedness_result=_load(row[8]),
        policy_result=_load(row[9]),
        missing_data=tuple(_load(row[10])),
        caveats=tuple(_load(row[11])),
        correlation_id=row[12] or "legacy:unknown",
    )


def _dump(value: object) -> str:
    return json.dumps(value, default=str, ensure_ascii=False, sort_keys=True)


def _load(value: str | None) -> Any:
    return json.loads(value) if value else {}


__all__ = ["ResearchModelsRepository"]

"""Post-analysis projection of validated evidence into symbol knowledge.

Issue #164 requires that after a successful chat deep-analysis turn — one whose
answer already passed groundedness and research-policy validation — the
deterministic evidence the turn produced is projected into the per-symbol
knowledge base. This module is that projector.

It never introduces a second knowledge store: it reuses the existing
``symbol_memory`` adapters, ``SymbolMemoryIngestionService`` (idempotent,
supersession-aware, source-grounded) and ``SymbolMemoryCompactionService`` so a
projected turn behaves exactly like ``generate_watchlist``'s existing
candidate-score projection. Evidence is read back from the persisted warehouse
rows the analysis produced, so the ``has_persisted_evidence`` gate can confirm
each claim against a real artifact; raw chat text and model prose can never
enter memory.

Projection is best-effort and fail-open for the answer: a failure is captured
and returned to the caller as a caveat, never raised, because the analysis
answer has already been validated and must not regress.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from datetime import date as DateType

import duckdb

from vnalpha.core.logging import get_logger
from vnalpha.symbol_memory.adapters import (
    CandidateScoreSnapshot,
    FeatureSnapshot,
    candidate_score_evidence,
    canonical_ohlcv_basis_evidence,
    feature_snapshot_evidence,
    symbol_identity_evidence,
)
from vnalpha.symbol_memory.compaction import SymbolMemoryCompactionService
from vnalpha.symbol_memory.context_snapshots import (
    load_canonical_ohlcv_basis,
    load_symbol_identity,
)
from vnalpha.symbol_memory.ingestion import (
    MemoryEvidence,
    MemoryIngestionError,
    MemoryIngestionResult,
    SymbolMemoryIngestionService,
)
from vnalpha.symbol_memory.paths import normalize_symbol
from vnalpha.symbol_memory.repository import SymbolMemoryRepository

logger = get_logger("symbol_memory.projection")

_DEEP_ANALYSIS_TOOL = "analysis.deep_symbol"


@dataclass(frozen=True, slots=True)
class ProjectedClaim:
    """One projected claim summarised for the answer trace."""

    claim_type: str
    predicate: str
    source_ref: str
    created: bool


@dataclass(frozen=True, slots=True)
class EvidenceProjectionResult:
    """Outcome of one post-analysis projection turn."""

    symbol: str | None
    as_of_date: str | None
    projected: tuple[ProjectedClaim, ...]
    warnings: tuple[str, ...]

    def to_trace_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "as_of_date": self.as_of_date,
            "projected": [
                {
                    "claim_type": claim.claim_type,
                    "predicate": claim.predicate,
                    "source_ref": claim.source_ref,
                    "created": claim.created,
                }
                for claim in self.projected
            ],
            "warnings": list(self.warnings),
        }


def project_analysis_evidence(
    conn: duckdb.DuckDBPyConnection,
    tool_outputs: dict[str, object],
    *,
    correlation_id: str,
    memory_root=None,
) -> EvidenceProjectionResult:
    """Project a successful deep-analysis turn's validated evidence into memory.

    Args:
        conn: Live warehouse connection.
        tool_outputs: The executed plan's tool outputs (step_id -> output).
        correlation_id: The turn's correlation chain, linked onto each claim.
        memory_root: Optional knowledge-root override; ``None`` resolves the
            configured default, matching the scoring projection path.

    Returns:
        A typed :class:`EvidenceProjectionResult`. Never raises for a projection
        failure — failures are returned as warnings so a validated answer never
        regresses.
    """

    analysis = _find_deep_analysis_payload(tool_outputs)
    if analysis is None:
        return EvidenceProjectionResult(None, None, (), ())

    symbol_raw = analysis.get("symbol")
    as_of_raw = analysis.get("as_of_date")
    if not isinstance(symbol_raw, str) or not symbol_raw.strip():
        return EvidenceProjectionResult(None, None, (), ())
    symbol = normalize_symbol(symbol_raw)
    try:
        as_of_date = _coerce_date(as_of_raw)
    except (TypeError, ValueError):
        return EvidenceProjectionResult(
            symbol, None, (), ("Analysis as-of date was not projectable.",)
        )

    requested_raw = analysis.get("requested_date")
    requested_date = (
        requested_raw.strip()
        if isinstance(requested_raw, str) and requested_raw.strip()
        else as_of_date.isoformat()
    )
    evidences = _build_evidences(
        conn,
        symbol,
        as_of_date,
        requested_date,
        correlation_id,
    )
    predicates = {evidence.predicate for evidence in evidences}
    missing_required = [
        label
        for predicate, label in (
            ("security_identity", "point-in-time security identity"),
            ("canonical_ohlcv_basis", "verified canonical OHLCV basis"),
        )
        if predicate not in predicates
    ]
    if missing_required:
        return EvidenceProjectionResult(
            symbol,
            as_of_date.isoformat(),
            (),
            (
                "Required minimal evidence was unavailable: "
                + ", ".join(missing_required)
                + ".",
            ),
        )
    if not evidences:
        return EvidenceProjectionResult(symbol, as_of_date.isoformat(), (), ())

    repository = SymbolMemoryRepository(conn)
    ingestion = SymbolMemoryIngestionService(repository)
    compaction = SymbolMemoryCompactionService(repository, memory_root)

    def ingest_all() -> list[MemoryIngestionResult]:
        return [ingestion.ingest_evidence(evidence) for evidence in evidences]

    try:
        results, _ = compaction.mutate_and_compact(symbol, ingest_all)
    except (MemoryIngestionError, OSError, ValueError, duckdb.Error) as exc:
        logger.warning(
            "Evidence projection failed for symbol=%s: %s",
            symbol,
            exc,
        )
        return EvidenceProjectionResult(
            symbol,
            as_of_date.isoformat(),
            (),
            (f"Could not project validated evidence for {symbol}.",),
        )

    projected = [
        ProjectedClaim(
            claim_type=evidence.claim_type,
            predicate=evidence.predicate,
            source_ref=evidence.source_ref,
            created=result.created,
        )
        for evidence, result in zip(evidences, results, strict=True)
    ]
    return EvidenceProjectionResult(
        symbol,
        as_of_date.isoformat(),
        tuple(projected),
        (),
    )


def _find_deep_analysis_payload(
    tool_outputs: dict[str, object],
) -> dict[str, object] | None:
    """Return the deep-symbol analysis data payload from the plan outputs."""
    for output in tool_outputs.values():
        data = output.get("data") if isinstance(output, dict) else None
        if isinstance(data, dict) and data.get("tool") == _DEEP_ANALYSIS_TOOL:
            return data
    return None


def _build_evidences(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    as_of_date: DateType,
    requested_date: str,
    correlation_id: str,
) -> list[MemoryEvidence]:
    """Read persisted rows and build grounded evidence for the allowlist."""
    observed_at = datetime.now(UTC)
    evidences: list[MemoryEvidence] = []

    identity = load_symbol_identity(conn, symbol, as_of_date)
    if identity is not None:
        evidences.append(
            symbol_identity_evidence(
                identity,
                correlation_id=correlation_id,
                observed_at=observed_at,
                as_of_date=as_of_date,
            )
        )

    basis = load_canonical_ohlcv_basis(
        conn,
        symbol,
        requested_date,
        as_of_date,
    )
    if basis is not None:
        evidences.append(
            canonical_ohlcv_basis_evidence(
                basis,
                correlation_id=correlation_id,
                observed_at=observed_at,
                as_of_date=as_of_date,
            )
        )

    candidate = _read_candidate_score(conn, symbol, as_of_date)
    if candidate is not None:
        evidences.append(
            candidate_score_evidence(
                CandidateScoreSnapshot(
                    symbol=symbol,
                    as_of_date=as_of_date,
                    score=float(candidate["score"]),
                    candidate_class=str(candidate["candidate_class"]),
                    setup_type=(
                        None
                        if candidate["setup_type"] is None
                        else str(candidate["setup_type"])
                    ),
                    correlation_id=correlation_id,
                    persisted_at=observed_at,
                    scoring_policy_id=str(candidate["scoring_policy_id"]),
                    scoring_policy_hash=str(candidate["scoring_policy_hash"]),
                )
            )
        )

    feature_status = _read_feature_status(conn, symbol, as_of_date)
    if feature_status is not None:
        evidences.append(
            feature_snapshot_evidence(
                FeatureSnapshot(
                    symbol=symbol,
                    as_of_date=as_of_date,
                    quality_status=feature_status,
                    source_ref=f"feature_snapshot:{symbol}:{as_of_date.isoformat()}",
                    correlation_id=correlation_id,
                    persisted_at=observed_at,
                )
            )
        )
    return evidences


def _read_candidate_score(
    conn: duckdb.DuckDBPyConnection, symbol: str, as_of_date: DateType
) -> dict[str, object] | None:
    row = conn.execute(
        "SELECT score, candidate_class, setup_type, scoring_policy_id, "
        "scoring_policy_hash "
        "FROM candidate_score WHERE symbol = ? AND date = ?",
        [symbol, as_of_date],
    ).fetchone()
    if row is None or row[0] is None or row[3] is None or row[4] is None:
        return None
    return {
        "score": row[0],
        "candidate_class": row[1],
        "setup_type": row[2],
        "scoring_policy_id": row[3],
        "scoring_policy_hash": row[4],
    }


def _read_feature_status(
    conn: duckdb.DuckDBPyConnection, symbol: str, as_of_date: DateType
) -> str | None:
    row = conn.execute(
        "SELECT feature_data_status "
        "FROM feature_snapshot WHERE symbol = ? AND date = ?",
        [symbol, as_of_date],
    ).fetchone()
    if row is None or row[0] is None:
        return None
    return str(row[0])


def _coerce_date(value: object) -> DateType:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, DateType):
        return value
    if isinstance(value, str):
        return DateType.fromisoformat(value)
    raise TypeError(f"Unsupported as-of date value: {value!r}")


__all__ = [
    "EvidenceProjectionResult",
    "ProjectedClaim",
    "project_analysis_evidence",
]

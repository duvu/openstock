from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Mapping

import duckdb

from vnalpha.research_intelligence.models import (
    MarketRegimeSnapshot,
    SectorStrengthSnapshot,
)
from vnalpha.research_intelligence.policy import (
    PRODUCTION_SECTOR_STRENGTH_POLICY,
    SectorStrengthPolicy,
)
from vnalpha.research_intelligence.sector import _rankability_reasons
from vnalpha.research_intelligence.sector_context import (
    FeatureRow,
    SectorAggregate,
    load_sector_input_context,
)
from vnalpha.symbol_memory.entity_compaction import EntityMemoryCompactionService
from vnalpha.symbol_memory.lifecycle import SymbolMemoryLifecycleService
from vnalpha.symbol_memory.models import (
    ClaimOrigin,
    ClaimStatus,
    MemoryClaim,
    MemoryEntity,
    MemoryEntityType,
    MemoryEvent,
)
from vnalpha.symbol_memory.repository import SymbolMemoryRepository
from vnalpha.warehouse.point_in_time import history_is_available, resolve_universe
from vnalpha.warehouse.repositories import (
    get_market_regime_as_of,
    get_sector_strength_as_of,
)


class GroupType(StrEnum):
    SECTOR = "SECTOR"
    INDUSTRY = "INDUSTRY"
    ASSET_CLASS = "ASSET_CLASS"


@dataclass(frozen=True, slots=True)
class GroupContextSnapshot:
    as_of_date: date
    group_type: GroupType
    entity_id: str
    group_code: str
    group_name: str
    taxonomy_name: str
    taxonomy_version: str
    rank: int
    member_count: int
    eligible_count: int
    median_return20: float
    median_return60: float
    median_rs20_vs_vnindex: float
    median_rs60_vs_vnindex: float
    pct_above_ma20: float
    pct_above_ma50: float
    leadership_count: int
    leadership_concentration: float
    score: float
    rotation: str
    coverage: float
    unclassified_count: int
    quality: str
    caveats: tuple[str, ...]
    lineage: Mapping[str, str]
    methodology_version: str
    source_hash: str
    generated_at: datetime


@dataclass(frozen=True, slots=True)
class GroupContextBuildResult:
    snapshots: tuple[GroupContextSnapshot, ...]
    caveats: tuple[str, ...]
    unclassified_counts: Mapping[GroupType, int]


@dataclass(frozen=True, slots=True)
class GroupProjectionResult:
    claims_created: int
    claims_superseded: int
    cards_compacted: int
    failed_entities: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Classification:
    symbol: str
    security_type: str
    sector_code: str | None
    sector_name: str | None
    industry_code: str | None
    industry_name: str | None
    taxonomy_name: str
    taxonomy_version: str


def build_group_context(
    conn: duckdb.DuckDBPyConnection,
    as_of_date: date,
    *,
    generated_at: datetime | None = None,
    policy: SectorStrengthPolicy = PRODUCTION_SECTOR_STRENGTH_POLICY,
) -> GroupContextBuildResult:
    timestamp = generated_at or datetime.now(UTC)
    classifications, membership_lineage = _classifications(conn, as_of_date)
    input_context = load_sector_input_context(conn, as_of_date, policy=policy)
    eligible_by_symbol = {row.symbol: row for row in input_context.eligible_rows}
    caveats: list[str] = []
    unclassified_counts: dict[GroupType, int] = {}
    snapshots: list[GroupContextSnapshot] = []

    sector_snapshots = get_sector_strength_as_of(conn, as_of_date)
    sector_rows, sector_unclassified, sector_caveats = _sector_rows(
        sector_snapshots,
        classifications,
        membership_lineage,
        timestamp,
    )
    snapshots.extend(sector_rows)
    unclassified_counts[GroupType.SECTOR] = sector_unclassified
    caveats.extend(sector_caveats)

    for group_type in (GroupType.INDUSTRY, GroupType.ASSET_CLASS):
        built, unclassified, group_caveats = _aggregate_group(
            group_type,
            classifications,
            eligible_by_symbol,
            as_of_date,
            membership_lineage,
            timestamp,
            policy,
        )
        snapshots.extend(built)
        unclassified_counts[group_type] = unclassified
        caveats.extend(group_caveats)

    persisted = tuple(
        sorted(
            snapshots,
            key=lambda item: (item.group_type.value, item.rank, item.entity_id),
        )
    )
    _replace_snapshots(conn, as_of_date, persisted)
    return GroupContextBuildResult(
        persisted,
        tuple(caveats),
        dict(unclassified_counts),
    )


def list_group_context(
    conn: duckdb.DuckDBPyConnection,
    as_of_date: date,
    group_type: GroupType | None = None,
) -> tuple[GroupContextSnapshot, ...]:
    values: list[object] = [as_of_date]
    where = "WHERE as_of_date = ?"
    if group_type is not None:
        where += " AND group_type = ?"
        values.append(group_type.value)
    rows = conn.execute(
        "SELECT as_of_date, group_type, entity_id, group_code, group_name, "
        "taxonomy_name, taxonomy_version, rank, member_count, eligible_count, "
        "median_return20, median_return60, median_rs20_vs_vnindex, "
        "median_rs60_vs_vnindex, pct_above_ma20, pct_above_ma50, "
        "leadership_count, leadership_concentration, score, rotation, coverage, "
        "unclassified_count, quality, caveats_json, lineage_json, methodology_version, "
        f"source_hash, generated_at FROM group_context_snapshot {where} "
        "ORDER BY group_type, rank, entity_id",
        values,
    ).fetchall()
    return tuple(_snapshot_from_row(row) for row in rows)


class GroupContextProjector:
    def __init__(
        self,
        conn: duckdb.DuckDBPyConnection,
        *,
        memory_root: Path | None = None,
    ) -> None:
        self.repository = SymbolMemoryRepository(conn)
        self.lifecycle = SymbolMemoryLifecycleService(self.repository)
        self.compaction = EntityMemoryCompactionService(self.repository, memory_root)

    def project(
        self, as_of_date: date, *, correlation_id: str
    ) -> GroupProjectionResult:
        created = 0
        superseded = 0
        compacted = 0
        failed: list[str] = []
        market = get_market_regime_as_of(self.repository.connection, as_of_date)
        if market is not None:
            market_entity = MemoryEntity.market()
            try:
                market_created, market_superseded = self._project_market(
                    market_entity, market, correlation_id
                )
                created += market_created
                superseded += market_superseded
                if market_created and self.compaction.compact(market_entity).changed:
                    compacted += 1
            except (duckdb.Error, OSError, ValueError):
                failed.append("MARKET:VN")
        for snapshot in list_group_context(self.repository.connection, as_of_date):
            entity = _snapshot_entity(snapshot)
            try:
                claim_created, claim_superseded = self._project_snapshot(
                    entity, snapshot, correlation_id
                )
                created += claim_created
                superseded += claim_superseded
                if claim_created and self.compaction.compact(entity).changed:
                    compacted += 1
            except (duckdb.Error, OSError, ValueError):
                failed.append(f"{entity.entity_type.value}:{entity.entity_id}")
        return GroupProjectionResult(created, superseded, compacted, tuple(failed))

    def _project_market(
        self,
        entity: MemoryEntity,
        snapshot: MarketRegimeSnapshot,
        correlation_id: str,
    ) -> tuple[int, int]:
        value = {
            "regime": snapshot.regime,
            "trend": snapshot.trend,
            "volatility": snapshot.volatility,
            "breadth_coverage": snapshot.breadth_coverage,
            "quality": snapshot.quality,
            "caveats": list(snapshot.caveats),
            "unit": "regime_state_and_coverage_ratio",
            "meaning": "validated Vietnamese market regime and data coverage",
        }
        active = self.repository.list_entity_claims(
            entity, statuses=(ClaimStatus.ACTIVE,), limit=1_000
        )
        if any(
            claim.claim_type == "market_context"
            and claim.predicate == "market_regime"
            and dict(claim.value) == value
            for claim in active
        ):
            return 0, 0
        payload = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
        identity = hashlib.sha256(
            f"{snapshot.as_of_date}:{snapshot.methodology_version}:{payload}".encode()
        ).hexdigest()
        source_ref = f"market_regime_snapshot:{snapshot.as_of_date.isoformat()}"
        event = MemoryEvent(
            event_id=f"market-context-event-{identity}",
            symbol=None,
            event_type="EVIDENCE_OBSERVED",
            evidence_ref=source_ref,
            content_hash=f"sha256:{identity}",
            observed_at=snapshot.generated_at,
            as_of_date=snapshot.as_of_date,
            origin=ClaimOrigin.VALIDATED_EVIDENCE,
            correlation_id=correlation_id,
            created_at=snapshot.generated_at,
            entity_type=entity.entity_type,
            entity_id=entity.entity_id,
        )
        claim = MemoryClaim(
            claim_id=f"market-context-claim-{identity}",
            symbol=None,
            claim_type="market_context",
            predicate="market_regime",
            value=value,
            status=ClaimStatus.ACTIVE,
            pinned=False,
            confidence=None,
            observed_at=snapshot.generated_at,
            as_of_date=snapshot.as_of_date,
            valid_from=snapshot.as_of_date,
            valid_until=None,
            origin=ClaimOrigin.VALIDATED_EVIDENCE,
            source_refs=(source_ref,),
            correlation_id=correlation_id,
            created_at=snapshot.generated_at,
            entity_type=entity.entity_type,
            entity_id=entity.entity_id,
        )
        before = sum(item.status is ClaimStatus.ACTIVE for item in active)
        with self.repository.transaction():
            persisted = self.repository.connection.execute(
                "SELECT 1 FROM market_regime_snapshot WHERE as_of_date = ? "
                "AND methodology_version = ?",
                [snapshot.as_of_date, snapshot.methodology_version],
            ).fetchone()
            if persisted is None:
                raise ValueError(
                    "Market memory source snapshot is no longer validated."
                )
            if not self.repository.append_event(event):
                return 0, 0
            accepted = self.lifecycle.accept(claim)
        after_active = self.repository.list_entity_claims(
            entity, statuses=(ClaimStatus.ACTIVE,), limit=1_000
        )
        superseded = max(0, before + 1 - len(after_active))
        return (1 if accepted.claim_id == claim.claim_id else 0), superseded

    def _project_snapshot(
        self,
        entity: MemoryEntity,
        snapshot: GroupContextSnapshot,
        correlation_id: str,
    ) -> tuple[int, int]:
        value = _memory_value(snapshot)
        active = self.repository.list_entity_claims(
            entity, statuses=(ClaimStatus.ACTIVE,), limit=1_000
        )
        if any(
            claim.claim_type == "group_context"
            and claim.predicate == "group_strength"
            and dict(claim.value) == value
            for claim in active
        ):
            return 0, 0
        identity = hashlib.sha256(
            f"{snapshot.source_hash}:{entity.entity_type.value}:{entity.entity_id}".encode()
        ).hexdigest()
        source_ref = (
            f"group_context_snapshot:{snapshot.as_of_date.isoformat()}:"
            f"{snapshot.group_type.value}:{snapshot.source_hash}"
        )
        observed_at = snapshot.generated_at
        event = MemoryEvent(
            event_id=f"group-context-event-{identity}",
            symbol=None,
            event_type="EVIDENCE_OBSERVED",
            evidence_ref=source_ref,
            content_hash=f"sha256:{identity}",
            observed_at=observed_at,
            as_of_date=snapshot.as_of_date,
            origin=ClaimOrigin.VALIDATED_EVIDENCE,
            correlation_id=correlation_id,
            created_at=observed_at,
            entity_type=entity.entity_type,
            entity_id=entity.entity_id,
        )
        claim = MemoryClaim(
            claim_id=f"group-context-claim-{identity}",
            symbol=None,
            claim_type="group_context",
            predicate="group_strength",
            value=value,
            status=ClaimStatus.ACTIVE,
            pinned=False,
            confidence=None,
            observed_at=observed_at,
            as_of_date=snapshot.as_of_date,
            valid_from=snapshot.as_of_date,
            valid_until=None,
            origin=ClaimOrigin.VALIDATED_EVIDENCE,
            source_refs=(source_ref,),
            correlation_id=correlation_id,
            created_at=observed_at,
            entity_type=entity.entity_type,
            entity_id=entity.entity_id,
        )
        before = sum(item.status is ClaimStatus.ACTIVE for item in active)
        with self.repository.transaction():
            persisted = self.repository.connection.execute(
                "SELECT 1 FROM group_context_snapshot WHERE as_of_date = ? "
                "AND group_type = ? AND entity_id = ? AND source_hash = ?",
                [
                    snapshot.as_of_date,
                    snapshot.group_type.value,
                    snapshot.entity_id,
                    snapshot.source_hash,
                ],
            ).fetchone()
            if persisted is None:
                raise ValueError("Group memory source snapshot is no longer validated.")
            if not self.repository.append_event(event):
                return 0, 0
            accepted = self.lifecycle.accept(claim)
        after_active = self.repository.list_entity_claims(
            entity, statuses=(ClaimStatus.ACTIVE,), limit=1_000
        )
        superseded = max(0, before + 1 - len(after_active))
        return (1 if accepted.claim_id == claim.claim_id else 0), superseded


def _classifications(
    conn: duckdb.DuckDBPyConnection, as_of_date: date
) -> tuple[dict[str, _Classification], dict[str, str]]:
    if history_is_available(conn):
        universe = resolve_universe(conn, as_of_date)
        return (
            {
                symbol: _Classification(
                    symbol,
                    item.security_type,
                    item.sector_code,
                    item.sector_name,
                    item.industry_code,
                    item.industry_name,
                    item.taxonomy_name,
                    item.taxonomy_version,
                )
                for symbol, item in universe.classifications.items()
                if item.lifecycle_status.upper() == "ACTIVE"
            },
            universe.lineage(),
        )
    rows = conn.execute(
        "SELECT symbol, security_type, sector_code, sector_name, industry_code, "
        "industry_name, taxonomy_name, taxonomy_version FROM symbol_master "
        "WHERE is_active = TRUE AND COALESCE(lifecycle_status, 'ACTIVE') = 'ACTIVE'"
    ).fetchall()
    return (
        {
            str(row[0]): _Classification(
                str(row[0]),
                str(row[1]),
                None if row[2] is None else str(row[2]),
                None if row[3] is None else str(row[3]),
                None if row[4] is None else str(row[4]),
                None if row[5] is None else str(row[5]),
                str(row[6] or "UNKNOWN"),
                str(row[7] or "UNKNOWN"),
            )
            for row in rows
        },
        {"membership_basis": "symbol_master"},
    )


def _sector_rows(
    sector_snapshots: list[SectorStrengthSnapshot],
    classifications: Mapping[str, _Classification],
    membership_lineage: Mapping[str, str],
    generated_at: datetime,
) -> tuple[list[GroupContextSnapshot], int, list[str]]:
    identity_by_name: defaultdict[str, set[tuple[str, str, str]]] = defaultdict(set)
    unclassified = 0
    for item in classifications.values():
        if item.sector_name and item.sector_code:
            identity_by_name[item.sector_name].add(
                (item.taxonomy_name, item.taxonomy_version, item.sector_code)
            )
        else:
            unclassified += 1
    built: list[GroupContextSnapshot] = []
    caveats: list[str] = []
    for snapshot in sector_snapshots:
        identities = identity_by_name.get(snapshot.sector, set())
        if len(identities) != 1:
            caveats.append(
                f"Sector {snapshot.sector} was excluded because its taxonomy identity was not unique."
            )
            continue
        taxonomy_name, taxonomy_version, code = next(iter(identities))
        entity_id = f"{taxonomy_name}:{taxonomy_version}:{code}".upper()
        built.append(
            _from_sector_snapshot(
                snapshot,
                entity_id,
                code,
                taxonomy_name,
                taxonomy_version,
                unclassified,
                membership_lineage,
                generated_at,
            )
        )
    return built, unclassified, caveats


def _aggregate_group(
    group_type: GroupType,
    classifications: Mapping[str, _Classification],
    eligible_by_symbol: Mapping[str, FeatureRow],
    as_of_date: date,
    membership_lineage: Mapping[str, str],
    generated_at: datetime,
    policy: SectorStrengthPolicy,
) -> tuple[list[GroupContextSnapshot], int, list[str]]:
    members: defaultdict[str, list[str]] = defaultdict(list)
    rows: defaultdict[str, list[FeatureRow]] = defaultdict(list)
    identities: dict[str, tuple[str, str, str, str]] = {}
    unclassified = 0
    for symbol, classification in classifications.items():
        identity = _group_identity(group_type, classification)
        if identity is None:
            unclassified += 1
            continue
        entity_id, code, name, taxonomy = identity
        identities[entity_id] = (code, name, taxonomy, classification.taxonomy_version)
        members[entity_id].append(symbol)
        if symbol in eligible_by_symbol:
            rows[entity_id].append(eligible_by_symbol[symbol])
    aggregates = [
        SectorAggregate(
            sector=entity_id,
            member_count=len(symbols),
            feature_candidate_count=len(symbols),
            rows=tuple(rows[entity_id]),
            policy=policy,
        )
        for entity_id, symbols in sorted(members.items())
    ]
    caveats: list[str] = []
    rankable: list[SectorAggregate] = []
    for aggregate in aggregates:
        reasons = _rankability_reasons(aggregate, policy)
        if reasons:
            caveats.extend(reasons)
        else:
            rankable.append(aggregate)
    ordered = sorted(
        rankable,
        key=lambda item: (-item.score, -item.median_rs20, item.sector),
    )
    snapshots = [
        _from_aggregate(
            group_type,
            aggregate,
            identities[aggregate.sector],
            as_of_date,
            rank,
            unclassified,
            membership_lineage,
            caveats,
            generated_at,
            policy,
        )
        for rank, aggregate in enumerate(ordered, start=1)
    ]
    return snapshots, unclassified, caveats


def _group_identity(
    group_type: GroupType, item: _Classification
) -> tuple[str, str, str, str] | None:
    if group_type is GroupType.INDUSTRY:
        if not item.industry_code or not item.industry_name:
            return None
        entity_id = (
            f"{item.taxonomy_name}:{item.taxonomy_version}:{item.industry_code}".upper()
        )
        return entity_id, item.industry_code, item.industry_name, item.taxonomy_name
    security_type = item.security_type.strip().upper()
    if not security_type:
        return None
    return security_type, security_type, security_type, "OPENSTOCK_SECURITY_TYPE"


def _from_sector_snapshot(
    snapshot: SectorStrengthSnapshot,
    entity_id: str,
    code: str,
    taxonomy_name: str,
    taxonomy_version: str,
    unclassified_count: int,
    membership_lineage: Mapping[str, str],
    generated_at: datetime,
) -> GroupContextSnapshot:
    lineage = {**dict(snapshot.lineage), **dict(membership_lineage)}
    concentration = float(snapshot.lineage.get("sector_concentration_ratio", 0.0))
    values = {
        "as_of_date": snapshot.as_of_date,
        "group_type": GroupType.SECTOR,
        "entity_id": entity_id,
        "group_code": code,
        "group_name": snapshot.sector,
        "taxonomy_name": taxonomy_name,
        "taxonomy_version": taxonomy_version,
        "rank": snapshot.rank,
        "member_count": snapshot.member_count,
        "eligible_count": snapshot.eligible_count,
        "median_return20": snapshot.median_return20,
        "median_return60": snapshot.median_return60,
        "median_rs20_vs_vnindex": snapshot.median_rs20_vs_vnindex,
        "median_rs60_vs_vnindex": snapshot.median_rs60_vs_vnindex,
        "pct_above_ma20": snapshot.pct_above_ma20,
        "pct_above_ma50": snapshot.pct_above_ma50,
        "leadership_count": snapshot.leadership_count,
        "leadership_concentration": concentration,
        "score": snapshot.score,
        "rotation": snapshot.rotation,
        "coverage": snapshot.eligible_count / snapshot.member_count,
        "unclassified_count": unclassified_count,
        "quality": snapshot.quality,
        "caveats": snapshot.caveats,
        "lineage": lineage,
        "methodology_version": snapshot.methodology_version,
        "generated_at": generated_at,
    }
    return GroupContextSnapshot(
        **values,
        source_hash=_source_hash(values),
    )


def _from_aggregate(
    group_type: GroupType,
    aggregate: SectorAggregate,
    identity: tuple[str, str, str, str],
    as_of_date: date,
    rank: int,
    unclassified_count: int,
    membership_lineage: Mapping[str, str],
    caveats: list[str],
    generated_at: datetime,
    policy: SectorStrengthPolicy,
) -> GroupContextSnapshot:
    code, name, taxonomy_name, taxonomy_version = identity
    lineage = {
        **dict(membership_lineage),
        "member_symbols": ",".join(sorted(row.symbol for row in aggregate.rows)),
        "group_member_count": str(aggregate.member_count),
        "group_eligible_count": str(aggregate.eligible_count),
    }
    values = {
        "as_of_date": as_of_date,
        "group_type": group_type,
        "entity_id": aggregate.sector,
        "group_code": code,
        "group_name": name,
        "taxonomy_name": taxonomy_name,
        "taxonomy_version": taxonomy_version,
        "rank": rank,
        "member_count": aggregate.member_count,
        "eligible_count": aggregate.eligible_count,
        "median_return20": aggregate.median_return20,
        "median_return60": aggregate.median_return60,
        "median_rs20_vs_vnindex": aggregate.median_rs20,
        "median_rs60_vs_vnindex": aggregate.median_rs60,
        "pct_above_ma20": aggregate.pct_above_ma20,
        "pct_above_ma50": aggregate.pct_above_ma50,
        "leadership_count": aggregate.leadership_count,
        "leadership_concentration": aggregate.concentration_ratio,
        "score": aggregate.score,
        "rotation": aggregate.rotation,
        "coverage": aggregate.sector_coverage,
        "unclassified_count": unclassified_count,
        "quality": "OK",
        "caveats": tuple(caveats),
        "lineage": lineage,
        "methodology_version": policy.methodology_version,
        "generated_at": generated_at,
    }
    return GroupContextSnapshot(**values, source_hash=_source_hash(values))


def _source_hash(values: Mapping[str, object]) -> str:
    stable = {key: value for key, value in values.items() if key != "generated_at"}
    payload = json.dumps(stable, sort_keys=True, default=str, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def _replace_snapshots(
    conn: duckdb.DuckDBPyConnection,
    as_of_date: date,
    snapshots: tuple[GroupContextSnapshot, ...],
) -> None:
    conn.execute("BEGIN TRANSACTION")
    try:
        conn.execute(
            "DELETE FROM group_context_snapshot WHERE as_of_date = ?", [as_of_date]
        )
        for item in snapshots:
            conn.execute(
                "INSERT INTO group_context_snapshot VALUES ("
                + ",".join("?" for _ in range(28))
                + ")",
                [
                    item.as_of_date,
                    item.group_type.value,
                    item.entity_id,
                    item.group_code,
                    item.group_name,
                    item.taxonomy_name,
                    item.taxonomy_version,
                    item.rank,
                    item.member_count,
                    item.eligible_count,
                    item.median_return20,
                    item.median_return60,
                    item.median_rs20_vs_vnindex,
                    item.median_rs60_vs_vnindex,
                    item.pct_above_ma20,
                    item.pct_above_ma50,
                    item.leadership_count,
                    item.leadership_concentration,
                    item.score,
                    item.rotation,
                    item.coverage,
                    item.unclassified_count,
                    item.quality,
                    json.dumps(item.caveats),
                    json.dumps(dict(item.lineage), sort_keys=True),
                    item.methodology_version,
                    item.source_hash,
                    item.generated_at,
                ],
            )
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def _snapshot_from_row(row: tuple[object, ...]) -> GroupContextSnapshot:
    return GroupContextSnapshot(
        as_of_date=row[0],
        group_type=GroupType(str(row[1])),
        entity_id=str(row[2]),
        group_code=str(row[3]),
        group_name=str(row[4]),
        taxonomy_name=str(row[5]),
        taxonomy_version=str(row[6]),
        rank=int(row[7]),
        member_count=int(row[8]),
        eligible_count=int(row[9]),
        median_return20=float(row[10]),
        median_return60=float(row[11]),
        median_rs20_vs_vnindex=float(row[12]),
        median_rs60_vs_vnindex=float(row[13]),
        pct_above_ma20=float(row[14]),
        pct_above_ma50=float(row[15]),
        leadership_count=int(row[16]),
        leadership_concentration=float(row[17]),
        score=float(row[18]),
        rotation=str(row[19]),
        coverage=float(row[20]),
        unclassified_count=int(row[21]),
        quality=str(row[22]),
        caveats=tuple(json.loads(str(row[23]))),
        lineage=json.loads(str(row[24])),
        methodology_version=str(row[25]),
        source_hash=str(row[26]),
        generated_at=row[27],
    )


def _snapshot_entity(snapshot: GroupContextSnapshot) -> MemoryEntity:
    entity_type = {
        GroupType.SECTOR: MemoryEntityType.SECTOR,
        GroupType.INDUSTRY: MemoryEntityType.INDUSTRY,
        GroupType.ASSET_CLASS: MemoryEntityType.ASSET_CLASS,
    }[snapshot.group_type]
    return MemoryEntity(entity_type, snapshot.entity_id)


def _memory_value(snapshot: GroupContextSnapshot) -> dict[str, object]:
    return {
        "rank": snapshot.rank,
        "score": snapshot.score,
        "rotation": snapshot.rotation,
        "breadth": {
            "pct_above_ma20": snapshot.pct_above_ma20,
            "pct_above_ma50": snapshot.pct_above_ma50,
        },
        "coverage": snapshot.coverage,
        "leadership_concentration": snapshot.leadership_concentration,
        "quality": snapshot.quality,
        "caveats": list(snapshot.caveats),
        "unit": "policy_score_and_ratios",
        "meaning": "validated group strength, rank, rotation, breadth and coverage",
    }


__all__ = [
    "GroupContextBuildResult",
    "GroupContextProjector",
    "GroupContextSnapshot",
    "GroupProjectionResult",
    "GroupType",
    "build_group_context",
    "list_group_context",
]

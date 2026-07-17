from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import UTC, date, datetime
from typing import Any, Iterable, Mapping

import duckdb

from vnalpha.symbol_memory.models import (
    ClaimOrigin,
    ClaimStatus,
    MemoryClaim,
    MemoryCompactionRun,
    MemoryDocument,
    MemoryEvent,
)
from vnalpha.symbol_memory.paths import normalize_symbol
from vnalpha.symbol_memory.validators import validate_claim


class SymbolMemoryRepository:
    def __init__(self, connection: duckdb.DuckDBPyConnection) -> None:
        self.connection = connection
        self._transaction_depth = 0

    @contextmanager
    def transaction(self):
        outermost = self._transaction_depth == 0
        if outermost:
            self.connection.execute("BEGIN TRANSACTION")
        self._transaction_depth += 1
        try:
            yield
        except BaseException:
            self._transaction_depth -= 1
            if outermost:
                self.connection.execute("ROLLBACK")
            raise
        else:
            self._transaction_depth -= 1
            if outermost:
                try:
                    self.connection.execute("COMMIT")
                except BaseException:
                    try:
                        self.connection.execute("ROLLBACK")
                    except duckdb.Error:
                        pass
                    raise

    def append_event(self, event: MemoryEvent) -> bool:
        symbol = normalize_symbol(event.symbol)
        duplicate = self.connection.execute(
            "SELECT 1 FROM memory_event "
            "WHERE symbol = ? AND evidence_ref IS NOT DISTINCT FROM ? "
            "AND content_hash = ?",
            [symbol, event.evidence_ref, event.content_hash],
        ).fetchone()
        if duplicate is not None:
            return False
        self.connection.execute(
            "INSERT INTO memory_event ("
            "event_id, symbol, event_type, evidence_ref, content_hash, observed_at, "
            "as_of_date, origin, correlation_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                event.event_id,
                symbol,
                event.event_type,
                event.evidence_ref,
                event.content_hash,
                _storage_datetime(event.observed_at),
                event.as_of_date,
                event.origin.value,
                event.correlation_id,
                _storage_datetime(event.created_at),
            ],
        )
        return True

    def list_events(self, symbol: str, *, limit: int = 100) -> list[MemoryEvent]:
        rows = self.connection.execute(
            "SELECT event_id, symbol, event_type, evidence_ref, content_hash, observed_at, "
            "as_of_date, origin, correlation_id, created_at FROM memory_event "
            "WHERE symbol = ? ORDER BY created_at, event_id LIMIT ?",
            [normalize_symbol(symbol), _event_limit(limit)],
        ).fetchall()
        return [_event_from_row(row) for row in rows]

    def list_events_after(
        self,
        symbol: str,
        *,
        after: tuple[datetime, str] | None,
        limit: int = 10_000,
    ) -> list[MemoryEvent]:
        values: list[object] = [normalize_symbol(symbol)]
        query = (
            "SELECT event_id, symbol, event_type, evidence_ref, content_hash, observed_at, "
            "as_of_date, origin, correlation_id, created_at FROM memory_event "
            "WHERE symbol = ?"
        )
        if after is not None:
            after_storage = _storage_datetime(after[0])
            query += " AND (created_at > ? OR (created_at = ? AND event_id > ?))"
            values.extend((after_storage, after_storage, after[1]))
        query += " ORDER BY created_at, event_id LIMIT ?"
        values.append(_event_limit(limit))
        rows = self.connection.execute(query, values).fetchall()
        return [_event_from_row(row) for row in rows]

    def count_events(self, symbol: str) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) FROM memory_event WHERE symbol = ?",
            [normalize_symbol(symbol)],
        ).fetchone()
        return int(row[0])

    def has_persisted_evidence(
        self,
        source_ref: str,
        symbol: str,
        as_of_date: date,
        claim_type: str,
        predicate: str,
        value: Mapping[str, Any],
    ) -> bool:
        source_kind, _, identifier = source_ref.partition(":")
        canonical_symbol = normalize_symbol(symbol)
        if source_kind in {"candidate_score", "feature_snapshot"}:
            parts = identifier.split(":")
            if len(parts) != 2 or normalize_symbol(parts[0]) != canonical_symbol:
                return False
            try:
                reference_date = date.fromisoformat(parts[1])
            except ValueError:
                return False
            if reference_date != as_of_date:
                return False
            if source_kind == "candidate_score":
                row = self.connection.execute(
                    "SELECT score, candidate_class, setup_type, "
                    "scoring_policy_id, scoring_policy_hash "
                    "FROM candidate_score WHERE symbol = ? AND date = ?",
                    [canonical_symbol, reference_date],
                ).fetchone()
                return (
                    row is not None
                    and claim_type == "candidate_score"
                    and predicate == "composite_score"
                    and value.get("value") == row[0]
                    and value.get("unit") == "score"
                    and value.get("meaning") == "persisted composite candidate score"
                    and set(value).issubset(
                        {
                            "value",
                            "unit",
                            "meaning",
                            "candidate_class",
                            "setup_type",
                            "scoring_policy_id",
                            "scoring_policy_hash",
                        }
                    )
                    and (
                        "candidate_class" not in value
                        or value["candidate_class"] == row[1]
                    )
                    and ("setup_type" not in value or value["setup_type"] == row[2])
                    and value.get("scoring_policy_id") == row[3]
                    and value.get("scoring_policy_hash") == row[4]
                )
            row = self.connection.execute(
                "SELECT feature_data_status FROM feature_snapshot WHERE symbol = ? AND date = ?",
                [canonical_symbol, reference_date],
            ).fetchone()
            return (
                row is not None
                and claim_type == "data_quality_caveat"
                and predicate == "feature_data_quality"
                and value == {"status": row[0]}
            )
        if source_kind in {"symbol_identity", "canonical_ohlcv"}:
            from vnalpha.symbol_memory.context_snapshots import (
                canonical_ohlcv_basis_value,
                load_canonical_ohlcv_basis,
                load_symbol_identity,
                symbol_identity_value,
            )

            parts = identifier.split(":")
            if len(parts) != 2 or normalize_symbol(parts[0]) != canonical_symbol:
                return False
            try:
                reference_date = date.fromisoformat(parts[1])
            except ValueError:
                return False
            if reference_date != as_of_date:
                return False
            if source_kind == "symbol_identity":
                snapshot = load_symbol_identity(
                    self.connection,
                    canonical_symbol,
                    reference_date,
                )
                return (
                    snapshot is not None
                    and claim_type == "symbol_identity"
                    and predicate == "security_identity"
                    and value == symbol_identity_value(snapshot)
                )
            requested_as_of = value.get("requested_as_of_date")
            if not isinstance(requested_as_of, str):
                return False
            basis = load_canonical_ohlcv_basis(
                self.connection,
                canonical_symbol,
                requested_as_of,
                reference_date,
            )
            return (
                basis is not None
                and claim_type == "data_readiness"
                and predicate == "canonical_ohlcv_basis"
                and value == canonical_ohlcv_basis_value(basis)
            )
        references = {
            "research_market_regime_snapshot": (
                "research_market_regime_snapshot",
                "market_regime_snapshot_id",
            ),
            "research_symbol_level_snapshot": (
                "research_symbol_level_snapshot",
                "symbol_level_snapshot_id",
            ),
            "research_setup_analysis": (
                "research_setup_analysis",
                "setup_analysis_id",
            ),
        }
        if source_kind in references:
            table, identifier_column = references[source_kind]
            row = self.connection.execute(
                f"SELECT as_of_date, symbol, payload_json FROM {table} WHERE {identifier_column} = ?",
                [identifier],
            ).fetchone()
            return (
                row is not None
                and row[0] == as_of_date
                and (
                    row[1] is None or normalize_symbol(str(row[1])) == canonical_symbol
                )
                and _claim_shape_matches_source(source_kind, claim_type, predicate)
                and _source_payload_matches(source_kind, value, row[2])
            )
        if source_kind == "research_automation":
            row = self.connection.execute(
                "SELECT status, input_datasets_json, artifact_type, caveats_json FROM research_artifact WHERE artifact_id = ?",
                [identifier],
            ).fetchone()
            if (
                row is None
                or row[0] not in {"validated", "promoted"}
                or not _claim_shape_matches_source(source_kind, claim_type, predicate)
            ):
                return False
            try:
                caveats = json.loads(str(row[3]))
            except (TypeError, json.JSONDecodeError):
                return False
            if value != {
                "artifact_id": identifier,
                "artifact_type": row[2],
                "validation_status": row[0],
                "caveats": caveats,
            }:
                return False
            try:
                datasets = json.loads(str(row[1]))
            except (TypeError, json.JSONDecodeError):
                return False
            return any(
                canonical_symbol
                in {normalize_symbol(item) for item in dataset["symbols"]}
                and date.fromisoformat(
                    str(dataset.get("end_date") or dataset.get("start_date"))
                )
                == as_of_date
                for dataset in datasets
                if isinstance(dataset, dict)
                and isinstance(dataset.get("symbols"), list)
                and (dataset.get("end_date") or dataset.get("start_date"))
            )
        return False

    def list_symbols(self, *, limit: int = 1_000) -> tuple[str, ...]:
        rows = self.connection.execute(
            "SELECT DISTINCT symbol FROM memory_claim ORDER BY symbol LIMIT ?",
            [_event_limit(limit)],
        ).fetchall()
        return tuple(str(row[0]) for row in rows)

    def create_claim(self, claim: MemoryClaim) -> None:
        validate_claim(claim)
        self.connection.execute(
            "INSERT INTO memory_claim ("
            "claim_id, symbol, claim_type, predicate, value_json, status, pinned, "
            "confidence, observed_at, as_of_date, valid_from, valid_until, origin, "
            "source_refs_json, correlation_id, created_at, supersedes_claim_id, "
            "lifecycle_reason, source_published_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _claim_values(claim),
        )

    def get_claim(self, claim_id: str) -> MemoryClaim | None:
        row = self.connection.execute(
            _CLAIM_SELECT + " WHERE claim_id = ?", [claim_id]
        ).fetchone()
        return None if row is None else _claim_from_row(row)

    def list_claims(
        self,
        symbol: str,
        *,
        statuses: Iterable[ClaimStatus] | None = None,
        limit: int = 100,
    ) -> list[MemoryClaim]:
        values: list[object] = [normalize_symbol(symbol)]
        query = _CLAIM_SELECT + " WHERE symbol = ?"
        status_values = tuple(status.value for status in statuses) if statuses else ()
        if status_values:
            placeholders = ", ".join("?" for _ in status_values)
            query += f" AND status IN ({placeholders})"
            values.extend(status_values)
        query += " ORDER BY created_at, claim_id LIMIT ?"
        values.append(_limit(limit))
        rows = self.connection.execute(query, values).fetchall()
        return [_claim_from_row(row) for row in rows]

    def transition_claim(
        self,
        claim_id: str,
        status: ClaimStatus,
        lifecycle_reason: str,
    ) -> None:
        if not lifecycle_reason.strip():
            raise ValueError("lifecycle_reason is required.")
        updated = self.connection.execute(
            "UPDATE memory_claim SET status = ?, lifecycle_reason = ? WHERE claim_id = ?",
            [status.value, lifecycle_reason, claim_id],
        ).fetchone()
        if updated is None:
            existing = self.get_claim(claim_id)
            if existing is None:
                raise KeyError(f"Unknown memory claim: {claim_id}")

    def set_claim_pinned(self, claim_id: str, pinned: bool) -> None:
        existing = self.get_claim(claim_id)
        if existing is None:
            raise KeyError(f"Unknown memory claim: {claim_id}")
        self.connection.execute(
            "UPDATE memory_claim SET pinned = ? WHERE claim_id = ?",
            [pinned, claim_id],
        )

    def upsert_document(self, document: MemoryDocument) -> None:
        symbol = normalize_symbol(document.symbol)
        self.connection.execute(
            "INSERT INTO memory_document ("
            "symbol, path, schema_version, generation, managed_hash, document_hash, "
            "token_estimate, last_compacted_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(symbol) DO UPDATE SET "
            "path = excluded.path, schema_version = excluded.schema_version, "
            "generation = excluded.generation, managed_hash = excluded.managed_hash, "
            "document_hash = excluded.document_hash, token_estimate = excluded.token_estimate, "
            "last_compacted_at = excluded.last_compacted_at, updated_at = excluded.updated_at",
            [
                symbol,
                document.path,
                document.schema_version,
                document.generation,
                document.managed_hash,
                document.document_hash,
                document.token_estimate,
                _storage_datetime(document.last_compacted_at),
                _storage_datetime(document.updated_at),
            ],
        )

    def delete_document(self, symbol: str) -> None:
        self.connection.execute(
            "DELETE FROM memory_document WHERE symbol = ?", [normalize_symbol(symbol)]
        )

    def get_document(self, symbol: str) -> MemoryDocument | None:
        row = self.connection.execute(
            "SELECT symbol, path, schema_version, generation, managed_hash, document_hash, "
            "token_estimate, last_compacted_at, updated_at FROM memory_document "
            "WHERE symbol = ?",
            [normalize_symbol(symbol)],
        ).fetchone()
        return None if row is None else _document_from_row(row)

    def record_compaction_run(self, run: MemoryCompactionRun) -> None:
        self.connection.execute(
            "INSERT INTO memory_compaction_run ("
            "compaction_run_id, symbol, before_generation, after_generation, before_hash, "
            "after_hash, retained_claim_count, archived_claim_count, conflicted_claim_count, "
            "before_token_estimate, after_token_estimate, source_coverage, created_at, "
            "correlation_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                run.compaction_run_id,
                normalize_symbol(run.symbol),
                run.before_generation,
                run.after_generation,
                run.before_hash,
                run.after_hash,
                run.retained_claim_count,
                run.archived_claim_count,
                run.conflicted_claim_count,
                run.before_token_estimate,
                run.after_token_estimate,
                run.source_coverage,
                _storage_datetime(run.created_at),
                run.correlation_id,
            ],
        )

    def list_compaction_runs(
        self, symbol: str, *, limit: int = 100
    ) -> list[MemoryCompactionRun]:
        rows = self.connection.execute(
            "SELECT compaction_run_id, symbol, before_generation, after_generation, "
            "before_hash, after_hash, retained_claim_count, archived_claim_count, "
            "conflicted_claim_count, before_token_estimate, after_token_estimate, "
            "source_coverage, created_at, correlation_id FROM memory_compaction_run "
            "WHERE symbol = ? ORDER BY created_at, compaction_run_id LIMIT ?",
            [normalize_symbol(symbol), _limit(limit)],
        ).fetchall()
        return [_compaction_run_from_row(row) for row in rows]


_CLAIM_SELECT = (
    "SELECT claim_id, symbol, claim_type, predicate, value_json, status, pinned, "
    "confidence, observed_at, as_of_date, valid_from, valid_until, origin, "
    "source_refs_json, correlation_id, created_at, supersedes_claim_id, lifecycle_reason, "
    "source_published_at "
    "FROM memory_claim"
)


def _limit(limit: int) -> int:
    return max(1, min(limit, 500))


def _event_limit(limit: int) -> int:
    return max(1, min(limit, 10_000))


def _claim_shape_matches_source(
    source_kind: str, claim_type: str, predicate: str
) -> bool:
    return {
        "research_market_regime_snapshot": (
            "market_or_sector_context",
            "market_regime",
        ),
        "research_symbol_level_snapshot": ("technical_observation", "symbol_levels"),
        "research_setup_analysis": ("technical_observation", "setup_analysis"),
        "research_automation": (
            "research_automation_artifact",
            "validated_research_artifact",
        ),
    }.get(source_kind) == (claim_type, predicate)


def _source_payload_matches(
    source_kind: str, value: Mapping[str, Any], payload_json: object
) -> bool:
    try:
        payload = json.loads(str(payload_json))
    except (TypeError, json.JSONDecodeError):
        return False
    fields = {
        "research_market_regime_snapshot": (
            "regime_state",
            "index_trend",
            "index_volatility",
        ),
        "research_symbol_level_snapshot": (
            "support_levels",
            "resistance_levels",
            "pivot_levels",
            "unit",
            "meaning",
        ),
        "research_setup_analysis": (
            "setup_type",
            "setup_quality",
            "trend_context",
            "confidence",
            "unit",
            "meaning",
        ),
    }.get(source_kind, ())
    return (
        set(value) == set(fields)
        and all(
            value[key] == payload.get(key)
            for key in fields
            if key not in {"meaning", "unit"}
        )
        and (
            source_kind != "research_symbol_level_snapshot"
            or (
                value.get("unit") == "price"
                and value.get("meaning") == "persisted symbol levels"
            )
        )
        and (
            source_kind != "research_setup_analysis"
            or (
                value.get("unit") == "probability"
                and value.get("meaning")
                == "validated persisted setup analysis confidence"
            )
        )
    )


def _claim_values(claim: MemoryClaim) -> list[object]:
    return [
        claim.claim_id,
        normalize_symbol(claim.symbol),
        claim.claim_type,
        claim.predicate,
        json.dumps(dict(claim.value), sort_keys=True, separators=(",", ":")),
        claim.status.value,
        claim.pinned,
        claim.confidence,
        _storage_datetime(claim.observed_at),
        claim.as_of_date,
        claim.valid_from,
        claim.valid_until,
        claim.origin.value,
        json.dumps(claim.source_refs),
        claim.correlation_id,
        _storage_datetime(claim.created_at),
        claim.supersedes_claim_id,
        claim.lifecycle_reason,
        claim.source_published_at,
    ]


def _event_from_row(row: tuple[object, ...]) -> MemoryEvent:
    return MemoryEvent(
        event_id=str(row[0]),
        symbol=str(row[1]),
        event_type=str(row[2]),
        evidence_ref=_optional_string(row[3]),
        content_hash=str(row[4]),
        observed_at=_optional_datetime(row[5]),
        as_of_date=_optional_date(row[6]),
        origin=ClaimOrigin(str(row[7])),
        correlation_id=str(row[8]),
        created_at=_datetime(row[9]),
    )


def _claim_from_row(row: tuple[object, ...]) -> MemoryClaim:
    return MemoryClaim(
        claim_id=str(row[0]),
        symbol=str(row[1]),
        claim_type=str(row[2]),
        predicate=str(row[3]),
        value=json.loads(str(row[4])),
        status=ClaimStatus(str(row[5])),
        pinned=bool(row[6]),
        confidence=None if row[7] is None else float(row[7]),
        observed_at=_optional_datetime(row[8]),
        as_of_date=_optional_date(row[9]),
        valid_from=_optional_date(row[10]),
        valid_until=_optional_date(row[11]),
        origin=ClaimOrigin(str(row[12])),
        source_refs=tuple(json.loads(str(row[13]))),
        correlation_id=str(row[14]),
        created_at=_datetime(row[15]),
        supersedes_claim_id=_optional_string(row[16]),
        lifecycle_reason=_optional_string(row[17]),
        source_published_at=_optional_date(row[18]),
    )


def _document_from_row(row: tuple[object, ...]) -> MemoryDocument:
    return MemoryDocument(
        symbol=str(row[0]),
        path=str(row[1]),
        schema_version=int(row[2]),
        generation=int(row[3]),
        managed_hash=str(row[4]),
        document_hash=str(row[5]),
        token_estimate=int(row[6]),
        last_compacted_at=_optional_datetime(row[7]),
        updated_at=_datetime(row[8]),
    )


def _compaction_run_from_row(row: tuple[object, ...]) -> MemoryCompactionRun:
    return MemoryCompactionRun(
        compaction_run_id=str(row[0]),
        symbol=str(row[1]),
        before_generation=int(row[2]),
        after_generation=int(row[3]),
        before_hash=str(row[4]),
        after_hash=str(row[5]),
        retained_claim_count=int(row[6]),
        archived_claim_count=int(row[7]),
        conflicted_claim_count=int(row[8]),
        before_token_estimate=int(row[9]),
        after_token_estimate=int(row[10]),
        source_coverage=float(row[11]),
        created_at=_datetime(row[12]),
        correlation_id=str(row[13]),
    )


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)


def _optional_datetime(value: object) -> datetime | None:
    return None if value is None else _datetime(value)


def _datetime(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError("Expected datetime value from memory persistence.")
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _storage_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC).isoformat()
    return value.astimezone(UTC).isoformat()


def _optional_date(value: object) -> date | None:
    if value is None:
        return None
    if not isinstance(value, date):
        raise TypeError("Expected date value from memory persistence.")
    return value


__all__ = ["SymbolMemoryRepository"]

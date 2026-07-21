from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import duckdb

from vnalpha.commands.errors import CommandValidationError
from vnalpha.commands.models import CommandResult, ParsedCommand, ResultPanel
from vnalpha.symbol_memory.compaction import (
    MemoryCompactionPolicy,
    SymbolMemoryCompactionService,
)
from vnalpha.symbol_memory.ingestion import SymbolMemoryIngestionService
from vnalpha.symbol_memory.locking import root_maintenance_lock
from vnalpha.symbol_memory.maintenance import SymbolMemoryMaintenanceService
from vnalpha.symbol_memory.models import ClaimOrigin, ClaimStatus, MemoryEvent
from vnalpha.symbol_memory.recovery import inspect_symbol_card, repair_symbol_card
from vnalpha.symbol_memory.repository import SymbolMemoryRepository
from vnalpha.symbol_memory.retrieval import (
    MemoryContextBudget,
    SymbolMemoryRetrievalService,
)
from vnalpha.symbol_memory.storage import ensure_knowledge_layout


def handle_memory(
    parsed: ParsedCommand,
    *,
    conn=None,
    root: Path | None = None,
    session_id: str | None = None,
    **_kwargs,
) -> CommandResult:
    if conn is None:
        return CommandResult(
            status="FAILED", title="/memory", summary="No database connection."
        )
    if not parsed.positional:
        raise CommandValidationError(_usage())
    try:
        conn.execute("SELECT 1 FROM memory_claim LIMIT 0")
    except duckdb.Error:
        return CommandResult(
            status="PARTIAL",
            title="/memory unavailable",
            summary="Memory schema is unavailable; run warehouse migrations then retry.",
            metadata={"availability": "unavailable"},
        )
    repository = SymbolMemoryRepository(conn)
    ingestion = SymbolMemoryIngestionService(repository)
    compaction = SymbolMemoryCompactionService(repository, root)
    subcommand = parsed.positional[0]
    if subcommand == "status":
        return _status(repository, root)
    if subcommand == "show":
        return _show(parsed, repository, root)
    if subcommand == "remember":
        return _remember(parsed, ingestion, compaction, root, session_id)
    if subcommand == "correct":
        return _correct(parsed, ingestion, compaction)
    if subcommand in {"pin", "unpin"}:
        return _pin(parsed, repository, compaction, subcommand == "pin")
    if subcommand == "conflicts":
        return _conflicts(parsed, repository)
    if subcommand == "sources":
        return _sources(parsed, repository)
    if subcommand == "compact":
        return _compact(parsed, compaction)
    if subcommand == "repair":
        return _repair(parsed, repository, root)
    if subcommand == "rebuild-index":
        return _rebuild(repository, compaction)
    if subcommand == "maintain":
        return _maintain(parsed, repository, root)
    raise CommandValidationError(_usage())


def _status(repository: SymbolMemoryRepository, root: Path | None) -> CommandResult:
    rows = repository.connection.execute(
        "SELECT status, COUNT(*) FROM memory_claim GROUP BY status ORDER BY status"
    ).fetchall()
    document_count = repository.connection.execute(
        "SELECT COUNT(*) FROM memory_document"
    ).fetchone()[0]
    conflicts = sum(count for status, count in rows if status == "conflicted")
    stale_or_expired = sum(
        count for status, count in rows if status in {"expired", "superseded"}
    )
    latest_as_of = repository.connection.execute(
        "SELECT MAX(as_of_date) FROM memory_claim"
    ).fetchone()[0]
    last_compaction = repository.connection.execute(
        "SELECT MAX(created_at) FROM memory_compaction_run"
    ).fetchone()[0]
    layout = ensure_knowledge_layout(root)
    archive_bytes = sum(
        path.stat().st_size for path in layout.archive_dir.rglob("*") if path.is_file()
    )
    compaction_policy = MemoryCompactionPolicy()
    context_budget = MemoryContextBudget()
    return CommandResult(
        status="SUCCESS",
        title="/memory status",
        summary=f"{document_count} symbol card(s), {sum(row[1] for row in rows)} claim(s).",
        panels=[
            ResultPanel(
                title="Memory Status",
                content={
                    "availability": "available",
                    "migration": {"status": "current", "schema_version": 1},
                    "documents": document_count,
                    "claim_counts": dict(rows),
                    "conflicts": conflicts,
                    "stale_or_expired": stale_or_expired,
                    "freshness": None
                    if latest_as_of is None
                    else latest_as_of.isoformat(),
                    "archive_bytes": archive_bytes,
                    "token_budgets": {
                        "symbol_card": compaction_policy.symbol_card_token_budget,
                        "total_context": context_budget.total_tokens,
                        "sections": dict(context_budget.section_token_budgets),
                    },
                    "compaction": {
                        "last_completed_at": None
                        if last_compaction is None
                        else last_compaction.isoformat(),
                        "uncompacted_event_threshold": compaction_policy.uncompacted_event_threshold,
                    },
                },
            )
        ],
    )


def _show(
    parsed: ParsedCommand, repository: SymbolMemoryRepository, root: Path | None
) -> CommandResult:
    if len(parsed.positional) != 2:
        raise CommandValidationError(_usage())
    symbol = parsed.positional[1]
    inspection = inspect_symbol_card(root, symbol, repository)
    retrieval = SymbolMemoryRetrievalService(repository).retrieve(symbol)
    return CommandResult(
        status="SUCCESS",
        title=f"/memory show {retrieval.symbol}",
        summary=f"{retrieval.symbol}: {inspection.status} memory card.",
        panels=[
            ResultPanel(
                title="Memory Context",
                content=SymbolMemoryRetrievalService(repository).render_context(
                    retrieval
                ),
            )
        ],
    )


def _remember(
    parsed: ParsedCommand,
    ingestion: SymbolMemoryIngestionService,
    compaction: SymbolMemoryCompactionService,
    root: Path | None,
    session_id: str | None,
) -> CommandResult:
    if len(parsed.positional) < 3:
        raise CommandValidationError(_usage())
    symbol = parsed.positional[1]
    note = " ".join(parsed.positional[2:])
    result, _preview = compaction.mutate_and_compact(
        symbol,
        lambda: ingestion.remember(
            symbol,
            note,
            correlation_id=session_id or "memory-command",
        ),
        user_content_factory=lambda previous_note: _append_user_note(
            previous_note, note
        ),
    )
    return CommandResult(
        status="SUCCESS",
        title=f"/memory remember {symbol.upper()}",
        summary="Recorded an unverified user memory note.",
        metadata={"created": result.created},
    )


def _correct(
    parsed: ParsedCommand,
    ingestion: SymbolMemoryIngestionService,
    compaction: SymbolMemoryCompactionService,
) -> CommandResult:
    if len(parsed.positional) < 4:
        raise CommandValidationError(_usage())
    symbol, claim_id = parsed.positional[1:3]
    claim = ingestion.repository.get_claim(claim_id)
    if claim is None or claim.symbol != symbol.upper():
        raise CommandValidationError("Claim does not belong to the requested symbol.")
    compaction.mutate_and_compact(
        symbol,
        lambda: ingestion.lifecycle.correct(claim_id, " ".join(parsed.positional[3:])),
    )
    return CommandResult(
        status="SUCCESS",
        title=f"/memory correct {symbol.upper()}",
        summary=f"Corrected claim {claim_id} without altering source warehouse records.",
    )


def _pin(
    parsed: ParsedCommand,
    repository: SymbolMemoryRepository,
    compaction: SymbolMemoryCompactionService,
    pinned: bool,
) -> CommandResult:
    if len(parsed.positional) != 2:
        raise CommandValidationError(_usage())
    claim_id = parsed.positional[1]
    claim = repository.get_claim(claim_id)
    if claim is None:
        raise CommandValidationError(f"Unknown memory claim: {claim_id}")
    compaction.mutate_and_compact(
        claim.symbol,
        lambda: _set_pinned_with_event(repository, claim, pinned),
    )
    action = "Pinned" if pinned else "Unpinned"
    return CommandResult(
        status="SUCCESS",
        title=f"/memory {action.lower()}",
        summary=f"{action} claim {claim_id}.",
    )


def _conflicts(
    parsed: ParsedCommand, repository: SymbolMemoryRepository
) -> CommandResult:
    if len(parsed.positional) != 2:
        raise CommandValidationError(_usage())
    claims = repository.list_claims(parsed.positional[1])
    conflicts = [
        claim.claim_id for claim in claims if claim.status.value == "conflicted"
    ]
    return CommandResult(
        status="SUCCESS",
        title=f"/memory conflicts {parsed.positional[1].upper()}",
        summary=f"{len(conflicts)} unresolved conflict(s).",
        metadata={"claim_ids": conflicts},
    )


def _sources(
    parsed: ParsedCommand, repository: SymbolMemoryRepository
) -> CommandResult:
    if len(parsed.positional) != 2:
        raise CommandValidationError(_usage())
    sources = sorted(
        (
            {
                "claim_id": claim.claim_id,
                "source_ref": source,
                "as_of_date": None
                if claim.as_of_date is None
                else claim.as_of_date.isoformat(),
                "source_published_at": None
                if claim.source_published_at is None
                else claim.source_published_at.isoformat(),
                "status": claim.status.value,
                "confidence": claim.confidence,
                "lineage": {
                    "correlation_id": claim.correlation_id,
                    "origin": claim.origin.value,
                },
            }
            for claim in repository.list_claims(
                parsed.positional[1], statuses=(ClaimStatus.ACTIVE,)
            )
            for source in claim.source_refs
        ),
        key=lambda item: (item["source_ref"], item["claim_id"]),
    )
    return CommandResult(
        status="SUCCESS",
        title=f"/memory sources {parsed.positional[1].upper()}",
        summary=f"{len(sources)} source reference(s).",
        metadata={"sources": sources},
    )


def _compact(
    parsed: ParsedCommand, compaction: SymbolMemoryCompactionService
) -> CommandResult:
    if len(parsed.positional) != 2:
        raise CommandValidationError(_usage())
    preview = (
        compaction.preview(parsed.positional[1])
        if parsed.options.get("dry-run") is True
        else compaction.compact(parsed.positional[1])
    )
    return CommandResult(
        status="SUCCESS",
        title=f"/memory compact {parsed.positional[1].upper()}",
        summary=("Previewed" if parsed.options.get("dry-run") is True else "Compacted")
        + f" {preview.retained_claim_count} claim(s).",
        metadata={
            "changed": preview.changed,
            "retained_claim_count": preview.retained_claim_count,
            "archived_claim_count": preview.archived_claim_count,
            "conflicted_claim_count": preview.conflicted_claim_count,
            "before_token_estimate": preview.before_token_estimate,
            "after_token_estimate": preview.after_token_estimate,
            "source_coverage": preview.source_coverage,
            "proposed_change": "update" if preview.changed else "no_change",
            "proposed_managed_content": preview.managed_content,
        },
    )


def _repair(
    parsed: ParsedCommand, repository: SymbolMemoryRepository, root: Path | None
) -> CommandResult:
    if len(parsed.positional) != 2:
        raise CommandValidationError(_usage())
    result = repair_symbol_card(root, parsed.positional[1], repository)
    return CommandResult(
        status="SUCCESS",
        title=f"/memory repair {parsed.positional[1].upper()}",
        summary=f"Memory card is {result.status}.",
    )


def _rebuild(
    repository: SymbolMemoryRepository, compaction: SymbolMemoryCompactionService
) -> CommandResult:
    symbols = [
        row[0]
        for row in repository.connection.execute(
            "SELECT DISTINCT symbol FROM memory_claim"
        ).fetchall()
    ]
    with root_maintenance_lock(compaction.root):
        for symbol in symbols:
            compaction.compact(symbol)
    return CommandResult(
        status="SUCCESS",
        title="/memory rebuild-index",
        summary=f"Rebuilt {len(symbols)} symbol card index entries.",
    )


def _maintain(
    parsed: ParsedCommand, repository: SymbolMemoryRepository, root: Path | None
) -> CommandResult:
    if len(parsed.positional) > 2:
        raise CommandValidationError(_usage())
    try:
        as_of_date = (
            datetime.now(UTC).date()
            if len(parsed.positional) == 1
            else datetime.fromisoformat(parsed.positional[1]).date()
        )
    except ValueError as exc:
        raise CommandValidationError("Maintenance date must be YYYY-MM-DD.") from exc
    result = SymbolMemoryMaintenanceService(repository, root).run(as_of_date=as_of_date)
    return CommandResult(
        status="SUCCESS" if not result.failed_symbols else "PARTIAL",
        title="/memory maintain",
        summary=f"Maintained {len(result.processed_symbols)} symbol(s).",
        metadata={
            "processed_symbols": list(result.processed_symbols),
            "failed_symbols": list(result.failed_symbols),
        },
    )


def _usage() -> str:
    return (
        "Usage: /memory <status|show SYMBOL|remember SYMBOL NOTE|correct SYMBOL CLAIM_ID NOTE|"
        "pin CLAIM_ID|unpin CLAIM_ID|conflicts SYMBOL|sources SYMBOL|compact SYMBOL [--dry-run]|"
        "repair SYMBOL|rebuild-index|maintain [YYYY-MM-DD]>"
    )


def _append_user_note(previous_note: str, note: str) -> str:
    separator = "" if not previous_note or previous_note.endswith("\n") else "\n"
    return f"{previous_note}{separator}- {note}\n"


def _set_pinned_with_event(
    repository: SymbolMemoryRepository, claim, pinned: bool
) -> None:
    repository.set_claim_pinned(claim.claim_id, pinned)
    timestamp = datetime.now(UTC)
    repository.append_event(
        MemoryEvent(
            event_id=f"memory-claim-{'pinned' if pinned else 'unpinned'}-{claim.claim_id}",
            symbol=claim.symbol,
            event_type="CLAIM_PINNED" if pinned else "CLAIM_UNPINNED",
            evidence_ref=claim.claim_id,
            content_hash=f"sha256:{'pinned' if pinned else 'unpinned'}:{claim.claim_id}",
            observed_at=timestamp,
            as_of_date=timestamp.date(),
            origin=ClaimOrigin.USER_CORRECTION,
            correlation_id=claim.correlation_id,
            created_at=timestamp,
        )
    )

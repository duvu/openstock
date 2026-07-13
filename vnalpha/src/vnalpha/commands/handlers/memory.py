from __future__ import annotations

from pathlib import Path

from vnalpha.commands.errors import CommandValidationError
from vnalpha.commands.models import CommandResult, ParsedCommand, ResultPanel
from vnalpha.symbol_memory.compaction import SymbolMemoryCompactionService
from vnalpha.symbol_memory.ingestion import SymbolMemoryIngestionService
from vnalpha.symbol_memory.recovery import inspect_symbol_card
from vnalpha.symbol_memory.repository import SymbolMemoryRepository
from vnalpha.symbol_memory.retrieval import SymbolMemoryRetrievalService
from vnalpha.warehouse.migrations import run_migrations


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
    run_migrations(conn)
    repository = SymbolMemoryRepository(conn)
    ingestion = SymbolMemoryIngestionService(repository)
    compaction = SymbolMemoryCompactionService(repository, root)
    subcommand = parsed.positional[0]
    if subcommand == "status":
        return _status(repository)
    if subcommand == "show":
        return _show(parsed, repository, root)
    if subcommand == "remember":
        return _remember(parsed, ingestion, compaction, root, session_id)
    if subcommand == "correct":
        return _correct(parsed, ingestion, compaction)
    if subcommand in {"pin", "unpin"}:
        return _pin(parsed, repository, subcommand == "pin")
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
    raise CommandValidationError(_usage())


def _status(repository: SymbolMemoryRepository) -> CommandResult:
    rows = repository.connection.execute(
        "SELECT status, COUNT(*) FROM memory_claim GROUP BY status ORDER BY status"
    ).fetchall()
    document_count = repository.connection.execute(
        "SELECT COUNT(*) FROM memory_document"
    ).fetchone()[0]
    return CommandResult(
        status="SUCCESS",
        title="/memory status",
        summary=f"{document_count} symbol card(s), {sum(row[1] for row in rows)} claim(s).",
        panels=[
            ResultPanel(
                title="Memory Status",
                content={"documents": document_count, "claim_counts": dict(rows)},
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
                content=SymbolMemoryRetrievalService(repository).render_context(retrieval),
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
    result = ingestion.remember(
        symbol,
        note,
        correlation_id=session_id or "memory-command",
    )
    current = inspect_symbol_card(root, symbol, ingestion.repository)
    previous_note = "" if current.card is None else current.card.user_content
    separator = "" if not previous_note or previous_note.endswith("\n") else "\n"
    compaction.compact(
        symbol,
        user_content=f"{previous_note}{separator}- {note}\n",
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
    ingestion.lifecycle.correct(claim_id, " ".join(parsed.positional[3:]))
    compaction.compact(symbol)
    return CommandResult(
        status="SUCCESS",
        title=f"/memory correct {symbol.upper()}",
        summary=f"Corrected claim {claim_id} without altering source warehouse records.",
    )


def _pin(
    parsed: ParsedCommand, repository: SymbolMemoryRepository, pinned: bool
) -> CommandResult:
    if len(parsed.positional) != 2:
        raise CommandValidationError(_usage())
    repository.set_claim_pinned(parsed.positional[1], pinned)
    action = "Pinned" if pinned else "Unpinned"
    return CommandResult(
        status="SUCCESS",
        title=f"/memory {action.lower()}",
        summary=f"{action} claim {parsed.positional[1]}.",
    )


def _conflicts(parsed: ParsedCommand, repository: SymbolMemoryRepository) -> CommandResult:
    if len(parsed.positional) != 2:
        raise CommandValidationError(_usage())
    claims = repository.list_claims(parsed.positional[1])
    conflicts = [claim.claim_id for claim in claims if claim.status.value == "conflicted"]
    return CommandResult(
        status="SUCCESS",
        title=f"/memory conflicts {parsed.positional[1].upper()}",
        summary=f"{len(conflicts)} unresolved conflict(s).",
        metadata={"claim_ids": conflicts},
    )


def _sources(parsed: ParsedCommand, repository: SymbolMemoryRepository) -> CommandResult:
    if len(parsed.positional) != 2:
        raise CommandValidationError(_usage())
    sources = sorted(
        {
            source
            for claim in repository.list_claims(parsed.positional[1])
            for source in claim.source_refs
        }
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
            "source_coverage": preview.source_coverage,
        },
    )


def _repair(
    parsed: ParsedCommand, repository: SymbolMemoryRepository, root: Path | None
) -> CommandResult:
    if len(parsed.positional) != 2:
        raise CommandValidationError(_usage())
    result = inspect_symbol_card(root, parsed.positional[1], repository)
    return CommandResult(
        status="SUCCESS",
        title=f"/memory repair {parsed.positional[1].upper()}",
        summary=f"Memory card is {result.status}.",
    )


def _rebuild(
    repository: SymbolMemoryRepository, compaction: SymbolMemoryCompactionService
) -> CommandResult:
    symbols = [row[0] for row in repository.connection.execute("SELECT DISTINCT symbol FROM memory_claim").fetchall()]
    for symbol in symbols:
        compaction.compact(symbol)
    return CommandResult(
        status="SUCCESS",
        title="/memory rebuild-index",
        summary=f"Rebuilt {len(symbols)} symbol card index entries.",
    )


def _usage() -> str:
    return (
        "Usage: /memory <status|show SYMBOL|remember SYMBOL NOTE|correct SYMBOL CLAIM_ID NOTE|"
        "pin CLAIM_ID|unpin CLAIM_ID|conflicts SYMBOL|sources SYMBOL|compact SYMBOL [--dry-run]|"
        "repair SYMBOL|rebuild-index>"
    )

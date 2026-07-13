from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import duckdb

from vnalpha.symbol_memory.archive import SymbolMemoryArchiveService
from vnalpha.symbol_memory.compaction import SymbolMemoryCompactionService
from vnalpha.symbol_memory.locking import root_maintenance_lock
from vnalpha.symbol_memory.markdown import MemoryCardError
from vnalpha.symbol_memory.paths import normalize_symbol
from vnalpha.symbol_memory.repository import SymbolMemoryRepository


@dataclass(frozen=True, slots=True)
class MemoryMaintenanceResult:
    processed_symbols: tuple[str, ...]
    failed_symbols: tuple[str, ...]


class SymbolMemoryMaintenanceService:
    def __init__(self, repository: SymbolMemoryRepository, root: Path | None) -> None:
        self.repository = repository
        self.compaction = SymbolMemoryCompactionService(repository, root)
        self.archive = SymbolMemoryArchiveService(repository, root)

    def run(
        self,
        *,
        symbols: tuple[str, ...] | None = None,
        as_of_date: date,
        max_symbols: int = 100,
    ) -> MemoryMaintenanceResult:
        candidates = symbols or self.repository.list_symbols(limit=max_symbols)
        processed: list[str] = []
        failed: list[str] = []
        with root_maintenance_lock(self.compaction.root):
            for symbol in tuple(
                sorted({normalize_symbol(value) for value in candidates})
            )[: max(0, max_symbols)]:
                try:
                    self.compaction.micro_compact(symbol, as_of_date=as_of_date)
                    self.archive.rotate(symbol)
                except (duckdb.Error, MemoryCardError, OSError, ValueError):
                    failed.append(symbol)
                    continue
                processed.append(symbol)
        return MemoryMaintenanceResult(tuple(processed), tuple(failed))


__all__ = ["MemoryMaintenanceResult", "SymbolMemoryMaintenanceService"]

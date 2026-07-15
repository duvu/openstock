from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

import duckdb


class BenchmarkRole(StrEnum):
    DEFAULT = "DEFAULT"
    SECONDARY = "SECONDARY"


@dataclass(frozen=True, slots=True)
class BenchmarkDefinition:
    symbol: str
    benchmark_type: str
    exchange: str | None
    universe: str | None
    role: BenchmarkRole
    source: str
    methodology_version: str
    active_from: date | None
    active_to: date | None


@dataclass(frozen=True, slots=True)
class BenchmarkSelectionError(ValueError):
    symbol: str
    reason: str

    def __str__(self) -> str:
        return f"Benchmark selection for {self.symbol} failed: {self.reason}"


def registered_benchmark_symbols(conn: duckdb.DuckDBPyConnection) -> frozenset[str]:
    """Return every registry symbol that must not enter equity universes."""

    rows = conn.execute("SELECT symbol FROM benchmark_definition").fetchall()
    return frozenset(str(row[0]) for row in rows)


def resolve_benchmark(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    as_of: date,
    requested_symbol: str | None = None,
) -> BenchmarkDefinition:
    """Resolve one active, applicable benchmark for a common-equity symbol."""

    normalized_symbol = symbol.upper().strip()
    exchange, security_type = _symbol_classification(conn, normalized_symbol)
    if security_type is not None and security_type != "COMMON_EQUITY":
        raise BenchmarkSelectionError(
            normalized_symbol, "symbol is not a common equity"
        )
    benchmark_symbol = (
        requested_symbol.upper().strip()
        if requested_symbol
        else _default_symbol(exchange)
    )
    definition = _load_definition(conn, benchmark_symbol)
    if definition is None:
        raise BenchmarkSelectionError(
            normalized_symbol, f"{benchmark_symbol} is not registered"
        )
    if not _active_on(definition, as_of):
        raise BenchmarkSelectionError(
            normalized_symbol, f"{benchmark_symbol} is not active"
        )
    if (
        definition.exchange is not None
        and exchange is not None
        and definition.exchange != exchange
    ):
        raise BenchmarkSelectionError(
            normalized_symbol, f"{benchmark_symbol} is not applicable to {exchange}"
        )
    return definition


def _symbol_classification(
    conn: duckdb.DuckDBPyConnection, symbol: str
) -> tuple[str | None, str | None]:
    row = conn.execute(
        "SELECT exchange, security_type FROM symbol_master WHERE symbol = ? LIMIT 1",
        [symbol],
    ).fetchone()
    if row is None:
        return None, None
    exchange = str(row[0]).upper() if row[0] is not None else None
    security_type = str(row[1]).upper() if row[1] is not None else None
    return exchange, security_type


def _default_symbol(exchange: str | None) -> str:
    match exchange:
        case "HNX":
            return "HNXINDEX"
        case "UPCOM":
            return "UPCOMINDEX"
        case _:
            return "VNINDEX"


def _load_definition(
    conn: duckdb.DuckDBPyConnection, symbol: str
) -> BenchmarkDefinition | None:
    row = conn.execute(
        "SELECT symbol, benchmark_type, exchange, universe, role, source, "
        "methodology_version, active_from, active_to "
        "FROM benchmark_definition WHERE symbol = ? LIMIT 1",
        [symbol],
    ).fetchone()
    if row is None:
        return None
    return BenchmarkDefinition(
        symbol=str(row[0]),
        benchmark_type=str(row[1]),
        exchange=str(row[2]) if row[2] is not None else None,
        universe=str(row[3]) if row[3] is not None else None,
        role=BenchmarkRole(str(row[4])),
        source=str(row[5]),
        methodology_version=str(row[6]),
        active_from=row[7],
        active_to=row[8],
    )


def _active_on(definition: BenchmarkDefinition, as_of: date) -> bool:
    lower_bound_met = definition.active_from is None or definition.active_from <= as_of
    upper_bound_met = definition.active_to is None or as_of <= definition.active_to
    return lower_bound_met and upper_bound_met

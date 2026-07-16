"""Shared point-in-time identity and classification resolver.

Every dated/as-of historical research path must resolve symbol identity and
classification through this module rather than reading current state from
``symbol_master``. It reads ``symbol_classification_history`` (effective
intervals + lifecycle + listing/delisting + sector/industry + taxonomy) so that
recomputing an old date uses the classification that was effective *on that
date*, avoiding survivorship and taxonomy look-ahead bias.

``symbol_master`` remains the current-state convenience view; current/latest
commands may continue to read it explicitly.

Determinism: identical warehouse data, resolver version and date produce the
same result. When a symbol has overlapping/ambiguous history rows effective on
the requested date, the row with the latest ``effective_from`` then the highest
``source_snapshot_id`` wins (matching :func:`get_symbol_taxonomy_as_of`), and
the ambiguity is recorded so callers can fail closed.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from types import MappingProxyType

import duckdb

RESOLVER_VERSION = "pit-classification-v1"


def _as_datetime(value: date | datetime | str) -> datetime:
    """Normalize a requested as-of date to a UTC-naive datetime boundary.

    A plain ``date`` resolves at end-of-day so that a classification effective
    from anywhere on that calendar date is considered in force.
    """
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value)
        return parsed
    # date → end of the calendar day
    return datetime(value.year, value.month, value.day, 23, 59, 59, 999999)


@dataclass(frozen=True, slots=True)
class SymbolClassification:
    """The classification effective for one symbol on the requested as-of date."""

    symbol: str
    exchange: str | None
    security_type: str
    lifecycle_status: str
    listing_date: date | None
    delisting_date: date | None
    sector_code: str | None
    sector_name: str | None
    industry_code: str | None
    industry_name: str | None
    taxonomy_name: str
    taxonomy_version: str
    effective_from: object | None
    effective_to: object | None
    source_snapshot_id: str

    @property
    def sector(self) -> str | None:
        """Nonblank sector name, or ``None`` when unclassified."""
        value = (self.sector_name or "").strip()
        return value or None


@dataclass(frozen=True, slots=True)
class PointInTimeUniverse:
    """The point-in-time eligible universe and classification for one as-of date.

    Attributes:
        as_of_date: The requested historical date.
        resolver_version: Version tag of the resolver logic used.
        classifications: symbol → resolved :class:`SymbolClassification` for
            every symbol whose lifecycle interval covers the requested date
            (i.e. listed on/before and not delisted on/before it).
        ambiguous_symbols: symbols with more than one distinct history row
            effective on the requested date (overlapping intervals). The
            resolver still picks a deterministic winner, but production callers
            should treat these as insufficient/degraded evidence.
        coverage: fraction of history-known symbols that resolved to an
            in-interval classification on the requested date.
        source_snapshot_ids: distinct history snapshot ids that contributed.
    """

    as_of_date: date
    resolver_version: str
    classifications: Mapping[str, SymbolClassification]
    ambiguous_symbols: tuple[str, ...] = ()
    known_symbol_count: int = 0
    source_snapshot_ids: tuple[str, ...] = ()
    _lineage: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "classifications", MappingProxyType(dict(self.classifications))
        )
        object.__setattr__(self, "ambiguous_symbols", tuple(self.ambiguous_symbols))
        object.__setattr__(self, "source_snapshot_ids", tuple(self.source_snapshot_ids))
        object.__setattr__(self, "_lineage", MappingProxyType(dict(self._lineage)))

    @property
    def symbols(self) -> tuple[str, ...]:
        """Deterministically ordered eligible symbols on the as-of date."""
        return tuple(sorted(self.classifications))

    @property
    def coverage(self) -> float:
        if self.known_symbol_count <= 0:
            return 0.0
        return len(self.classifications) / self.known_symbol_count

    def get(self, symbol: str) -> SymbolClassification | None:
        return self.classifications.get(symbol)

    def is_ambiguous(self, symbol: str) -> bool:
        return symbol in set(self.ambiguous_symbols)

    def lineage(self) -> dict[str, str]:
        """Coverage/version lineage fields for persistence."""
        return {
            "pit_resolver_version": self.resolver_version,
            "pit_as_of_date": self.as_of_date.isoformat(),
            "pit_eligible_symbol_count": str(len(self.classifications)),
            "pit_known_symbol_count": str(self.known_symbol_count),
            "pit_coverage": f"{self.coverage:.6f}",
            "pit_ambiguous_symbol_count": str(len(self.ambiguous_symbols)),
            "pit_source_snapshot_ids": ",".join(self.source_snapshot_ids),
            **dict(self._lineage),
        }


class PointInTimeClassificationUnavailable(RuntimeError):
    """Raised when point-in-time classification evidence is required but absent."""

    def __init__(self, symbol: str, as_of_date: object) -> None:
        self.symbol = symbol
        self.as_of_date = as_of_date
        super().__init__(
            f"No point-in-time classification for '{symbol}' as of {as_of_date}."
        )


def _to_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value)).date()
    except (TypeError, ValueError):
        return None


def _covers_lifecycle(
    listing_date: date | None,
    delisting_date: date | None,
    as_of: date,
) -> bool:
    """Whether a symbol's listing lifecycle covers the requested date.

    A symbol listed after the requested date is excluded; a symbol delisted on
    or before the requested date is excluded. Unknown listing/delisting dates
    do not by themselves exclude a symbol (the effective interval already
    bounds the classification), matching the fail-open-on-missing-lifecycle
    policy for legacy/current-only rows.
    """
    if listing_date is not None and listing_date > as_of:
        return False
    if delisting_date is not None and delisting_date <= as_of:
        return False
    return True


def resolve_symbol_classification(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    as_of_date: date | datetime | str,
) -> SymbolClassification | None:
    """Resolve one symbol's classification effective on ``as_of_date``.

    Returns ``None`` when the symbol has no history row whose effective interval
    covers the requested date, or when its listing lifecycle excludes it.
    """
    boundary = _as_datetime(as_of_date)
    rows = conn.execute(
        """
        SELECT symbol, exchange, security_type, lifecycle_status,
               listing_date, delisting_date, sector_code, sector_name,
               industry_code, industry_name, taxonomy_name, taxonomy_version,
               effective_from, effective_to, source_snapshot_id
        FROM symbol_classification_history
        WHERE symbol = ? AND effective_from <= ?
          AND (effective_to IS NULL OR effective_to > ?)
        ORDER BY effective_from DESC, source_snapshot_id DESC
        """,
        [symbol, boundary, boundary],
    ).fetchall()
    if not rows:
        return None
    winner = rows[0]
    classification = _row_to_classification(winner)
    resolved_date = _to_date(as_of_date if not isinstance(as_of_date, str) else None)
    if resolved_date is None:
        resolved_date = boundary.date()
    if not _covers_lifecycle(
        classification.listing_date, classification.delisting_date, resolved_date
    ):
        return None
    return classification


def _row_to_classification(row: tuple) -> SymbolClassification:
    (
        symbol,
        exchange,
        security_type,
        lifecycle_status,
        listing_date,
        delisting_date,
        sector_code,
        sector_name,
        industry_code,
        industry_name,
        taxonomy_name,
        taxonomy_version,
        effective_from,
        effective_to,
        source_snapshot_id,
    ) = row
    return SymbolClassification(
        symbol=symbol,
        exchange=(exchange.strip() if isinstance(exchange, str) else exchange) or None,
        security_type=security_type,
        lifecycle_status=lifecycle_status,
        listing_date=_to_date(listing_date),
        delisting_date=_to_date(delisting_date),
        sector_code=sector_code,
        sector_name=sector_name,
        industry_code=industry_code,
        industry_name=industry_name,
        taxonomy_name=taxonomy_name,
        taxonomy_version=taxonomy_version,
        effective_from=effective_from,
        effective_to=effective_to,
        source_snapshot_id=source_snapshot_id,
    )


def resolve_universe(
    conn: duckdb.DuckDBPyConnection,
    as_of_date: date | datetime,
) -> PointInTimeUniverse:
    """Resolve the point-in-time eligible universe for ``as_of_date``.

    For every symbol present in classification history, the row effective on the
    requested date is selected deterministically. Symbols whose listing
    lifecycle does not cover the date (listed after, or delisted on/before) are
    excluded. Symbols with multiple distinct rows effective on the date are
    recorded as ambiguous.
    """
    resolved_date = (
        as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
    )
    boundary = _as_datetime(as_of_date)

    rows = conn.execute(
        """
        SELECT symbol, exchange, security_type, lifecycle_status,
               listing_date, delisting_date, sector_code, sector_name,
               industry_code, industry_name, taxonomy_name, taxonomy_version,
               effective_from, effective_to, source_snapshot_id
        FROM symbol_classification_history
        WHERE effective_from <= ?
          AND (effective_to IS NULL OR effective_to > ?)
        ORDER BY symbol, effective_from DESC, source_snapshot_id DESC
        """,
        [boundary, boundary],
    ).fetchall()

    known_symbols = {
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT symbol FROM symbol_classification_history"
        ).fetchall()
    }

    winners: dict[str, SymbolClassification] = {}
    row_counts: dict[str, int] = {}
    snapshot_ids: set[str] = set()
    for row in rows:
        symbol = row[0]
        row_counts[symbol] = row_counts.get(symbol, 0) + 1
        if symbol in winners:
            continue  # first row per symbol wins (ORDER BY guarantees determinism)
        classification = _row_to_classification(row)
        if not _covers_lifecycle(
            classification.listing_date, classification.delisting_date, resolved_date
        ):
            continue
        winners[symbol] = classification
        snapshot_ids.add(classification.source_snapshot_id)

    ambiguous = tuple(
        sorted(sym for sym, count in row_counts.items() if count > 1 and sym in winners)
    )

    return PointInTimeUniverse(
        as_of_date=resolved_date,
        resolver_version=RESOLVER_VERSION,
        classifications=winners,
        ambiguous_symbols=ambiguous,
        known_symbol_count=len(known_symbols),
        source_snapshot_ids=tuple(sorted(snapshot_ids)),
    )


def history_is_available(conn: duckdb.DuckDBPyConnection) -> bool:
    """Whether any classification history exists (else callers use compat path)."""
    row = conn.execute("SELECT 1 FROM symbol_classification_history LIMIT 1").fetchone()
    return row is not None


__all__ = [
    "RESOLVER_VERSION",
    "PointInTimeClassificationUnavailable",
    "PointInTimeUniverse",
    "SymbolClassification",
    "history_is_available",
    "resolve_symbol_classification",
    "resolve_universe",
]

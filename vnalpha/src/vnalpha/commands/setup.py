"""Build and return the default command registry with all Phase 5.8 commands."""

from __future__ import annotations

from vnalpha.commands.handlers.compare import handle_compare
from vnalpha.commands.handlers.context import handle_context
from vnalpha.commands.handlers.explain import handle_explain
from vnalpha.commands.handlers.filter import handle_filter
from vnalpha.commands.handlers.help import handle_help
from vnalpha.commands.handlers.history import handle_history
from vnalpha.commands.handlers.lineage import handle_lineage
from vnalpha.commands.handlers.note import handle_note
from vnalpha.commands.handlers.quality import handle_quality
from vnalpha.commands.handlers.scan import handle_scan
from vnalpha.commands.registry import CommandMeta, CommandRegistry


def build_default_registry() -> CommandRegistry:
    """Return a CommandRegistry pre-populated with all Phase 5.8 commands."""
    reg = CommandRegistry()

    reg.register(
        CommandMeta(
            name="scan",
            description="Scan the daily watchlist for research candidates.",
            usage="/scan [UNIVERSE] [--date DATE]",
            examples=["/scan", "/scan VN30", "/scan --date 2026-07-06"],
            permissions=["READ_WATCHLIST"],
            handler=handle_scan,
        )
    )
    reg.register(
        CommandMeta(
            name="filter",
            description="Filter candidate scores by deterministic conditions.",
            usage="/filter FILTER_EXPR... [--date DATE]",
            examples=[
                "/filter score>=0.70",
                "/filter class=STRONG_CANDIDATE setup=ACCUMULATION_BASE",
            ],
            permissions=["READ_SCORE"],
            handler=handle_filter,
        )
    )
    reg.register(
        CommandMeta(
            name="compare",
            description="Compare a list of symbols by score, setup, and risk.",
            usage="/compare SYMBOL1 SYMBOL2 [SYMBOL3...] [--date DATE]",
            examples=["/compare FPT VNM MWG"],
            permissions=["READ_SCORE"],
            handler=handle_compare,
        )
    )
    reg.register(
        CommandMeta(
            name="explain",
            description="Explain a symbol from persisted candidate score artifacts.",
            usage="/explain SYMBOL [--date DATE]",
            examples=["/explain FPT", "/explain FPT --date 2026-07-06"],
            permissions=["READ_SCORE", "READ_LINEAGE", "READ_QUALITY"],
            handler=handle_explain,
        )
    )
    reg.register(
        CommandMeta(
            name="quality",
            description="Show data quality for a symbol or the latest watchlist.",
            usage="/quality [SYMBOL] [--date DATE]",
            examples=["/quality", "/quality FPT"],
            permissions=["READ_QUALITY"],
            handler=handle_quality,
        )
    )
    reg.register(
        CommandMeta(
            name="lineage",
            description="Show provider, ingestion, feature date, and scoring version for a symbol.",
            usage="/lineage SYMBOL [--date DATE]",
            examples=["/lineage FPT"],
            permissions=["READ_LINEAGE"],
            handler=handle_lineage,
        )
    )
    reg.register(
        CommandMeta(
            name="note",
            description="Create a research note linked to a symbol.",
            usage='/note SYMBOL "note text" [--tags tag1,tag2]',
            examples=['/note FPT "watch relative strength"'],
            permissions=["WRITE_NOTE"],
            handler=handle_note,
        )
    )
    reg.register(
        CommandMeta(
            name="history",
            description="Show recent research sessions.",
            usage="/history [--limit N]",
            examples=["/history", "/history --limit 20"],
            permissions=["READ_HISTORY"],
            handler=handle_history,
        )
    )
    reg.register(
        CommandMeta(
            name="context",
            description="Inspect or compact the active workspace context.",
            usage="/context <status|compact>",
            examples=["/context status", "/context compact"],
            permissions=[],
            handler=handle_context,
        )
    )
    reg.register(
        CommandMeta(
            name="help",
            description="List available commands and usage.",
            usage="/help",
            examples=["/help"],
            permissions=[],
            handler=handle_help,
        )
    )

    return reg

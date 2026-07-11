"""Build the default registry of policy-governed research commands."""

from __future__ import annotations

from vnalpha.commands.handlers.analyze import handle_analyze
from vnalpha.commands.handlers.compare import handle_compare
from vnalpha.commands.handlers.context import handle_context
from vnalpha.commands.handlers.explain import handle_explain
from vnalpha.commands.handlers.filter import handle_filter
from vnalpha.commands.handlers.help import handle_help
from vnalpha.commands.handlers.history import handle_history
from vnalpha.commands.handlers.lineage import handle_lineage
from vnalpha.commands.handlers.market_regime import handle_market_regime
from vnalpha.commands.handlers.note import handle_note
from vnalpha.commands.handlers.quality import handle_quality
from vnalpha.commands.handlers.research_plan import handle_research_plan
from vnalpha.commands.handlers.scan import handle_scan
from vnalpha.commands.handlers.sector_strength import handle_sector_strength
from vnalpha.commands.handlers.todo import handle_todo
from vnalpha.commands.registry import CommandMeta, CommandRegistry
from vnalpha.policy.command_policy import permission_names


def build_default_registry() -> CommandRegistry:
    """Return a registry populated with capability-approved research commands."""
    reg = CommandRegistry()

    reg.register(
        CommandMeta(
            name="market-regime",
            description="Build research-only market regime context from persisted artifacts.",
            usage="/market-regime [--date DATE]",
            examples=["/market-regime", "/market-regime --date 2025-01-31"],
            permissions=permission_names("market-regime"),
            handler=handle_market_regime,
        )
    )
    reg.register(
        CommandMeta(
            name="sector-strength",
            description="Rank sector research context from persisted artifacts.",
            usage="/sector-strength [SYMBOL] [--date DATE] [--top N]",
            examples=[
                "/sector-strength",
                "/sector-strength --top 5",
                "/sector-strength FPT",
            ],
            permissions=permission_names("sector-strength"),
            handler=handle_sector_strength,
        )
    )

    reg.register(
        CommandMeta(
            name="analyze",
            description="Build detailed research context from persisted warehouse artifacts.",
            usage="/analyze SYMBOL [--date DATE] [--with-sector] [--with-regime]",
            examples=["/analyze FPT", "/analyze FPT --date 2026-07-06"],
            permissions=permission_names("analyze"),
            handler=handle_analyze,
        )
    )
    reg.register(
        CommandMeta(
            name="research-plan",
            description="Build a conditional research-only scenario plan.",
            usage=(
                "/research-plan SYMBOL [--date DATE] [--with-evidence] [--with-regime]"
            ),
            examples=["/research-plan FPT", "/research-plan FPT --date 2025-01-31"],
            permissions=permission_names("research-plan"),
            handler=handle_research_plan,
        )
    )
    reg.register(
        CommandMeta(
            name="scan",
            description="Scan the daily watchlist for research candidates.",
            usage="/scan [UNIVERSE] [--date DATE]",
            examples=["/scan", "/scan VN30", "/scan --date 2026-07-06"],
            permissions=permission_names("scan"),
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
            permissions=permission_names("filter"),
            handler=handle_filter,
        )
    )
    reg.register(
        CommandMeta(
            name="compare",
            description="Compare a list of symbols by score, setup, and risk.",
            usage="/compare SYMBOL1 SYMBOL2 [SYMBOL3...] [--date DATE]",
            examples=["/compare FPT VNM MWG"],
            permissions=permission_names("compare"),
            handler=handle_compare,
        )
    )
    reg.register(
        CommandMeta(
            name="explain",
            description="Explain a symbol from persisted candidate score artifacts.",
            usage="/explain SYMBOL [--date DATE]",
            examples=["/explain FPT", "/explain FPT --date 2026-07-06"],
            permissions=permission_names("explain"),
            handler=handle_explain,
        )
    )
    reg.register(
        CommandMeta(
            name="quality",
            description="Show data quality for a symbol or the latest watchlist.",
            usage="/quality [SYMBOL] [--date DATE]",
            examples=["/quality", "/quality FPT"],
            permissions=permission_names("quality"),
            handler=handle_quality,
        )
    )
    reg.register(
        CommandMeta(
            name="lineage",
            description="Show provider, ingestion, feature date, and scoring version for a symbol.",
            usage="/lineage SYMBOL [--date DATE]",
            examples=["/lineage FPT"],
            permissions=permission_names("lineage"),
            handler=handle_lineage,
        )
    )
    reg.register(
        CommandMeta(
            name="note",
            description="Create a research note linked to a symbol.",
            usage='/note SYMBOL "note text" [--tags tag1,tag2]',
            examples=['/note FPT "watch relative strength"'],
            permissions=permission_names("note"),
            handler=handle_note,
        )
    )
    reg.register(
        CommandMeta(
            name="history",
            description="Show recent research sessions.",
            usage="/history [--limit N]",
            examples=["/history", "/history --limit 20"],
            permissions=permission_names("history"),
            handler=handle_history,
        )
    )
    reg.register(
        CommandMeta(
            name="context",
            description="Inspect, maintain, resume, list, or export workspace context.",
            usage=(
                "/context <status|compact|clean|new|resume|list|export> "
                "[--execute|--no-compact|--resolved-errors]; aliases: "
                "/status, /compact, /clean, /new, /resume"
            ),
            examples=[
                "/context status",
                "/context compact",
                "/context clean",
                "/context clean --execute",
                "/context new --no-compact",
                "/context resume [WORKSPACE_ID]",
                "/context list",
                "/context export [WORKSPACE_ID]",
                "Aliases: /status, /compact, /clean, /new, /resume",
            ],
            permissions=permission_names("context"),
            handler=handle_context,
        )
    )
    reg.register(
        CommandMeta(
            name="todo",
            description="List and mutate persisted workspace TODO items.",
            usage="/todo <list|add|done|block|clear-done> [text|id]",
            examples=[
                "/todo list",
                "/todo add Review FPT",
                "/todo done task-1234",
                "/todo block task-1234",
                "/todo clear-done",
            ],
            permissions=permission_names("todo"),
            handler=handle_todo,
        )
    )
    reg.register(
        CommandMeta(
            name="help",
            description="List available commands and usage.",
            usage="/help",
            examples=["/help"],
            permissions=permission_names("help"),
            handler=handle_help,
        )
    )

    return reg

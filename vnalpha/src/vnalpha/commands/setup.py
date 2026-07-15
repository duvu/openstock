"""Build the default registry of policy-governed research commands."""

from __future__ import annotations

from vnalpha.commands.handlers.analyze import handle_analyze
from vnalpha.commands.handlers.chat import handle_chat
from vnalpha.commands.handlers.closed_loop import (
    handle_deploy,
    handle_repair,
    handle_validate,
)
from vnalpha.commands.handlers.compare import handle_compare
from vnalpha.commands.handlers.context import handle_context
from vnalpha.commands.handlers.data import handle_data
from vnalpha.commands.handlers.experiment import handle_experiment
from vnalpha.commands.handlers.explain import handle_explain
from vnalpha.commands.handlers.feature import handle_feature
from vnalpha.commands.handlers.filter import handle_filter
from vnalpha.commands.handlers.help import handle_help
from vnalpha.commands.handlers.history import handle_history
from vnalpha.commands.handlers.hypothesis import handle_hypothesis
from vnalpha.commands.handlers.lineage import handle_lineage
from vnalpha.commands.handlers.memory import handle_memory
from vnalpha.commands.handlers.model import handle_model
from vnalpha.commands.handlers.note import handle_note
from vnalpha.commands.handlers.pattern import handle_pattern
from vnalpha.commands.handlers.quality import handle_quality
from vnalpha.commands.handlers.research_context import (
    handle_market_regime,
    handle_sector_strength,
)
from vnalpha.commands.handlers.research_plan import handle_research_plan
from vnalpha.commands.handlers.sandbox import handle_sandbox
from vnalpha.commands.handlers.scan import handle_scan
from vnalpha.commands.handlers.setup_evidence import handle_setup_evidence
from vnalpha.commands.handlers.shortlist import handle_shortlist
from vnalpha.commands.handlers.todo import handle_todo
from vnalpha.commands.handlers.watchlist_summary import handle_watchlist_summary
from vnalpha.commands.registry import CommandMeta, CommandRegistry
from vnalpha.policy.command_policy import permission_names


def build_default_registry() -> CommandRegistry:
    """Return a registry populated with capability-approved research commands."""
    reg = CommandRegistry()

    reg.register(
        CommandMeta(
            name="data",
            description="Download approved data or build deterministic research artifacts.",
            usage=(
                "/data download <symbols|ohlcv SYMBOL|index [SYMBOL]> | "
                "/data build <canonical SYMBOL|features SYMBOL --date DATE|score SYMBOL --date DATE|"
                "market-regime --date DATE|sector-strength --date DATE> | "
                "/data sync daily [--date DATE] | /data gaps SYMBOL [--from DATE] [--to DATE] | "
                "/data repair ohlcv SYMBOL [--from DATE] [--to DATE]"
            ),
            examples=[
                "/data download ohlcv FPT --start 2026-01-01",
                "/data build features FPT --date 2026-07-10",
                "/data build market-regime --date 2026-07-10",
                "/data sync daily --date 2026-07-10",
                "/data gaps FPT --from 2026-07-01 --to 2026-07-10",
            ],
            permissions=permission_names("data"),
            handler=handle_data,
        )
    )
    reg.register(
        CommandMeta(
            name="memory",
            description="Inspect and maintain bounded symbol research memory.",
            usage="/memory <status|show|remember|correct|pin|unpin|conflicts|sources|compact|repair|rebuild-index|maintain> ...",
            examples=[
                "/memory status",
                '/memory remember FPT "watch source coverage"',
                "/memory compact FPT --dry-run",
            ],
            permissions=permission_names("memory"),
            handler=handle_memory,
        )
    )

    reg.register(
        CommandMeta(
            name="experiment",
            description="Run indicator experiments or offline research event studies.",
            usage="/experiment indicator <description> [--universe VN30] [--start YYYY-MM-DD] [--end YYYY-MM-DD] | /experiment backtest <event-study-description> [--horizon N]",
            examples=[
                "/experiment indicator relative strength 20 sessions vs VNINDEX --universe VN30",
                "/experiment backtest FPT accumulation breakout --horizon 10",
            ],
            permissions=permission_names("experiment"),
            handler=handle_experiment,
        )
    )
    reg.register(
        CommandMeta(
            name="hypothesis",
            description="Test a bounded historical research hypothesis.",
            usage="/hypothesis test <hypothesis-text>",
            examples=[
                "/hypothesis test VN30 symbols with positive rs_20 have better 20-session return"
            ],
            permissions=permission_names("hypothesis"),
            handler=handle_hypothesis,
        )
    )
    reg.register(
        CommandMeta(
            name="pattern",
            description="Scan persisted Vietnamese equity research features for supported patterns.",
            usage="/pattern scan <pattern-description> [--universe VN30] [--date YYYY-MM-DD]",
            examples=[
                "/pattern scan accumulation base with volatility contraction and volume dry-up --universe VN30"
            ],
            permissions=permission_names("pattern"),
            handler=handle_pattern,
        )
    )

    reg.register(
        CommandMeta(
            name="feature",
            description="Create and validate reproducible research-only features.",
            usage="/feature create <name = expression> [--universe UNIVERSE] | /feature validate <feature-id-or-name>",
            examples=[
                "/feature create rs_20 = rs_20d_vs_vnindex --universe VN30",
                "/feature validate rs_20",
            ],
            permissions=permission_names("feature"),
            handler=handle_feature,
        )
    )

    reg.register(
        CommandMeta(
            name="repair",
            description="Package, inspect, propose, and apply bounded sandbox research repairs.",
            usage="/repair <prepare|status|propose|apply> ...",
            examples=[
                "/repair prepare --latest",
                "/repair status repair-id",
                "/repair propose repair-id",
                "/repair apply repair-id --attempt 1",
            ],
            permissions=permission_names("repair"),
            handler=handle_repair,
        )
    )
    reg.register(
        CommandMeta(
            name="validate",
            description="Run the research-artifact validation gate.",
            usage="/validate run ARTIFACT_ID",
            examples=["/validate run artifact-123"],
            permissions=permission_names("validate"),
            handler=handle_validate,
        )
    )
    reg.register(
        CommandMeta(
            name="deploy",
            description="Verify, promote, or roll back research artifacts only.",
            usage="/deploy <verify|promote|rollback> ...",
            examples=[
                "/deploy verify artifact-123",
                "/deploy promote artifact-123 --deployment-id deployment-1",
                "/deploy rollback deployment-1",
            ],
            permissions=permission_names("deploy"),
            handler=handle_deploy,
        )
    )

    reg.register(
        CommandMeta(
            name="sandbox",
            description="Preview approval-gated sandbox work or inspect persisted job metadata.",
            usage=(
                "/sandbox run <purpose> | /sandbox status <job-id> | "
                "/sandbox artifact <job-id> | /sandbox list --latest"
            ),
            examples=[
                "/sandbox run mean of 1, 2, 3",
                "/sandbox status job-123",
                "/sandbox artifact job-123",
                "/sandbox list --latest",
            ],
            permissions=permission_names("sandbox"),
            handler=handle_sandbox,
        )
    )
    reg.register(
        CommandMeta(
            name="market-regime",
            description="Show persisted market regime research context.",
            usage="/market-regime [--date YYYY-MM-DD]",
            examples=["/market-regime", "/market-regime --date 2026-07-06"],
            permissions=permission_names("market-regime"),
            handler=handle_market_regime,
        )
    )
    reg.register(
        CommandMeta(
            name="sector-strength",
            description="Show persisted sector rankings or symbol alignment research context.",
            usage=(
                "/sector-strength [--date YYYY-MM-DD] [--top N] | "
                "/sector-strength SYMBOL [--date YYYY-MM-DD]"
            ),
            examples=[
                "/sector-strength",
                "/sector-strength --top 10",
                "/sector-strength FPT --date 2026-07-06",
            ],
            permissions=permission_names("sector-strength"),
            handler=handle_sector_strength,
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
            name="analyze",
            description="Return deep persisted research analysis for one symbol.",
            usage="/analyze SYMBOL [--date YYYY-MM-DD] [--with-sector] [--with-regime]",
            examples=[
                "/analyze FPT",
                "/analyze FPT --date 2026-07-06",
                "/analyze VNM --with-sector",
            ],
            permissions=permission_names("analyze"),
            handler=handle_analyze,
        )
    )
    reg.register(
        CommandMeta(
            name="watchlist-summary",
            description=(
                "Summarize persisted watchlist structure by class, setup, "
                "sector, and risk for research review."
            ),
            usage="/watchlist-summary [--date YYYY-MM-DD] [--top N]",
            examples=[
                "/watchlist-summary",
                "/watchlist-summary --date 2026-07-06",
                "/watchlist-summary --top 20",
            ],
            permissions=permission_names("watchlist-summary"),
            handler=handle_watchlist_summary,
        )
    )
    reg.register(
        CommandMeta(
            name="shortlist",
            description="Build a deterministic research shortlist from persisted watchlist evidence.",
            usage=(
                "/shortlist [--date YYYY-MM-DD] [--limit N] "
                "[--setup SETUP] [--sector SECTOR] [--min-score SCORE]"
            ),
            examples=[
                "/shortlist",
                "/shortlist --date 2026-07-06",
                "/shortlist --setup MOMENTUM_CONTINUATION --limit 8",
                "/shortlist --sector TECHNOLOGY",
            ],
            permissions=permission_names("shortlist"),
            handler=handle_shortlist,
        )
    )
    reg.register(
        CommandMeta(
            name="research-plan",
            description="Build a conditional research-only scenario plan for one symbol.",
            usage="/research-plan SYMBOL [--date YYYY-MM-DD] [--with-evidence] [--with-regime]",
            examples=[
                "/research-plan FPT",
                "/research-plan FPT --date 2026-07-06",
                "/research-plan VNM --with-evidence",
            ],
            permissions=permission_names("research-plan"),
            handler=handle_research_plan,
        )
    )
    reg.register(
        CommandMeta(
            name="setup-evidence",
            description="Return persisted historical setup evidence for a setup type or symbol.",
            usage="/setup-evidence SETUP_TYPE|SYMBOL [--horizon N] [--date YYYY-MM-DD] [--regime NAME]",
            examples=[
                "/setup-evidence ACCUMULATION_BASE",
                "/setup-evidence ACCUMULATION_BASE --horizon 10",
                "/setup-evidence FPT --date 2026-07-06",
            ],
            permissions=permission_names("setup-evidence"),
            handler=handle_setup_evidence,
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
            name="chat",
            description="Manage chat session control.",
            usage="/chat new",
            examples=["/chat new"],
            permissions=permission_names("chat"),
            handler=handle_chat,
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
                "/context <status|repair|compact|clean|new|resume|list|export> "
                "[--dry-run|--execute|--no-compact|--resolved-errors]; aliases: "
                "/status, /compact, /clean, /new, /resume"
            ),
            examples=[
                "/context status",
                "/context repair --dry-run",
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
            name="model",
            description="Inspect or override model-routing profiles.",
            usage=(
                "/model <status|profiles|use|reset|explain-route> "
                "[PROFILE|STAGE|TASK] [--scope session|workspace|all]"
            ),
            examples=[
                "/model status",
                "/model profiles",
                "/model use reasoning",
                "/model reset",
                "/model explain-route deep_symbol_analysis",
            ],
            permissions=permission_names("model"),
            handler=handle_model,
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

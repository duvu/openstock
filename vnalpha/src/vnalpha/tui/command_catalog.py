from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UiCommand:
    name: str
    aliases: tuple[str, ...] = ()
    description: str = ""
    usage: str = ""
    category: str = "Operations"
    examples: tuple[str, ...] = ()
    key_binding: str | None = None

    @property
    def all_names(self) -> tuple[str, ...]:
        return (self.name, *self.aliases)


def _static_catalog() -> list[UiCommand]:
    return [
        UiCommand(
            name="chat",
            aliases=("c",),
            description="Manage chat session control.",
            usage="/chat new",
            category="Chat",
            examples=("/chat new",),
        ),
        UiCommand(
            name="scan",
            description="Scan watchlist and return scored candidates.",
            usage="/scan [UNIVERSE] [--date YYYY-MM-DD]",
            category="Research",
            examples=("/scan", "/scan VN30", "/scan --date 2026-07-06"),
        ),
        UiCommand(
            name="experiment",
            description="Run indicator experiments or offline research event studies.",
            usage="/experiment indicator DESCRIPTION | /experiment backtest DESCRIPTION",
            category="Research Automation",
            examples=(
                "/experiment indicator relative strength 20 sessions vs VNINDEX --universe VN30",
                "/experiment backtest FPT accumulation breakout --horizon 10",
            ),
        ),
        UiCommand(
            name="feature",
            description="Create or validate a reproducible research feature.",
            usage="/feature create NAME = EXPRESSION | /feature validate NAME",
            category="Research Automation",
            examples=(
                "/feature create rs_20 = rs_20d_vs_vnindex --universe VN30",
                "/feature validate rs_20",
            ),
        ),
        UiCommand(
            name="hypothesis",
            description="Test a bounded historical research hypothesis.",
            usage="/hypothesis test HYPOTHESIS",
            category="Research Automation",
            examples=("/hypothesis test positive rs_20 has better 20-session return",),
        ),
        UiCommand(
            name="pattern",
            description="Scan persisted features for supported historical patterns.",
            usage="/pattern scan DESCRIPTION [--universe VN30] [--date YYYY-MM-DD]",
            category="Research Automation",
            examples=(
                "/pattern scan accumulation base with volatility contraction and volume dry-up --universe VN30",
            ),
        ),
        UiCommand(
            name="analyze",
            description="Return deep persisted research analysis for one symbol.",
            usage="/analyze SYMBOL [--date YYYY-MM-DD]",
            category="Research",
            examples=("/analyze FPT", "/analyze FPT --date 2026-07-06"),
        ),
        UiCommand(
            name="watchlist-summary",
            description="Summarize persisted watchlist structure by class, setup, sector, and risk.",
            usage="/watchlist-summary [--date YYYY-MM-DD] [--top N]",
            category="Research",
            examples=(
                "/watchlist-summary",
                "/watchlist-summary --date 2026-07-06",
                "/watchlist-summary --top 20",
            ),
        ),
        UiCommand(
            name="shortlist",
            description="Build a deterministic research shortlist from persisted watchlist evidence.",
            usage=(
                "/shortlist [--date YYYY-MM-DD] [--limit N] "
                "[--setup SETUP] [--sector SECTOR] [--min-score SCORE]"
            ),
            category="Research",
            examples=(
                "/shortlist",
                "/shortlist --date 2026-07-06",
                "/shortlist --setup MOMENTUM_CONTINUATION",
                "/shortlist --sector TECHNOLOGY",
            ),
        ),
        UiCommand(
            name="research-plan",
            description="Build a conditional research-only scenario plan for one symbol.",
            usage="/research-plan SYMBOL [--date YYYY-MM-DD]",
            category="Research",
            examples=(
                "/research-plan FPT",
                "/research-plan FPT --date 2026-07-06",
            ),
        ),
        UiCommand(
            name="setup-evidence",
            description="Return persisted historical evidence for a setup type or symbol.",
            usage="/setup-evidence SETUP_TYPE|SYMBOL [--horizon N] [--date YYYY-MM-DD]",
            category="Research",
            examples=(
                "/setup-evidence ACCUMULATION_BASE",
                "/setup-evidence FPT --date 2026-07-06",
            ),
        ),
        UiCommand(
            name="filter",
            description="Filter candidate scores by deterministic conditions.",
            usage="/filter FILTER_EXPR [--date YYYY-MM-DD]",
            category="Research",
            examples=("/filter score>=0.7", "/filter setup=ACCUMULATION_BASE"),
        ),
        UiCommand(
            name="compare",
            description="Compare symbols by score, setup and risk profile.",
            usage="/compare SYMBOL1 SYMBOL2 [SYMBOL3...]",
            category="Research",
            examples=("/compare FPT VNM MWG",),
        ),
        UiCommand(
            name="explain",
            description="Explain symbol from persisted score artifacts.",
            usage="/explain SYMBOL [--date YYYY-MM-DD]",
            category="Research",
            examples=("/explain FPT",),
        ),
        UiCommand(
            name="quality",
            description="Show data quality snapshots.",
            usage="/quality [SYMBOL] [--date YYYY-MM-DD]",
            category="Research",
            examples=("/quality", "/quality FPT"),
        ),
        UiCommand(
            name="lineage",
            description="Show score lineage and feature provenance.",
            usage="/lineage SYMBOL [--date YYYY-MM-DD]",
            category="Research",
            examples=("/lineage FPT",),
        ),
        UiCommand(
            name="note",
            description="Create a research note linked to a symbol.",
            usage='/note SYMBOL "text" [--tags tag1,tag2]',
            category="Research",
            examples=('/note FPT "watchlist quality"',),
        ),
        UiCommand(
            name="history",
            description="Show recent research sessions.",
            usage="/history [--limit N]",
            category="Research",
            examples=("/history", "/history --limit 20"),
        ),
        UiCommand(
            name="context",
            aliases=("ctx",),
            description="Inspect or mutate workspace context.",
            usage="/context status",
            category="Workspace",
            examples=("/context status", "/context clean", "/context list"),
        ),
        UiCommand(
            name="todo",
            description="List and mutate workspace TODO tasks.",
            usage="/todo list | /todo add TEXT | /todo done ID",
            category="Workspace",
            examples=("/todo list", "/todo add Review FPT", "/todo done task-1"),
        ),
        UiCommand(
            name="model",
            description="Inspect and control model routing.",
            usage="/model status",
            category="Application",
            examples=("/model status", "/model profiles", "/model reset"),
        ),
        UiCommand(
            name="help",
            description="Show help for research and workspace commands.",
            usage="/help",
            category="Application",
            examples=("/help",),
        ),
        UiCommand(
            name="market-regime",
            aliases=("regime",),
            description="Show market regime context.",
            usage="/market-regime [--date YYYY-MM-DD]",
            category="Research",
            examples=("/market-regime", "/market-regime --date 2026-07-06"),
        ),
        UiCommand(
            name="sector-strength",
            description="Show sector strength context.",
            usage="/sector-strength [--top N] [SYMBOL]",
            category="Research",
            examples=("/sector-strength", "/sector-strength FPT --top 10"),
        ),
        UiCommand(
            name="sandbox",
            description="Prepare and inspect sandbox execution plans.",
            usage="/sandbox run | status | artifact | list",
            category="Application",
            examples=(
                "/sandbox run mean of 1, 2, 3",
                "/sandbox status job-1",
                "/sandbox list",
            ),
        ),
        UiCommand(
            name="plan",
            description="Show / switch execution plan mode.",
            usage="/plan [on|off|only]",
            category="Chat",
            examples=("/plan", "/plan on"),
        ),
        UiCommand(
            name="trace",
            description="Show tool trace timeline for chat session.",
            usage="/trace",
            category="Chat",
            examples=("/trace",),
        ),
        UiCommand(
            name="clear",
            description="Clear visible chat transcript for current session.",
            usage="/clear [--forget]",
            category="Chat",
            examples=("/clear", "/clear --forget"),
        ),
        UiCommand(
            name="new",
            description="Start a new chat session (alias: /chat new).",
            usage="/new",
            category="Chat",
            examples=("/new",),
            key_binding="ctrl+n",
        ),
        UiCommand(
            name="approve",
            description="Approve a prepared plan before execution.",
            usage="/approve",
            category="Pending action",
            examples=("/approve",),
        ),
        UiCommand(
            name="cancel",
            description="Cancel a prepared plan.",
            usage="/cancel",
            category="Pending action",
            examples=("/cancel",),
        ),
    ]


def list_commands() -> list[UiCommand]:
    return _static_catalog()


def command_names() -> list[str]:
    names: list[str] = []
    for command in list_commands():
        names.append(command.name)
        names.extend(alias for alias in command.aliases)
    seen: set[str] = set()
    deduped: list[str] = []
    for name in names:
        name = name.strip().lower()
        if not name or name in seen:
            continue
        seen.add(name)
        deduped.append(name)
    return deduped


def find_command(name: str) -> UiCommand | None:
    normalized = name.lower().lstrip("/")
    for command in list_commands():
        for known in command.all_names:
            if normalized == known:
                return command
    return None


def commands_for_prefix(prefix: str) -> list[UiCommand]:
    normalized = prefix.lower().lstrip("/")
    if not normalized:
        return list_commands()
    results: list[UiCommand] = []
    for command in list_commands():
        if command.name.lower().startswith(normalized) or any(
            alias.lower().startswith(normalized) for alias in command.aliases
        ):
            results.append(command)
    return results

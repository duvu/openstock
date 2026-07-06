"""Symbol detail screen — reads persisted candidate_score record."""

from __future__ import annotations

import json
from datetime import date
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, Static


class DetailScreen(Screen):
    """Shows detailed research analysis for a single symbol.

    Reads the persisted candidate_score record for (symbol, date) as the
    authoritative data source. Feature snapshot values shown as supporting context.
    """

    TITLE = "Symbol Detail"
    BINDINGS = [
        Binding("escape", "pop_screen", "Back"),
    ]

    def __init__(self, symbol: str, target_date: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self._symbol = symbol
        self._target_date = target_date or str(date.today())

    def compose(self) -> ComposeResult:
        yield Header()
        yield ScrollableContainer(
            Vertical(
                Label(f"[bold]Symbol: {self._symbol}[/bold]", id="detail-title"),
                Static("", id="score-panel"),
                Static("", id="evidence-panel"),
                Static("", id="risk-panel"),
                Static("", id="lineage-panel"),
                id="detail-container",
            )
        )
        yield Footer()

    def on_mount(self) -> None:
        self._load_detail()

    def _load_detail(self) -> None:
        try:
            from vnalpha.warehouse.connection import get_connection
            from vnalpha.warehouse.repositories import get_candidate_score

            conn = get_connection()
            # Read the authoritative persisted candidate score record
            record = get_candidate_score(conn, self._symbol, self._target_date)

            if record is None:
                self.query_one("#score-panel", Static).update(
                    f"[yellow]No persisted score for {self._symbol} on {self._target_date}.[/yellow]\n"
                    f"Run: vnalpha score --date {self._target_date}"
                )
                return

            # Score and classification panel
            score_text = (
                f"[bold]Research Score:[/bold] {record['score']:.3f}\n"
                f"[bold]Class:[/bold] {record['candidate_class']}\n"
                f"[bold]Setup:[/bold] {record['setup_type']}\n\n"
                f"Trend: {record['trend_score']:.3f}  "
                f"RS: {record['relative_strength_score']:.3f}  "
                f"Volume: {record['volume_score']:.3f}\n"
                f"Base: {record['base_score']:.3f}  "
                f"Breakout: {record['breakout_score']:.3f}  "
                f"Risk Quality: {record['risk_quality_score']:.3f}"
            )
            self.query_one("#score-panel", Static).update(score_text)

            # Evidence panel — sub-score breakdown from persisted evidence
            evidence = record.get("evidence_json") or {}
            if evidence:
                ev_lines = ["[bold]Evidence:[/bold]"]
                for k, v in evidence.items():
                    if k != "rule_outcomes" and v is not None:
                        ev_lines.append(
                            f"  {k}: {v:.3f}" if isinstance(v, float) else f"  {k}: {v}"
                        )
                rule_outcomes = evidence.get("rule_outcomes")
                if rule_outcomes and isinstance(rule_outcomes, dict):
                    ev_lines.append("  [dim]Rule outcomes:[/dim]")
                    for rule, outcome in rule_outcomes.items():
                        ev_lines.append(f"    {rule}: {outcome}")
                self.query_one("#evidence-panel", Static).update("\n".join(ev_lines))

            # Risk flags panel
            risk_flags = record.get("risk_flags_json") or []
            if isinstance(risk_flags, str):
                risk_flags = json.loads(risk_flags)
            if risk_flags:
                risk_text = (
                    f"[red]Risk Flags:[/red] {', '.join(str(f) for f in risk_flags)}"
                )
            else:
                risk_text = "[green]No risk flags detected[/green]"
            self.query_one("#risk-panel", Static).update(risk_text)

            # Lineage panel — scoring metadata for auditability
            lineage = record.get("lineage_json") or {}
            if isinstance(lineage, str):
                lineage = json.loads(lineage)
            if lineage:
                lin_lines = ["[bold][dim]Lineage:[/dim][/bold]"]
                for k, v in lineage.items():
                    if v is not None:
                        lin_lines.append(f"  [dim]{k}: {v}[/dim]")
                self.query_one("#lineage-panel", Static).update("\n".join(lin_lines))

        except Exception as e:
            self.query_one("#score-panel", Static).update(
                f"[red]Error loading detail: {e}[/red]"
            )

"""Symbol detail screen — reads persisted candidate_score record."""

from __future__ import annotations

import json

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, Static

from vnalpha.core.text_safety import sanitize_text
from vnalpha.tui.error_boundary import (
    capture_tui_exception,
    generic_load_error,
    literal_text,
)
from vnalpha.tui.research_date import resolve_tui_research_date
from vnalpha.warehouse.connection import get_connection
from vnalpha.warehouse.repositories import get_candidate_score


class DetailScreen(Screen):
    """Shows detailed research analysis for a single symbol.

    Reads the persisted candidate_score record for (symbol, date) as the
    authoritative data source. Feature snapshot values shown as supporting context.
    """

    TITLE = "Symbol Detail"
    BINDINGS = [
        Binding("escape", "pop_screen", "Back"),
    ]

    def __init__(self, symbol: str, target_date: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self._symbol = symbol
        self._target_date = resolve_tui_research_date(target_date)

    def compose(self) -> ComposeResult:
        yield Header()
        yield ScrollableContainer(
            Vertical(
                Label(
                    literal_text(f"Symbol: {self._symbol}", style="bold"),
                    id="detail-title",
                ),
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
            conn = get_connection()
            try:
                # Read the authoritative persisted candidate score record
                record = get_candidate_score(conn, self._symbol, self._target_date)
            finally:
                conn.close()

            if record is None:
                self.query_one("#score-panel", Static).update(
                    literal_text(
                        f"No persisted score for {self._symbol} on {self._target_date}.\n"
                        f"Run: vnalpha score --date {self._target_date}",
                        style="yellow",
                    )
                )
                return

            # Score and classification panel
            score_text = (
                f"Research Score: {record['score']:.3f}\n"
                f"Class: {sanitize_text(record['candidate_class'])}\n"
                f"Setup: {sanitize_text(record['setup_type'])}\n\n"
                f"Trend: {record['trend_score']:.3f}  "
                f"RS: {record['relative_strength_score']:.3f}  "
                f"Volume: {record['volume_score']:.3f}\n"
                f"Base: {record['base_score']:.3f}  "
                f"Breakout: {record['breakout_score']:.3f}  "
                f"Risk Quality: {record['risk_quality_score']:.3f}"
            )
            self.query_one("#score-panel", Static).update(literal_text(score_text))

            # Evidence panel — sub-score breakdown from persisted evidence
            evidence = record.get("evidence_json") or {}
            if evidence:
                ev_lines = ["Evidence:"]
                for k, v in evidence.items():
                    if k != "rule_outcomes" and v is not None:
                        ev_lines.append(
                            f"  {sanitize_text(k)}: {v:.3f}"
                            if isinstance(v, float)
                            else f"  {sanitize_text(k)}: {sanitize_text(v)}"
                        )
                rule_outcomes = evidence.get("rule_outcomes")
                if rule_outcomes and isinstance(rule_outcomes, dict):
                    ev_lines.append("  Rule outcomes:")
                    for rule, outcome in rule_outcomes.items():
                        ev_lines.append(
                            f"    {sanitize_text(rule)}: {sanitize_text(outcome)}"
                        )
                self.query_one("#evidence-panel", Static).update(
                    literal_text("\n".join(ev_lines))
                )

            # Risk flags panel
            risk_flags = record.get("risk_flags_json") or []
            if isinstance(risk_flags, str):
                risk_flags = json.loads(risk_flags)
            if risk_flags:
                risk_text = (
                    f"Risk Flags: {', '.join(sanitize_text(f) for f in risk_flags)}"
                )
            else:
                risk_text = "No risk flags detected"
            self.query_one("#risk-panel", Static).update(literal_text(risk_text))

            # Lineage panel — scoring metadata for auditability
            lineage = record.get("lineage_json") or {}
            if isinstance(lineage, str):
                lineage = json.loads(lineage)
            if lineage:
                lin_lines = ["Lineage:"]
                for k, v in lineage.items():
                    if v is not None:
                        lin_lines.append(f"  {sanitize_text(k)}: {sanitize_text(v)}")
                self.query_one("#lineage-panel", Static).update(
                    literal_text("\n".join(lin_lines))
                )

        except Exception as exc:
            capture_tui_exception(exc)
            self.query_one("#score-panel", Static).update(
                generic_load_error("Symbol detail")
            )

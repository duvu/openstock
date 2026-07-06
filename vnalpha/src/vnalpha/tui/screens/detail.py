"""Symbol detail screen."""
from __future__ import annotations

from datetime import date
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, Static


class DetailScreen(Screen):
    """Shows detailed research analysis for a single symbol."""

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
                Static("", id="feature-panel"),
                Static("", id="risk-panel"),
                id="detail-container",
            )
        )
        yield Footer()

    def on_mount(self) -> None:
        self._load_detail()

    def _load_detail(self) -> None:
        try:
            from vnalpha.warehouse.connection import get_connection
            conn = get_connection()
            # Load feature snapshot
            row = conn.execute(
                """SELECT close, ma20, ma50, ma100, volume_ratio, atr14,
                          return_20d, return_60d, rs_20d_vs_vnindex, rs_60d_vs_vnindex,
                          distance_to_ma20, distance_to_52w_high, base_range_30d,
                          close_strength, volatility_20d
                   FROM feature_snapshot WHERE symbol = ? AND date = ?""",
                [self._symbol, self._target_date],
            ).fetchone()

            if row is None:
                self.query_one("#score-panel", Static).update(
                    f"[yellow]No data for {self._symbol} on {self._target_date}[/yellow]"
                )
                return

            cols = ["close", "ma20", "ma50", "ma100", "volume_ratio", "atr14",
                    "return_20d", "return_60d", "rs_20d_vs_vnindex", "rs_60d_vs_vnindex",
                    "distance_to_ma20", "distance_to_52w_high", "base_range_30d",
                    "close_strength", "volatility_20d"]
            features = dict(zip(cols, row, strict=False))

            from vnalpha.scoring.score import compute_composite_score
            result = compute_composite_score(features)

            score_text = (
                f"[bold]Research Score:[/bold] {result['score']:.3f}\n"
                f"[bold]Class:[/bold] {result['candidate_class']}\n"
                f"[bold]Setup:[/bold] {result['setup_type']}\n\n"
                f"Trend: {result['trend_score']:.3f}  "
                f"RS: {result['relative_strength_score']:.3f}  "
                f"Volume: {result['volume_score']:.3f}\n"
                f"Base: {result['base_score']:.3f}  "
                f"Breakout: {result['breakout_score']:.3f}  "
                f"Risk Quality: {result['risk_quality_score']:.3f}"
            )
            self.query_one("#score-panel", Static).update(score_text)

            feature_text = "\n".join([
                f"Close: {features.get('close', 'N/A')}  MA20: {features.get('ma20', 'N/A'):.1f}"
                if features.get('ma20') else f"Close: {features.get('close', 'N/A')}",
                f"Return 20d: {(features.get('return_20d') or 0)*100:.1f}%  "
                f"RS vs VNINDEX 20d: {(features.get('rs_20d_vs_vnindex') or 0)*100:.1f}%",
                f"Volume ratio: {features.get('volume_ratio', 'N/A')}  "
                f"Volatility 20d: {(features.get('volatility_20d') or 0)*100:.2f}%",
            ])
            self.query_one("#feature-panel", Static).update(feature_text)

            risk_flags = result.get("risk_flags", [])
            if risk_flags:
                risk_text = f"[red]Risk Flags:[/red] {', '.join(risk_flags)}"
            else:
                risk_text = "[green]No risk flags detected[/green]"
            self.query_one("#risk-panel", Static).update(risk_text)

        except Exception as e:
            self.query_one("#score-panel", Static).update(f"[red]Error: {e}[/red]")

"""Risk panel widget — shows risk flags for a symbol."""
from __future__ import annotations

from typing import List
from textual.widgets import Static


class RiskPanel(Static):
    """Displays risk flags for the selected symbol."""

    def show(self, risk_flags: List[str]) -> None:
        """Update display with given risk flags."""
        if not risk_flags:
            self.update("[green]No risk flags[/green]")
        else:
            items = "\n".join(f"  [red]• {f}[/red]" for f in risk_flags)
            self.update(f"[bold]Risk Flags:[/bold]\n{items}")

"""Score table widget — renders sorted research candidates."""

from __future__ import annotations

from typing import Any, List

from textual.widgets import DataTable


class ScoreTable(DataTable):
    """DataTable specialization for research score display."""

    # Column specs: (header, width, no_wrap)
    # Widths are calibrated for an 80-col tmux pane and scale wider automatically.
    _COLUMN_SPECS: list[tuple[str, int, bool]] = [
        ("Rank", 4, True),
        ("Symbol", 8, True),
        ("Score", 7, True),
        ("Class", 10, False),
        ("Setup", 16, False),
        ("Risk Flags", 20, False),
    ]

    COLUMNS = [spec[0] for spec in _COLUMN_SPECS]

    def on_mount(self) -> None:
        if not self.columns:
            self._add_columns()

    def _add_columns(self) -> None:
        for header, width, no_wrap in self._COLUMN_SPECS:
            self.add_column(header, width=width, no_wrap=no_wrap)

    def populate(self, candidates: List[dict[str, Any]]) -> None:
        """Populate table with scored candidate dicts."""
        self.clear()
        if not self.columns:
            self._add_columns()
        for i, c in enumerate(candidates, start=1):
            import json

            flags = c.get("risk_flags", [])
            if isinstance(flags, str):
                flags = json.loads(flags)
            self.add_row(
                str(i),
                c.get("symbol", "—"),
                f"{c['score']:.3f}" if "score" in c else "—",
                c.get("candidate_class", "—"),
                c.get("setup_type", "—"),
                ", ".join(flags) if flags else "—",
            )

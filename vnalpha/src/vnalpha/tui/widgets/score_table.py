"""Score table widget — renders sorted research candidates."""
from __future__ import annotations

from typing import Any, List

from textual.widgets import DataTable


class ScoreTable(DataTable):
    """DataTable specialization for research score display."""

    COLUMNS = ["Rank", "Symbol", "Score", "Class", "Setup", "Risk Flags"]

    def populate(self, candidates: List[dict[str, Any]]) -> None:
        """Populate table with scored candidate dicts."""
        self.clear()
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

"""TUI Outcome Review screen."""

from __future__ import annotations

try:
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.containers import ScrollableContainer
    from textual.screen import Screen
    from textual.widgets import DataTable, Footer, Header, Label, Static

    _TEXTUAL_AVAILABLE = True
except ImportError:
    _TEXTUAL_AVAILABLE = False

from vnalpha.core.logging import get_logger

logger = get_logger("tui.screens.outcomes")


if _TEXTUAL_AVAILABLE:

    class OutcomeScreen(Screen):
        """Outcome Review screen showing Phase 6 evaluation results."""

        BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

        DEFAULT_CSS = """
        OutcomeScreen > ScrollableContainer {
            height: 1fr;
            width: 100%;
        }
        """

        def __init__(
            self, target_date: str = "today", horizon: int = 20, **kwargs
        ) -> None:
            super().__init__(**kwargs)
            self.target_date = target_date
            self.horizon = horizon
            self._conn = None

        def compose(self) -> ComposeResult:
            yield Header()
            with ScrollableContainer(id="outcome-scroll"):
                yield Label(
                    f"Outcome Review — {self.target_date} | Horizon {self.horizon} sessions",
                    id="outcome-title",
                )
                yield Static("Loading...", id="outcome-summary")
                yield Label("Candidate Outcomes", id="outcome-candidates-label")
                yield DataTable(id="outcome-candidates-table")
                yield Label("Score Bucket Performance", id="outcome-buckets-label")
                yield DataTable(id="outcome-buckets-table")
                yield Label("Setup Type Performance", id="outcome-setups-label")
                yield DataTable(id="outcome-setups-table")
                yield Label("Risk Flag Performance", id="outcome-risks-label")
                yield DataTable(id="outcome-risks-table")
                yield Static("Loading...", id="outcome-pending-panel")
            yield Footer()

        def _open_connection(self):
            """Open a single connection for this screen mount. Returns conn or None."""
            try:
                from vnalpha.warehouse.connection import get_connection
                from vnalpha.warehouse.migrations import run_migrations

                conn = get_connection()
                run_migrations(conn=conn)
                return conn
            except Exception as exc:
                logger.warning(f"Error opening outcome screen connection: {exc}")
                return None

        def on_mount(self) -> None:
            self._conn = self._open_connection()
            self._load_summary()
            self._load_pending_panel()
            self._populate_candidates_table()
            self._populate_buckets_table()
            self._populate_setups_table()
            self._populate_risks_table()

        def on_unmount(self) -> None:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None

        def _load_summary(self) -> None:
            try:
                from vnalpha.outcomes.repositories import get_watchlist_outcome

                result = (
                    get_watchlist_outcome(self._conn, self.target_date, self.horizon)
                    if self._conn
                    else None
                )
                if result is None:
                    text = (
                        f"No outcome data for {self.target_date} horizon={self.horizon}"
                    )
                else:
                    hit_rate_str = (
                        f"{result['hit_rate']:.1%}"
                        if result.get("hit_rate") is not None
                        else "—"
                    )
                    failure_rate_str = (
                        f"{result['failure_rate']:.1%}"
                        if result.get("failure_rate") is not None
                        else "—"
                    )
                    text = (
                        f"Candidates: {result.get('candidate_count')} | "
                        f"Complete: {result.get('complete_count')} | "
                        f"Pending: {result.get('pending_count')} | "
                        f"Hit Rate: {hit_rate_str} | "
                        f"Failure Rate: {failure_rate_str}"
                    )
                self.query_one("#outcome-summary", Static).update(text)
            except Exception as exc:
                logger.warning(f"Error loading outcome summary: {exc}")
                self.query_one("#outcome-summary", Static).update(
                    "Outcome summary unavailable."
                )

        def _load_pending_panel(self) -> None:
            try:
                from vnalpha.outcomes.repositories import get_watchlist_outcome

                result = (
                    get_watchlist_outcome(self._conn, self.target_date, self.horizon)
                    if self._conn
                    else None
                )
                if result is None:
                    text = "No pending/missing data info available."
                else:
                    pending = result.get("pending_count") or 0
                    missing = result.get("missing_data_count") or 0
                    text = (
                        f"[Pending/Missing Data] "
                        f"Pending horizons: {pending} | Missing data: {missing}\n"
                        "Note: outcomes are retrospective research evaluation only."
                    )
                self.query_one("#outcome-pending-panel", Static).update(text)
            except Exception as exc:
                logger.warning(f"Error loading pending panel: {exc}")
                self.query_one("#outcome-pending-panel", Static).update(
                    "Pending/missing data unavailable."
                )

        def _populate_candidates_table(self) -> None:
            try:
                from vnalpha.outcomes.repositories import get_candidate_outcomes

                rows = (
                    get_candidate_outcomes(self._conn, self.target_date, self.horizon)
                    if self._conn
                    else []
                )
                table = self.query_one("#outcome-candidates-table", DataTable)
                self._reset_table(
                    table,
                    "Symbol",
                    "Status",
                    "Score",
                    "Fwd Rtn",
                    "Excess Rtn",
                    "Hit",
                    "Failure",
                )
                if not rows:
                    table.add_row(
                        "No candidate outcome data available.",
                        "—",
                        "—",
                        "—",
                        "—",
                        "—",
                        "—",
                    )
                    return
                for row in rows:
                    fwd = (
                        f"{row['forward_return']:.2%}"
                        if row["forward_return"] is not None
                        else "—"
                    )
                    exc = (
                        f"{row['excess_return_vs_vnindex']:.2%}"
                        if row["excess_return_vs_vnindex"] is not None
                        else "—"
                    )
                    score = f"{row['score']:.2f}" if row["score"] is not None else "—"
                    table.add_row(
                        row["symbol"],
                        row["outcome_status"],
                        score,
                        fwd,
                        exc,
                        str(row["hit"]) if row["hit"] is not None else "—",
                        str(row["failure"]) if row["failure"] is not None else "—",
                    )
            except Exception as exc:
                logger.warning(f"Error populating candidates table: {exc}")

        def _populate_buckets_table(self) -> None:
            try:
                from vnalpha.outcomes.repositories import list_score_bucket_performance

                rows = (
                    list_score_bucket_performance(self._conn, self.horizon)
                    if self._conn
                    else []
                )
                table = self.query_one("#outcome-buckets-table", DataTable)
                self._reset_table(
                    table, "Bucket", "Count", "Avg Fwd Rtn", "Hit Rate", "Failure Rate"
                )
                if not rows:
                    table.add_row("No score bucket data available.", "—", "—", "—", "—")
                    return
                for row in rows:
                    fwd = (
                        f"{row['avg_forward_return']:.2%}"
                        if row["avg_forward_return"] is not None
                        else "—"
                    )
                    hit_rate_str = (
                        f"{row['hit_rate']:.1%}" if row["hit_rate"] is not None else "—"
                    )
                    failure_rate_str = (
                        f"{row['failure_rate']:.1%}"
                        if row["failure_rate"] is not None
                        else "—"
                    )
                    table.add_row(
                        row["score_bucket"],
                        str(row["candidate_count"] or 0),
                        fwd,
                        hit_rate_str,
                        failure_rate_str,
                    )
            except Exception as exc:
                logger.warning(f"Error populating buckets table: {exc}")

        def _populate_setups_table(self) -> None:
            try:
                from vnalpha.outcomes.repositories import list_setup_type_performance

                rows = (
                    list_setup_type_performance(self._conn, self.horizon)
                    if self._conn
                    else []
                )
                table = self.query_one("#outcome-setups-table", DataTable)
                self._reset_table(
                    table,
                    "Setup Type",
                    "Count",
                    "Avg Fwd Rtn",
                    "Hit Rate",
                    "Failure Rate",
                )
                if not rows:
                    table.add_row("No setup type data available.", "—", "—", "—", "—")
                    return
                for row in rows:
                    fwd = (
                        f"{row['avg_forward_return']:.2%}"
                        if row["avg_forward_return"] is not None
                        else "—"
                    )
                    hit_rate_str = (
                        f"{row['hit_rate']:.1%}" if row["hit_rate"] is not None else "—"
                    )
                    failure_rate_str = (
                        f"{row['failure_rate']:.1%}"
                        if row["failure_rate"] is not None
                        else "—"
                    )
                    table.add_row(
                        row["setup_type"],
                        str(row["candidate_count"] or 0),
                        fwd,
                        hit_rate_str,
                        failure_rate_str,
                    )
            except Exception as exc:
                logger.warning(f"Error populating setups table: {exc}")

        def _populate_risks_table(self) -> None:
            try:
                from vnalpha.outcomes.repositories import list_risk_flag_performance

                rows = (
                    list_risk_flag_performance(self._conn, self.horizon)
                    if self._conn
                    else []
                )
                table = self.query_one("#outcome-risks-table", DataTable)
                self._reset_table(
                    table,
                    "Risk Flag",
                    "Count",
                    "Avg Fwd Rtn",
                    "Hit Rate",
                    "Failure Rate",
                )
                if not rows:
                    table.add_row("No risk flag data available.", "—", "—", "—", "—")
                    return
                for row in rows:
                    fwd = (
                        f"{row['avg_forward_return']:.2%}"
                        if row["avg_forward_return"] is not None
                        else "—"
                    )
                    hit_rate_str = (
                        f"{row['hit_rate']:.1%}" if row["hit_rate"] is not None else "—"
                    )
                    failure_rate_str = (
                        f"{row['failure_rate']:.1%}"
                        if row["failure_rate"] is not None
                        else "—"
                    )
                    table.add_row(
                        row["risk_flag"],
                        str(row["candidate_count"] or 0),
                        fwd,
                        hit_rate_str,
                        failure_rate_str,
                    )
            except Exception as exc:
                logger.warning(f"Error populating risks table: {exc}")

        def _reset_table(self, table, *columns: str) -> None:
            table.clear(columns=True)
            table.add_columns(*columns)

else:
    # Stub for environments without textual
    class OutcomeScreen:  # type: ignore[no-redef]
        """Stub OutcomeScreen for environments without textual."""

        def __init__(self, target_date: str = "today", horizon: int = 20) -> None:
            self.target_date = target_date
            self.horizon = horizon

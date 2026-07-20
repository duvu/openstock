from __future__ import annotations

import typer

from vnalpha.core.logging import set_correlation_id
from vnalpha.observability.commands import command_lifecycle


def register(app: typer.Typer) -> None:
    @app.command("preflight")
    def preflight(
        as_json: bool = typer.Option(
            False, "--json", help="Emit the redaction-safe result as JSON."
        ),
    ) -> None:
        """Verify the single MVP1 assistant LLM route (issue #165).

        Exits non-zero when natural-language chat is unavailable. Deterministic
        slash and data commands remain usable regardless of this result. No
        secrets or prompt content are printed.
        """
        set_correlation_id()
        with command_lifecycle("preflight"):
            import json as _json
            from datetime import date as _date

            from vnalpha.assistant.preflight import run_llm_preflight
            from vnalpha.ingestion.trading_calendar import VietnamSessionCalendar

            result = run_llm_preflight()
            status = result.to_status_dict()

            calendar = VietnamSessionCalendar()
            calendar_status = calendar.get_coverage_status(_date.today())

            if as_json:
                typer.echo(
                    _json.dumps(
                        {
                            "assistant_llm_route": status,
                            "trading_calendar": calendar_status,
                        },
                        sort_keys=True,
                    )
                )
            else:
                typer.echo(
                    f"Trading calendar: {calendar_status['status']} "
                    f"(version={calendar_status['version']}, "
                    f"valid_through={calendar_status['valid_through']}, "
                    f"days_remaining={calendar_status['days_remaining']})"
                )
                if calendar_status["status"] == "WARNING":
                    typer.echo(
                        "  note:     calendar approaches its validity horizon; "
                        "refresh official holiday data for the next operating year."
                    )
                elif calendar_status["status"] == "EXPIRED":
                    typer.echo(
                        "  note:     calendar is beyond its validity horizon; "
                        "maintenance fails closed until it is updated."
                    )
                marker = "READY" if result.ready else "UNAVAILABLE"
                typer.echo(f"Assistant LLM route: {marker} ({result.code.value})")
                typer.echo(f"  detail:   {result.detail}")
                if result.model:
                    typer.echo(f"  model:    {result.model}")
                if result.endpoint:
                    typer.echo(f"  endpoint: {result.endpoint}")
                if result.route and result.route.get("model_id"):
                    typer.echo(f"  route:    {result.route.get('model_id')}")
                if not result.ready:
                    typer.echo(
                        "  note:     Natural-language chat is unavailable; "
                        "deterministic slash commands remain usable."
                    )
                    if result.remediation:
                        typer.echo(f"  fix:      {result.remediation}")

            if not result.ready:
                raise typer.Exit(code=1)

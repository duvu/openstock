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

            from vnalpha.assistant.preflight import run_llm_preflight

            result = run_llm_preflight()
            status = result.to_status_dict()

            if as_json:
                typer.echo(_json.dumps(status, sort_keys=True))
            else:
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

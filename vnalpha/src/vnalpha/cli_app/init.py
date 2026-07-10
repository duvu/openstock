import typer

from vnalpha.core.logging import set_correlation_id
from vnalpha.observability.commands import command_lifecycle


def register(app: typer.Typer) -> None:
    @app.command("init")
    def init() -> None:
        """Initialize the local DuckDB warehouse."""
        set_correlation_id()
        with command_lifecycle("init"):
            typer.echo("Initializing warehouse...")
            from vnalpha.warehouse import migrations

            migrations.run_migrations()
            typer.echo("Warehouse ready.")

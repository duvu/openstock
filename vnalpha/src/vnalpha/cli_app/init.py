import typer

from vnalpha.core.config import get_config
from vnalpha.core.logging import set_correlation_id
from vnalpha.observability.commands import command_lifecycle
from vnalpha.warehouse.status import inspect_warehouse


def register(app: typer.Typer) -> None:
    @app.command("init")
    def init() -> None:
        """Initialize the local DuckDB warehouse."""
        set_correlation_id()
        with command_lifecycle("init"):
            typer.echo("Initializing warehouse...")
            from vnalpha.warehouse import migrations

            migrations.run_migrations()
            status = inspect_warehouse(get_config().warehouse.path)
            if not status.ready:
                typer.echo(
                    f"Warehouse migration incomplete ({status.code.value}): "
                    f"{status.path}"
                )
                typer.echo(status.detail)
                for missing in status.missing_schema:
                    typer.echo(f"Missing: {missing}")
                raise typer.Exit(code=1)
            typer.echo("Warehouse ready.")

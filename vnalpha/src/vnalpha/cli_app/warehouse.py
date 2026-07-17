from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from vnalpha.core.config import get_config
from vnalpha.warehouse.status import inspect_warehouse

app = typer.Typer(help="Inspect the local warehouse without mutating it.")


@app.command("status")
def status(
    path: Annotated[Path | None, typer.Option("--path")] = None,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    target = path or Path(get_config().warehouse.path)
    result = inspect_warehouse(target)
    if json_output:
        typer.echo(json.dumps(result.to_dict(), sort_keys=True))
    else:
        label = "READY" if result.ready else "FAILED"
        typer.echo(f"Warehouse {label}: {result.path}")
        typer.echo(result.detail)
        for missing in result.missing_schema:
            typer.echo(f"Missing: {missing}")
    if not result.ready:
        raise typer.Exit(code=1)


__all__ = ["app"]

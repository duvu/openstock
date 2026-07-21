from __future__ import annotations

from pathlib import Path
from socket import gethostname
from typing import Annotated

import typer

from vnalpha.provisioning_queue import DEFAULT_QUEUE_PATH, ProvisioningQueue
from vnalpha.provisioning_queue.worker import ProvisioningWorker

app = typer.Typer(help="Run the one sequential durable provisioning worker.")


@app.command("worker")
def worker(
    once: Annotated[bool, typer.Option("--once")] = False,
    queue_path: Annotated[Path, typer.Option("--queue-path")] = DEFAULT_QUEUE_PATH,
    warehouse_path: Annotated[Path | None, typer.Option("--warehouse-path")] = None,
    worker_id: Annotated[str, typer.Option("--worker-id")] = (
        f"vnalpha-{gethostname()[:96]}"
    ),
) -> None:
    provisioner = ProvisioningWorker(
        ProvisioningQueue(queue_path),
        worker_id=worker_id,
        warehouse_path=warehouse_path,
    )
    with provisioner.shutdown_signals():
        processed = provisioner.run(once=once)
    typer.echo(f"processed={processed}")


__all__ = ["app"]

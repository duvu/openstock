from __future__ import annotations

import typer

try:
    from dotenv import find_dotenv, load_dotenv
except ImportError:
    find_dotenv = None
    load_dotenv = None

from vnalpha.core.logging import LogSurface, configure_logging
from vnalpha.maintenance.runtime_identity import collect_runtime_identity
from vnalpha.observability.context import init_run_context
from vnalpha.observability.logger import log_app


def configure_app(app: typer.Typer) -> None:
    @app.callback()
    def _app_callback() -> None:
        """Configure logging at the start of every CLI invocation."""
        _load_dotenv()
        configure_logging(surface=LogSurface.CLI)
        try:
            init_run_context(surface="cli", actor="cli")
            log_app("CLI_STARTED", "vnalpha CLI started", module="vnalpha.cli")
            log_app(
                "RUNTIME_IDENTITY",
                "vnalpha runtime identity recorded",
                module="vnalpha.cli",
                extra=collect_runtime_identity().to_log_fields(),
            )
        except Exception:  # noqa: BLE001
            pass


def _load_dotenv() -> None:
    """Load .env from the workspace root (best-effort, never raises)."""
    if find_dotenv is None or load_dotenv is None:
        return
    try:
        env_file = find_dotenv(usecwd=True)
        if env_file:
            load_dotenv(env_file, override=False)
    except Exception:  # noqa: BLE001
        pass

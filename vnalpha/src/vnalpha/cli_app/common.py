from __future__ import annotations

import typer

from vnalpha.core.logging import configure_logging


def configure_app(app: typer.Typer) -> None:
    @app.callback()
    def _app_callback() -> None:
        """Configure logging at the start of every CLI invocation."""
        _load_dotenv()
        configure_logging()
        try:
            from vnalpha.observability.context import init_run_context
            from vnalpha.observability.logger import log_app

            init_run_context(surface="cli", actor="cli")
            log_app("CLI_STARTED", "vnalpha CLI started", module="vnalpha.cli")
        except Exception:  # noqa: BLE001
            pass


def _load_dotenv() -> None:
    """Load .env from the workspace root (best-effort, never raises)."""
    try:
        from dotenv import find_dotenv, load_dotenv

        env_file = find_dotenv(usecwd=True)
        if env_file:
            load_dotenv(env_file, override=False)
    except Exception:  # noqa: BLE001
        pass

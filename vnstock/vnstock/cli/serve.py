"""CLI entry point for the vnstock local data service.

Usage::

    vnstock-serve --host 127.0.0.1 --port 6900
    python -m vnstock.cli.serve --port 6900

Or via module shorthand::

    python -m vnstock.service --host 127.0.0.1 --port 6900

Security:
  - Default host is 127.0.0.1 (localhost-only).
  - No auth login endpoint is exposed.
  - Token material is never returned.
"""

from __future__ import annotations

import argparse
import logging
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vnstock serve",
        description="Start the vnstock local data service.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        metavar="HOST",
        help="Bind address (default: 127.0.0.1 — localhost only).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=6900,
        metavar="PORT",
        help="Bind port (default: 6900).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level (default: INFO).",
    )
    parser.add_argument(
        "--with-auth",
        action="store_true",
        default=False,
        help="Enable auth status endpoint using LocalFileCredentialStore.",
    )
    return parser


def main(argv=None) -> int:
    """Entry point for ``vnstock-serve`` CLI command."""
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger(__name__)

    auth_manager = None
    if args.with_auth:
        try:
            from vnstock.core.auth.credential_store import LocalFileCredentialStore
            from vnstock.core.auth.manager import AuthManager
            from vnstock.explorer.tcbs.auth_handler import tcbs_login_handler

            store = LocalFileCredentialStore()
            auth_manager = AuthManager(store=store)
            auth_manager.register_login_handler("tcbs", tcbs_login_handler)
            logger.info("Auth manager loaded (LocalFileCredentialStore).")
        except Exception as exc:
            logger.warning(f"Could not initialize auth manager: {exc}")

    logger.info(f"Starting vnstock service on http://{args.host}:{args.port}")
    logger.info("Press Ctrl+C to stop.")
    logger.info("NOTE: Auth login must be done via CLI, not this service.")

    from vnstock.service.server import run_server

    run_server(host=args.host, port=args.port, auth_manager=auth_manager)
    return 0


if __name__ == "__main__":
    sys.exit(main())

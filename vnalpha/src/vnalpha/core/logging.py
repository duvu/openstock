"""vnalpha structured logging."""
from __future__ import annotations

import logging


def get_logger(name: str) -> logging.Logger:
    """Return a logger with vnalpha prefix."""
    return logging.getLogger(f"vnalpha.{name}")


def configure_logging(level: str = "INFO") -> None:
    """Configure root vnalpha logger."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

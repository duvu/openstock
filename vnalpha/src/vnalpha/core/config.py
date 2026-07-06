"""vnalpha configuration."""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class VnstockServiceConfig:
    base_url: str = field(
        default_factory=lambda: os.getenv("VNSTOCK_SERVICE_URL", "http://127.0.0.1:6900")
    )
    timeout: float = 30.0


@dataclass
class WarehouseConfig:
    path: Path = field(
        default_factory=lambda: Path(
            os.getenv(
                "VNALPHA_WAREHOUSE_PATH",
                str(Path.home() / ".local" / "share" / "vnalpha" / "warehouse.duckdb"),
            )
        )
    )


@dataclass
class AppConfig:
    universe: str = field(
        default_factory=lambda: os.getenv("VNALPHA_UNIVERSE", "VN30")
    )
    log_level: str = field(
        default_factory=lambda: os.getenv("VNALPHA_LOG_LEVEL", "INFO")
    )
    vnstock: VnstockServiceConfig = field(default_factory=VnstockServiceConfig)
    warehouse: WarehouseConfig = field(default_factory=WarehouseConfig)


_config: AppConfig | None = None


def get_config() -> AppConfig:
    global _config
    if _config is None:
        _config = AppConfig()
    return _config


def reset_config() -> None:
    """Reset config singleton (for testing)."""
    global _config
    _config = None

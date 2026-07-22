from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from vnalpha.core.config import AppConfig, get_config
from vnalpha.data_provisioning.source_policy import (
    SourcePolicyResolver,
    get_default_resolver,
)
from vnalpha.maintenance.software_identity import (
    SoftwareIdentity,
    resolve_software_identity,
)

_POLICY_DATASETS = (
    "reference.symbols",
    "equity.ohlcv",
    "index.ohlcv",
    "reference.index_membership_snapshot",
    "reference.sector_membership_snapshot",
)


@dataclass(frozen=True, slots=True)
class RuntimeIdentity:
    application_version: str
    source_commit: str | None
    tree_state: str | None
    package_installation_path: str
    warehouse_path: str
    vnstock_service_url: str
    provider_source_policy: Mapping[str, Mapping[str, bool | str | None]]
    process_started_at: str | None

    def to_log_fields(self) -> dict[str, object]:
        return {
            "application_version": self.application_version,
            "source_commit": self.source_commit,
            "tree_state": self.tree_state,
            "package_installation_path": self.package_installation_path,
            "warehouse_path": self.warehouse_path,
            "vnstock_service_url": self.vnstock_service_url,
            "provider_source_policy": dict(self.provider_source_policy),
            "process_started_at": self.process_started_at,
        }


def collect_runtime_identity(
    *,
    config: AppConfig | None = None,
    software_identity: SoftwareIdentity | None = None,
    source_policy_resolver: SourcePolicyResolver | None = None,
) -> RuntimeIdentity:
    resolved_config = config or get_config()
    resolved_software_identity = software_identity or resolve_software_identity()
    resolver = source_policy_resolver or get_default_resolver()
    source_policy = {
        dataset: {
            "source": resolved.source,
            "mode": resolved.mode.value,
            "fallback_allowed": resolved.fallback_allowed,
        }
        for dataset in _POLICY_DATASETS
        if (resolved := resolver.resolve(dataset))
    }
    return RuntimeIdentity(
        application_version=resolved_software_identity.package_version,
        source_commit=(
            resolved_software_identity.source_commit
            or _source_checkout_commit(Path(__file__).resolve().parents[1])
        ),
        tree_state=resolved_software_identity.tree_state,
        package_installation_path=str(Path(__file__).resolve().parents[1]),
        warehouse_path=str(resolved_config.warehouse.path.expanduser().resolve()),
        vnstock_service_url=resolved_config.vnstock.base_url,
        provider_source_policy=source_policy,
        process_started_at=_process_started_at(),
    )


def _process_started_at() -> str | None:
    try:
        stat_fields = (
            Path("/proc/self/stat")
            .read_text(encoding="utf-8")
            .rsplit(")", 1)[1]
            .split()
        )
        start_ticks = int(stat_fields[19])
        clock_ticks = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
        boot_time = next(
            int(line.split()[1])
            for line in Path("/proc/stat").read_text(encoding="utf-8").splitlines()
            if line.startswith("btime ")
        )
    except (IndexError, KeyError, OSError, StopIteration, ValueError):
        return None
    started_at = boot_time + (start_ticks / clock_ticks)
    return datetime.fromtimestamp(started_at, tz=timezone.utc).isoformat()


def _source_checkout_commit(package_path: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(package_path), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=1,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    commit = result.stdout.strip()
    if result.returncode != 0 or len(commit) != 40:
        return None
    return commit


__all__ = ["RuntimeIdentity", "collect_runtime_identity"]

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit, urlunsplit

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


class RuntimeBuildMatchStatus(StrEnum):
    MATCH = "MATCH"
    STALE = "STALE"
    UNVERIFIABLE = "UNVERIFIABLE"


@dataclass(frozen=True, slots=True)
class RuntimeIdentity:
    application_version: str
    source_commit: str | None
    current_source_commit: str | None
    build_match_status: RuntimeBuildMatchStatus
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
            "current_source_commit": self.current_source_commit,
            "build_match_status": self.build_match_status.value,
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
    current_checkout_path: Path | None = None,
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
    source_commit = resolved_software_identity.source_commit or _source_checkout_commit(
        Path(__file__).resolve().parents[1]
    )
    current_source_commit = (
        _source_checkout_commit(current_checkout_path)
        if current_checkout_path is not None
        else None
    )
    return RuntimeIdentity(
        application_version=resolved_software_identity.package_version,
        source_commit=source_commit,
        current_source_commit=current_source_commit,
        build_match_status=_build_match_status(source_commit, current_source_commit),
        tree_state=resolved_software_identity.tree_state,
        package_installation_path=str(Path(__file__).resolve().parents[1]),
        warehouse_path=str(resolved_config.warehouse.path.expanduser().resolve()),
        vnstock_service_url=_service_origin(resolved_config.vnstock.base_url),
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


def _service_origin(service_url: str) -> str:
    parsed = urlsplit(service_url)
    try:
        port = parsed.port
    except ValueError:
        return ""
    if not parsed.scheme or parsed.hostname is None:
        return ""
    host = parsed.hostname
    host_display = f"[{host}]" if ":" in host else host
    netloc = f"{host_display}:{port}" if port is not None else host_display
    return urlunsplit((parsed.scheme, netloc, "", "", ""))


def _build_match_status(
    source_commit: str | None, current_source_commit: str | None
) -> RuntimeBuildMatchStatus:
    if source_commit is None or current_source_commit is None:
        return RuntimeBuildMatchStatus.UNVERIFIABLE
    if source_commit == current_source_commit:
        return RuntimeBuildMatchStatus.MATCH
    return RuntimeBuildMatchStatus.STALE


__all__ = ["RuntimeBuildMatchStatus", "RuntimeIdentity", "collect_runtime_identity"]

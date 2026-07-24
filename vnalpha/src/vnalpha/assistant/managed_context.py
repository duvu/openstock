from __future__ import annotations

import os
from pathlib import Path

from vnalpha.assistant.app import AssistantApp
from vnalpha.assistant.gateway import LLMGatewayClient
from vnalpha.provisioning_queue import DEFAULT_QUEUE_PATH
from vnalpha.warehouse.write_coordinator import WarehouseWriteCoordinator


class ManagedAssistantContext:
    def __init__(
        self,
        *,
        surface: str,
        llm_client: LLMGatewayClient | None,
        warehouse_path: Path | str | None,
    ) -> None:
        self._engine = AssistantApp(None, surface=surface, llm_client=llm_client)
        self._surface = surface
        self._warehouse_path = warehouse_path
        self._queue_path = _queue_path_for_warehouse(warehouse_path)
        self._coordinator = WarehouseWriteCoordinator(path=warehouse_path)

    def _connected_engine(self, connection) -> AssistantApp:
        return AssistantApp(
            connection,
            surface=self._surface,
            llm_client=self._engine._llm,
        )


def _queue_path_for_warehouse(warehouse_path: Path | str | None) -> Path:
    configured = os.environ.get("VNALPHA_PROVISIONING_QUEUE_PATH", "").strip()
    if configured:
        return Path(configured).expanduser()
    if warehouse_path is None:
        return DEFAULT_QUEUE_PATH
    warehouse_parent = Path(warehouse_path).expanduser().parent
    runtime_root = (
        warehouse_parent.parent
        if warehouse_parent.name == "warehouse"
        else warehouse_parent
    )
    return runtime_root / "queue" / "provisioning.sqlite3"

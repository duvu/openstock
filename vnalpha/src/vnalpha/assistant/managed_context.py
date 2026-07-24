from __future__ import annotations

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
        self._queue_path = (
            DEFAULT_QUEUE_PATH
            if warehouse_path is None
            else Path(warehouse_path).parent / "queue" / "provisioning.sqlite3"
        )
        self._coordinator = WarehouseWriteCoordinator(path=warehouse_path)

    def _connected_engine(self, connection) -> AssistantApp:
        return AssistantApp(
            connection,
            surface=self._surface,
            llm_client=self._engine._llm,
        )

from __future__ import annotations

from typing import TYPE_CHECKING

from vnalpha.assistant.gateway import LLMGatewayClient, LLMGatewayConfig
from vnalpha.assistant.intent import IntentClassifier
from vnalpha.assistant.planner import PlanBuilder
from vnalpha.assistant.synthesizer import AnswerSynthesizer

if TYPE_CHECKING:
    from vnalpha.assistant.managed_runtime import ManagedAssistantRuntime


class ConnectedAssistantContext:
    def __init__(
        self,
        conn,
        *,
        surface: str = "cli",
        llm_client: LLMGatewayClient | None = None,
    ) -> None:
        self._conn = conn
        self._surface = surface
        self._llm = llm_client or LLMGatewayClient(LLMGatewayConfig.from_env())
        self._classifier = IntentClassifier(self._llm)
        self._planner = PlanBuilder()
        self._synthesizer = AnswerSynthesizer(self._llm)
        self._managed_runtime: ManagedAssistantRuntime | None = None

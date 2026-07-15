from __future__ import annotations


class AssistantError(Exception):
    """Base class for all assistant errors."""


class IntentClassificationError(AssistantError):
    """Raised when intent classification fails."""


class PlanBuildError(AssistantError):
    """Raised when plan construction fails."""


class PlanValidationError(AssistantError):
    """Raised when a built plan fails validation."""


class AssistantInputValidationError(AssistantError):
    pass


class ToolExecutionError(AssistantError):
    """Raised when a tool call fails during plan execution."""


class SynthesisError(AssistantError):
    """Raised when the synthesis/answer generation step fails."""


class RefusalError(AssistantError):
    """Raised when the assistant refuses to fulfil a request."""

    def __init__(
        self,
        reason: str,
        policy_category: str,
        suggestion: str | None = None,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.policy_category = policy_category
        self.suggestion = suggestion


class LLMGatewayError(AssistantError):
    """Base class for LLM gateway errors."""


class LLMTimeoutError(LLMGatewayError):
    """Raised when the LLM call times out (all retries exhausted)."""


class LLMResponseError(LLMGatewayError):
    """Raised when the LLM returns an HTTP or parse error."""


class LLMConfigError(LLMGatewayError):
    """Raised when the LLM gateway is misconfigured (e.g. missing API key)."""


class LLMNoCompatibleFallbackError(LLMGatewayError):
    """Raised when a failed strict route has no verified compatible fallback."""

    error_code = "no_compatible_fallback"

    def __init__(
        self,
        *,
        stage: str,
        primary_model: str,
        required_capability: str,
        primary_error: Exception,
    ) -> None:
        super().__init__(
            f"Primary model '{primary_model}' failed for stage '{stage}', and no "
            f"distinct configured fallback explicitly declares capability "
            f"'{required_capability}'."
        )
        self.stage = stage
        self.primary_model = primary_model
        self.required_capability = required_capability
        self.primary_error = primary_error

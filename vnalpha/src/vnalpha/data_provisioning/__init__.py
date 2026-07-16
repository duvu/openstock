from vnalpha.clients.vnstock.source_policy import ENVIRONMENT_APPROVED_SOURCES
from vnalpha.data_provisioning import service as _service
from vnalpha.data_provisioning.ensure_current_symbol import (
    CurrentSymbolReadyResult,
    ProvisioningAction,
    ProvisioningOutcome,
    ensure_current_symbol_ready,
)
from vnalpha.data_provisioning.service import (
    DataProvisioningDependencies,
    DataProvisioningRequest,
    DataProvisioningResult,
    DataProvisioningService,
    DataProvisioningValidationError,
    ProvisioningStatus,
)

# Keep the existing service API stable while making the source allowlist dynamic.
# This covers callers that import ``vnalpha.data_provisioning.service`` directly,
# because Python initialises this package before returning the submodule.
_service._APPROVED_SOURCES = ENVIRONMENT_APPROVED_SOURCES

__all__ = [
    "DataProvisioningDependencies",
    "DataProvisioningRequest",
    "DataProvisioningResult",
    "DataProvisioningService",
    "DataProvisioningValidationError",
    "ProvisioningStatus",
    "ensure_current_symbol_ready",
    "CurrentSymbolReadyResult",
    "ProvisioningAction",
    "ProvisioningOutcome",
]

# Provider Plugin Interface

The `ProviderPlugin` protocol defines how internal provider adapters are
structured for the vnstock plugin architecture.

## Protocol

```python
from typing import Protocol, Any, runtime_checkable
import pandas as pd


@runtime_checkable
class ProviderPlugin(Protocol):
    name: str  # Short uppercase name, e.g. "KBS"

    def capabilities(self) -> dict[str, Any]: ...
    def fetch(self, dataset: str, params: dict[str, Any]) -> pd.DataFrame: ...
    def validate_params(self, dataset: str, params: dict[str, Any]) -> None: ...
    def diagnostics(self) -> dict[str, Any]: ...
```

## Capability declaration

```python
def capabilities(self) -> dict:
    return {
        "equity.ohlcv": {
            "supported": True,
            "status": "stable",       # stable | experimental | partial | deprecated | unsupported
            "auth_required": False,
            "intervals": ["1D", "1W", "1M"],
            "notes": "Default OHLCV provider for Vietnamese equities.",
        },
        "equity.quote": {
            "supported": True,
            "status": "stable",
            "auth_required": False,
        },
    }
```

## Example minimal implementation

```python
import pandas as pd
from vnstock.core.provider.exceptions import UnsupportedDatasetForProviderError


class MyProvider:
    name = "MY_PROVIDER"

    _SUPPORTED = {"equity.ohlcv"}

    def capabilities(self) -> dict:
        return {
            "equity.ohlcv": {
                "supported": True,
                "status": "stable",
                "auth_required": False,
                "intervals": ["1D"],
            }
        }

    def fetch(self, dataset: str, params: dict) -> pd.DataFrame:
        if dataset not in self._SUPPORTED:
            raise UnsupportedDatasetForProviderError(self.name, dataset)
        # ... fetch and return normalized DataFrame

    def validate_params(self, dataset: str, params: dict) -> None:
        pass  # validate required params here

    def diagnostics(self) -> dict:
        return {"name": self.name, "status": "ok"}
```

## Registering a provider

```python
from vnstock.core.provider.plugin_registry import PluginRegistry

registry = PluginRegistry()
registry.register(MyProvider())

# Retrieve
provider = registry.get("MY_PROVIDER")

# Find providers for a dataset
candidates = registry.providers_for("equity.ohlcv")

# Generate capability matrix
matrix = registry.capability_matrix()
```

## Routing

```python
from vnstock.core.provider.plugin_router import PluginRouter

router = PluginRouter(registry, default_priority=["MY_PROVIDER"])

# Auto routing
provider = router.resolve("equity.ohlcv")

# Explicit routing
provider = router.resolve("equity.ohlcv", source="MY_PROVIDER")

# Routing diagnostics
print(router.last_diagnostics)
```

## Note: external packages not in Phase 1

Provider plugins in Phase 1 are internal only. External package splitting
(e.g. `vnstock-provider-kbs`) is planned for a future phase.

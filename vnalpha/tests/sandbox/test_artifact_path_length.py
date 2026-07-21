from __future__ import annotations

import pytest
from pydantic import ValidationError

from vnalpha.sandbox.contracts import SandboxOutputSchema

_OVERLONG_CHART_PATH = f"output/charts/{'a' * 1_025}.png"


def test_output_schema_rejects_overlong_optional_artifact_path() -> None:
    with pytest.raises(ValidationError):
        _ = SandboxOutputSchema.model_validate(
            {
                "artifacts": (
                    {
                        "kind": "result",
                        "path": "output/result.json",
                        "media_type": "application/json",
                    },
                    {
                        "kind": "summary",
                        "path": "output/summary.md",
                        "media_type": "text/markdown",
                    },
                    {
                        "kind": "chart",
                        "path": _OVERLONG_CHART_PATH,
                        "media_type": "image/png",
                    },
                )
            }
        )

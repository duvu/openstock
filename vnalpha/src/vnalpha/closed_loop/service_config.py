from __future__ import annotations

import os

MAX_REPAIR_ATTEMPTS = 10
DEFAULT_REPAIR_ATTEMPTS = 3


def configured_max_attempts() -> int:
    value = os.environ.get("VNALPHA_MAX_REPAIR_ATTEMPTS", str(DEFAULT_REPAIR_ATTEMPTS))
    try:
        parsed = int(value)
    except ValueError:
        return DEFAULT_REPAIR_ATTEMPTS
    return parsed if 1 <= parsed <= MAX_REPAIR_ATTEMPTS else DEFAULT_REPAIR_ATTEMPTS

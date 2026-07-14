from __future__ import annotations

import importlib
from dataclasses import dataclass
from enum import Enum
from importlib.metadata import PackageNotFoundError, version
from types import ModuleType


class FiinQuantXState(str, Enum):
    NOT_INSTALLED = "NOT_INSTALLED"
    UNTESTED_VERSION = "UNTESTED_VERSION"
    INSTALLED_SUPPORTED = "INSTALLED_SUPPORTED"


@dataclass(frozen=True)
class FiinQuantXSDK:
    state: FiinQuantXState
    module: ModuleType | None
    version: str | None


SUPPORTED_VERSIONS = {"0.1.64": "fiinquantx-contract-v1"}


def load_fiinquantx_sdk() -> FiinQuantXSDK:
    try:
        installed_version = version("fiinquantx")
    except PackageNotFoundError:
        return FiinQuantXSDK(FiinQuantXState.NOT_INSTALLED, None, None)

    state = (
        FiinQuantXState.INSTALLED_SUPPORTED
        if installed_version in SUPPORTED_VERSIONS
        else FiinQuantXState.UNTESTED_VERSION
    )
    if state is FiinQuantXState.UNTESTED_VERSION:
        return FiinQuantXSDK(state, None, installed_version)
    return FiinQuantXSDK(state, importlib.import_module("FiinQuantX"), installed_version)

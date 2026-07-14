from __future__ import annotations

import os
from types import ModuleType
from typing import Protocol

import pandas as pd

from vnstock.providers.fiinquantx.exceptions import (
    FiinQuantXCredentialsMissingError,
    FiinQuantXLicenseNotAcknowledgedError,
)


class FiinQuantXTradingEvent(Protocol):
    def get_data(self) -> pd.DataFrame: ...


class FiinQuantXSession(Protocol):
    def Fetch_Trading_Data(
        self,
        **kwargs: str | int | bool | list[str] | None,
    ) -> FiinQuantXTradingEvent: ...

    def TickerList(self, ticker: str) -> list[str]: ...


class FiinQuantXSessionProvider:
    def get_session(self, module: ModuleType, dataset: str) -> FiinQuantXSession:
        if os.environ.get("VNSTOCK_FIINQUANTX_LICENSED", "false").lower() not in {
            "1",
            "true",
            "yes",
        }:
            raise FiinQuantXLicenseNotAcknowledgedError(dataset)
        username = os.environ.get("FIINQUANT_USERNAME")
        password = os.environ.get("FIINQUANT_PASSWORD")
        if not username or not password:
            raise FiinQuantXCredentialsMissingError(dataset)
        factory = getattr(module, "FiinSession", None)
        if factory is None or not callable(factory):
            raise FiinQuantXCredentialsMissingError(dataset)
        return factory(username=username, password=password).login()

from __future__ import annotations

from vnstock.core.provider.exceptions import ProviderFetchError


class FiinQuantXProviderError(ProviderFetchError):
    def __init__(self, dataset: str) -> None:
        super().__init__("FIINQUANTX", dataset)


class FiinQuantXCredentialsMissingError(FiinQuantXProviderError):
    pass


class FiinQuantXLicenseNotAcknowledgedError(FiinQuantXProviderError):
    pass


class FiinQuantXNotInstalledError(FiinQuantXProviderError):
    pass


class FiinQuantXVersionError(FiinQuantXProviderError):
    pass


class FiinQuantXSchemaError(FiinQuantXProviderError):
    pass

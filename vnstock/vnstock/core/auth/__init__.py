"""vnstock.core.auth — centralized authentication layer.

Provides auth types, specs, contexts, policies, credential store interface,
session cache, redaction utilities, and the AuthManager.

Usage::

    from vnstock.core.auth import AuthManager, AuthType, AuthSpec, AuthPolicy
    from vnstock.core.auth.credential_store import MemoryCredentialStore

    store = MemoryCredentialStore()
    manager = AuthManager(store=store)
"""

from vnstock.core.auth.context import AuthContext
from vnstock.core.auth.credential_store import CredentialStore, MemoryCredentialStore
from vnstock.core.auth.manager import AuthManager
from vnstock.core.auth.policies import AuthPolicy
from vnstock.core.auth.redaction import redact
from vnstock.core.auth.spec import AuthSpec
from vnstock.core.auth.types import AuthType

__all__ = [
    "AuthType",
    "AuthSpec",
    "AuthContext",
    "AuthPolicy",
    "CredentialStore",
    "MemoryCredentialStore",
    "AuthManager",
    "redact",
]

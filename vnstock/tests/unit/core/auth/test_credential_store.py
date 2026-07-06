"""Tests for credential store implementations."""

from __future__ import annotations

import pytest

from vnstock.core.auth.credential_store import (
    CredentialStore,
    EnvCredentialStore,
    KeyringCredentialStore,
    LocalFileCredentialStore,
    MemoryCredentialStore,
    VaultCredentialStore,
)

# ---------------------------------------------------------------------------
# MemoryCredentialStore
# ---------------------------------------------------------------------------


class TestMemoryCredentialStore:
    def test_write_and_read(self):
        store = MemoryCredentialStore()
        store.write("tcbs", {"token": "abc123"})
        result = store.read("tcbs")
        assert result == {"token": "abc123"}

    def test_read_missing_returns_none(self):
        store = MemoryCredentialStore()
        assert store.read("nonexistent") is None

    def test_delete(self):
        store = MemoryCredentialStore()
        store.write("tcbs", {"token": "abc"})
        store.delete("tcbs")
        assert store.read("tcbs") is None

    def test_delete_nonexistent_no_error(self):
        store = MemoryCredentialStore()
        store.delete("nonexistent")  # no-op, no error

    def test_has_returns_true_when_stored(self):
        store = MemoryCredentialStore()
        assert not store.has("tcbs")
        store.write("tcbs", {"token": "abc"})
        assert store.has("tcbs")

    def test_write_returns_copy(self):
        store = MemoryCredentialStore()
        original = {"token": "abc"}
        store.write("tcbs", original)
        original["token"] = "mutated"
        result = store.read("tcbs")
        assert result["token"] == "abc"  # not mutated

    def test_read_returns_copy(self):
        store = MemoryCredentialStore()
        store.write("tcbs", {"token": "abc"})
        r1 = store.read("tcbs")
        r1["token"] = "mutated"
        r2 = store.read("tcbs")
        assert r2["token"] == "abc"  # not mutated

    def test_safe_diagnostics(self):
        store = MemoryCredentialStore()
        diag = store.safe_diagnostics("tcbs")
        assert diag["stored"] is False
        assert diag["source"] == "memory"

        store.write("tcbs", {"token": "abc"})
        diag2 = store.safe_diagnostics("tcbs")
        assert diag2["stored"] is True
        assert "token" not in diag2

    def test_multiple_providers(self):
        store = MemoryCredentialStore()
        store.write("tcbs", {"token": "t1"})
        store.write("vci", {"token": "t2"})
        assert store.read("tcbs") == {"token": "t1"}
        assert store.read("vci") == {"token": "t2"}


# ---------------------------------------------------------------------------
# EnvCredentialStore
# ---------------------------------------------------------------------------


class TestEnvCredentialStore:
    def test_read_from_env(self, monkeypatch):
        monkeypatch.setenv("VNSTOCK_TCBS_TOKEN", "env_token_123")
        store = EnvCredentialStore()
        result = store.read("tcbs")
        assert result is not None
        assert result["token"] == "env_token_123"

    def test_read_missing_env_returns_none(self, monkeypatch):
        monkeypatch.delenv("VNSTOCK_TCBS_TOKEN", raising=False)
        store = EnvCredentialStore()
        assert store.read("tcbs") is None

    def test_write_is_noop(self):
        store = EnvCredentialStore()
        store.write("tcbs", {"token": "test"})  # no-op

    def test_delete_is_noop(self):
        store = EnvCredentialStore()
        store.delete("tcbs")  # no-op

    def test_has_with_env(self, monkeypatch):
        monkeypatch.setenv("VNSTOCK_TCBS_TOKEN", "tok")
        store = EnvCredentialStore()
        assert store.has("tcbs") is True

    def test_custom_prefix(self, monkeypatch):
        monkeypatch.setenv("MYAPP_TCBS_TOKEN", "tok")
        store = EnvCredentialStore(prefix="MYAPP")
        result = store.read("tcbs")
        assert result is not None
        assert result["token"] == "tok"

    def test_safe_diagnostics_no_token(self, monkeypatch):
        monkeypatch.delenv("VNSTOCK_TCBS_TOKEN", raising=False)
        store = EnvCredentialStore()
        diag = store.safe_diagnostics("tcbs")
        assert diag["stored"] is False
        assert diag["source"] == "env"
        # env_key shows the key name (safe), not the value
        assert "env_key" in diag
        assert diag["env_key"] == "VNSTOCK_TCBS_TOKEN"


# ---------------------------------------------------------------------------
# LocalFileCredentialStore
# ---------------------------------------------------------------------------


class TestLocalFileCredentialStore:
    def test_write_and_read(self, tmp_path):
        store = LocalFileCredentialStore(base_dir=tmp_path)
        store.write("tcbs", {"token": "file_token"})
        result = store.read("tcbs")
        assert result == {"token": "file_token"}

    def test_read_missing_returns_none(self, tmp_path):
        store = LocalFileCredentialStore(base_dir=tmp_path)
        assert store.read("nonexistent") is None

    def test_delete(self, tmp_path):
        store = LocalFileCredentialStore(base_dir=tmp_path)
        store.write("tcbs", {"token": "abc"})
        store.delete("tcbs")
        assert store.read("tcbs") is None

    def test_delete_nonexistent_no_error(self, tmp_path):
        store = LocalFileCredentialStore(base_dir=tmp_path)
        store.delete("nonexistent")  # no-op

    def test_has(self, tmp_path):
        store = LocalFileCredentialStore(base_dir=tmp_path)
        assert not store.has("tcbs")
        store.write("tcbs", {"token": "x"})
        assert store.has("tcbs")

    def test_safe_diagnostics(self, tmp_path):
        store = LocalFileCredentialStore(base_dir=tmp_path)
        diag = store.safe_diagnostics("tcbs")
        assert diag["stored"] is False
        assert diag["source"] == "local_file"
        assert "token" not in diag

        store.write("tcbs", {"token": "x"})
        diag2 = store.safe_diagnostics("tcbs")
        assert diag2["stored"] is True

    def test_multiple_providers(self, tmp_path):
        store = LocalFileCredentialStore(base_dir=tmp_path)
        store.write("tcbs", {"token": "t1"})
        store.write("vci", {"token": "t2"})
        assert store.read("tcbs") == {"token": "t1"}
        assert store.read("vci") == {"token": "t2"}


# ---------------------------------------------------------------------------
# KeyringCredentialStore
# ---------------------------------------------------------------------------


class TestKeyringCredentialStore:
    def test_graceful_when_keyring_unavailable(self):
        """Store should not raise if keyring package is missing."""
        store = KeyringCredentialStore()
        # read returns None (no error) even if keyring unavailable
        result = store.read("tcbs")
        assert result is None or isinstance(result, dict)

    def test_write_no_error_when_unavailable(self):
        store = KeyringCredentialStore()
        store.write("tcbs", {"token": "x"})  # no-op if unavailable

    def test_delete_no_error_when_unavailable(self):
        store = KeyringCredentialStore()
        store.delete("tcbs")  # no-op if unavailable

    def test_safe_diagnostics_includes_available(self):
        store = KeyringCredentialStore()
        diag = store.safe_diagnostics("tcbs")
        assert "available" in diag
        assert diag["source"] == "keyring"


# ---------------------------------------------------------------------------
# VaultCredentialStore
# ---------------------------------------------------------------------------


class TestVaultCredentialStore:
    def test_read_raises_not_implemented(self):
        store = VaultCredentialStore()
        with pytest.raises(NotImplementedError):
            store.read("tcbs")

    def test_write_raises_not_implemented(self):
        store = VaultCredentialStore()
        with pytest.raises(NotImplementedError):
            store.write("tcbs", {"token": "abc"})

    def test_delete_raises_not_implemented(self):
        store = VaultCredentialStore()
        with pytest.raises(NotImplementedError):
            store.delete("tcbs")

    def test_safe_diagnostics_returns_dict(self):
        store = VaultCredentialStore()
        diag = store.safe_diagnostics("tcbs")
        assert isinstance(diag, dict)
        assert diag["source"] == "vault"


# ---------------------------------------------------------------------------
# CredentialStore interface compliance
# ---------------------------------------------------------------------------


class TestCredentialStoreInterface:
    """Ensure all implementations satisfy the CredentialStore interface."""

    def test_memory_is_credential_store(self):
        assert isinstance(MemoryCredentialStore(), CredentialStore)

    def test_env_is_credential_store(self):
        assert isinstance(EnvCredentialStore(), CredentialStore)

    def test_local_file_is_credential_store(self):
        assert isinstance(LocalFileCredentialStore(), CredentialStore)

    def test_keyring_is_credential_store(self):
        assert isinstance(KeyringCredentialStore(), CredentialStore)

    def test_vault_is_credential_store(self):
        assert isinstance(VaultCredentialStore(), CredentialStore)

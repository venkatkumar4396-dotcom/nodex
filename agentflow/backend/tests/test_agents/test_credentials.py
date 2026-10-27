"""
Phase 2 tests — CredentialStore.

Tests encryption, decryption, env var loading, and node resolution.
"""
from __future__ import annotations

import pytest


class TestCredentialStore:
    @pytest.fixture
    def store(self):
        """Fresh credential store for each test."""
        from agentflow.core.tools.credentials import CredentialStore
        return CredentialStore()

    def test_set_and_get(self, store):
        """Credentials survive encrypt/decrypt round-trip."""
        store.set("my_key", "super-secret-value")
        assert store.get("my_key") == "super-secret-value"

    def test_get_missing_returns_none(self, store):
        assert store.get("nonexistent") is None

    def test_has(self, store):
        assert not store.has("x")
        store.set("x", "v")
        assert store.has("x")

    def test_list_ids(self, store):
        store.set("a", "1")
        store.set("b", "2")
        ids = store.list_ids()
        assert "a" in ids
        assert "b" in ids

    def test_load_from_env(self, store):
        """Loads credentials from env vars using the mapping."""
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("TEST_API_KEY_ABC", "my-test-key")
            store.load_from_env({"test_key": "TEST_API_KEY_ABC"})

        assert store.get("test_key") == "my-test-key"

    def test_load_from_env_skips_empty(self, store):
        """Empty env vars are not stored."""
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("EMPTY_VAR", "")
            store.load_from_env({"empty_cred": "EMPTY_VAR"})

        assert not store.has("empty_cred")

    def test_resolve_for_node(self, store):
        """resolve_for_node returns tool_name → value mapping."""
        store.set("sg_key", "SG.abc123")
        result = store.resolve_for_node({"email_send": "sg_key"})
        assert result == {"email_send": "SG.abc123"}

    def test_resolve_for_node_skips_missing(self, store):
        """Missing credential IDs are omitted from the result."""
        result = store.resolve_for_node({"some_tool": "nonexistent_cred"})
        assert result == {}

    def test_value_not_exposed_in_repr(self, store):
        """Credential values must never appear in string representations."""
        store.set("secret_cred", "TOP_SECRET_VALUE")
        # The raw _store has encrypted bytes, not plaintext
        raw = store._store.get("secret_cred", b"")
        assert b"TOP_SECRET_VALUE" not in raw

    def test_special_chars_round_trip(self, store):
        """Unicode and special characters survive the round-trip."""
        value = "p@ssw0rd!🔐 日本語"
        store.set("unicode_key", value)
        assert store.get("unicode_key") == value

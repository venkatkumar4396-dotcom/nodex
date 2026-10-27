"""
CredentialStore — encrypted credential management for Phase 2+.

Design:
  - Credentials are stored encrypted with Fernet symmetric encryption.
  - In Phase 2, credentials are stored in-memory (loaded from env/.env).
  - In Phase 4, they'll live encrypted in Postgres.
  - Credentials are NEVER logged, put in prompts, or included in ToolResult.
  - Injection: node_runner calls store.inject(tool, credential_ids)
    which returns a new tool copy with the credential set, keeping the
    original tool credential-free.

Security:
  - Fernet key loaded from FERNET_KEY env var. If missing, a one-session
    ephemeral key is generated and a warning is logged.
  - All credential values are scrubbed from structured logs.
"""
from __future__ import annotations

import base64
import os

import structlog

log = structlog.get_logger(__name__)

# ── Fernet encryption setup ───────────────────────────────────────────────────

def _get_or_create_fernet():
    """Load or generate a Fernet encryption key. Warn if ephemeral."""
    try:
        from cryptography.fernet import Fernet
        key_str = os.environ.get("FERNET_KEY", "")
        if key_str:
            return Fernet(key_str.encode())
        else:
            # Ephemeral key — works within a session but credentials don't
            # survive restart. Fine for Phase 2 dev; Phase 4 requires a real key.
            key = Fernet.generate_key()
            log.warning(
                "fernet_ephemeral_key",
                msg="FERNET_KEY not set; using an ephemeral session key. "
                    "Credentials will be lost on restart. Set FERNET_KEY in .env.",
            )
            return Fernet(key)
    except ImportError:
        log.warning(
            "cryptography_not_installed",
            msg="cryptography package not installed; credentials stored as plaintext. "
                "Run: pip install cryptography",
        )
        return None


class CredentialStore:
    """
    In-memory encrypted credential store.

    Phase 2: credentials loaded from environment variables or set programmatically.
    Phase 4: backed by Postgres with per-workspace encryption.

    Usage:
        store = CredentialStore()
        store.set("my_sendgrid_key", "SG.xxx...")
        value = store.get("my_sendgrid_key")
    """

    def __init__(self) -> None:
        self._fernet = _get_or_create_fernet()
        # cred_id → encrypted bytes (or plaintext bytes if no Fernet)
        self._store: dict[str, bytes] = {}

    def set(self, cred_id: str, value: str) -> None:
        """Store a credential value (encrypted)."""
        raw = value.encode("utf-8")
        if self._fernet:
            stored = self._fernet.encrypt(raw)
        else:
            stored = base64.b64encode(raw)
        self._store[cred_id] = stored
        log.debug("credential_stored", cred_id=cred_id)  # Never log value!

    def get(self, cred_id: str) -> str | None:
        """Retrieve and decrypt a credential. Returns None if not found."""
        encrypted = self._store.get(cred_id)
        if encrypted is None:
            return None
        try:
            if self._fernet:
                return self._fernet.decrypt(encrypted).decode("utf-8")
            else:
                return base64.b64decode(encrypted).decode("utf-8")
        except Exception as e:
            log.error("credential_decrypt_failed", cred_id=cred_id, error=str(e))
            return None

    def load_from_env(self, mappings: dict[str, str]) -> None:
        """
        Load credentials from environment variables.

        Args:
            mappings: {cred_id: env_var_name}
                      e.g. {"sendgrid_key": "SENDGRID_API_KEY"}
        """
        for cred_id, env_var in mappings.items():
            value = os.environ.get(env_var, "")
            if value:
                self.set(cred_id, value)
                log.debug("credential_loaded_from_env", cred_id=cred_id, env_var=env_var)

    def resolve_for_node(
        self,
        credential_ids: dict[str, str],
    ) -> dict[str, str]:
        """
        Resolve credential_ids map for a node into actual credential values.

        Args:
            credential_ids: {tool_name: cred_id}
                e.g. {"email_send": "my_sendgrid_key"}

        Returns:
            {tool_name: decrypted_value} — keys missing from the store are omitted.
        """
        result: dict[str, str] = {}
        for tool_name, cred_id in credential_ids.items():
            value = self.get(cred_id)
            if value is not None:
                result[tool_name] = value
        return result

    def has(self, cred_id: str) -> bool:
        return cred_id in self._store

    def list_ids(self) -> list[str]:
        return list(self._store.keys())


# Global singleton
credential_store = CredentialStore()


def load_default_credentials_from_env() -> None:
    """
    Load the standard set of credential mappings from environment variables.

    Called at startup alongside register_all_builtin_tools().
    Tools check for their credential at execution time via the store.
    """
    credential_store.load_from_env({
        # Web search
        "serper_api_key": "SERPER_API_KEY",
        "serpapi_key": "SERPAPI_KEY",
        "brave_search_key": "BRAVE_SEARCH_API_KEY",
        # Email (SendGrid / SMTP)
        "sendgrid_key": "SENDGRID_API_KEY",
        "smtp_password": "SMTP_PASSWORD",
        # HTTP tool
        "http_bearer_token": "HTTP_BEARER_TOKEN",
        # OpenAI / LLM keys (also loaded by litellm directly but stored here
        # so the credential system can override them per-workspace in Phase 4)
        "openai_key": "OPENAI_API_KEY",
        "anthropic_key": "ANTHROPIC_API_KEY",
        "moonshot_key": "MOONSHOT_API_KEY",
    })

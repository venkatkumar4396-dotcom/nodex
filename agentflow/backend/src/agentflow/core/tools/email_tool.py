"""
EmailSendTool — send emails via SendGrid or SMTP.

Security:
  - API keys are retrieved from CredentialStore at execution time.
  - No secrets ever appear in logs, prompts, or ToolResult.
  - The "to" address is validated before sending.
  - Email body is treated as content data, not instructions.

Supports:
  1. SendGrid API   (SENDGRID_API_KEY)   — default, reliable delivery
  2. SMTP           (SMTP_* env vars)    — fallback / self-hosted
  3. Stub/dry-run   (no key configured)  — logs but doesn't send; returns success

In Phase 2, stub mode is the default unless an API key is configured.
This keeps CI and demos safe.
"""
from __future__ import annotations

import re
from typing import Any, ClassVar

import structlog

from agentflow.core.schemas.tool import ToolResult
from agentflow.core.tools.base import BaseTool

log = structlog.get_logger(__name__)

# Simple email regex (not RFC-complete but good enough for validation)
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class EmailSendTool(BaseTool):
    """
    Send an email. Supports SendGrid and SMTP, with a dry-run stub fallback.

    Arguments:
      to      (str)  : Recipient email address
      subject (str)  : Email subject line
      body    (str)  : Email body (plain text or HTML)
      from_email (str, optional): Sender address (defaults to FROM_EMAIL env var)
      is_html (bool, optional): True if body is HTML (default False)

    Returns ToolResult.data:
      {
        "sent": true,
        "to": "...",
        "subject": "...",
        "backend": "sendgrid" | "smtp" | "stub",
        "message_id": "..."  # if available
      }
    """

    name: ClassVar[str] = "email_send"
    is_destructive: ClassVar[bool] = True
    description: ClassVar[str] = (
        "Send an email to a recipient. Use for outreach emails, notifications, "
        "reports, or any other email communication. "
        "Specify the recipient address, subject, and body."
    )
    parameters_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "to": {
                "type": "string",
                "description": "Recipient email address",
            },
            "subject": {
                "type": "string",
                "description": "Email subject line",
            },
            "body": {
                "type": "string",
                "description": "Email body content (plain text or HTML)",
            },
            "from_email": {
                "type": "string",
                "description": "Sender email address (optional, uses FROM_EMAIL env var if not set)",
            },
            "is_html": {
                "type": "boolean",
                "description": "Set to true if body is HTML (default false = plain text)",
                "default": False,
            },
        },
        "required": ["to", "subject", "body"],
    }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        import os

        to: str = arguments.get("to", "").strip()
        subject: str = arguments.get("subject", "").strip()
        body: str = arguments.get("body", "").strip()
        from_email: str = arguments.get("from_email", "").strip() or os.environ.get(
            "FROM_EMAIL", "agentflow@example.com"
        )
        is_html: bool = bool(arguments.get("is_html", False))

        # Validate
        if not to or not _EMAIL_RE.match(to):
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Invalid or missing recipient email: '{to}'",
            )
        if not subject:
            return ToolResult(tool_name=self.name, success=False, error="Subject is required")
        if not body:
            return ToolResult(tool_name=self.name, success=False, error="Body is required")

        log.info("email_send_execute", to=to, subject=subject, backend_attempt="sendgrid")

        # Try SendGrid
        result = await self._try_sendgrid(to, subject, body, from_email, is_html)
        if result is not None:
            return result

        # Try SMTP
        result = await self._try_smtp(to, subject, body, from_email, is_html)
        if result is not None:
            return result

        # Stub mode — log and return success without actually sending
        log.warning(
            "email_send_stub",
            to=to,
            subject=subject,
            msg="No email backend configured; email NOT sent (stub mode). "
                "Set SENDGRID_API_KEY or SMTP_* env vars to send real emails.",
        )
        return ToolResult(
            tool_name=self.name,
            success=True,
            data={
                "sent": False,
                "stub": True,
                "to": to,
                "subject": subject,
                "backend": "stub",
                "message_id": None,
                "note": "Email not actually sent — no backend configured.",
            },
            metadata={"stub": True},
        )

    async def _try_sendgrid(
        self,
        to: str,
        subject: str,
        body: str,
        from_email: str,
        is_html: bool,
    ) -> ToolResult | None:
        """Send via SendGrid API v3."""
        from agentflow.core.tools.credentials import credential_store
        api_key = credential_store.get("sendgrid_key")
        if not api_key:
            return None

        try:
            import httpx
            content_type = "text/html" if is_html else "text/plain"
            payload = {
                "personalizations": [{"to": [{"email": to}]}],
                "from": {"email": from_email},
                "subject": subject,
                "content": [{"type": content_type, "value": body}],
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                )

            if response.status_code in (200, 202):
                message_id = response.headers.get("X-Message-Id", "")
                log.info("email_sendgrid_ok", to=to, message_id=message_id)
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    data={
                        "sent": True,
                        "to": to,
                        "subject": subject,
                        "backend": "sendgrid",
                        "message_id": message_id,
                    },
                )
            else:
                log.warning(
                    "email_sendgrid_error",
                    status=response.status_code,
                    body=response.text[:200],
                )
                return ToolResult(
                    tool_name=self.name,
                    success=False,
                    error=f"SendGrid error {response.status_code}: {response.text[:200]}",
                )
        except Exception as e:
            log.warning("email_sendgrid_failed", error=str(e))
            return None

    async def _try_smtp(
        self,
        to: str,
        subject: str,
        body: str,
        from_email: str,
        is_html: bool,
    ) -> ToolResult | None:
        """Send via SMTP (using aiosmtplib if available)."""
        import os

        from agentflow.core.tools.credentials import credential_store

        smtp_host = os.environ.get("SMTP_HOST", "")
        smtp_port_str = os.environ.get("SMTP_PORT", "587")
        smtp_user = os.environ.get("SMTP_USER", "")
        smtp_password = credential_store.get("smtp_password") or os.environ.get("SMTP_PASSWORD", "")

        if not smtp_host or not smtp_user:
            return None

        try:
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            import aiosmtplib

            msg = MIMEMultipart("alternative")
            msg["From"] = from_email
            msg["To"] = to
            msg["Subject"] = subject
            mime_type = "html" if is_html else "plain"
            msg.attach(MIMEText(body, mime_type, "utf-8"))

            await aiosmtplib.send(
                msg,
                hostname=smtp_host,
                port=int(smtp_port_str),
                username=smtp_user,
                password=smtp_password,
                start_tls=True,
            )

            log.info("email_smtp_ok", to=to, subject=subject)
            return ToolResult(
                tool_name=self.name,
                success=True,
                data={
                    "sent": True,
                    "to": to,
                    "subject": subject,
                    "backend": "smtp",
                    "message_id": None,
                },
            )
        except ImportError:
            log.debug("aiosmtplib_not_installed", msg="Install aiosmtplib for SMTP support")
            return None
        except Exception as e:
            log.warning("email_smtp_failed", error=str(e))
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"SMTP error: {str(e)[:300]}",
            )

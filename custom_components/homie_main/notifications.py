# custom_components/homie_main/notifications.py
"""Notification service for Homie Main."""

from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    LEVEL_INFO,
    LEVEL_TIP,
    LEVEL_WARNING,
    LEVEL_ALERT,
    LEVEL_AWARD,
    LEVEL_HIERARCHY,
    OPT_SMTP_HOST,
    OPT_SMTP_PORT,
    OPT_SMTP_SSL,
    OPT_SMTP_STARTTLS,
    OPT_SMTP_USERNAME,
    OPT_SMTP_PASSWORD,
    OPT_SMTP_TO,
    CONF_PUSH_GENERAL,
    CONF_PUSH_WARNINGS,
    CONF_PUSH_ALERTS,
    CONF_MAIL_WARNINGS,
    CONF_MAIL_ALERTS,
    DEFAULT_SMTP_HOST,
    DEFAULT_SMTP_PORT,
    DEFAULT_SMTP_SSL,
    DEFAULT_SMTP_STARTTLS,
    DEFAULT_SMTP_USERNAME,
    DEFAULT_SMTP_PASSWORD,
    DEFAULT_SMTP_TO,
)

_LOGGER = logging.getLogger(__name__)

# Level to emoji mapping
LEVEL_EMOJI = {
    LEVEL_INFO: "ℹ️",
    LEVEL_TIP: "💡",
    LEVEL_WARNING: "⚠️",
    LEVEL_ALERT: "🚨",
    LEVEL_AWARD: "🏆",
}


class NotificationService:
    """Service for sending notifications via email and push."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        """Initialize the notification service."""
        self.hass = hass
        self._config = config

    def _should_send_push(self, level: str) -> bool:
        """Check if push notification should be sent for this level."""
        level_lower = level.lower()
        level_value = LEVEL_HIERARCHY.get(level_lower, 0)

        # Check config settings
        if level_lower in ("alert",) and self._config.get(CONF_PUSH_ALERTS, True):
            return True
        if level_lower in ("warning",) and self._config.get(CONF_PUSH_WARNINGS, True):
            return True
        if level_lower in ("info", "tip", "award") and self._config.get(CONF_PUSH_GENERAL, True):
            return True

        return False

    def _should_send_email(self, level: str) -> bool:
        """Check if email notification should be sent for this level."""
        level_lower = level.lower()

        # Only warnings and alerts can trigger emails
        if level_lower == "alert" and self._config.get(CONF_MAIL_ALERTS, True):
            return True
        if level_lower == "warning" and self._config.get(CONF_MAIL_WARNINGS, True):
            return True

        return False

    async def send_notification(
        self,
        title: str,
        message: str,
        level: str = LEVEL_INFO,
        push: bool | None = None,
        email: bool | None = None,
    ) -> dict[str, Any]:
        """Send a notification via configured channels.

        Args:
            title: Notification title
            message: Notification message body
            level: Notification level (Info, Tip, Warning, Alert, Award)
            push: Override push setting (None = use config)
            email: Override email setting (None = use config)

        Returns:
            Dict with results for each channel
        """
        results: dict[str, Any] = {
            "push_sent": False,
            "email_sent": False,
            "push_error": None,
            "email_error": None,
        }

        emoji = LEVEL_EMOJI.get(level, "")

        # Format title: "Homie - 🚨 Title"
        full_title = f"Homie - {emoji} {title}".strip()

        # Determine if we should send
        should_push = push if push is not None else self._should_send_push(level)
        should_email = email if email is not None else self._should_send_email(level)

        # Send push notification
        if should_push:
            try:
                await self._send_push(full_title, message)
                results["push_sent"] = True
                _LOGGER.info("Push notification sent: %s", title)
            except Exception as err:
                results["push_error"] = str(err)
                _LOGGER.error("Failed to send push notification: %s", err)

        # Send email notification
        if should_email:
            try:
                await self._send_email(full_title, message, level)
                results["email_sent"] = True
                _LOGGER.info("Email notification sent: %s", title)
            except Exception as err:
                results["email_error"] = str(err)
                _LOGGER.error("Failed to send email notification: %s", err)

        return results

    async def _send_push(self, title: str, message: str) -> None:
        """Send push notification via Home Assistant notify service."""
        # Use persistent_notification as fallback, or mobile_app if available
        # First try to find mobile app notify services
        notify_services = [
            service
            for service in self.hass.services.async_services().get("notify", {})
            if service.startswith("mobile_app_")
        ]

        if notify_services:
            # Send to all mobile app services
            for service_name in notify_services:
                await self.hass.services.async_call(
                    "notify",
                    service_name,
                    {
                        "title": title,
                        "message": message,
                    },
                    blocking=True,
                )
        else:
            # Fallback to persistent notification
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": title,
                    "message": message,
                    "notification_id": f"homie_main_{hash(title + message) % 10000}",
                },
                blocking=True,
            )

    async def _send_email(self, title: str, message: str, level: str) -> None:
        """Send email notification via SMTP."""
        smtp_host = self._config.get(OPT_SMTP_HOST, DEFAULT_SMTP_HOST)
        smtp_port = self._config.get(OPT_SMTP_PORT, DEFAULT_SMTP_PORT)
        smtp_ssl = self._config.get(OPT_SMTP_SSL, DEFAULT_SMTP_SSL)
        smtp_starttls = self._config.get(OPT_SMTP_STARTTLS, DEFAULT_SMTP_STARTTLS)
        smtp_username = self._config.get(OPT_SMTP_USERNAME, DEFAULT_SMTP_USERNAME)
        smtp_password = self._config.get(OPT_SMTP_PASSWORD, DEFAULT_SMTP_PASSWORD)
        smtp_to = self._config.get(OPT_SMTP_TO, DEFAULT_SMTP_TO)

        if not smtp_to:
            _LOGGER.warning("No email recipients configured, skipping email")
            return

        # Parse recipients (comma-separated)
        recipients = [r.strip() for r in smtp_to.split(",") if r.strip()]
        if not recipients:
            _LOGGER.warning("No valid email recipients found")
            return

        # Create email
        msg = MIMEMultipart("alternative")
        msg["Subject"] = title
        msg["From"] = smtp_username
        msg["To"] = ", ".join(recipients)

        # Plain text version
        text_content = f"{title}\n\n{message}\n\n---\nAutomatisch verzonden vanuit Homie, a.u.b. niet reageren."

        # HTML version with black/white styling
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px; color: #000;">
            <p style="color: #666; font-size: 11px; margin-bottom: 20px;">
                This is an auto-generated email, please do not reply.
            </p>
            <div style="border-left: 4px solid #000; padding-left: 15px;">
                <h2 style="color: #000; margin: 0 0 10px 0;">{title}</h2>
                <p style="color: #333; line-height: 1.6;">{message}</p>
            </div>
            <hr style="border: none; border-top: 1px solid #ccc; margin: 20px 0;">
            <p style="color: #999; font-size: 12px;">
                Automatisch verzonden vanuit Homie, a.u.b. niet reageren.
            </p>
        </body>
        </html>
        """

        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        # Send email in executor to not block
        await self.hass.async_add_executor_job(
            self._send_email_sync,
            smtp_host,
            smtp_port,
            smtp_ssl,
            smtp_starttls,
            smtp_username,
            smtp_password,
            recipients,
            msg,
        )

    def _send_email_sync(
        self,
        host: str,
        port: int,
        use_ssl: bool,
        use_starttls: bool,
        username: str,
        password: str,
        recipients: list[str],
        msg: MIMEMultipart,
    ) -> None:
        """Send email synchronously (called from executor)."""
        context = ssl.create_default_context()

        if use_ssl:
            # SSL connection from the start
            with smtplib.SMTP_SSL(host, port, context=context) as server:
                server.login(username, password)
                server.sendmail(username, recipients, msg.as_string())
        else:
            # Plain connection, optionally upgrade to TLS
            with smtplib.SMTP(host, port) as server:
                if use_starttls:
                    server.starttls(context=context)
                server.login(username, password)
                server.sendmail(username, recipients, msg.as_string())

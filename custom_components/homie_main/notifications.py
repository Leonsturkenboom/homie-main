# custom_components/homie_main/notifications.py
"""Notification system for Homie Main integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from collections import deque
from email.message import EmailMessage
from typing import Any, Deque, Dict, Optional

import aiosmtplib

from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    OPT_NOTIFICATIONS_ENABLED,
    OPT_PUSH_ENABLED,
    OPT_EMAIL_ENABLED,
    OPT_NOTIFICATION_LEVEL,
    OPT_PUSH_LEVEL,
    OPT_NOTIFY_TARGET_PUSH,
    DEFAULT_NOTIFICATIONS_ENABLED,
    DEFAULT_PUSH_ENABLED,
    DEFAULT_EMAIL_ENABLED,
    DEFAULT_NOTIFICATION_LEVEL,
    DEFAULT_PUSH_LEVEL,
    DEFAULT_NOTIFY_TARGET_PUSH,
    # SMTP
    OPT_SMTP_HOST,
    OPT_SMTP_PORT,
    OPT_SMTP_STARTTLS,
    OPT_SMTP_SSL,
    OPT_SMTP_USERNAME,
    OPT_SMTP_PASSWORD,
    OPT_SMTP_FROM,
    OPT_SMTP_TO_WARNINGS,
    OPT_SMTP_TO_ALERTS,
    DEFAULT_SMTP_HOST,
    DEFAULT_SMTP_PORT,
    DEFAULT_SMTP_STARTTLS,
    DEFAULT_SMTP_SSL,
    DEFAULT_SMTP_USERNAME,
    DEFAULT_SMTP_PASSWORD,
    DEFAULT_SMTP_FROM,
    DEFAULT_SMTP_TO_WARNINGS,
    DEFAULT_SMTP_TO_ALERTS,
    # Others
    EVENT_HOMIE_NOTIFICATION,
    NOTIFICATION_STORE_KEY,
    NOTIFICATION_HISTORY_SIZE,
    LEVEL_HIERARCHY,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class HomieNotification:
    """Represents a notification in the Homie system."""

    ts: str
    level: str
    title: str
    message: str
    source: str
    tag: str


def _now_iso() -> str:
    """Return current UTC time as ISO string."""
    return dt_util.utcnow().isoformat()


def _normalize_level(level: str | None) -> str:
    """Normalize notification level to lowercase."""
    if not level:
        return "info"
    return str(level).strip().lower()


def _parse_recipients(raw: str) -> list[str]:
    """Parse comma-separated email recipients."""
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def _get_smtp_recipients(level: str, entry_options: dict[str, Any]) -> list[str]:
    """Determine SMTP recipients based on notification level.

    Warnings go to TO_WARNINGS, Alerts go to TO_ALERTS.
    """
    level_lower = _normalize_level(level)

    # Alerts go to TO_ALERTS
    if level_lower == "alert":
        to_raw = entry_options.get(OPT_SMTP_TO_ALERTS, DEFAULT_SMTP_TO_ALERTS)
        return _parse_recipients(to_raw)

    # Warnings and below go to TO_WARNINGS
    to_raw = entry_options.get(OPT_SMTP_TO_WARNINGS, DEFAULT_SMTP_TO_WARNINGS)
    return _parse_recipients(to_raw)


def _should_send_by_level(
    level: str, threshold_level: str
) -> bool:
    """Check if notification should be sent based on level threshold."""
    if threshold_level == "All":
        return True

    level_value = LEVEL_HIERARCHY.get(_normalize_level(level), 0)
    threshold_value = LEVEL_HIERARCHY.get(_normalize_level(threshold_level), 999)

    return level_value >= threshold_value


async def async_setup_notifications(hass: HomeAssistant) -> None:
    """Setup the Homie notification system."""
    if NOTIFICATION_STORE_KEY not in hass.data:
        hass.data[NOTIFICATION_STORE_KEY] = {
            "items": deque(maxlen=NOTIFICATION_HISTORY_SIZE)
        }

    @callback
    def _append(item: HomieNotification) -> None:
        """Add notification to history."""
        hass.data[NOTIFICATION_STORE_KEY]["items"].appendleft(item)

    async def _call_notify_service(target: str, payload: dict[str, Any]) -> None:
        """Call a notification service safely."""
        if not target or "." not in target:
            return
        domain, service = target.split(".", 1)
        try:
            await hass.services.async_call(domain, service, payload, blocking=False)
        except Exception as err:
            _LOGGER.warning("Failed to call notify service %s: %s", target, err)

    async def _send_smtp_email(
        entry_options: dict[str, Any], level: str, subject: str, body: str
    ) -> None:
        """Send email notification via SMTP."""
        host = str(entry_options.get(OPT_SMTP_HOST, DEFAULT_SMTP_HOST)).strip()
        port = int(entry_options.get(OPT_SMTP_PORT, DEFAULT_SMTP_PORT))
        starttls = bool(entry_options.get(OPT_SMTP_STARTTLS, DEFAULT_SMTP_STARTTLS))
        use_ssl = bool(entry_options.get(OPT_SMTP_SSL, DEFAULT_SMTP_SSL))
        username = str(entry_options.get(OPT_SMTP_USERNAME, DEFAULT_SMTP_USERNAME))
        password = str(entry_options.get(OPT_SMTP_PASSWORD, DEFAULT_SMTP_PASSWORD))
        from_addr = str(entry_options.get(OPT_SMTP_FROM, DEFAULT_SMTP_FROM)).strip()

        # Get recipients based on level
        to_addrs = _get_smtp_recipients(level, entry_options)

        # Not configured -> no-op
        if not host or not from_addr or not to_addrs:
            _LOGGER.debug("SMTP not fully configured, skipping email")
            return

        msg = EmailMessage()
        msg["From"] = from_addr
        msg["To"] = ", ".join(to_addrs)
        msg["Subject"] = subject
        msg.set_content(body)

        try:
            await aiosmtplib.send(
                msg,
                hostname=host,
                port=port,
                start_tls=starttls,
                use_tls=use_ssl,
                username=username or None,
                password=password or None,
                timeout=15,
            )
            _LOGGER.debug("Email sent to %s", ", ".join(to_addrs))
        except Exception as err:
            _LOGGER.warning("Failed to send email: %s", err)

    async def _publish(
        *,
        title: str,
        message: str,
        level: str = "info",
        source: str = DOMAIN,
        entry_options: Optional[dict[str, Any]] = None,
        push: bool = True,
        email: bool = False,
        persistent: bool = True,
    ) -> None:
        """Publish a notification with level filtering."""
        tag = "homie"
        lvl = _normalize_level(level)

        # Create notification item
        item = HomieNotification(
            ts=_now_iso(),
            level=lvl,
            title=title,
            message=message,
            source=source,
            tag=tag,
        )
        _append(item)

        # Always create persistent notification if requested
        if persistent:
            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": f"[{tag}] {title}",
                    "message": f"{message}\n\nsource={source} level={lvl} tag={tag}",
                    "notification_id": f"{tag}_{source}_{lvl}",
                },
                blocking=False,
            )

        # Get options with defaults
        if entry_options is None:
            entry_options = {}

        notifications_enabled = entry_options.get(
            OPT_NOTIFICATIONS_ENABLED, DEFAULT_NOTIFICATIONS_ENABLED
        )
        push_enabled = entry_options.get(OPT_PUSH_ENABLED, DEFAULT_PUSH_ENABLED)
        email_enabled = entry_options.get(OPT_EMAIL_ENABLED, DEFAULT_EMAIL_ENABLED)
        notification_level = entry_options.get(
            OPT_NOTIFICATION_LEVEL, DEFAULT_NOTIFICATION_LEVEL
        )
        push_level = entry_options.get(OPT_PUSH_LEVEL, DEFAULT_PUSH_LEVEL)
        push_target = entry_options.get(
            OPT_NOTIFY_TARGET_PUSH, DEFAULT_NOTIFY_TARGET_PUSH
        )

        if not notifications_enabled:
            return

        # Push notification with level filtering
        if push and push_enabled:
            if _should_send_by_level(lvl, push_level):
                await _call_notify_service(
                    push_target,
                    {
                        "message": f"[{tag}] {title}\n{message}",
                        "data": {"tag": tag},
                    },
                )

        # Email notification with level filtering
        if email and email_enabled:
            if _should_send_by_level(lvl, notification_level):
                await _send_smtp_email(
                    entry_options,
                    lvl,
                    subject=f"[{tag}] {title}",
                    body=f"{message}\n\nsource={source}\nlevel={lvl}\ntag={tag}\n",
                )

    async def handle_service(call) -> None:
        """Handle homie_main.notify service calls."""
        data = call.data or {}
        await _publish(
            title=str(data.get("title", "Notification")),
            message=str(data.get("message", "")),
            level=str(data.get("level", "info")),
            source=str(data.get("source", DOMAIN)),
            entry_options=data.get("entry_options"),
            push=bool(data.get("push", True)),
            email=bool(data.get("email", False)),
            persistent=bool(data.get("persistent", True)),
        )

    hass.services.async_register(DOMAIN, "notify", handle_service)

    @callback
    def handle_event(event) -> None:
        """Handle homie_notification events."""
        ed = event.data or {}
        item = HomieNotification(
            ts=_now_iso(),
            level=_normalize_level(ed.get("level")),
            title=str(ed.get("title", "Notification")),
            message=str(ed.get("message", "")),
            source=str(ed.get("source", "unknown")),
            tag="homie",
        )
        _append(item)

    hass.bus.async_listen(EVENT_HOMIE_NOTIFICATION, handle_event)
    _LOGGER.info("Homie notification system initialized")


def get_feed(hass: HomeAssistant) -> list[Dict[str, Any]]:
    """Get notification feed (last N notifications)."""
    store = hass.data.get(NOTIFICATION_STORE_KEY, {})
    items: Deque[HomieNotification] = store.get("items", deque())
    return [
        {
            "ts": i.ts,
            "level": i.level,
            "title": i.title,
            "message": i.message,
            "source": i.source,
            "tag": i.tag,
        }
        for i in list(items)
    ]

from __future__ import annotations

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
    OPT_NOTIFY_TARGET_PUSH,
    DEFAULT_NOTIFICATIONS_ENABLED,
    DEFAULT_PUSH_ENABLED,
    DEFAULT_EMAIL_ENABLED,
    DEFAULT_NOTIFY_TARGET_PUSH,
    # smtp
    OPT_SMTP_HOST,
    OPT_SMTP_PORT,
    OPT_SMTP_STARTTLS,
    OPT_SMTP_SSL,
    OPT_SMTP_USERNAME,
    OPT_SMTP_PASSWORD,
    OPT_SMTP_FROM,
    OPT_SMTP_TO,
    DEFAULT_SMTP_HOST,
    DEFAULT_SMTP_PORT,
    DEFAULT_SMTP_STARTTLS,
    DEFAULT_SMTP_SSL,
    DEFAULT_SMTP_USERNAME,
    DEFAULT_SMTP_PASSWORD,
    DEFAULT_SMTP_FROM,
    DEFAULT_SMTP_TO,
)

EVENT_HOMIE_NOTIFICATION = "homie_notification"
STORE_KEY = "homie_notification_store"


@dataclass
class HomieNotification:
    ts: str
    level: str
    title: str
    message: str
    source: str
    tag: str


def _now_iso() -> str:
    return dt_util.utcnow().isoformat()


def _normalize_level(level: str | None) -> str:
    if not level:
        return "info"
    return str(level).strip().lower()


def _parse_recipients(raw: str) -> list[str]:
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


async def async_setup_notifications(hass: HomeAssistant) -> None:
    if STORE_KEY not in hass.data:
        hass.data[STORE_KEY] = {"items": deque(maxlen=100)}

    @callback
    def _append(item: HomieNotification) -> None:
        hass.data[STORE_KEY]["items"].appendleft(item)

    async def _call_notify_service(target: str, payload: dict[str, Any]) -> None:
        if not target or "." not in target:
            return
        domain, service = target.split(".", 1)
        try:
            await hass.services.async_call(domain, service, payload, blocking=False)
        except Exception:
            return

    async def _send_smtp_email(entry_options: dict[str, Any], subject: str, body: str) -> None:
        host = str(entry_options.get(OPT_SMTP_HOST, DEFAULT_SMTP_HOST)).strip()
        port = int(entry_options.get(OPT_SMTP_PORT, DEFAULT_SMTP_PORT))
        starttls = bool(entry_options.get(OPT_SMTP_STARTTLS, DEFAULT_SMTP_STARTTLS))
        use_ssl = bool(entry_options.get(OPT_SMTP_SSL, DEFAULT_SMTP_SSL))
        username = str(entry_options.get(OPT_SMTP_USERNAME, DEFAULT_SMTP_USERNAME))
        password = str(entry_options.get(OPT_SMTP_PASSWORD, DEFAULT_SMTP_PASSWORD))
        from_addr = str(entry_options.get(OPT_SMTP_FROM, DEFAULT_SMTP_FROM)).strip()
        to_raw = str(entry_options.get(OPT_SMTP_TO, DEFAULT_SMTP_TO))
        to_addrs = _parse_recipients(to_raw)

        # Not configured -> no-op
        if not host or not from_addr or not to_addrs:
            return

        msg = EmailMessage()
        msg["From"] = from_addr
        msg["To"] = ", ".join(to_addrs)
        msg["Subject"] = subject
        msg.set_content(body)

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
        tag = "homie"
        lvl = _normalize_level(level)

        item = HomieNotification(
            ts=_now_iso(),
            level=lvl,
            title=title,
            message=message,
            source=source,
            tag=tag,
        )
        _append(item)

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

        # Defaults for non-entry calls
        notifications_enabled = True
        push_enabled = True
        email_enabled = False
        push_target = DEFAULT_NOTIFY_TARGET_PUSH

        if entry_options is not None:
            notifications_enabled = bool(entry_options.get(OPT_NOTIFICATIONS_ENABLED, DEFAULT_NOTIFICATIONS_ENABLED))
            push_enabled = bool(entry_options.get(OPT_PUSH_ENABLED, DEFAULT_PUSH_ENABLED))
            email_enabled = bool(entry_options.get(OPT_EMAIL_ENABLED, DEFAULT_EMAIL_ENABLED))
            push_target = str(entry_options.get(OPT_NOTIFY_TARGET_PUSH, DEFAULT_NOTIFY_TARGET_PUSH))

        if not notifications_enabled:
            return

        if push and push_enabled:
            await _call_notify_service(
                push_target,
                {
                    "message": f"[{tag}] {title}\n{message}",
                    "data": {"tag": tag},
                },
            )

        if email and email_enabled and entry_options is not None:
            try:
                await _send_smtp_email(
                    entry_options,
                    subject=f"[{tag}] {title}",
                    body=f"{message}\n\nsource={source}\nlevel={lvl}\ntag={tag}\n",
                )
            except Exception:
                # no hard fail
                return

    async def handle_service(call) -> None:
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


def get_feed(hass: HomeAssistant) -> list[Dict[str, Any]]:
    store = hass.data.get(STORE_KEY, {})
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

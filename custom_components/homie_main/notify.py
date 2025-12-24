from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_NOTIFY_TARGET,
    WARNING_COOLDOWN_HOURS,
)

@dataclass
class NotifyConfig:
    target: str = DEFAULT_NOTIFY_TARGET
    cooldown_hours: int = WARNING_COOLDOWN_HOURS

def _cooldown_key(entry_id: str, warn_key: str) -> str:
    return f"homie_main::{entry_id}::{warn_key}::last_sent"

async def send_warning(
    hass: HomeAssistant,
    entry_id: str,
    warn_key: str,
    title: str,
    message: str,
    *,
    config: Optional[NotifyConfig] = None,
) -> None:
    """Send warning with cooldown + persistent notification + push fallback."""
    cfg = config or NotifyConfig()
    now = dt_util.utcnow()

    # Cooldown check
    store = hass.data.setdefault("homie_main_notify", {})
    key = _cooldown_key(entry_id, warn_key)
    last = store.get(key)

    if last and (now - last) < timedelta(hours=cfg.cooldown_hours):
        # still create persistent notification? No: avoid spam.
        return

    # Always persistent notification (audit)
    await hass.services.async_call(
        "persistent_notification",
        "create",
        {
            "title": title,
            "message": message,
            "notification_id": f"homie_main_{warn_key}",
        },
        blocking=False,
    )

    # Push attempt (best effort)
    target = cfg.target or DEFAULT_NOTIFY_TARGET
    if "." not in target:
        # invalid target; stop silently
        store[key] = now
        return

    domain, service = target.split(".", 1)
    try:
        await hass.services.async_call(
            domain,
            service,
            {"message": f"{title}\n{message}"},
            blocking=False,
        )
    except Exception:
        # Fallback: do nothing (persistent already created)
        pass

    store[key] = now

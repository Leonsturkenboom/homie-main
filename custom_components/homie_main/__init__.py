from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import HomieMainCoordinator

PLATFORMS: list[str] = ["sensor", "select", "switch", "button"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Homie Main (shared resources)."""
    # Lazy import to avoid dependency issues during bootstrap
    from .notifications import async_setup_notifications

    await async_setup_notifications(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Homie Main from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(entry.entry_id, {})

    coordinator = HomieMainCoordinator(hass, entry)
    hass.data[DOMAIN][entry.entry_id]["coordinator"] = coordinator

    await coordinator.async_config_entry_first_refresh()

    # Ensure notification bus exists even if async_setup ran earlier
    from .notifications import async_setup_notifications
    await async_setup_notifications(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))
    return True


async def _async_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    coordinator: HomieMainCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    await coordinator.async_request_refresh()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = hass.data[DOMAIN].get(entry.entry_id, {}).get("coordinator")
    if coordinator and hasattr(coordinator, "async_shutdown"):
        await coordinator.async_shutdown()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok

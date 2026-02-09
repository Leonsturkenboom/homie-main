# custom_components/homie_main/__init__.py
"""The Homie Main integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, PLATFORMS, NOTIFICATION_LEVELS, LEVEL_INFO
from .coordinator import HomieMainCoordinator

_LOGGER = logging.getLogger(__name__)

# Service schema
SERVICE_SEND_NOTIFICATION = "send_notification"
SERVICE_SEND_NOTIFICATION_SCHEMA = vol.Schema(
    {
        vol.Required("title"): cv.string,
        vol.Required("message"): cv.string,
        vol.Optional("level", default=LEVEL_INFO): vol.In(NOTIFICATION_LEVELS),
        vol.Optional("push"): cv.boolean,
        vol.Optional("email"): cv.boolean,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Homie Main from a config entry."""
    _LOGGER.info("Setting up Homie Main integration for %s", entry.title)

    # Create coordinator
    coordinator = HomieMainCoordinator(hass, entry)
    await coordinator.async_setup()

    # Store entry data in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "config": entry.data,
        "options": entry.options,
        "coordinator": coordinator,
    }

    # Set up platforms
    if PLATFORMS:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services (only once for the domain)
    if not hass.services.has_service(DOMAIN, SERVICE_SEND_NOTIFICATION):
        async def handle_send_notification(call: ServiceCall) -> None:
            """Handle send_notification service call."""
            # Find any coordinator (use first available)
            for entry_data in hass.data[DOMAIN].values():
                coordinator: HomieMainCoordinator = entry_data.get("coordinator")
                if coordinator:
                    await coordinator.send_notification(
                        title=call.data["title"],
                        message=call.data["message"],
                        level=call.data.get("level", LEVEL_INFO),
                        push=call.data.get("push"),
                        email=call.data.get("email"),
                    )
                    break

        hass.services.async_register(
            DOMAIN,
            SERVICE_SEND_NOTIFICATION,
            handle_send_notification,
            schema=SERVICE_SEND_NOTIFICATION_SCHEMA,
        )
        _LOGGER.info("Registered service: %s.%s", DOMAIN, SERVICE_SEND_NOTIFICATION)

    # Register update listener for options
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    _LOGGER.info("Homie Main integration setup complete for %s", entry.title)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Homie Main integration for %s", entry.title)

    # Unload platforms
    unload_ok = True
    if PLATFORMS:
        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Shut down coordinator
    if unload_ok:
        coordinator: HomieMainCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        await coordinator.async_shutdown()
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    _LOGGER.info("Options updated for %s, reloading integration", entry.title)
    await hass.config_entries.async_reload(entry.entry_id)

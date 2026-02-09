# custom_components/homie_main/switch.py
"""Switch platform for Homie Main - Config Board toggles (PRD Output 14)."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    CONF_PUSH_ENABLED,
    CONF_PUSH_GENERAL,
    CONF_PUSH_WARNINGS,
    CONF_PUSH_ALERTS,
    CONF_MAIL_ENABLED,
    CONF_MAIL_WARNINGS,
    CONF_MAIL_ALERTS,
    CONF_USE_GPS,
    CONF_USE_WIFI,
    CONF_USE_MOTION,
    CONF_USE_CALENDAR,
    DEFAULT_PUSH_ENABLED,
    DEFAULT_PUSH_GENERAL,
    DEFAULT_PUSH_WARNINGS,
    DEFAULT_PUSH_ALERTS,
    DEFAULT_MAIL_ENABLED,
    DEFAULT_MAIL_WARNINGS,
    DEFAULT_MAIL_ALERTS,
    DEFAULT_USE_GPS,
    DEFAULT_USE_WIFI,
    DEFAULT_USE_MOTION,
    DEFAULT_USE_CALENDAR,
)
from .coordinator import HomieMainCoordinator

_LOGGER = logging.getLogger(__name__)

# Switch definitions: (key, name, icon, default, category)
SWITCH_DEFINITIONS = [
    # Notifications - Push
    (CONF_PUSH_ENABLED, "HM Push Enabled", "mdi:bell", DEFAULT_PUSH_ENABLED, "notifications"),
    (CONF_PUSH_GENERAL, "HM Push General", "mdi:bell-outline", DEFAULT_PUSH_GENERAL, "notifications"),
    (CONF_PUSH_WARNINGS, "HM Push Warnings", "mdi:bell-alert", DEFAULT_PUSH_WARNINGS, "notifications"),
    (CONF_PUSH_ALERTS, "HM Push Alerts", "mdi:bell-ring", DEFAULT_PUSH_ALERTS, "notifications"),
    # Notifications - Email
    (CONF_MAIL_ENABLED, "HM Mail Enabled", "mdi:email", DEFAULT_MAIL_ENABLED, "notifications"),
    (CONF_MAIL_WARNINGS, "HM Mail Warnings", "mdi:email-alert", DEFAULT_MAIL_WARNINGS, "notifications"),
    (CONF_MAIL_ALERTS, "HM Mail Alerts", "mdi:email-fast", DEFAULT_MAIL_ALERTS, "notifications"),
    # Presence Detection
    (CONF_USE_GPS, "HM Use GPS", "mdi:crosshairs-gps", DEFAULT_USE_GPS, "presence"),
    (CONF_USE_WIFI, "HM Use WiFi", "mdi:wifi", DEFAULT_USE_WIFI, "presence"),
    (CONF_USE_MOTION, "HM Use Motion", "mdi:motion-sensor", DEFAULT_USE_MOTION, "presence"),
    (CONF_USE_CALENDAR, "HM Use Calendar", "mdi:calendar", DEFAULT_USE_CALENDAR, "presence"),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homie Main switches from a config entry."""
    coordinator: HomieMainCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = [
        HMConfigSwitch(coordinator, entry, hass, key, name, icon, default, category)
        for key, name, icon, default, category in SWITCH_DEFINITIONS
    ]

    async_add_entities(entities)
    _LOGGER.info("Added %d Homie Main config switches", len(entities))


class HMConfigSwitch(SwitchEntity):
    """Config switch for Homie Main settings (PRD Output 14)."""

    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: HomieMainCoordinator,
        entry: ConfigEntry,
        hass: HomeAssistant,
        key: str,
        name: str,
        icon: str,
        default: bool,
        category: str,
    ) -> None:
        """Initialize the config switch."""
        self._coordinator = coordinator
        self._entry = entry
        self._hass = hass
        self._key = key
        self._default = default
        self._category = category

        # Entity attributes
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon

        # Device info for grouping
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Homie Main ({entry.title})",
            "manufacturer": "Homie",
            "model": "Main",
            "sw_version": "0.1.0",
        }

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        # Read from config entry (data + options merged)
        current = {**self._entry.data, **self._entry.options}
        return current.get(self._key, self._default)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "category": self._category,
            "config_key": self._key,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._update_config(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._update_config(False)

    async def _update_config(self, value: bool) -> None:
        """Update the config entry with new value."""
        # Get current options
        new_options = {**self._entry.options, self._key: value}

        # Update the config entry options
        self._hass.config_entries.async_update_entry(
            self._entry,
            options=new_options,
        )

        # Update coordinator config cache
        self._coordinator.config[self._key] = value

        # Write state to HA
        self.async_write_ha_state()

        _LOGGER.debug("Updated %s to %s", self._key, value)

# custom_components/homie_main/button.py
"""Button platform for Homie Main."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HomieMainCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homie Main button entities from a config entry."""
    coordinator: HomieMainCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities: list[ButtonEntity] = [
        HMClearOverrideButton(coordinator, entry),
    ]

    async_add_entities(entities)
    _LOGGER.info("Added %d Homie Main button entities", len(entities))


class HMClearOverrideButton(CoordinatorEntity[HomieMainCoordinator], ButtonEntity):
    """Button to clear manual override."""

    _attr_has_entity_name = False  # Use explicit entity_id naming

    def __init__(self, coordinator: HomieMainCoordinator, entry: ConfigEntry) -> None:
        """Initialize the clear override button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_hm_clear_override"
        self._attr_name = "HM Clear Override"  # Explicit name for entity_id generation
        self._attr_icon = "mdi:refresh"

        # Device info for grouping all entities together
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Homie Main ({entry.title})",
            "manufacturer": "Homie",
            "model": "Main",
            "sw_version": "0.1.0",
        }

    async def async_press(self) -> None:
        """Handle button press."""
        _LOGGER.info("Clear override button pressed")
        self.coordinator.clear_manual_override()

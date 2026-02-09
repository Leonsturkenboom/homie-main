# custom_components/homie_main/binary_sensor.py
"""Binary sensor platform for Homie Main."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HomieMainCoordinator

_LOGGER = logging.getLogger(__name__)

SUN_ENTITY = "sun.sun"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homie Main binary sensors from a config entry."""
    coordinator: HomieMainCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities: list[BinarySensorEntity] = [
        HMNighttimeSensor(coordinator, entry, hass),
    ]

    async_add_entities(entities)
    _LOGGER.info("Added %d Homie Main binary sensors", len(entities))


class HMNighttimeSensor(CoordinatorEntity[HomieMainCoordinator], BinarySensorEntity):
    """Binary sensor that indicates if it's nighttime."""

    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: HomieMainCoordinator,
        entry: ConfigEntry,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the nighttime sensor."""
        super().__init__(coordinator)
        self._hass = hass
        self._attr_unique_id = f"{entry.entry_id}_hm_nighttime"
        self._attr_name = "HM Nighttime"
        self._attr_icon = "mdi:weather-night"

        # Device info for grouping all entities together
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Homie Main ({entry.title})",
            "manufacturer": "Homie",
            "model": "Main",
            "sw_version": "0.1.0",
        }

        # Track sun state changes
        self._unsub_sun = None

    async def async_added_to_hass(self) -> None:
        """Register callbacks when added to hass."""
        await super().async_added_to_hass()

        @callback
        def sun_state_changed(event) -> None:
            """Handle sun state changes."""
            self.async_write_ha_state()

        self._unsub_sun = async_track_state_change_event(
            self._hass, [SUN_ENTITY], sun_state_changed
        )

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when removed from hass."""
        await super().async_will_remove_from_hass()
        if self._unsub_sun:
            self._unsub_sun()

    @property
    def is_on(self) -> bool:
        """Return True if it's nighttime (sun is below horizon)."""
        sun_state = self._hass.states.get(SUN_ENTITY)
        if sun_state is None:
            return False
        return sun_state.state == "below_horizon"

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        sun_state = self._hass.states.get(SUN_ENTITY)
        if sun_state is None:
            return {}

        return {
            "sun_state": sun_state.state,
            "next_dawn": sun_state.attributes.get("next_dawn"),
            "next_dusk": sun_state.attributes.get("next_dusk"),
            "next_rising": sun_state.attributes.get("next_rising"),
            "next_setting": sun_state.attributes.get("next_setting"),
        }

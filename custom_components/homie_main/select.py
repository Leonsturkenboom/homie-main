# custom_components/homie_main/select.py
"""Select platform for Homie Main."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    HOME_STATUS_OPTIONS_HOME,
    HOME_STATUS_OPTIONS_BUSINESS,
    VISUALIZATION_OPTIONS,
    OPERATING_MODES,
    LOCATION_BUSINESS,
)
from .coordinator import HomieMainCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homie Main select entities from a config entry."""
    coordinator: HomieMainCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities: list[SelectEntity] = [
        HMHomeStatusSelect(coordinator, entry),
        HMOperatingModeSelect(coordinator, entry),
        HMVisualizationSelect(coordinator, entry),
    ]

    async_add_entities(entities)
    _LOGGER.info("Added %d Homie Main select entities", len(entities))


class HMBaseSelect(CoordinatorEntity[HomieMainCoordinator], SelectEntity):
    """Base class for Homie Main select entities."""

    _attr_has_entity_name = False  # Use explicit entity_id naming

    def __init__(
        self,
        coordinator: HomieMainCoordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
        options: list[str],
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name  # Explicit name for entity_id generation
        self._attr_options = options
        self._key = key

        # Device info for grouping all entities together
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Homie Main ({entry.title})",
            "manufacturer": "Homie",
            "model": "Main",
            "sw_version": "0.1.0",
        }


class HMHomeStatusSelect(HMBaseSelect):
    """Select entity for manual presence override."""

    _attr_translation_key = "hm_home_status"

    def __init__(self, coordinator: HomieMainCoordinator, entry: ConfigEntry) -> None:
        """Initialize the home status select."""
        # Get options based on location type
        is_business = coordinator.data.location_type == LOCATION_BUSINESS
        options = HOME_STATUS_OPTIONS_BUSINESS if is_business else HOME_STATUS_OPTIONS_HOME

        super().__init__(
            coordinator,
            entry,
            "hm_home_status",
            "HM Home Status",
            options,
        )
        self._attr_icon = "mdi:home-switch" if not is_business else "mdi:office-building"

    @property
    def current_option(self) -> str:
        """Return the current selected option."""
        return self.coordinator.data.home_status_selection

    async def async_select_option(self, option: str) -> None:
        """Handle option selection."""
        _LOGGER.info("Home status changed to: %s", option)
        self.coordinator.set_home_status(option)


class HMOperatingModeSelect(HMBaseSelect):
    """Select entity for operating mode with manual override capability."""

    _attr_translation_key = "hm_operating_mode"

    def __init__(self, coordinator: HomieMainCoordinator, entry: ConfigEntry) -> None:
        """Initialize the operating mode select."""
        super().__init__(
            coordinator,
            entry,
            "hm_operating_mode",
            "HM Operating Mode",
            OPERATING_MODES,
        )

    @property
    def current_option(self) -> str:
        """Return the current operating mode."""
        return self.coordinator.data.operating_mode

    @property
    def icon(self) -> str:
        """Return icon based on operating mode."""
        mode = self.coordinator.data.operating_mode
        if mode == "Active":
            return "mdi:home-lightning-bolt"
        elif mode == "Stand-by":
            return "mdi:home-clock"
        elif mode == "Hibernation":
            return "mdi:home-sleep"
        return "mdi:home"

    async def async_select_option(self, option: str) -> None:
        """Handle option selection (manual override)."""
        _LOGGER.info("Operating mode manually changed to: %s", option)
        self.coordinator.set_operating_mode_override(option)


class HMVisualizationSelect(HMBaseSelect):
    """Select entity for dashboard visualization mode."""

    _attr_translation_key = "hm_visualization"

    def __init__(self, coordinator: HomieMainCoordinator, entry: ConfigEntry) -> None:
        """Initialize the visualization select."""
        super().__init__(
            coordinator,
            entry,
            "hm_visualization",
            "HM Visualization",
            VISUALIZATION_OPTIONS,
        )
        self._attr_icon = "mdi:chart-line"

    @property
    def current_option(self) -> str:
        """Return the current selected option."""
        return self.coordinator.data.visualization_selection

    async def async_select_option(self, option: str) -> None:
        """Handle option selection."""
        _LOGGER.info("Visualization changed to: %s", option)
        self.coordinator.set_visualization(option)

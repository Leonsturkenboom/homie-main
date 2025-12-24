from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([HMManualOverrideClearButton(entry, coordinator)])


class HMManualOverrideClearButton(ButtonEntity):
    _attr_name = "HM Clear Manual Override"
    _attr_icon = "mdi:shield-off"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, coordinator) -> None:
        self.entry = entry
        self.coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_manual_override_clear"

    async def async_press(self) -> None:
        self.coordinator.manual_override_clear()
        await self.coordinator.async_request_refresh()

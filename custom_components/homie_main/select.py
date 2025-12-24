from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from .const import (
    DOMAIN,
    OPT_NOTIFICATION_LEVEL,
    OPT_PUSH_LEVEL,
    DEFAULT_NOTIFICATION_LEVEL,
    DEFAULT_PUSH_LEVEL,
    NOTIFICATION_LEVELS,
    PUSH_LEVELS,
)


HOME_STATUS_OPTIONS = ["Auto", "Home", "Away", "Holiday", "Guests"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities(
        [
            HMNotificationLevelSelect(hass, entry),
            HMPushNotificationLevelSelect(hass, entry),
            HMHomeStatusSelect(hass, entry, coordinator),
        ]
    )


# ---------------------------
# Notification level selects
# ---------------------------

class HMNotificationLevelSelect(SelectEntity):
    _attr_name = "HM Notification Level"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_notification_level"

    @property
    def options(self) -> list[str]:
        return NOTIFICATION_LEVELS

    @property
    def current_option(self) -> str:
        return self.entry.options.get(OPT_NOTIFICATION_LEVEL, DEFAULT_NOTIFICATION_LEVEL)

    async def async_select_option(self, option: str) -> None:
        options = dict(self.entry.options)
        options[OPT_NOTIFICATION_LEVEL] = option
        self.hass.config_entries.async_update_entry(self.entry, options=options)
        self.async_write_ha_state()


class HMPushNotificationLevelSelect(SelectEntity):
    _attr_name = "HM Push Notification Level"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_push_notification_level"

    @property
    def options(self) -> list[str]:
        return PUSH_LEVELS

    @property
    def current_option(self) -> str:
        return self.entry.options.get(OPT_PUSH_LEVEL, DEFAULT_PUSH_LEVEL)

    async def async_select_option(self, option: str) -> None:
        options = dict(self.entry.options)
        options[OPT_PUSH_LEVEL] = option
        self.hass.config_entries.async_update_entry(self.entry, options=options)
        self.async_write_ha_state()


# ---------------------------
# Home status / manual override
# ---------------------------

class HMHomeStatusSelect(SelectEntity):
    _attr_name = "HM Home Status"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True
    _attr_icon = "mdi:home-switch"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_home_status"

    @property
    def options(self) -> list[str]:
        return HOME_STATUS_OPTIONS

    @property
    def current_option(self) -> str:
        mo = self.coordinator.manual_override_state()
        if not mo.active or not mo.status:
            return "Auto"
        return mo.status

    async def async_select_option(self, option: str) -> None:
        if option == "Auto":
            self.coordinator.manual_override_clear()
        else:
            self.coordinator.manual_override_set(option)

        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

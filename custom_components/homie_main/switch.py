# custom_components/homie_main/switch.py

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from .const import (
    DOMAIN,
    OPT_NOTIFICATIONS_ENABLED,
    OPT_PUSH_ENABLED,
    OPT_EMAIL_ENABLED,
    DEFAULT_NOTIFICATIONS_ENABLED,
    DEFAULT_PUSH_ENABLED,
    DEFAULT_EMAIL_ENABLED,
)

SWITCH_DEFINITIONS = {
    OPT_NOTIFICATIONS_ENABLED: {
        "name": "Homie Notifications",
        "default": DEFAULT_NOTIFICATIONS_ENABLED,
    },
    OPT_PUSH_ENABLED: {
        "name": "Homie Push Notifications",
        "default": DEFAULT_PUSH_ENABLED,
    },
    OPT_EMAIL_ENABLED: {
        "name": "Homie Email Notifications",
        "default": DEFAULT_EMAIL_ENABLED,
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    entities: list[SwitchEntity] = []

    for option_key, meta in SWITCH_DEFINITIONS.items():
        entities.append(
            HomieOptionSwitch(
                hass=hass,
                entry=entry,
                option_key=option_key,
                name=meta["name"],
                default=meta["default"],
            )
        )

    async_add_entities(entities)


class HomieOptionSwitch(SwitchEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        *,
        hass: HomeAssistant,
        entry: ConfigEntry,
        option_key: str,
        name: str,
        default: bool,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.option_key = option_key
        self._default = default

        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{option_key}"
        self._attr_has_entity_name = True

    @property
    def is_on(self) -> bool:
        return self.entry.options.get(self.option_key, self._default)

    async def async_turn_on(self, **kwargs) -> None:
        await self._update_option(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._update_option(False)

    async def _update_option(self, value: bool) -> None:
        options = dict(self.entry.options)
        options[self.option_key] = value
        self.hass.config_entries.async_update_entry(self.entry, options=options)
        self.async_write_ha_state()

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    DEFAULT_NAME,
    CONF_IMPORTED_ENTITIES,
    CONF_EXPORTED_ENTITIES,
    CONF_PRODUCED_ENTITIES,
    CONF_BATTERY_CHARGE_ENTITIES,
    CONF_BATTERY_DISCHARGE_ENTITIES,
    CONF_CO2_INTENSITY_ENTITY,
    CONF_PRESENCE_ENTITY,
)


ALLOWED_ENERGY_UNITS = {"kwh", "wh"}


class EnergyCoreConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def _validate_energy_list(self, entity_ids: list[str]) -> list[str]:
        """Return a list of invalid entity_ids based on unit_of_measurement."""
        invalid: list[str] = []

        for eid in entity_ids or []:
            st = self.hass.states.get(eid)
            if st is None:
                # If state is not available right now, don't hard fail.
                # This keeps setup resilient during startup.
                continue

            unit = (st.attributes.get("unit_of_measurement") or "").lower().strip()
            if unit not in ALLOWED_ENERGY_UNITS:
                invalid.append(eid)

        return invalid

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}

        if user_input is not None:
            imported = user_input.get(CONF_IMPORTED_ENTITIES, [])
            exported = user_input.get(CONF_EXPORTED_ENTITIES, [])
            produced = user_input.get(CONF_PRODUCED_ENTITIES, [])
            charge = user_input.get(CONF_BATTERY_CHARGE_ENTITIES, [])
            discharge = user_input.get(CONF_BATTERY_DISCHARGE_ENTITIES, [])

            # Validate each list independently so we can show field-level errors
            invalid_imported = self._validate_energy_list(imported)
            invalid_exported = self._validate_energy_list(exported)
            invalid_produced = self._validate_energy_list(produced)
            invalid_charge = self._validate_energy_list(charge)
            invalid_discharge = self._validate_energy_list(discharge)

            if invalid_imported:
                errors[CONF_IMPORTED_ENTITIES] = "invalid_unit"
            if invalid_exported:
                errors[CONF_EXPORTED_ENTITIES] = "invalid_unit"
            if invalid_produced:
                errors[CONF_PRODUCED_ENTITIES] = "invalid_unit"
            if invalid_charge:
                errors[CONF_BATTERY_CHARGE_ENTITIES] = "invalid_unit"
            if invalid_discharge:
                errors[CONF_BATTERY_DISCHARGE_ENTITIES] = "invalid_unit"

            # Fallback base error (for older UI behaviour)
            if errors:
                errors["base"] = "invalid_unit"

            if not errors:
                return self.async_create_entry(title=DEFAULT_NAME, data=user_input)

        schema = vol.Schema(
            {
                # Energy totals (only sensors; user may select multiple)
                vol.Required(CONF_IMPORTED_ENTITIES): selector.EntitySelector(
                    selector.EntitySelectorConfig(multiple=True, domain="sensor")
                ),
                vol.Required(CONF_EXPORTED_ENTITIES): selector.EntitySelector(
                    selector.EntitySelectorConfig(multiple=True, domain="sensor")
                ),
                vol.Optional(CONF_PRODUCED_ENTITIES): selector.EntitySelector(
                    selector.EntitySelectorConfig(multiple=True, domain="sensor")
                ),
                vol.Optional(CONF_BATTERY_CHARGE_ENTITIES): selector.EntitySelector(
                    selector.EntitySelectorConfig(multiple=True, domain="sensor")
                ),
                vol.Optional(CONF_BATTERY_DISCHARGE_ENTITIES): selector.EntitySelector(
                    selector.EntitySelectorConfig(multiple=True, domain="sensor")
                ),

                # CO2 intensity (single sensor)
                vol.Required(CONF_CO2_INTENSITY_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(multiple=False, domain="sensor")
                ),

                # Presence can be a person, binary_sensor, etc.
                vol.Optional(CONF_PRESENCE_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(multiple=False)
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

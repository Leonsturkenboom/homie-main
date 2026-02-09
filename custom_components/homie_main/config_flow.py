# custom_components/homie_main/config_flow.py
"""Config flow for Homie Main integration."""

from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    # Step 1 - General
    CONF_SITE_NAME,
    CONF_ADMIN_EMAILS,
    CONF_LOCATION_TYPE,
    CONF_PUSH_ENABLED,
    CONF_PUSH_GENERAL,
    CONF_PUSH_ALERTS,
    CONF_PUSH_WARNINGS,
    CONF_MAIL_ENABLED,
    CONF_MAIL_WARNINGS,
    CONF_MAIL_ALERTS,
    CONF_PRESENCE_DETECTION,
    # Location types
    LOCATION_HOME,
    LOCATION_BUSINESS,
    # Step 2 - Presence
    CONF_USE_GPS,
    CONF_USE_WIFI,
    CONF_USE_MOTION,
    CONF_USE_CALENDAR,
    CONF_USE_SCHEDULE,
    # Step 3 - Presence follow-up
    CONF_GPS_ENTITIES,
    CONF_GPS_DISTANCE,
    CONF_PING_ENTITIES,
    CONF_MOTION_ENTITIES,
    CONF_MOTION_AWAY_HOURS,
    CONF_CALENDAR_ENTITIES,
    # Schedule
    CONF_SCHEDULE,
    WEEKDAYS,
    # Step 4 - KPI mapping
    CONF_KPI_POWER_USE,
    CONF_KPI_DAY_ENERGY_USE,
    CONF_KPI_SOLAR_POWER,
    CONF_KPI_SOLAR_DAY_ENERGY,
    CONF_KPI_FORECAST_USE,
    CONF_KPI_SOLAR_FORECAST,
    CONF_KPI_PURCHASE_PRICE,
    # Options - SMTP (only recipient is configurable)
    OPT_SMTP_TO,
    # Defaults
    DEFAULT_SITE_NAME,
    DEFAULT_ADMIN_EMAILS,
    DEFAULT_LOCATION_TYPE,
    DEFAULT_PUSH_ENABLED,
    DEFAULT_PUSH_GENERAL,
    DEFAULT_PUSH_ALERTS,
    DEFAULT_PUSH_WARNINGS,
    DEFAULT_MAIL_ENABLED,
    DEFAULT_MAIL_WARNINGS,
    DEFAULT_MAIL_ALERTS,
    DEFAULT_PRESENCE_DETECTION,
    DEFAULT_USE_GPS,
    DEFAULT_USE_WIFI,
    DEFAULT_USE_MOTION,
    DEFAULT_USE_CALENDAR,
    DEFAULT_USE_SCHEDULE,
    DEFAULT_GPS_DISTANCE,
    DEFAULT_MOTION_AWAY_HOURS,
    DEFAULT_SCHEDULE,
    DEFAULT_KPI_POWER_USE,
    DEFAULT_KPI_DAY_ENERGY_USE,
    DEFAULT_KPI_SOLAR_POWER,
    DEFAULT_KPI_SOLAR_DAY_ENERGY,
    DEFAULT_KPI_FORECAST_USE,
    DEFAULT_KPI_SOLAR_FORECAST,
    DEFAULT_KPI_PURCHASE_PRICE,
    DEFAULT_SMTP_TO,
)

_LOGGER = logging.getLogger(__name__)

# Email validation regex
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def validate_emails(email_string: str) -> bool:
    """Validate a comma-separated list of email addresses."""
    if not email_string or not email_string.strip():
        return True  # Empty is allowed

    emails = [e.strip() for e in email_string.split(",") if e.strip()]
    for email in emails:
        if not EMAIL_REGEX.match(email):
            return False
    return True


class HomieMain2ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Homie Main."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle Step 1: General settings."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate site_name
            if not user_input.get(CONF_SITE_NAME, "").strip():
                errors[CONF_SITE_NAME] = "empty_site_name"

            # Validate admin_emails
            admin_emails = user_input.get(CONF_ADMIN_EMAILS, "")
            if admin_emails and not validate_emails(admin_emails):
                errors[CONF_ADMIN_EMAILS] = "invalid_email"

            if not errors:
                self._data.update(user_input)

                # If presence detection enabled, go to step 2
                if user_input.get(CONF_PRESENCE_DETECTION, False):
                    return await self.async_step_presence()
                else:
                    # Skip to KPI mapping
                    return await self.async_step_kpi_mapping()

        schema = vol.Schema(
            {
                vol.Required(CONF_SITE_NAME, default=DEFAULT_SITE_NAME): str,
                vol.Optional(CONF_ADMIN_EMAILS, default=DEFAULT_ADMIN_EMAILS): str,
                vol.Required(CONF_LOCATION_TYPE, default=DEFAULT_LOCATION_TYPE): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": LOCATION_HOME, "label": "Home"},
                            {"value": LOCATION_BUSINESS, "label": "Business"},
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_PUSH_ENABLED, default=DEFAULT_PUSH_ENABLED): selector.BooleanSelector(
                    selector.BooleanSelectorConfig()
                ),
                vol.Required(CONF_PUSH_GENERAL, default=DEFAULT_PUSH_GENERAL): bool,
                vol.Required(CONF_PUSH_ALERTS, default=DEFAULT_PUSH_ALERTS): bool,
                vol.Required(CONF_PUSH_WARNINGS, default=DEFAULT_PUSH_WARNINGS): bool,
                vol.Required(CONF_MAIL_ENABLED, default=DEFAULT_MAIL_ENABLED): selector.BooleanSelector(
                    selector.BooleanSelectorConfig()
                ),
                vol.Required(CONF_MAIL_WARNINGS, default=DEFAULT_MAIL_WARNINGS): bool,
                vol.Required(CONF_MAIL_ALERTS, default=DEFAULT_MAIL_ALERTS): bool,
                vol.Required(CONF_PRESENCE_DETECTION, default=DEFAULT_PRESENCE_DETECTION): selector.BooleanSelector(
                    selector.BooleanSelectorConfig()
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_presence(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle Step 2: Presence detection methods."""
        if user_input is not None:
            self._data.update(user_input)

            # Check if any presence method or schedule is selected
            has_presence_method = any([
                user_input.get(CONF_USE_GPS, False),
                user_input.get(CONF_USE_WIFI, False),
                user_input.get(CONF_USE_MOTION, False),
                user_input.get(CONF_USE_CALENDAR, False),
                user_input.get(CONF_USE_SCHEDULE, False),
            ])

            if has_presence_method:
                return await self.async_step_presence_followup()
            else:
                # No methods selected, skip to KPI mapping
                return await self.async_step_kpi_mapping()

        # Build schema - add schedule option only for business locations
        is_business = self._data.get(CONF_LOCATION_TYPE) == LOCATION_BUSINESS

        schema_dict: dict[Any, Any] = {
            vol.Required(CONF_USE_GPS, default=DEFAULT_USE_GPS): selector.BooleanSelector(
                selector.BooleanSelectorConfig()
            ),
            vol.Required(CONF_USE_WIFI, default=DEFAULT_USE_WIFI): selector.BooleanSelector(
                selector.BooleanSelectorConfig()
            ),
            vol.Required(CONF_USE_MOTION, default=DEFAULT_USE_MOTION): selector.BooleanSelector(
                selector.BooleanSelectorConfig()
            ),
            vol.Required(CONF_USE_CALENDAR, default=DEFAULT_USE_CALENDAR): selector.BooleanSelector(
                selector.BooleanSelectorConfig()
            ),
        }

        if is_business:
            schema_dict[vol.Required(CONF_USE_SCHEDULE, default=DEFAULT_USE_SCHEDULE)] = selector.BooleanSelector(
                selector.BooleanSelectorConfig()
            )

        schema = vol.Schema(schema_dict)

        return self.async_show_form(
            step_id="presence",
            data_schema=schema,
        )

    async def async_step_presence_followup(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle Step 3: Presence follow-up (entity selection + schedule)."""
        if user_input is not None:
            # Process schedule data if schedule is enabled
            if self._data.get(CONF_USE_SCHEDULE, False):
                schedule = {}
                for day in WEEKDAYS:
                    # Parse time range string (e.g., "09:00-17:00")
                    times = user_input.get(f"schedule_{day}_times", "09:00-17:00")
                    try:
                        start, end = times.split("-")
                        start = start.strip()
                        end = end.strip()
                    except ValueError:
                        start, end = "09:00", "17:00"
                    schedule[day] = {
                        "enabled": user_input.get(f"schedule_{day}", False),
                        "start": start,
                        "end": end,
                    }
                    # Remove individual keys from user_input
                    user_input.pop(f"schedule_{day}", None)
                    user_input.pop(f"schedule_{day}_times", None)
                user_input[CONF_SCHEDULE] = schedule

            self._data.update(user_input)
            return await self.async_step_kpi_mapping()

        # Build schema dynamically based on selected presence methods
        schema_dict: dict[Any, Any] = {}

        if self._data.get(CONF_USE_GPS, False):
            schema_dict[vol.Optional(CONF_GPS_ENTITIES, default=[])] = selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="device_tracker",
                    multiple=True,
                )
            )
            schema_dict[vol.Required(CONF_GPS_DISTANCE, default=DEFAULT_GPS_DISTANCE)] = selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=10,
                    max=5000,
                    step=10,
                    unit_of_measurement="m",
                    mode=selector.NumberSelectorMode.BOX,
                )
            )

        if self._data.get(CONF_USE_WIFI, False):
            # WiFi presence uses ping binary_sensors
            schema_dict[vol.Optional(CONF_PING_ENTITIES, default=[])] = selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="binary_sensor",
                    multiple=True,
                )
            )

        if self._data.get(CONF_USE_MOTION, False):
            schema_dict[vol.Optional(CONF_MOTION_ENTITIES, default=[])] = selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="binary_sensor",
                    multiple=True,
                )
            )
            schema_dict[vol.Required(CONF_MOTION_AWAY_HOURS, default=DEFAULT_MOTION_AWAY_HOURS)] = selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=24,
                    step=1,
                    unit_of_measurement="hours",
                    mode=selector.NumberSelectorMode.BOX,
                )
            )

        if self._data.get(CONF_USE_CALENDAR, False):
            schema_dict[vol.Optional(CONF_CALENDAR_ENTITIES, default=[])] = selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="calendar",
                    multiple=True,
                )
            )

        # Add schedule configuration for business locations (compact: toggle + time range)
        if self._data.get(CONF_USE_SCHEDULE, False):
            for day in WEEKDAYS:
                default = DEFAULT_SCHEDULE.get(day, {"enabled": False, "start": "09:00", "end": "17:00"})
                # Toggle for enabled
                schema_dict[vol.Required(f"schedule_{day}", default=default["enabled"])] = selector.BooleanSelector(
                    selector.BooleanSelectorConfig()
                )
                # Time range as string (e.g., "09:00-17:00")
                time_range = f"{default['start']}-{default['end']}"
                schema_dict[vol.Optional(f"schedule_{day}_times", default=time_range)] = str

        schema = vol.Schema(schema_dict)

        return self.async_show_form(
            step_id="presence_followup",
            data_schema=schema,
        )

    def _kpi_default(self, default_entity: str) -> str:
        """Return default entity ID only if it exists in HA, otherwise empty string."""
        state = self.hass.states.get(default_entity)
        if state is not None:
            return default_entity
        return ""

    async def async_step_kpi_mapping(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle Step 4: KPI sensor mappings."""
        if user_input is not None:
            self._data.update(user_input)

            # Create the config entry
            return self.async_create_entry(
                title=self._data.get(CONF_SITE_NAME, DEFAULT_SITE_NAME),
                data=self._data,
            )

        schema = vol.Schema(
            {
                vol.Optional(CONF_KPI_POWER_USE, default=self._kpi_default(DEFAULT_KPI_POWER_USE)): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_KPI_DAY_ENERGY_USE, default=self._kpi_default(DEFAULT_KPI_DAY_ENERGY_USE)): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_KPI_SOLAR_POWER, default=self._kpi_default(DEFAULT_KPI_SOLAR_POWER)): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_KPI_SOLAR_DAY_ENERGY, default=self._kpi_default(DEFAULT_KPI_SOLAR_DAY_ENERGY)): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_KPI_FORECAST_USE, default=self._kpi_default(DEFAULT_KPI_FORECAST_USE)): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_KPI_SOLAR_FORECAST, default=self._kpi_default(DEFAULT_KPI_SOLAR_FORECAST)): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_KPI_PURCHASE_PRICE, default=self._kpi_default(DEFAULT_KPI_PURCHASE_PRICE)): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
            }
        )

        return self.async_show_form(
            step_id="kpi_mapping",
            data_schema=schema,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> HomieMain2OptionsFlow:
        """Get the options flow for this handler."""
        return HomieMain2OptionsFlow(config_entry)


class HomieMain2OptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Homie Main."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the options flow."""
        if user_input is not None:
            # Process schedule data if schedule is enabled
            current = {**self.config_entry.data, **self.config_entry.options}
            if current.get(CONF_USE_SCHEDULE, False):
                schedule = {}
                for day in WEEKDAYS:
                    # Parse time range string (e.g., "09:00-17:00")
                    times = user_input.get(f"schedule_{day}_times", "09:00-17:00")
                    try:
                        start, end = times.split("-")
                        start = start.strip()
                        end = end.strip()
                    except ValueError:
                        start, end = "09:00", "17:00"
                    schedule[day] = {
                        "enabled": user_input.get(f"schedule_{day}", False),
                        "start": start,
                        "end": end,
                    }
                    # Remove individual keys from user_input
                    user_input.pop(f"schedule_{day}", None)
                    user_input.pop(f"schedule_{day}_times", None)
                user_input[CONF_SCHEDULE] = schedule
            return self.async_create_entry(title="", data=user_input)

        # Get current values from config entry data and options
        current = {**self.config_entry.data, **self.config_entry.options}

        # Determine which presence methods are enabled
        presence_enabled = current.get(CONF_PRESENCE_DETECTION, False)
        use_gps = current.get(CONF_USE_GPS, False)
        use_wifi = current.get(CONF_USE_WIFI, False)
        use_motion = current.get(CONF_USE_MOTION, False)
        use_calendar = current.get(CONF_USE_CALENDAR, False)
        use_schedule = current.get(CONF_USE_SCHEDULE, False)
        is_business = current.get(CONF_LOCATION_TYPE) == LOCATION_BUSINESS

        schema_dict: dict[Any, Any] = {
            # Push notifications master switch + sub-options
            vol.Required(
                CONF_PUSH_ENABLED,
                default=current.get(CONF_PUSH_ENABLED, DEFAULT_PUSH_ENABLED),
            ): selector.BooleanSelector(selector.BooleanSelectorConfig()),
            vol.Required(
                CONF_PUSH_GENERAL,
                default=current.get(CONF_PUSH_GENERAL, DEFAULT_PUSH_GENERAL),
            ): bool,
            vol.Required(
                CONF_PUSH_WARNINGS,
                default=current.get(CONF_PUSH_WARNINGS, DEFAULT_PUSH_WARNINGS),
            ): bool,
            vol.Required(
                CONF_PUSH_ALERTS,
                default=current.get(CONF_PUSH_ALERTS, DEFAULT_PUSH_ALERTS),
            ): bool,
            # Email notifications master switch + sub-options
            vol.Required(
                CONF_MAIL_ENABLED,
                default=current.get(CONF_MAIL_ENABLED, DEFAULT_MAIL_ENABLED),
            ): selector.BooleanSelector(selector.BooleanSelectorConfig()),
            vol.Required(
                CONF_MAIL_WARNINGS,
                default=current.get(CONF_MAIL_WARNINGS, DEFAULT_MAIL_WARNINGS),
            ): bool,
            vol.Required(
                CONF_MAIL_ALERTS,
                default=current.get(CONF_MAIL_ALERTS, DEFAULT_MAIL_ALERTS),
            ): bool,
        }

        # Presence detection section (only show if enabled in wizard)
        if presence_enabled:
            if use_gps:
                schema_dict[vol.Required(
                    CONF_USE_GPS,
                    default=use_gps,
                )] = selector.BooleanSelector(selector.BooleanSelectorConfig())
            if use_wifi:
                schema_dict[vol.Required(
                    CONF_USE_WIFI,
                    default=use_wifi,
                )] = selector.BooleanSelector(selector.BooleanSelectorConfig())
            if use_motion:
                schema_dict[vol.Required(
                    CONF_USE_MOTION,
                    default=use_motion,
                )] = selector.BooleanSelector(selector.BooleanSelectorConfig())
            if use_calendar:
                schema_dict[vol.Required(
                    CONF_USE_CALENDAR,
                    default=use_calendar,
                )] = selector.BooleanSelector(selector.BooleanSelectorConfig())

        # Schedule configuration for business locations (compact: toggle + time range)
        if is_business and use_schedule:
            current_schedule = current.get(CONF_SCHEDULE, DEFAULT_SCHEDULE)
            for day in WEEKDAYS:
                day_schedule = current_schedule.get(day, DEFAULT_SCHEDULE.get(day, {}))
                # Toggle for enabled
                schema_dict[vol.Required(
                    f"schedule_{day}",
                    default=day_schedule.get("enabled", False),
                )] = selector.BooleanSelector(selector.BooleanSelectorConfig())
                # Time range as string (e.g., "09:00-17:00")
                time_range = f"{day_schedule.get('start', '09:00')}-{day_schedule.get('end', '17:00')}"
                schema_dict[vol.Optional(
                    f"schedule_{day}_times",
                    default=time_range,
                )] = str

        # Email recipient (only smtp_to is configurable, other SMTP settings are fixed)
        schema_dict.update({
            vol.Optional(
                OPT_SMTP_TO,
                default=current.get(OPT_SMTP_TO, DEFAULT_SMTP_TO),
            ): str,
        })

        # KPI mappings section
        schema_dict.update({
            vol.Optional(
                CONF_KPI_POWER_USE,
                default=current.get(CONF_KPI_POWER_USE, DEFAULT_KPI_POWER_USE),
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Optional(
                CONF_KPI_DAY_ENERGY_USE,
                default=current.get(CONF_KPI_DAY_ENERGY_USE, DEFAULT_KPI_DAY_ENERGY_USE),
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Optional(
                CONF_KPI_SOLAR_POWER,
                default=current.get(CONF_KPI_SOLAR_POWER, DEFAULT_KPI_SOLAR_POWER),
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Optional(
                CONF_KPI_SOLAR_DAY_ENERGY,
                default=current.get(CONF_KPI_SOLAR_DAY_ENERGY, DEFAULT_KPI_SOLAR_DAY_ENERGY),
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Optional(
                CONF_KPI_FORECAST_USE,
                default=current.get(CONF_KPI_FORECAST_USE, DEFAULT_KPI_FORECAST_USE),
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Optional(
                CONF_KPI_SOLAR_FORECAST,
                default=current.get(CONF_KPI_SOLAR_FORECAST, DEFAULT_KPI_SOLAR_FORECAST),
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Optional(
                CONF_KPI_PURCHASE_PRICE,
                default=current.get(CONF_KPI_PURCHASE_PRICE, DEFAULT_KPI_PURCHASE_PRICE),
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
        })

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
        )

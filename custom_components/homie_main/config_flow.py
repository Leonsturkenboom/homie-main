# custom_components/homie_main/config_flow.py
"""Config flow for Homie Main integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.core import callback

from .const import (
    DOMAIN,
    # Locked data keys
    CONF_SITE_NAME,
    CONF_PRESENCE_MODE,
    PRESENCE_MODES,
    CONF_GPS_ENTITIES,
    CONF_WIFI_ENTITIES,
    CONF_MOTION_ENTITIES,
    CONF_CALENDAR_ENTITY,
    DEFAULT_CALENDAR,
    # Options defaults
    DEFAULT_KPIS,
    OPT_NOTIFICATIONS_ENABLED,
    OPT_PUSH_ENABLED,
    OPT_EMAIL_ENABLED,
    OPT_NOTIFICATION_LEVEL,
    OPT_PUSH_LEVEL,
    OPT_NOTIFY_TARGET_PUSH,
    DEFAULT_NOTIFICATIONS_ENABLED,
    DEFAULT_PUSH_ENABLED,
    DEFAULT_EMAIL_ENABLED,
    DEFAULT_NOTIFICATION_LEVEL,
    DEFAULT_PUSH_LEVEL,
    DEFAULT_NOTIFY_TARGET_PUSH,
    NOTIFICATION_LEVELS,
    PUSH_LEVELS,
    # SMTP
    OPT_SMTP_HOST,
    OPT_SMTP_PORT,
    OPT_SMTP_STARTTLS,
    OPT_SMTP_SSL,
    OPT_SMTP_USERNAME,
    OPT_SMTP_PASSWORD,
    OPT_SMTP_FROM,
    OPT_SMTP_TO_WARNINGS,
    OPT_SMTP_TO_ALERTS,
    DEFAULT_SMTP_HOST,
    DEFAULT_SMTP_PORT,
    DEFAULT_SMTP_STARTTLS,
    DEFAULT_SMTP_SSL,
    DEFAULT_SMTP_USERNAME,
    DEFAULT_SMTP_PASSWORD,
    DEFAULT_SMTP_FROM,
    DEFAULT_SMTP_TO_WARNINGS,
    DEFAULT_SMTP_TO_ALERTS,
    # KPI keys
    CONF_KPI_POWER_USE,
    CONF_KPI_DAY_ENERGY_USE,
    CONF_KPI_SOLAR_POWER,
    CONF_KPI_SOLAR_DAY_ENERGY,
    CONF_KPI_FORECAST_USE,
    CONF_KPI_SOLAR_FORECAST,
    CONF_KPI_PURCHASE_PRICE,
)

_LOGGER = logging.getLogger(__name__)


class HomieMainConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Homie Main."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._site_name: str = "Home"
        self._presence_mode: str = "GPS"
        self._presence_data: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step: site name and presence mode selection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate site name
            site_name = user_input.get(CONF_SITE_NAME, "").strip()
            if not site_name:
                errors[CONF_SITE_NAME] = "empty_site_name"
            else:
                self._site_name = site_name
                self._presence_mode = user_input[CONF_PRESENCE_MODE]
                return await self.async_step_presence_inputs()

        schema = vol.Schema(
            {
                vol.Required(CONF_SITE_NAME, default="Home"): str,
                vol.Required(CONF_PRESENCE_MODE, default="GPS"): vol.In(PRESENCE_MODES),
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    async def async_step_presence_inputs(
        self, user_input: dict[str, Any] | None = None
    ):
        """Handle presence entity selection based on chosen mode."""
        mode = self._presence_mode or "GPS"
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate calendar entity if provided
            cal_entity = user_input.get(CONF_CALENDAR_ENTITY, DEFAULT_CALENDAR)
            if cal_entity and cal_entity != DEFAULT_CALENDAR:
                # Check if calendar entity exists
                if not self.hass.states.get(cal_entity):
                    errors[CONF_CALENDAR_ENTITY] = "calendar_not_found"
                    _LOGGER.warning("Calendar entity %s not found", cal_entity)

            # Validate presence entities based on mode
            if mode == "GPS":
                entities = user_input.get(CONF_GPS_ENTITIES, [])
                if not entities:
                    _LOGGER.info("No GPS entities configured - will use empty list")
            elif mode == "WiFi":
                entities = user_input.get(CONF_WIFI_ENTITIES, [])
                if not entities:
                    _LOGGER.info("No WiFi entities configured - will use empty list")
            elif mode == "Motion":
                entities = user_input.get(CONF_MOTION_ENTITIES, [])
                if not entities:
                    _LOGGER.info("No Motion entities configured - will use empty list")

            if not errors:
                self._presence_data = {
                    CONF_SITE_NAME: self._site_name,
                    CONF_PRESENCE_MODE: mode,
                    CONF_CALENDAR_ENTITY: cal_entity,
                    CONF_GPS_ENTITIES: user_input.get(CONF_GPS_ENTITIES, []),
                    CONF_WIFI_ENTITIES: user_input.get(CONF_WIFI_ENTITIES, []),
                    CONF_MOTION_ENTITIES: user_input.get(CONF_MOTION_ENTITIES, []),
                }
                return await self.async_step_email_smtp()

        # Build form fields based on presence mode
        fields: dict = {
            vol.Optional(
                CONF_CALENDAR_ENTITY, default=DEFAULT_CALENDAR
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="calendar")
            ),
        }

        if mode == "GPS":
            fields[vol.Optional(CONF_GPS_ENTITIES, default=[])] = selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=["person", "device_tracker"], multiple=True
                )
            )
        elif mode == "WiFi":
            fields[vol.Optional(CONF_WIFI_ENTITIES, default=[])] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="device_tracker", multiple=True)
            )
        elif mode == "Motion":
            fields[vol.Optional(CONF_MOTION_ENTITIES, default=[])] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="binary_sensor", multiple=True)
            )
        elif mode == "Calendar":
            # Calendar mode uses calendar entity as primary source
            pass

        return self.async_show_form(
            step_id="presence_inputs",
            data_schema=vol.Schema(fields),
            errors=errors,
            description_placeholders={
                "mode": mode,
            },
        )

    async def async_step_email_smtp(self, user_input: dict[str, Any] | None = None):
        """Configure SMTP for email notifications (optional)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Build options with defaults
            options = dict(DEFAULT_KPIS)

            # Notification defaults (user can change later)
            options[OPT_NOTIFICATIONS_ENABLED] = DEFAULT_NOTIFICATIONS_ENABLED
            options[OPT_PUSH_ENABLED] = DEFAULT_PUSH_ENABLED
            options[OPT_EMAIL_ENABLED] = DEFAULT_EMAIL_ENABLED
            options[OPT_NOTIFICATION_LEVEL] = DEFAULT_NOTIFICATION_LEVEL
            options[OPT_PUSH_LEVEL] = DEFAULT_PUSH_LEVEL
            options[OPT_NOTIFY_TARGET_PUSH] = DEFAULT_NOTIFY_TARGET_PUSH

            # SMTP configuration from wizard
            options[OPT_SMTP_HOST] = user_input.get(OPT_SMTP_HOST, DEFAULT_SMTP_HOST)
            options[OPT_SMTP_PORT] = int(
                user_input.get(OPT_SMTP_PORT, DEFAULT_SMTP_PORT)
            )
            options[OPT_SMTP_SSL] = bool(user_input.get(OPT_SMTP_SSL, DEFAULT_SMTP_SSL))
            options[OPT_SMTP_STARTTLS] = bool(
                user_input.get(OPT_SMTP_STARTTLS, DEFAULT_SMTP_STARTTLS)
            )
            options[OPT_SMTP_USERNAME] = user_input.get(
                OPT_SMTP_USERNAME, DEFAULT_SMTP_USERNAME
            )
            options[OPT_SMTP_PASSWORD] = user_input.get(
                OPT_SMTP_PASSWORD, DEFAULT_SMTP_PASSWORD
            )
            options[OPT_SMTP_FROM] = user_input.get(OPT_SMTP_FROM, DEFAULT_SMTP_FROM)

            # Separate recipient lists for warnings and alerts
            options[OPT_SMTP_TO_WARNINGS] = user_input.get(
                OPT_SMTP_TO_WARNINGS, DEFAULT_SMTP_TO_WARNINGS
            )
            options[OPT_SMTP_TO_ALERTS] = user_input.get(
                OPT_SMTP_TO_ALERTS, DEFAULT_SMTP_TO_ALERTS
            )

            return self.async_create_entry(
                title=f"Homie Main ({self._site_name})",
                data=self._presence_data,
                options=options,
            )

        schema = vol.Schema(
            {
                vol.Optional(OPT_SMTP_HOST, default=DEFAULT_SMTP_HOST): str,
                vol.Optional(OPT_SMTP_PORT, default=DEFAULT_SMTP_PORT): vol.Coerce(int),
                vol.Optional(OPT_SMTP_SSL, default=DEFAULT_SMTP_SSL): bool,
                vol.Optional(OPT_SMTP_STARTTLS, default=DEFAULT_SMTP_STARTTLS): bool,
                vol.Optional(OPT_SMTP_USERNAME, default=DEFAULT_SMTP_USERNAME): str,
                vol.Optional(
                    OPT_SMTP_PASSWORD,
                    default=DEFAULT_SMTP_PASSWORD,
                ): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.PASSWORD
                    )
                ),
                vol.Optional(OPT_SMTP_FROM, default=DEFAULT_SMTP_FROM): str,
                vol.Optional(
                    OPT_SMTP_TO_WARNINGS,
                    default=DEFAULT_SMTP_TO_WARNINGS,
                ): str,
                vol.Optional(
                    OPT_SMTP_TO_ALERTS,
                    default=DEFAULT_SMTP_TO_ALERTS,
                ): str,
            }
        )

        return self.async_show_form(
            step_id="email_smtp",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "site_name": self._site_name,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return HomieMainOptionsFlowHandler(config_entry)


class HomieMainOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Homie Main."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                # Notification settings
                vol.Optional(
                    OPT_NOTIFICATIONS_ENABLED,
                    default=self.entry.options.get(
                        OPT_NOTIFICATIONS_ENABLED, DEFAULT_NOTIFICATIONS_ENABLED
                    ),
                ): bool,
                vol.Optional(
                    OPT_PUSH_ENABLED,
                    default=self.entry.options.get(
                        OPT_PUSH_ENABLED, DEFAULT_PUSH_ENABLED
                    ),
                ): bool,
                vol.Optional(
                    OPT_EMAIL_ENABLED,
                    default=self.entry.options.get(
                        OPT_EMAIL_ENABLED, DEFAULT_EMAIL_ENABLED
                    ),
                ): bool,
                vol.Optional(
                    OPT_NOTIFICATION_LEVEL,
                    default=self.entry.options.get(
                        OPT_NOTIFICATION_LEVEL, DEFAULT_NOTIFICATION_LEVEL
                    ),
                ): vol.In(NOTIFICATION_LEVELS),
                vol.Optional(
                    OPT_PUSH_LEVEL,
                    default=self.entry.options.get(OPT_PUSH_LEVEL, DEFAULT_PUSH_LEVEL),
                ): vol.In(PUSH_LEVELS),
                # Push target
                vol.Optional(
                    OPT_NOTIFY_TARGET_PUSH,
                    default=self.entry.options.get(
                        OPT_NOTIFY_TARGET_PUSH, DEFAULT_NOTIFY_TARGET_PUSH
                    ),
                ): str,
                # SMTP settings (editable later)
                vol.Optional(
                    OPT_SMTP_HOST,
                    default=self.entry.options.get(OPT_SMTP_HOST, DEFAULT_SMTP_HOST),
                ): str,
                vol.Optional(
                    OPT_SMTP_PORT,
                    default=int(
                        self.entry.options.get(OPT_SMTP_PORT, DEFAULT_SMTP_PORT)
                    ),
                ): vol.Coerce(int),
                vol.Optional(
                    OPT_SMTP_SSL,
                    default=bool(self.entry.options.get(OPT_SMTP_SSL, DEFAULT_SMTP_SSL)),
                ): bool,
                vol.Optional(
                    OPT_SMTP_STARTTLS,
                    default=bool(
                        self.entry.options.get(OPT_SMTP_STARTTLS, DEFAULT_SMTP_STARTTLS)
                    ),
                ): bool,
                vol.Optional(
                    OPT_SMTP_USERNAME,
                    default=self.entry.options.get(
                        OPT_SMTP_USERNAME, DEFAULT_SMTP_USERNAME
                    ),
                ): str,
                vol.Optional(
                    OPT_SMTP_PASSWORD,
                    default=self.entry.options.get(
                        OPT_SMTP_PASSWORD, DEFAULT_SMTP_PASSWORD
                    ),
                ): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.PASSWORD
                    )
                ),
                vol.Optional(
                    OPT_SMTP_FROM,
                    default=self.entry.options.get(OPT_SMTP_FROM, DEFAULT_SMTP_FROM),
                ): str,
                vol.Optional(
                    OPT_SMTP_TO_WARNINGS,
                    default=self.entry.options.get(
                        OPT_SMTP_TO_WARNINGS, DEFAULT_SMTP_TO_WARNINGS
                    ),
                ): str,
                vol.Optional(
                    OPT_SMTP_TO_ALERTS,
                    default=self.entry.options.get(
                        OPT_SMTP_TO_ALERTS, DEFAULT_SMTP_TO_ALERTS
                    ),
                ): str,
                # KPI mapping
                vol.Required(
                    CONF_KPI_POWER_USE,
                    default=self.entry.options.get(
                        CONF_KPI_POWER_USE, DEFAULT_KPIS[CONF_KPI_POWER_USE]
                    ),
                ): selector.EntitySelector(selector.EntitySelectorConfig()),
                vol.Required(
                    CONF_KPI_DAY_ENERGY_USE,
                    default=self.entry.options.get(
                        CONF_KPI_DAY_ENERGY_USE, DEFAULT_KPIS[CONF_KPI_DAY_ENERGY_USE]
                    ),
                ): selector.EntitySelector(selector.EntitySelectorConfig()),
                vol.Required(
                    CONF_KPI_SOLAR_POWER,
                    default=self.entry.options.get(
                        CONF_KPI_SOLAR_POWER, DEFAULT_KPIS[CONF_KPI_SOLAR_POWER]
                    ),
                ): selector.EntitySelector(selector.EntitySelectorConfig()),
                vol.Required(
                    CONF_KPI_SOLAR_DAY_ENERGY,
                    default=self.entry.options.get(
                        CONF_KPI_SOLAR_DAY_ENERGY, DEFAULT_KPIS[CONF_KPI_SOLAR_DAY_ENERGY]
                    ),
                ): selector.EntitySelector(selector.EntitySelectorConfig()),
                vol.Required(
                    CONF_KPI_FORECAST_USE,
                    default=self.entry.options.get(
                        CONF_KPI_FORECAST_USE, DEFAULT_KPIS[CONF_KPI_FORECAST_USE]
                    ),
                ): selector.EntitySelector(selector.EntitySelectorConfig()),
                vol.Required(
                    CONF_KPI_SOLAR_FORECAST,
                    default=self.entry.options.get(
                        CONF_KPI_SOLAR_FORECAST, DEFAULT_KPIS[CONF_KPI_SOLAR_FORECAST]
                    ),
                ): selector.EntitySelector(selector.EntitySelectorConfig()),
                vol.Required(
                    CONF_KPI_PURCHASE_PRICE,
                    default=self.entry.options.get(
                        CONF_KPI_PURCHASE_PRICE, DEFAULT_KPIS[CONF_KPI_PURCHASE_PRICE]
                    ),
                ): selector.EntitySelector(selector.EntitySelectorConfig()),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)

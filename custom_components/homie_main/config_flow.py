# custom_components/homie_main/config_flow.py

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    # locked data
    CONF_SITE_NAME,
    CONF_PRESENCE_MODE,
    PRESENCE_MODES,
    CONF_GPS_ENTITIES,
    CONF_WIFI_ENTITIES,
    CONF_MOTION_ENTITIES,
    CONF_CALENDAR_ENTITY,
    DEFAULT_CALENDAR,
    # options defaults
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
    # smtp
    OPT_SMTP_HOST,
    OPT_SMTP_PORT,
    OPT_SMTP_STARTTLS,
    OPT_SMTP_SSL,
    OPT_SMTP_USERNAME,
    OPT_SMTP_PASSWORD,
    OPT_SMTP_FROM,
    OPT_SMTP_TO,
    DEFAULT_SMTP_HOST,
    DEFAULT_SMTP_PORT,
    DEFAULT_SMTP_STARTTLS,
    DEFAULT_SMTP_SSL,
    DEFAULT_SMTP_USERNAME,
    DEFAULT_SMTP_PASSWORD,
    DEFAULT_SMTP_FROM,
    DEFAULT_SMTP_TO,
    # KPI keys
    CONF_KPI_POWER_USE,
    CONF_KPI_DAY_ENERGY_USE,
    CONF_KPI_SOLAR_POWER,
    CONF_KPI_SOLAR_DAY_ENERGY,
    CONF_KPI_FORECAST_USE,
    CONF_KPI_SOLAR_FORECAST,
    CONF_KPI_PURCHASE_PRICE,
)


class HomieMainConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._site_name: str = "Home"
        self._presence_mode: str = "GPS"
        self._data: dict = {}

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self._site_name = user_input[CONF_SITE_NAME]
            self._presence_mode = user_input[CONF_PRESENCE_MODE]
            return await self.async_step_presence_inputs()

        schema = vol.Schema(
            {
                vol.Required(CONF_SITE_NAME, default="Home"): str,
                vol.Required(CONF_PRESENCE_MODE, default="GPS"): vol.In(PRESENCE_MODES),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_presence_inputs(self, user_input=None):
        mode = self._presence_mode or "GPS"

        if user_input is not None:
            self._data = {
                CONF_SITE_NAME: self._site_name,
                CONF_PRESENCE_MODE: mode,  # locked after install
                CONF_CALENDAR_ENTITY: user_input.get(CONF_CALENDAR_ENTITY, DEFAULT_CALENDAR),
                CONF_GPS_ENTITIES: user_input.get(CONF_GPS_ENTITIES, []),
                CONF_WIFI_ENTITIES: user_input.get(CONF_WIFI_ENTITIES, []),
                CONF_MOTION_ENTITIES: user_input.get(CONF_MOTION_ENTITIES, []),
            }
            return await self.async_step_email_smtp()

        fields: dict = {
            vol.Optional(
                CONF_CALENDAR_ENTITY, default=DEFAULT_CALENDAR
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="calendar")),
        }

        if mode == "GPS":
            fields[vol.Optional(CONF_GPS_ENTITIES, default=[])] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["person", "device_tracker"], multiple=True)
            )
        elif mode == "WiFi":
            fields[vol.Optional(CONF_WIFI_ENTITIES, default=[])] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="device_tracker", multiple=True)
            )
        elif mode == "Motion":
            fields[vol.Optional(CONF_MOTION_ENTITIES, default=[])] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="binary_sensor", multiple=True)
            )

        return self.async_show_form(step_id="presence_inputs", data_schema=vol.Schema(fields))

    async def async_step_email_smtp(self, user_input=None):
        if user_input is not None:
            options = dict(DEFAULT_KPIS)

            # notification defaults
            options[OPT_NOTIFICATIONS_ENABLED] = DEFAULT_NOTIFICATIONS_ENABLED
            options[OPT_PUSH_ENABLED] = DEFAULT_PUSH_ENABLED
            options[OPT_EMAIL_ENABLED] = DEFAULT_EMAIL_ENABLED
            options[OPT_NOTIFICATION_LEVEL] = DEFAULT_NOTIFICATION_LEVEL
            options[OPT_PUSH_LEVEL] = DEFAULT_PUSH_LEVEL
            options[OPT_NOTIFY_TARGET_PUSH] = DEFAULT_NOTIFY_TARGET_PUSH

            # SMTP from wizard
            options[OPT_SMTP_HOST] = user_input.get(OPT_SMTP_HOST, DEFAULT_SMTP_HOST)
            options[OPT_SMTP_PORT] = int(user_input.get(OPT_SMTP_PORT, DEFAULT_SMTP_PORT))
            options[OPT_SMTP_SSL] = bool(user_input.get(OPT_SMTP_SSL, DEFAULT_SMTP_SSL))
            options[OPT_SMTP_STARTTLS] = bool(user_input.get(OPT_SMTP_STARTTLS, DEFAULT_SMTP_STARTTLS))
            options[OPT_SMTP_USERNAME] = user_input.get(OPT_SMTP_USERNAME, DEFAULT_SMTP_USERNAME)
            options[OPT_SMTP_PASSWORD] = user_input.get(OPT_SMTP_PASSWORD, DEFAULT_SMTP_PASSWORD)
            options[OPT_SMTP_FROM] = user_input.get(OPT_SMTP_FROM, DEFAULT_SMTP_FROM)
            options[OPT_SMTP_TO] = user_input.get(OPT_SMTP_TO, DEFAULT_SMTP_TO)

            return self.async_create_entry(
                title=f"Homie Main ({self._site_name})",
                data=self._data,
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
                ): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
                vol.Optional(OPT_SMTP_FROM, default=DEFAULT_SMTP_FROM): str,
                vol.Optional(OPT_SMTP_TO, default=DEFAULT_SMTP_TO): str,
            }
        )

        return self.async_show_form(step_id="email_smtp", data_schema=schema)

    @staticmethod
    def async_get_options_flow(config_entry):
        return HomieMainOptionsFlowHandler(config_entry)


class HomieMainOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self.entry = entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                # user toggles/levels
                vol.Optional(
                    OPT_NOTIFICATIONS_ENABLED,
                    default=self.entry.options.get(OPT_NOTIFICATIONS_ENABLED, DEFAULT_NOTIFICATIONS_ENABLED),
                ): bool,
                vol.Optional(
                    OPT_PUSH_ENABLED,
                    default=self.entry.options.get(OPT_PUSH_ENABLED, DEFAULT_PUSH_ENABLED),
                ): bool,
                vol.Optional(
                    OPT_EMAIL_ENABLED,
                    default=self.entry.options.get(OPT_EMAIL_ENABLED, DEFAULT_EMAIL_ENABLED),
                ): bool,
                vol.Optional(
                    OPT_NOTIFICATION_LEVEL,
                    default=self.entry.options.get(OPT_NOTIFICATION_LEVEL, DEFAULT_NOTIFICATION_LEVEL),
                ): vol.In(NOTIFICATION_LEVELS),
                vol.Optional(
                    OPT_PUSH_LEVEL,
                    default=self.entry.options.get(OPT_PUSH_LEVEL, DEFAULT_PUSH_LEVEL),
                ): vol.In(PUSH_LEVELS),

                # push target
                vol.Optional(
                    OPT_NOTIFY_TARGET_PUSH,
                    default=self.entry.options.get(OPT_NOTIFY_TARGET_PUSH, DEFAULT_NOTIFY_TARGET_PUSH),
                ): str,

                # SMTP editable later
                vol.Optional(
                    OPT_SMTP_HOST,
                    default=self.entry.options.get(OPT_SMTP_HOST, DEFAULT_SMTP_HOST),
                ): str,
                vol.Optional(
                    OPT_SMTP_PORT,
                    default=int(self.entry.options.get(OPT_SMTP_PORT, DEFAULT_SMTP_PORT)),
                ): vol.Coerce(int),
                vol.Optional(
                    OPT_SMTP_SSL,
                    default=bool(self.entry.options.get(OPT_SMTP_SSL, DEFAULT_SMTP_SSL)),
                ): bool,
                vol.Optional(
                    OPT_SMTP_STARTTLS,
                    default=bool(self.entry.options.get(OPT_SMTP_STARTTLS, DEFAULT_SMTP_STARTTLS)),
                ): bool,
                vol.Optional(
                    OPT_SMTP_USERNAME,
                    default=self.entry.options.get(OPT_SMTP_USERNAME, DEFAULT_SMTP_USERNAME),
                ): str,
                vol.Optional(
                    OPT_SMTP_PASSWORD,
                    default=self.entry.options.get(OPT_SMTP_PASSWORD, DEFAULT_SMTP_PASSWORD),
                ): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
                vol.Optional(
                    OPT_SMTP_FROM,
                    default=self.entry.options.get(OPT_SMTP_FROM, DEFAULT_SMTP_FROM),
                ): str,
                vol.Optional(
                    OPT_SMTP_TO,
                    default=self.entry.options.get(OPT_SMTP_TO, DEFAULT_SMTP_TO),
                ): str,

                # KPI mapping
                vol.Required(
                    CONF_KPI_POWER_USE,
                    default=self.entry.options.get(CONF_KPI_POWER_USE, DEFAULT_KPIS[CONF_KPI_POWER_USE]),
                ): selector.EntitySelector(selector.EntitySelectorConfig()),
                vol.Required(
                    CONF_KPI_DAY_ENERGY_USE,
                    default=self.entry.options.get(CONF_KPI_DAY_ENERGY_USE, DEFAULT_KPIS[CONF_KPI_DAY_ENERGY_USE]),
                ): selector.EntitySelector(selector.EntitySelectorConfig()),
                vol.Required(
                    CONF_KPI_SOLAR_POWER,
                    default=self.entry.options.get(CONF_KPI_SOLAR_POWER, DEFAULT_KPIS[CONF_KPI_SOLAR_POWER]),
                ): selector.EntitySelector(selector.EntitySelectorConfig()),
                vol.Required(
                    CONF_KPI_SOLAR_DAY_ENERGY,
                    default=self.entry.options.get(CONF_KPI_SOLAR_DAY_ENERGY, DEFAULT_KPIS[CONF_KPI_SOLAR_DAY_ENERGY]),
                ): selector.EntitySelector(selector.EntitySelectorConfig()),
                vol.Required(
                    CONF_KPI_FORECAST_USE,
                    default=self.entry.options.get(CONF_KPI_FORECAST_USE, DEFAULT_KPIS[CONF_KPI_FORECAST_USE]),
                ): selector.EntitySelector(selector.EntitySelectorConfig()),
                vol.Required(
                    CONF_KPI_SOLAR_FORECAST,
                    default=self.entry.options.get(CONF_KPI_SOLAR_FORECAST, DEFAULT_KPIS[CONF_KPI_SOLAR_FORECAST]),
                ): selector.EntitySelector(selector.EntitySelectorConfig()),
                vol.Required(
                    CONF_KPI_PURCHASE_PRICE,
                    default=self.entry.options.get(CONF_KPI_PURCHASE_PRICE, DEFAULT_KPIS[CONF_KPI_PURCHASE_PRICE]),
                ): selector.EntitySelector(selector.EntitySelectorConfig()),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)

# custom_components/homie_main/sensor.py

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import HomieMainCoordinator
from .const import (
    DOMAIN,
    # KPI option keys
    CONF_KPI_POWER_USE,
    CONF_KPI_DAY_ENERGY_USE,
    CONF_KPI_SOLAR_POWER,
    CONF_KPI_SOLAR_DAY_ENERGY,
    CONF_KPI_FORECAST_USE,
    CONF_KPI_SOLAR_FORECAST,
    CONF_KPI_PURCHASE_PRICE,
    DEFAULT_KPIS,
)

KPI_SENSORS = [
    (CONF_KPI_POWER_USE, "HM KPI Use Power", "W"),
    (CONF_KPI_DAY_ENERGY_USE, "HM KPI Use Day Energy", "kWh"),
    (CONF_KPI_SOLAR_POWER, "HM KPI Solar Power", "W"),
    (CONF_KPI_SOLAR_DAY_ENERGY, "HM KPI Solar Day Energy", "kWh"),
    (CONF_KPI_FORECAST_USE, "HM KPI Forecast Use", "kWh"),
    (CONF_KPI_SOLAR_FORECAST, "HM KPI Solar Forecast", "kWh"),
    (CONF_KPI_PURCHASE_PRICE, "HM KPI Purchase Price", None),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator: HomieMainCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities: list = [
        HMPresenceStatus(coordinator, entry),
        HMPresenceSource(coordinator, entry),
        HMManualOverrideActive(coordinator, entry),
        HMManualOverrideUntil(coordinator, entry),
        HMGapPresence(coordinator, entry),
        HMGapCalendar(coordinator, entry),
        HMGapMain(coordinator, entry),
    ]

    for opt_key, name, unit in KPI_SENSORS:
        entities.append(HMKpiPassthrough(coordinator, entry, opt_key, name, unit))

    async_add_entities(entities)


class BaseHmEntity(CoordinatorEntity[HomieMainCoordinator]):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: HomieMainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self.entry = entry


class HMPresenceStatus(BaseHmEntity, SensorEntity):
    _attr_name = "HM Presence"
    _attr_icon = "mdi:home-account"

    def __init__(self, coordinator: HomieMainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_presence_status"

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get("presence_status")


class HMPresenceSource(BaseHmEntity, SensorEntity):
    _attr_name = "HM Presence Source"
    _attr_icon = "mdi:source-branch"

    def __init__(self, coordinator: HomieMainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_presence_source"

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get("presence_source")


class HMManualOverrideActive(BaseHmEntity, BinarySensorEntity):
    _attr_name = "HM Manual Override Active"
    _attr_icon = "mdi:shield-lock"

    def __init__(self, coordinator: HomieMainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_manual_override_active"

    @property
    def is_on(self) -> bool:
        return bool((self.coordinator.data or {}).get("manual_override_active"))


class HMManualOverrideUntil(BaseHmEntity, SensorEntity):
    _attr_name = "HM Manual Override Until"
    _attr_icon = "mdi:clock-end"

    def __init__(self, coordinator: HomieMainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_manual_override_until"

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get("manual_override_until")


class HMGapPresence(BaseHmEntity, BinarySensorEntity):
    _attr_name = "HM Data Gap Presence"
    _attr_icon = "mdi:alert-circle-outline"

    def __init__(self, coordinator: HomieMainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_gap_presence"

    @property
    def is_on(self) -> bool:
        return bool((self.coordinator.data or {}).get("gap_presence"))


class HMGapCalendar(BaseHmEntity, BinarySensorEntity):
    _attr_name = "HM Data Gap Calendar"
    _attr_icon = "mdi:calendar-alert"

    def __init__(self, coordinator: HomieMainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_gap_calendar"

    @property
    def is_on(self) -> bool:
        return bool((self.coordinator.data or {}).get("gap_calendar"))


class HMGapMain(BaseHmEntity, BinarySensorEntity):
    _attr_name = "HM Data Gap Main"
    _attr_icon = "mdi:chart-line-variant"

    def __init__(self, coordinator: HomieMainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_gap_main"

    @property
    def is_on(self) -> bool:
        return bool((self.coordinator.data or {}).get("gap_main"))


class HMKpiPassthrough(CoordinatorEntity[HomieMainCoordinator], SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: HomieMainCoordinator,
        entry: ConfigEntry,
        option_key: str,
        name: str,
        unit: str | None,
    ) -> None:
        super().__init__(coordinator)
        self.entry = entry
        self.option_key = option_key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_kpi_{option_key}"
        self._attr_native_unit_of_measurement = unit

    @property
    def native_value(self):
        # passthrough: read the mapped entity state
        eid = self.entry.options.get(self.option_key, DEFAULT_KPIS.get(self.option_key, ""))
        if not eid:
            return 0
        st = self.hass.states.get(eid)
        if st is None or st.state in ("unknown", "unavailable"):
            return 0
        try:
            return float(st.state)
        except ValueError:
            return st.state

    @property
    def extra_state_attributes(self):
        eid = self.entry.options.get(self.option_key, DEFAULT_KPIS.get(self.option_key, ""))
        return {"source_entity": eid}

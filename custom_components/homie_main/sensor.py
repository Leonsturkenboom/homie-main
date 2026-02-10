# custom_components/homie_main/sensor.py
"""Sensor platform for Homie Main."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    OP_MODE_ACTIVE,
    OP_MODE_STANDBY,
    OP_MODE_HIBERNATION,
    VIS_POWER,
    VIS_DAY_ENERGY,
    VIS_DAY_PRICE,
    CONF_KPI_POWER_USE,
    CONF_KPI_DAY_ENERGY_USE,
    CONF_KPI_SOLAR_POWER,
    CONF_KPI_SOLAR_DAY_ENERGY,
    CONF_KPI_PURCHASE_PRICE,
    CONF_KPI_FORECAST_USE,
    CONF_KPI_SOLAR_FORECAST,
    CONF_GPS_ENTITIES,
    CONF_PING_ENTITIES,
    CONF_MOTION_ENTITIES,
    CONF_CALENDAR_ENTITIES,
    CONF_USE_GPS,
    CONF_USE_WIFI,
    CONF_USE_MOTION,
    CONF_USE_CALENDAR,
)
from .coordinator import HomieMainCoordinator

# Data gap threshold in seconds (1 hour)
DATA_GAP_THRESHOLD = 3600

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homie Main sensors from a config entry."""
    coordinator: HomieMainCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities: list[SensorEntity] = [
        HMPresenceSourceSensor(coordinator, entry),
        HMManualOverrideActiveSensor(coordinator, entry),
        HMManualOverrideUntilSensor(coordinator, entry),
        HMOperatingModeSensor(coordinator, entry),
        HMPriceDayCurveSensor(coordinator, entry),
        HMUseDisplaySensor(coordinator, entry),
        HMSolarDisplaySensor(coordinator, entry),
        # Weather forecast sensors
        HMWeatherTemperatureSensor(coordinator, entry),
        HMWeatherWindSensor(coordinator, entry),
        HMWeatherSolarSensor(coordinator, entry),
        # Data gap warning notifications (PRD Output 11-12-13)
        HMWarningDataGapPresenceSensor(coordinator, entry, hass),
        HMWarningDataGapCalendarSensor(coordinator, entry, hass),
        HMWarningDataGapMainSensor(coordinator, entry, hass),
    ]

    async_add_entities(entities)
    _LOGGER.info("Added %d Homie Main sensors", len(entities))


class HMBaseSensor(CoordinatorEntity[HomieMainCoordinator], SensorEntity):
    """Base class for Homie Main sensors."""

    _attr_has_entity_name = False  # Use explicit entity_id naming

    def __init__(
        self,
        coordinator: HomieMainCoordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name  # Explicit name for entity_id generation
        self._key = key

        # Device info for grouping all entities together
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Homie Main ({entry.title})",
            "manufacturer": "Homie",
            "model": "Main",
            "sw_version": "0.1.0",
        }


class HMPresenceSourceSensor(HMBaseSensor):
    """Sensor showing the source of the presence status."""

    def __init__(self, coordinator: HomieMainCoordinator, entry: ConfigEntry) -> None:
        """Initialize the presence source sensor."""
        super().__init__(coordinator, entry, "hm_presence_source", "HM Presence Source")
        self._attr_icon = "mdi:information-outline"

    @property
    def native_value(self) -> str:
        """Return the presence source."""
        return self.coordinator.data.presence.source

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "last_updated": self.coordinator.data.presence.last_updated.isoformat(),
            "active_methods": self.coordinator.data.presence.active_methods,
        }


class HMManualOverrideActiveSensor(HMBaseSensor):
    """Sensor showing if manual override is active."""

    def __init__(self, coordinator: HomieMainCoordinator, entry: ConfigEntry) -> None:
        """Initialize the manual override active sensor."""
        super().__init__(coordinator, entry, "hm_manual_override_active", "HM Manual Override Active")
        self._attr_icon = "mdi:hand-back-left"

    @property
    def native_value(self) -> str:
        """Return if manual override is active."""
        return "on" if self.coordinator.data.manual_override.active else "off"


class HMManualOverrideUntilSensor(HMBaseSensor):
    """Sensor showing when manual override expires."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: HomieMainCoordinator, entry: ConfigEntry) -> None:
        """Initialize the manual override until sensor."""
        super().__init__(coordinator, entry, "hm_manual_override_until", "HM Manual Override Until")
        self._attr_icon = "mdi:clock-outline"

    @property
    def native_value(self) -> str | None:
        """Return when manual override expires."""
        if self.coordinator.data.manual_override.active and self.coordinator.data.manual_override.expires_at:
            return self.coordinator.data.manual_override.expires_at.isoformat()
        return None


class HMOperatingModeSensor(HMBaseSensor):
    """Sensor showing the current operating mode."""

    def __init__(self, coordinator: HomieMainCoordinator, entry: ConfigEntry) -> None:
        """Initialize the operating mode sensor."""
        super().__init__(coordinator, entry, "hm_operating_mode", "HM Operating Mode")

    @property
    def native_value(self) -> str:
        """Return the operating mode."""
        return self.coordinator.data.operating_mode

    @property
    def icon(self) -> str:
        """Return icon based on operating mode."""
        mode = self.coordinator.data.operating_mode
        if mode == OP_MODE_ACTIVE:
            return "mdi:home-lightning-bolt"
        elif mode == OP_MODE_STANDBY:
            return "mdi:home-clock"
        elif mode == OP_MODE_HIBERNATION:
            return "mdi:home-sleep"
        return "mdi:home"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "presence_status": self.coordinator.data.presence.status,
            "presence_source": self.coordinator.data.presence.source,
            "location_type": self.coordinator.data.location_type,
        }


class HMPriceDayCurveSensor(HMBaseSensor):
    """Sensor that cycles through today's prices to create a day curve in mini-graph-card.

    Every clock-hour the sensor replays all of today's prices (24 for hourly,
    96 for 15-min data) in order, advancing to the next price at equal
    intervals.  With hours_to_show: 1 the recorder history of the last
    60 minutes contains exactly one complete day-curve plotted left-to-right
    (00:00 → 23:00).  Labels are hidden so the x-axis is invisible.
    """

    def __init__(self, coordinator: HomieMainCoordinator, entry: ConfigEntry) -> None:
        """Initialize the price day curve sensor."""
        super().__init__(coordinator, entry, "hm_price_day_curve", "HM Price Day Curve")
        self._attr_icon = "mdi:chart-line"
        self._attr_native_unit_of_measurement = "EUR/kWh"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._cycle_index: int = 0
        self._unsub_timer: callback | None = None

    # -- lifecycle ---------------------------------------------------------

    async def async_added_to_hass(self) -> None:
        """Start the cycling timer."""
        await super().async_added_to_hass()
        self._sync_cycle_index()
        # 30-second timer is fast enough for 96 entries (one every 37.5 s)
        self._unsub_timer = async_track_time_interval(
            self.hass, self._advance_cycle, timedelta(seconds=30)
        )

    async def async_will_remove_from_hass(self) -> None:
        """Cancel the cycling timer."""
        if self._unsub_timer:
            self._unsub_timer()
            self._unsub_timer = None
        await super().async_will_remove_from_hass()

    # -- cycling logic -----------------------------------------------------

    def _get_sorted_prices(self) -> list[float]:
        """Return today's prices sorted by start time."""
        price_state = self.coordinator.data.price_series_state
        entries: list[tuple[datetime, float]] = []
        for item in price_state.purchase_prices_today:
            if not isinstance(item, dict):
                continue
            start_str = item.get("start")
            price = item.get("price")
            if start_str is None or price is None:
                continue
            try:
                ts = dt_util.parse_datetime(start_str)
                if ts is None:
                    continue
                entries.append((ts, float(price)))
            except (ValueError, TypeError):
                continue
        entries.sort(key=lambda e: e[0])
        return [p for _, p in entries]

    def _sync_cycle_index(self) -> None:
        """Map current minute+second within the hour to a price index."""
        prices = self._get_sorted_prices()
        n = len(prices) if prices else 1
        now = dt_util.now()
        frac = (now.minute * 60 + now.second) / 3600.0
        self._cycle_index = int(frac * n) % n

    @callback
    def _advance_cycle(self, _now: datetime) -> None:
        """Timer callback – advance index and write state if changed."""
        old = self._cycle_index
        self._sync_cycle_index()
        if self._cycle_index != old:
            self.async_write_ha_state()

    # -- sensor properties -------------------------------------------------

    @property
    def native_value(self) -> float | None:
        """Return the price at the current cycle position."""
        prices = self._get_sorted_prices()
        if not prices:
            return self.coordinator.data.price_series_state.current_price
        idx = self._cycle_index % len(prices)
        # Tiny per-index offset so every step is a unique state for the recorder
        return round(prices[idx] + idx * 1e-7, 7)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose day-curve metadata."""
        prices = self._get_sorted_prices()
        price_state = self.coordinator.data.price_series_state
        valid = [p for p in prices if p is not None]
        min_price = min(valid) if valid else None
        max_price = max(valid) if valid else None
        return {
            "prices": prices,
            "count": len(prices),
            "cycle_index": self._cycle_index,
            "min_price": min_price,
            "max_price": max_price,
            "last_updated": (
                price_state.last_updated.isoformat()
                if price_state.last_updated else None
            ),
        }


class HMUseDisplaySensor(HMBaseSensor):
    """Dynamic use sensor that changes based on visualization selection."""

    def __init__(self, coordinator: HomieMainCoordinator, entry: ConfigEntry) -> None:
        """Initialize the use display sensor."""
        super().__init__(coordinator, entry, "hm_use_display", "HM Use Display")
        self._attr_icon = "mdi:flash"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the value based on current visualization mode."""
        vis_mode = self.coordinator.data.visualization_selection
        config = self.coordinator.config

        if vis_mode == VIS_POWER:
            # W - Power use
            return self.coordinator.get_kpi_value(CONF_KPI_POWER_USE)
        elif vis_mode == VIS_DAY_ENERGY:
            # kWh/day - Day energy use
            return self.coordinator.get_kpi_value(CONF_KPI_DAY_ENERGY_USE)
        elif vis_mode == VIS_DAY_PRICE:
            # €/day - Day energy × price
            energy = self.coordinator.get_kpi_value(CONF_KPI_DAY_ENERGY_USE)
            price = self.coordinator.get_kpi_value(CONF_KPI_PURCHASE_PRICE)
            if energy is not None and price is not None:
                return round(energy * price, 2)
            return None
        return None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit based on current visualization mode."""
        vis_mode = self.coordinator.data.visualization_selection
        if vis_mode == VIS_POWER:
            return "W"
        elif vis_mode == VIS_DAY_ENERGY:
            return "kWh"
        elif vis_mode == VIS_DAY_PRICE:
            return "€"
        return None

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return device class based on visualization mode."""
        vis_mode = self.coordinator.data.visualization_selection
        if vis_mode == VIS_POWER:
            return SensorDeviceClass.POWER
        elif vis_mode == VIS_DAY_ENERGY:
            return SensorDeviceClass.ENERGY
        elif vis_mode == VIS_DAY_PRICE:
            return SensorDeviceClass.MONETARY
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "visualization_mode": self.coordinator.data.visualization_selection,
            "source_power": self.coordinator.config.get(CONF_KPI_POWER_USE),
            "source_energy": self.coordinator.config.get(CONF_KPI_DAY_ENERGY_USE),
        }


class HMSolarDisplaySensor(HMBaseSensor):
    """Dynamic solar sensor that changes based on visualization selection."""

    def __init__(self, coordinator: HomieMainCoordinator, entry: ConfigEntry) -> None:
        """Initialize the solar display sensor."""
        super().__init__(coordinator, entry, "hm_solar_display", "HM Solar Display")
        self._attr_icon = "mdi:solar-power"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the value based on current visualization mode."""
        vis_mode = self.coordinator.data.visualization_selection
        config = self.coordinator.config

        if vis_mode == VIS_POWER:
            # W - Solar power
            return self.coordinator.get_kpi_value(CONF_KPI_SOLAR_POWER)
        elif vis_mode == VIS_DAY_ENERGY:
            # kWh/day - Day solar energy
            return self.coordinator.get_kpi_value(CONF_KPI_SOLAR_DAY_ENERGY)
        elif vis_mode == VIS_DAY_PRICE:
            # €/day - Day solar energy × price (savings)
            energy = self.coordinator.get_kpi_value(CONF_KPI_SOLAR_DAY_ENERGY)
            price = self.coordinator.get_kpi_value(CONF_KPI_PURCHASE_PRICE)
            if energy is not None and price is not None:
                return round(energy * price, 2)
            return None
        return None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit based on current visualization mode."""
        vis_mode = self.coordinator.data.visualization_selection
        if vis_mode == VIS_POWER:
            return "W"
        elif vis_mode == VIS_DAY_ENERGY:
            return "kWh"
        elif vis_mode == VIS_DAY_PRICE:
            return "€"
        return None

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return device class based on visualization mode."""
        vis_mode = self.coordinator.data.visualization_selection
        if vis_mode == VIS_POWER:
            return SensorDeviceClass.POWER
        elif vis_mode == VIS_DAY_ENERGY:
            return SensorDeviceClass.ENERGY
        elif vis_mode == VIS_DAY_PRICE:
            return SensorDeviceClass.MONETARY
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "visualization_mode": self.coordinator.data.visualization_selection,
            "source_power": self.coordinator.config.get(CONF_KPI_SOLAR_POWER),
            "source_energy": self.coordinator.config.get(CONF_KPI_SOLAR_DAY_ENERGY),
        }


# =============================================================================
# Weather Forecast Sensors
# =============================================================================

class HMWeatherTemperatureSensor(HMBaseSensor):
    """Weather temperature sensor with 7-day forecast."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "°C"

    def __init__(self, coordinator: HomieMainCoordinator, entry: ConfigEntry) -> None:
        """Initialize the weather temperature sensor."""
        super().__init__(coordinator, entry, "hm_weather_temperature", "HM Weather Temperature")
        self._attr_icon = "mdi:thermometer"

    @property
    def native_value(self) -> float | None:
        """Return the current temperature."""
        return self.coordinator.data.weather_state.temperature

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the 7-day temperature forecast as attributes."""
        weather = self.coordinator.data.weather_state
        return {
            "forecast": weather.temperature_forecast,
            "forecast_entries": len(weather.temperature_forecast),
            "last_updated": weather.last_updated.isoformat() if weather.last_updated else None,
            "latitude": weather.latitude,
            "longitude": weather.longitude,
            "error": weather.error,
        }


class HMWeatherWindSensor(HMBaseSensor):
    """Weather wind speed sensor with 7-day forecast."""

    _attr_device_class = SensorDeviceClass.WIND_SPEED
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "km/h"

    def __init__(self, coordinator: HomieMainCoordinator, entry: ConfigEntry) -> None:
        """Initialize the weather wind sensor."""
        super().__init__(coordinator, entry, "hm_weather_wind", "HM Weather Wind")
        self._attr_icon = "mdi:weather-windy"

    @property
    def native_value(self) -> float | None:
        """Return the current wind speed."""
        return self.coordinator.data.weather_state.wind_speed

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the 7-day wind forecast as attributes."""
        weather = self.coordinator.data.weather_state
        return {
            "forecast": weather.wind_forecast,
            "forecast_entries": len(weather.wind_forecast),
            "last_updated": weather.last_updated.isoformat() if weather.last_updated else None,
            "error": weather.error,
        }


class HMWeatherSolarSensor(HMBaseSensor):
    """Weather solar radiation sensor with 7-day forecast."""

    _attr_device_class = SensorDeviceClass.IRRADIANCE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "W/m²"

    def __init__(self, coordinator: HomieMainCoordinator, entry: ConfigEntry) -> None:
        """Initialize the weather solar sensor."""
        super().__init__(coordinator, entry, "hm_weather_solar", "HM Weather Solar")
        self._attr_icon = "mdi:white-balance-sunny"

    @property
    def native_value(self) -> float | None:
        """Return the current solar radiation."""
        return self.coordinator.data.weather_state.solar_radiation

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the 7-day solar forecast as attributes."""
        weather = self.coordinator.data.weather_state
        return {
            "forecast": weather.solar_forecast,
            "forecast_entries": len(weather.solar_forecast),
            "last_updated": weather.last_updated.isoformat() if weather.last_updated else None,
            "error": weather.error,
        }


# =============================================================================
# Data Gap Warning Sensors (PRD Output 11-12-13)
# =============================================================================

class HMDataGapBaseSensor(CoordinatorEntity[HomieMainCoordinator], SensorEntity):
    """Base class for data gap warning sensors."""

    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: HomieMainCoordinator,
        entry: ConfigEntry,
        hass: HomeAssistant,
        key: str,
        name: str,
    ) -> None:
        """Initialize the data gap sensor."""
        super().__init__(coordinator)
        self._hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = "mdi:alert-circle-outline"
        self._key = key

        # Track when each entity became unavailable
        self._unavailable_since: dict[str, datetime | None] = {}
        self._unsubscribe_listeners: list = []

        # Device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Homie Main ({entry.title})",
            "manufacturer": "Homie",
            "model": "Main",
            "sw_version": "0.1.0",
        }

    def _get_monitored_entities(self) -> list[str]:
        """Return list of entities to monitor. Override in subclass."""
        return []

    def _get_warning_message_nl(self) -> str:
        """Return Dutch warning message. Override in subclass."""
        return "Data onbeschikbaar"

    def _get_warning_message_en(self) -> str:
        """Return English warning message. Override in subclass."""
        return "Data unavailable"

    async def async_added_to_hass(self) -> None:
        """Subscribe to entity state changes when added to hass."""
        await super().async_added_to_hass()

        entities = self._get_monitored_entities()
        if entities:
            # Initialize unavailable tracking for current states
            for entity_id in entities:
                state = self._hass.states.get(entity_id)
                if state and state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                    self._unavailable_since[entity_id] = dt_util.utcnow()
                else:
                    self._unavailable_since[entity_id] = None

            # Subscribe to state changes
            @callback
            def _state_change_listener(event):
                """Handle state changes."""
                entity_id = event.data.get("entity_id")
                new_state = event.data.get("new_state")

                if entity_id not in self._unavailable_since:
                    return

                if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                    # Entity became unavailable
                    if self._unavailable_since.get(entity_id) is None:
                        self._unavailable_since[entity_id] = dt_util.utcnow()
                else:
                    # Entity became available again
                    self._unavailable_since[entity_id] = None

                self.async_write_ha_state()

            unsub = async_track_state_change_event(
                self._hass,
                entities,
                _state_change_listener,
            )
            self._unsubscribe_listeners.append(unsub)

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from events when removed."""
        for unsub in self._unsubscribe_listeners:
            unsub()
        self._unsubscribe_listeners.clear()

    def _check_data_gap(self) -> tuple[bool, list[str]]:
        """Check if any monitored entity has been unavailable for > 1 hour."""
        now = dt_util.utcnow()
        threshold = timedelta(seconds=DATA_GAP_THRESHOLD)
        gap_entities = []

        for entity_id, unavailable_time in self._unavailable_since.items():
            if unavailable_time is not None:
                if now - unavailable_time > threshold:
                    gap_entities.append(entity_id)

        return len(gap_entities) > 0, gap_entities

    @property
    def native_value(self) -> str:
        """Return warning message if data gap detected, otherwise 'off'."""
        has_gap, _ = self._check_data_gap()
        if has_gap:
            # Get language from HA config
            lang = self._hass.config.language if hasattr(self._hass.config, 'language') else "en"
            if lang == "nl":
                return self._get_warning_message_nl()
            return self._get_warning_message_en()
        return "off"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes including Homie tag."""
        has_gap, gap_entities = self._check_data_gap()
        return {
            "tag": "Homie",
            "category": "warning",
            "severity": "warning" if has_gap else "none",
            "monitored_entities": self._get_monitored_entities(),
            "unavailable_entities": gap_entities,
            "threshold_hours": DATA_GAP_THRESHOLD / 3600,
        }


class HMWarningDataGapPresenceSensor(HMDataGapBaseSensor):
    """Warning sensor for presence data gaps (PRD Output 11)."""

    def __init__(
        self,
        coordinator: HomieMainCoordinator,
        entry: ConfigEntry,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the presence data gap sensor."""
        super().__init__(
            coordinator,
            entry,
            hass,
            "hm_warning_data_gap_presence",
            "Warning Data Gap Presence",
        )

    def _get_monitored_entities(self) -> list[str]:
        """Return presence entities to monitor (GPS, WiFi, Motion)."""
        entities = []
        config = self.coordinator.config

        # Only monitor enabled presence methods
        if config.get(CONF_USE_GPS, False):
            entities.extend(config.get(CONF_GPS_ENTITIES, []))
        if config.get(CONF_USE_WIFI, False):
            entities.extend(config.get(CONF_PING_ENTITIES, []))
        if config.get(CONF_USE_MOTION, False):
            entities.extend(config.get(CONF_MOTION_ENTITIES, []))

        return entities

    def _get_warning_message_nl(self) -> str:
        return "Waarschuwing: 1 of meerdere data voor presence is onbeschikbaar"

    def _get_warning_message_en(self) -> str:
        return "Warning: One or more presence data sources unavailable"


class HMWarningDataGapCalendarSensor(HMDataGapBaseSensor):
    """Warning sensor for calendar data gaps (PRD Output 12)."""

    def __init__(
        self,
        coordinator: HomieMainCoordinator,
        entry: ConfigEntry,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the calendar data gap sensor."""
        super().__init__(
            coordinator,
            entry,
            hass,
            "hm_warning_data_gap_calendar",
            "Warning Data Gap Calendar",
        )

    def _get_monitored_entities(self) -> list[str]:
        """Return calendar entities to monitor."""
        config = self.coordinator.config
        if config.get(CONF_USE_CALENDAR, False):
            return config.get(CONF_CALENDAR_ENTITIES, [])
        return []

    def _get_warning_message_nl(self) -> str:
        return "Waarschuwing: Agenda data is onbeschikbaar"

    def _get_warning_message_en(self) -> str:
        return "Warning: Calendar data unavailable"


class HMWarningDataGapMainSensor(HMDataGapBaseSensor):
    """Warning sensor for main KPI data gaps (PRD Output 13)."""

    def __init__(
        self,
        coordinator: HomieMainCoordinator,
        entry: ConfigEntry,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the main KPI data gap sensor."""
        super().__init__(
            coordinator,
            entry,
            hass,
            "hm_warning_data_gap_main",
            "Warning Data Gap Main",
        )

    def _get_monitored_entities(self) -> list[str]:
        """Return main KPI entities to monitor (H-M from PRD)."""
        entities = []
        config = self.coordinator.config

        # KPI sensors (H-M in PRD)
        kpi_keys = [
            CONF_KPI_POWER_USE,        # H - Total power use
            CONF_KPI_DAY_ENERGY_USE,   # I - Total daily energy use
            CONF_KPI_SOLAR_POWER,      # J - Total production
            CONF_KPI_FORECAST_USE,     # K - Total forecasted use
            CONF_KPI_SOLAR_DAY_ENERGY, # L - Total daily production
            CONF_KPI_SOLAR_FORECAST,   # M - Forecast solar
            CONF_KPI_PURCHASE_PRICE,   # N - Purchase price
        ]

        for key in kpi_keys:
            entity_id = config.get(key)
            if entity_id:
                entities.append(entity_id)

        return entities

    def _get_warning_message_nl(self) -> str:
        return "Waarschuwing: 1 of meerdere KPI data inputs onbeschikbaar"

    def _get_warning_message_en(self) -> str:
        return "Warning: One or more KPI data inputs unavailable"

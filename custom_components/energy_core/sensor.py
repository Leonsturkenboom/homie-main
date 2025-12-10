from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, List
from datetime import datetime, timedelta, time

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
    SensorEntityDescription,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import EnergyCoreCoordinator, EnergyInputs


def _inputs(coordinator: EnergyCoreCoordinator) -> EnergyInputs:
    return coordinator.data.get("inputs")


def _clamp_min0(x: float) -> float:
    return x if x > 0 else 0.0


def _calc_self_sufficiency_percent(c: EnergyCoreCoordinator) -> float:
    i = _inputs(c)
    denom = i.imported_kwh + (i.produced_kwh - i.exported_kwh)
    if denom <= 0:
        return 0.0

    ss = 1.0 - (i.imported_kwh / denom)
    ss = max(0.0, min(1.0, ss))
    return round(ss * 100.0, 2)


@dataclass
class ECDescription(SensorEntityDescription):
    """Energy Core sensor description with a value function."""
    value_fn: Callable[[EnergyCoreCoordinator], float] = lambda c: 0.0


# -----------------------------
# Base + derived TOTAL sensors
# -----------------------------
DESCRIPTIONS: list[ECDescription] = [
    # Base totals from inputs
    ECDescription(
        key="ec_imported_energy",
        name="EC Imported Energy",
        icon="mdi:transmission-tower-import",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="kWh",
        value_fn=lambda c: _inputs(c).imported_kwh,
    ),
    ECDescription(
        key="ec_exported_energy",
        name="EC Exported Energy",
        icon="mdi:transmission-tower-export",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="kWh",
        value_fn=lambda c: _inputs(c).exported_kwh,
    ),
    ECDescription(
        key="ec_produced_energy",
        name="EC Produced Energy",
        icon="mdi:solar-power",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="kWh",
        value_fn=lambda c: _inputs(c).produced_kwh,
    ),
    ECDescription(
        key="ec_battery_charge_energy",
        name="EC Battery Charge Energy",
        icon="mdi:battery-arrow-up",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="kWh",
        value_fn=lambda c: _inputs(c).battery_charge_kwh,
    ),
    ECDescription(
        key="ec_battery_discharge_energy",
        name="EC Battery Discharge Energy",
        icon="mdi:battery-arrow-down",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="kWh",
        value_fn=lambda c: _inputs(c).battery_discharge_kwh,
    ),

    # Derived splits (input-only logic)
    ECDescription(
        key="ec_self_consumed_energy",
        name="EC Self Consumed Energy",
        icon="mdi:home-lightning-bolt",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="kWh",
        value_fn=lambda c: _clamp_min0(
            _inputs(c).produced_kwh
            - _inputs(c).exported_kwh
            - _inputs(c).battery_charge_kwh
        ),
    ),
    ECDescription(
        key="ec_self_stored_energy",
        name="EC Self Stored Energy",
        icon="mdi:battery-charging-70",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="kWh",
        value_fn=lambda c: min(
            _inputs(c).battery_charge_kwh,
            _clamp_min0(_inputs(c).produced_kwh - _inputs(c).exported_kwh),
        ),
    ),
    ECDescription(
        key="ec_imported_battery_energy",
        name="EC Imported Battery Energy",
        icon="mdi:battery-charging",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="kWh",
        value_fn=lambda c: _clamp_min0(
            _inputs(c).battery_charge_kwh
            - _clamp_min0(_inputs(c).produced_kwh - _inputs(c).exported_kwh)
        ),
    ),
    ECDescription(
        key="ec_exported_battery_energy",
        name="EC Exported Battery Energy",
        icon="mdi:battery-charging-wireless",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="kWh",
        value_fn=lambda c: min(_inputs(c).battery_discharge_kwh, _inputs(c).exported_kwh),
    ),
    ECDescription(
        key="ec_self_battery_energy",
        name="EC Self Battery Energy",
        icon="mdi:battery",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="kWh",
        value_fn=lambda c: _clamp_min0(
            _inputs(c).battery_discharge_kwh - _inputs(c).exported_kwh
        ),
    ),

    # Net KPIs (point-in-time derived)
    ECDescription(
        key="ec_net_energy_use",
        name="EC Net Energy Use (On-site)",
        icon="mdi:chart-sankey",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kWh",
        value_fn=lambda c: (
            _inputs(c).imported_kwh + _inputs(c).produced_kwh - _inputs(c).exported_kwh
        ),
    ),
    ECDescription(
        key="ec_net_import_energy",
        name="EC Net Import Energy (Grid)",
        icon="mdi:swap-horizontal",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kWh",
        value_fn=lambda c: (_inputs(c).imported_kwh - _inputs(c).exported_kwh),
    ),

    # Self sufficiency
    ECDescription(
        key="ec_self_sufficiency",
        name="EC Self Sufficiency",
        icon="mdi:percent",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
        value_fn=_calc_self_sufficiency_percent,
    ),

    # Emissions (totals-style derived)
    ECDescription(
        key="ec_emissions_imported",
        name="EC Emissions Imported",
        icon="mdi:cloud-upload",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="g CO2-eq",
        value_fn=lambda c: (
            _inputs(c).imported_kwh * _inputs(c).co2_intensity_g_per_kwh
        ),
    ),
    ECDescription(
        key="ec_emissions_avoided",
        name="EC Emissions Avoided",
        icon="mdi:cloud-download",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="g CO2-eq",
        value_fn=lambda c: (
            _inputs(c).exported_kwh * _inputs(c).co2_intensity_g_per_kwh
        ),
    ),
    ECDescription(
        key="ec_emissions_net",
        name="EC Emissions Net",
        icon="mdi:cloud",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="g CO2-eq",
        value_fn=lambda c: (
            (_inputs(c).imported_kwh - _inputs(c).exported_kwh)
            * _inputs(c).co2_intensity_g_per_kwh
        ),
    ),
]


# -----------------------------
# Period counter specs
# -----------------------------
@dataclass
class PeriodSpec:
    key: str
    label: str
    start_fn: Callable[[datetime], datetime]


def _local_floor(now_utc: datetime) -> datetime:
    return dt_util.as_local(now_utc)


def _start_15m(now_utc: datetime) -> datetime:
    nl = _local_floor(now_utc)
    minute = (nl.minute // 15) * 15
    start_local = nl.replace(minute=minute, second=0, microsecond=0)
    return dt_util.as_utc(start_local)


def _start_hour(now_utc: datetime) -> datetime:
    nl = _local_floor(now_utc)
    start_local = nl.replace(minute=0, second=0, microsecond=0)
    return dt_util.as_utc(start_local)


def _start_day(now_utc: datetime) -> datetime:
    nl = _local_floor(now_utc)
    start_local = nl.replace(hour=0, minute=0, second=0, microsecond=0)
    return dt_util.as_utc(start_local)


def _start_week(now_utc: datetime) -> datetime:
    nl = _local_floor(now_utc)
    # Monday as start of week
    start_local = nl.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=nl.weekday())
    return dt_util.as_utc(start_local)


def _start_month(now_utc: datetime) -> datetime:
    nl = _local_floor(now_utc)
    start_local = nl.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return dt_util.as_utc(start_local)


def _start_year(now_utc: datetime) -> datetime:
    nl = _local_floor(now_utc)
    start_local = nl.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return dt_util.as_utc(start_local)


PERIODS: list[PeriodSpec] = [
    PeriodSpec(key="p15m", label="15m", start_fn=_start_15m),
    PeriodSpec(key="phour", label="Hour", start_fn=_start_hour),
    PeriodSpec(key="pday", label="Day", start_fn=_start_day),
    PeriodSpec(key="pweek", label="Week", start_fn=_start_week),
    PeriodSpec(key="pmonth", label="Month", start_fn=_start_month),
    PeriodSpec(key="pyear", label="Year", start_fn=_start_year),
]


# -----------------------------
# Entity classes
# -----------------------------
class EnergyCoreSensor(CoordinatorEntity[EnergyCoreCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: EnergyCoreCoordinator, description: ECDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{description.key}"

        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class
        self._attr_icon = description.icon

    @property
    def native_value(self) -> float:
        try:
            val = self.entity_description.value_fn(self.coordinator)
            return round(float(val), 6)
        except Exception:
            return 0.0


class EnergyCorePeriodCounterSensor(CoordinatorEntity[EnergyCoreCoordinator], SensorEntity):
    """Period delta counter for an underlying TOTAL_INCREASING energy sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EnergyCoreCoordinator,
        base: ECDescription,
        period: PeriodSpec,
    ) -> None:
        super().__init__(coordinator)
        self._base = base
        self._period = period

        self._attr_unique_id = f"{coordinator.entry.entry_id}_{base.key}_{period.key}"
        self._attr_name = f"{base.name} {period.label}"
        self._attr_icon = base.icon

        self._attr_device_class = base.device_class
        self._attr_native_unit_of_measurement = base.native_unit_of_measurement
        # Period counters are deltas within a time bucket
        self._attr_state_class = SensorStateClass.MEASUREMENT

        self._baseline_start: Optional[datetime] = None
        self._baseline_total: Optional[float] = None

    def _current_total(self) -> float:
        try:
            return float(self._base.value_fn(self.coordinator))
        except Exception:
            return 0.0

    @property
    def native_value(self) -> float:
        now = dt_util.utcnow()
        start = self._period.start_fn(now)

        if self._baseline_start != start or self._baseline_total is None:
            self._baseline_start = start
            self._baseline_total = self._current_total()

        cur = self._current_total()
        base = self._baseline_total or 0.0
        return round(_clamp_min0(cur - base), 6)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "period_key": self._period.key,
            "period_label": self._period.label,
            "period_start_utc": self._baseline_start.isoformat() if self._baseline_start else None,
        }


# -----------------------------
# Setup
# -----------------------------
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: EnergyCoreCoordinator = hass.data[DOMAIN][entry.entry_id]

    base_entities: List[SensorEntity] = [
        EnergyCoreSensor(coordinator, d) for d in DESCRIPTIONS
    ]

    # Counters for ENERGY sensors that are totals
    counter_entities: List[SensorEntity] = []
    for d in DESCRIPTIONS:
        if d.device_class == SensorDeviceClass.ENERGY and d.state_class in (
            SensorStateClass.TOTAL,
            SensorStateClass.TOTAL_INCREASING,
        ):
            for p in PERIODS:
                counter_entities.append(EnergyCorePeriodCounterSensor(coordinator, d, p))

    async_add_entities(base_entities + counter_entities)

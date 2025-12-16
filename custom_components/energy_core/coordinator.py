from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_IMPORTED_ENTITIES,
    CONF_EXPORTED_ENTITIES,
    CONF_PRODUCED_ENTITIES,
    CONF_BATTERY_CHARGE_ENTITIES,
    CONF_BATTERY_DISCHARGE_ENTITIES,
    CONF_CO2_INTENSITY_ENTITY,
    CONF_DELTA_INTERVAL_SECONDS,
    DEFAULT_DELTA_INTERVAL_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class EnergyTotals:
    imported_kwh: float = 0.0
    exported_kwh: float = 0.0
    produced_kwh: float = 0.0
    battery_charge_kwh: float = 0.0
    battery_discharge_kwh: float = 0.0
    co2_intensity_g_per_kwh: float = 0.0


@dataclass
class EnergyDeltas:
    dA_imported_kwh: float = 0.0
    dB_exported_kwh: float = 0.0
    dC_produced_kwh: float = 0.0
    dD_charge_kwh: float = 0.0
    dE_discharge_kwh: float = 0.0
    valid: bool = True
    reason: str | None = None


class EnergyCoreCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        interval = int(entry.data.get(CONF_DELTA_INTERVAL_SECONDS, DEFAULT_DELTA_INTERVAL_SECONDS))
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )
        self.entry = entry
        self._prev_totals: EnergyTotals | None = None
        self._seq: int = 0

    def _state_to_kwh(self, entity_id: str) -> float:
        st = self.hass.states.get(entity_id)
        if st is None:
            return 0.0
        try:
            val = float(st.state)
        except (ValueError, TypeError):
            return 0.0

        unit = (st.attributes.get("unit_of_measurement") or "").lower().strip()
        if unit == "wh":
            return val / 1000.0
        # assume kWh if unknown
        return val

    def _state_to_float(self, entity_id: str) -> float:
        st = self.hass.states.get(entity_id)
        if st is None:
            return 0.0
        try:
            return float(st.state)
        except (ValueError, TypeError):
            return 0.0

    def _sum_kwh(self, entity_ids: list[str]) -> float:
        return round(sum(self._state_to_kwh(e) for e in (entity_ids or [])), 6)

    async def _async_update_data(self) -> dict[str, Any]:
        data = self.entry.data

        imported_entities = data.get(CONF_IMPORTED_ENTITIES, [])
        exported_entities = data.get(CONF_EXPORTED_ENTITIES, [])
        produced_entities = data.get(CONF_PRODUCED_ENTITIES, [])
        charge_entities = data.get(CONF_BATTERY_CHARGE_ENTITIES, [])
        discharge_entities = data.get(CONF_BATTERY_DISCHARGE_ENTITIES, [])
        co2_entity = data.get(CONF_CO2_INTENSITY_ENTITY)

        totals = EnergyTotals(
            imported_kwh=self._sum_kwh(imported_entities),
            exported_kwh=self._sum_kwh(exported_entities),
            produced_kwh=self._sum_kwh(produced_entities),
            battery_charge_kwh=self._sum_kwh(charge_entities),
            battery_discharge_kwh=self._sum_kwh(discharge_entities),
            co2_intensity_g_per_kwh=self._state_to_float(co2_entity) if co2_entity else 0.0,
        )

        # Compute deltas
        deltas = EnergyDeltas(valid=True, reason=None)
        if self._prev_totals is None:
            # First run: don't emit deltas to avoid spikes
            deltas.valid = False
            deltas.reason = "initial"
        else:
            dA = round(totals.imported_kwh - self._prev_totals.imported_kwh, 6)
            dB = round(totals.exported_kwh - self._prev_totals.exported_kwh, 6)
            dC = round(totals.produced_kwh - self._prev_totals.produced_kwh, 6)
            dD = round(totals.battery_charge_kwh - self._prev_totals.battery_charge_kwh, 6)
            dE = round(totals.battery_discharge_kwh - self._prev_totals.battery_discharge_kwh, 6)

            # Negative delta => invalid interval (meter reset/glitch)
            if any(x < 0 for x in (dA, dB, dC, dD, dE)):
                deltas.valid = False
                deltas.reason = "negative_delta"
                dA = dB = dC = dD = dE = 0.0

            deltas.dA_imported_kwh = max(0.0, dA)
            deltas.dB_exported_kwh = max(0.0, dB)
            deltas.dC_produced_kwh = max(0.0, dC)
            deltas.dD_charge_kwh = max(0.0, dD)
            deltas.dE_discharge_kwh = max(0.0, dE)

        # Update prev totals for next tick
        self._prev_totals = totals
        self._seq += 1

        return {
            "totals": totals,
            "deltas": deltas,
            "seq": self._seq,
            "updated_at": dt_util.utcnow().isoformat(),
        }

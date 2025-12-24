from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, time
from typing import Any, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    # installer / locked data
    CONF_SITE_NAME,
    CONF_PRESENCE_MODE,
    CONF_GPS_ENTITIES,
    CONF_WIFI_ENTITIES,
    CONF_MOTION_ENTITIES,
    CONF_CALENDAR_ENTITY,
    DEFAULT_CALENDAR,
    PRESENCE_MODES,
    # options
    OPT_NOTIFICATIONS_ENABLED,
    OPT_PUSH_ENABLED,
    OPT_NOTIFICATION_LEVEL,
    OPT_PUSH_LEVEL,
    DEFAULT_NOTIFICATIONS_ENABLED,
    DEFAULT_PUSH_ENABLED,
    DEFAULT_NOTIFICATION_LEVEL,
    DEFAULT_PUSH_LEVEL,
    # KPI
    CONF_KPI_POWER_USE,
    CONF_KPI_DAY_ENERGY_USE,
    CONF_KPI_SOLAR_POWER,
    CONF_KPI_SOLAR_DAY_ENERGY,
    CONF_KPI_FORECAST_USE,
    CONF_KPI_SOLAR_FORECAST,
    CONF_KPI_PURCHASE_PRICE,
    DEFAULT_KPIS,
    # warnings keys
    WARN_PRESENCE_GAP,
    WARN_CALENDAR_GAP,
    WARN_MAIN_GAP,
)

WARNING_GAP_THRESHOLD = timedelta(hours=1)
WARNING_COOLDOWN = timedelta(hours=6)

# We treat data-gap as "warning" level.
DATA_GAP_LEVEL = "warning"


@dataclass
class ManualOverride:
    active: bool = False
    until: Optional[datetime] = None
    status: Optional[str] = None  # "Home" / "Away" / "Holiday" / "Guests"


class HomieMainCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that computes Homie Main derived state + tagged warnings."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass=hass,
            logger=None,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=30),
        )
        self.entry = entry

        # runtime-only state
        self._manual_override = ManualOverride()
        self._last_ok: dict[str, datetime] = {
            "presence": dt_util.utcnow(),
            "calendar": dt_util.utcnow(),
            "main": dt_util.utcnow(),
        }
        self._last_warn_sent: dict[str, Optional[datetime]] = {
            WARN_PRESENCE_GAP: None,
            WARN_CALENDAR_GAP: None,
            WARN_MAIN_GAP: None,
        }

    # --------------------
    # Helpers
    # --------------------
    @property
    def site_name(self) -> str:
        return self.entry.data.get(CONF_SITE_NAME, "Home")

    def _opt(self, key: str, default: Any) -> Any:
        return self.entry.options.get(key, default)

    def _kpi_entity(self, key: str) -> str:
        return self.entry.options.get(key, DEFAULT_KPIS.get(key, ""))

    def _state(self, entity_id: str) -> Optional[str]:
        if not entity_id:
            return None
        st = self.hass.states.get(entity_id)
        return st.state if st else None

    # --------------------
    # Manual override (until 00:00 local)
    # --------------------
    def manual_override_set(self, status: str) -> None:
        """Activate manual override until next midnight (local time)."""
        now = dt_util.now()
        tomorrow = (now + timedelta(days=1)).date()
        until_local = datetime.combine(tomorrow, time(0, 0, 0), tzinfo=now.tzinfo)

        self._manual_override = ManualOverride(active=True, until=until_local, status=status)

    def manual_override_clear_if_expired(self) -> None:
        if not self._manual_override.active or not self._manual_override.until:
            return
        if dt_util.now() >= self._manual_override.until:
            self._manual_override = ManualOverride()

    def manual_override_clear(self) -> None:
        self._manual_override = ManualOverride()

    # --------------------
    # Presence compute
    # --------------------
    def _any_home(self, entity_ids: list[str]) -> Optional[bool]:
        """True if any is home/on. False if all known and not home/on. None if no entities configured."""
        if not entity_ids:
            return None

        any_known = False
        for eid in entity_ids:
            s = self._state(eid)
            if s is None:
                continue
            if s not in ("unknown", "unavailable"):
                any_known = True
            if s in ("home", "Home", "on"):
                return True

        if not any_known:
            return False
        return False

    def _presence_compute(self) -> tuple[str, str]:
        """Return (status, source). Status: Home/Away. source: GPS/WiFi/Motion/Calendar."""
        mode = self.entry.data.get(CONF_PRESENCE_MODE, "GPS")
        if mode not in PRESENCE_MODES:
            mode = "GPS"

        if mode == "GPS":
            ids = self.entry.data.get(CONF_GPS_ENTITIES, []) or []
            any_home = self._any_home(ids)
            return ("Home" if any_home else "Away", "GPS") if any_home is not None else ("Away", "GPS")

        if mode == "WiFi":
            ids = self.entry.data.get(CONF_WIFI_ENTITIES, []) or []
            any_home = self._any_home(ids)
            return ("Home" if any_home else "Away", "WiFi") if any_home is not None else ("Away", "WiFi")

        if mode == "Motion":
            ids = self.entry.data.get(CONF_MOTION_ENTITIES, []) or []
            if not ids:
                return ("Away", "Motion")
            any_on = False
            for eid in ids:
                if self._state(eid) == "on":
                    any_on = True
                    break
            return ("Home" if any_on else "Away", "Motion")

        if mode == "Calendar":
            # We still compute calendar flags below; base is Away.
            return ("Away", "Calendar")

        return ("Away", "LastKnown")

    def _calendar_status(self) -> tuple[Optional[str], bool]:
        """Return (Holiday/Guests/None, ok). Uses keywords in calendar message/summary."""
        cal = self.entry.data.get(CONF_CALENDAR_ENTITY, DEFAULT_CALENDAR)
        st = self.hass.states.get(cal) if cal else None
        if st is None or st.state in ("unknown", "unavailable"):
            return (None, False)

        msg = (st.attributes.get("message") or "").lower()
        summ = (st.attributes.get("summary") or "").lower()
        combined = f"{msg} {summ}"

        if "guests" in combined:
            return ("Guests", True)
        if "holiday" in combined:
            return ("Holiday", True)

        return (None, True)

    # --------------------
    # Health checks
    # --------------------
    def _presence_inputs_ok(self) -> bool:
        mode = self.entry.data.get(CONF_PRESENCE_MODE, "GPS")
        if mode == "GPS":
            ids = self.entry.data.get(CONF_GPS_ENTITIES, []) or []
        elif mode == "WiFi":
            ids = self.entry.data.get(CONF_WIFI_ENTITIES, []) or []
        elif mode == "Motion":
            ids = self.entry.data.get(CONF_MOTION_ENTITIES, []) or []
        else:
            ids = []

        if not ids:
            return True  # nothing configured -> don't warn

        for eid in ids:
            st = self.hass.states.get(eid)
            if st is None or st.state in ("unknown", "unavailable"):
                return False
        return True

    def _kpi_inputs_ok(self) -> bool:
        keys = [
            CONF_KPI_POWER_USE,
            CONF_KPI_DAY_ENERGY_USE,
            CONF_KPI_SOLAR_POWER,
            CONF_KPI_SOLAR_DAY_ENERGY,
            CONF_KPI_FORECAST_USE,
            CONF_KPI_SOLAR_FORECAST,
            CONF_KPI_PURCHASE_PRICE,
        ]

        any_mapped = False
        for k in keys:
            eid = self._kpi_entity(k)
            if not eid:
                continue
            any_mapped = True
            st = self.hass.states.get(eid)
            if st is None or st.state in ("unknown", "unavailable"):
                return False

        # If nothing mapped, do not create a gap warning.
        return True if any_mapped else True

    def _should_send_warning(self, warn_key: str) -> bool:
        last = self._last_warn_sent.get(warn_key)
        now = dt_util.utcnow()
        if last is None:
            return True
        return (now - last) >= WARNING_COOLDOWN

    async def _publish_homie_warning(self, warn_key: str, title: str, message: str) -> None:
        # Gate by user options
        if not self._opt(OPT_NOTIFICATIONS_ENABLED, DEFAULT_NOTIFICATIONS_ENABLED):
            return
        if not self._opt(OPT_PUSH_ENABLED, DEFAULT_PUSH_ENABLED):
            # Still publish to Homie feed + persistent by default; but you asked push toggle later.
            # We'll publish without push when push is disabled.
            push = False
        else:
            push = True

        # Level filtering (data-gaps are "warning")
        push_level = self._opt(OPT_PUSH_LEVEL, DEFAULT_PUSH_LEVEL)  # Warning/Alert/All
        if push and push_level not in ("Warning", "All"):
            push = False

        if not self._should_send_warning(warn_key):
            return

        await self.hass.services.async_call(
            DOMAIN,
            "notify",
            {
                "title": title,
                "message": message,
                "level": DATA_GAP_LEVEL,
                "source": DOMAIN,
                "push": push,
                "persistent": True,
            },
            blocking=False,
        )

        self._last_warn_sent[warn_key] = dt_util.utcnow()

    # --------------------
    # Main update loop
    # --------------------
    async def _async_update_data(self) -> dict[str, Any]:
        self.manual_override_clear_if_expired()
        now_utc = dt_util.utcnow()

        # compute base presence
        base_status, source = self._presence_compute()

        # calendar overlay (Holiday/Guests)
        cal_status, cal_ok = self._calendar_status()

        final_status = base_status
        final_source = source

        # manual override wins
        if self._manual_override.active and self._manual_override.status:
            final_status = self._manual_override.status
            final_source = "Manual"
        # then calendar overlay
        elif cal_status in ("Holiday", "Guests"):
            final_status = cal_status
            final_source = "Calendar"

        # update last ok timestamps
        presence_ok = self._presence_inputs_ok()
        if presence_ok:
            self._last_ok["presence"] = now_utc

        if cal_ok:
            self._last_ok["calendar"] = now_utc

        main_ok = self._kpi_inputs_ok()
        if main_ok:
            self._last_ok["main"] = now_utc

        # compute gaps
        gap_presence = (now_utc - self._last_ok["presence"]) > WARNING_GAP_THRESHOLD
        gap_calendar = (now_utc - self._last_ok["calendar"]) > WARNING_GAP_THRESHOLD
        gap_main = (now_utc - self._last_ok["main"]) > WARNING_GAP_THRESHOLD

        # publish warnings (tagged)
        if gap_presence:
            await self._publish_homie_warning(
                WARN_PRESENCE_GAP,
                "Presence data gap",
                "One or more presence inputs have been unavailable for > 1 hour.",
            )

        if gap_calendar:
            cal_entity = self.entry.data.get(CONF_CALENDAR_ENTITY, DEFAULT_CALENDAR)
            await self._publish_homie_warning(
                WARN_CALENDAR_GAP,
                "Calendar data gap",
                f"{cal_entity} has been unavailable for > 1 hour.",
            )

        if gap_main:
            await self._publish_homie_warning(
                WARN_MAIN_GAP,
                "Main KPI data gap",
                "One or more KPI inputs have been unavailable for > 1 hour.",
            )

        # expose computed state to sensors
        return {
            "site_name": self.site_name,
            "presence_status": final_status,
            "presence_source": final_source,
            "manual_override_active": self._manual_override.active,
            "manual_override_until": self._manual_override.until.isoformat() if self._manual_override.until else None,
            "gap_presence": gap_presence,
            "gap_calendar": gap_calendar,
            "gap_main": gap_main,
            "calendar_status": cal_status,
        }

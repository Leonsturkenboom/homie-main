# custom_components/homie_main/coordinator.py
"""Coordinator for Homie Main integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, time
from typing import Any, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, Event, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    # Configuration keys
    CONF_SITE_NAME,
    CONF_PRESENCE_MODE,
    CONF_GPS_ENTITIES,
    CONF_WIFI_ENTITIES,
    CONF_MOTION_ENTITIES,
    CONF_CALENDAR_ENTITY,
    DEFAULT_CALENDAR,
    PRESENCE_MODES,
    # Options
    OPT_NOTIFICATIONS_ENABLED,
    OPT_PUSH_ENABLED,
    OPT_EMAIL_ENABLED,
    OPT_NOTIFICATION_LEVEL,
    OPT_PUSH_LEVEL,
    DEFAULT_NOTIFICATIONS_ENABLED,
    DEFAULT_PUSH_ENABLED,
    DEFAULT_EMAIL_ENABLED,
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
    # Warnings
    WARN_PRESENCE_GAP,
    WARN_CALENDAR_GAP,
    WARN_MAIN_GAP,
    # Settings
    UPDATE_INTERVAL_SECONDS,
    DATA_GAP_THRESHOLD_HOURS,
    WARNING_COOLDOWN_HOURS,
    STORE_VERSION,
    STORE_MANUAL_OVERRIDE_KEY,
    # Level hierarchy
    LEVEL_HIERARCHY,
)

_LOGGER = logging.getLogger(__name__)

WARNING_GAP_THRESHOLD = timedelta(hours=DATA_GAP_THRESHOLD_HOURS)
WARNING_COOLDOWN = timedelta(hours=WARNING_COOLDOWN_HOURS)

# Data-gap notifications are classified as "warning" level
DATA_GAP_LEVEL = "warning"


@dataclass
class PresenceState:
    """Represents the computed presence state."""

    status: str  # "Home", "Away", "Holiday", "Guests"
    source: str  # "GPS", "WiFi", "Motion", "Calendar", "Manual"
    confidence: float  # 0.0-1.0 (reserved for future use)
    last_updated: datetime
    entities: list[str]  # Contributing entity IDs


@dataclass
class ManualOverride:
    """Represents manual override state."""

    active: bool = False
    until: Optional[datetime] = None
    status: Optional[str] = None  # "Home", "Away", "Holiday", "Guests"
    set_by: str = "user"  # "user" or "automation"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for storage."""
        return {
            "active": self.active,
            "until": self.until.isoformat() if self.until else None,
            "status": self.status,
            "set_by": self.set_by,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> ManualOverride:
        """Restore from dict."""
        until_str = data.get("until")
        until = datetime.fromisoformat(until_str) if until_str else None
        return ManualOverride(
            active=data.get("active", False),
            until=until,
            status=data.get("status"),
            set_by=data.get("set_by", "user"),
        )


@dataclass
class DataGapStatus:
    """Represents data gap detection status."""

    has_gap: bool
    gap_type: str  # "presence", "calendar", "main", "none"
    since: Optional[datetime]
    affected_entities: list[str]


class HomieMainCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that computes Homie Main derived state with data gap monitoring."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self.entry = entry

        # Runtime state
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

        # Storage for manual override persistence
        self._store: Store = Store(
            hass,
            STORE_VERSION,
            f"{STORE_MANUAL_OVERRIDE_KEY}.{entry.entry_id}",
        )

        # Event listeners (to be setup after first refresh)
        self._unsub_listeners: list = []

    async def async_setup(self) -> None:
        """Initialize the coordinator: restore state and setup listeners."""
        # Restore manual override from storage
        await self._restore_manual_override()

        # Setup event-driven listeners
        await self._setup_listeners()

        _LOGGER.info("Homie Main coordinator setup complete for %s", self.site_name)

    async def async_shutdown(self) -> None:
        """Clean shutdown: save state and remove listeners."""
        # Save manual override
        await self._save_manual_override()

        # Remove event listeners
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()

        _LOGGER.info("Homie Main coordinator shutdown complete for %s", self.site_name)

    async def _restore_manual_override(self) -> None:
        """Restore manual override from storage."""
        try:
            data = await self._store.async_load()
            if data:
                self._manual_override = ManualOverride.from_dict(data)
                _LOGGER.debug(
                    "Restored manual override: active=%s, status=%s",
                    self._manual_override.active,
                    self._manual_override.status,
                )
        except Exception as err:
            _LOGGER.warning("Failed to restore manual override: %s", err)

    async def _save_manual_override(self) -> None:
        """Save manual override to storage."""
        try:
            await self._store.async_save(self._manual_override.to_dict())
        except Exception as err:
            _LOGGER.warning("Failed to save manual override: %s", err)

    async def _setup_listeners(self) -> None:
        """Setup event listeners for presence and KPI entities."""
        # Collect all entities to monitor
        monitored_entities: set[str] = set()

        # Presence entities based on mode
        mode = self.entry.data.get(CONF_PRESENCE_MODE, "GPS")
        if mode == "GPS":
            monitored_entities.update(self.entry.data.get(CONF_GPS_ENTITIES, []))
        elif mode == "WiFi":
            monitored_entities.update(self.entry.data.get(CONF_WIFI_ENTITIES, []))
        elif mode == "Motion":
            monitored_entities.update(self.entry.data.get(CONF_MOTION_ENTITIES, []))

        # Calendar entity
        cal_entity = self.entry.data.get(CONF_CALENDAR_ENTITY, DEFAULT_CALENDAR)
        if cal_entity:
            monitored_entities.add(cal_entity)

        # KPI entities
        for key in [
            CONF_KPI_POWER_USE,
            CONF_KPI_DAY_ENERGY_USE,
            CONF_KPI_SOLAR_POWER,
            CONF_KPI_SOLAR_DAY_ENERGY,
            CONF_KPI_FORECAST_USE,
            CONF_KPI_SOLAR_FORECAST,
            CONF_KPI_PURCHASE_PRICE,
        ]:
            entity_id = self._kpi_entity(key)
            if entity_id:
                monitored_entities.add(entity_id)

        # Setup listeners
        if monitored_entities:
            _LOGGER.debug(
                "Setting up listeners for %d entities", len(monitored_entities)
            )

            @callback
            def _handle_state_change(event: Event) -> None:
                """Handle state change events."""
                entity_id = event.data.get("entity_id")
                if entity_id in monitored_entities:
                    # Trigger coordinator refresh
                    self.hass.async_create_task(self.async_request_refresh())

            unsub = async_track_state_change_event(
                self.hass, list(monitored_entities), _handle_state_change
            )
            self._unsub_listeners.append(unsub)

    # --------------------
    # Helper Properties
    # --------------------
    @property
    def site_name(self) -> str:
        """Return the configured site name."""
        return self.entry.data.get(CONF_SITE_NAME, "Home")

    def _opt(self, key: str, default: Any) -> Any:
        """Get an option value with fallback."""
        return self.entry.options.get(key, default)

    def _kpi_entity(self, key: str) -> str:
        """Get a KPI entity ID."""
        return self.entry.options.get(key, DEFAULT_KPIS.get(key, ""))

    def _state(self, entity_id: str) -> Optional[str]:
        """Get entity state safely."""
        if not entity_id:
            return None
        st = self.hass.states.get(entity_id)
        return st.state if st else None

    # --------------------
    # Manual Override Management
    # --------------------
    def manual_override_set(self, status: str) -> None:
        """Activate manual override until next midnight (local time)."""
        now = dt_util.now()
        tomorrow = (now + timedelta(days=1)).date()
        until_local = datetime.combine(tomorrow, time(0, 0, 0), tzinfo=now.tzinfo)

        self._manual_override = ManualOverride(
            active=True, until=until_local, status=status, set_by="user"
        )

        # Save to storage
        self.hass.async_create_task(self._save_manual_override())
        _LOGGER.info(
            "Manual override set to %s until %s", status, until_local.isoformat()
        )

    def manual_override_clear_if_expired(self) -> None:
        """Clear manual override if expired."""
        if not self._manual_override.active or not self._manual_override.until:
            return
        if dt_util.now() >= self._manual_override.until:
            _LOGGER.info("Manual override expired, clearing")
            self._manual_override = ManualOverride()
            self.hass.async_create_task(self._save_manual_override())

    def manual_override_clear(self) -> None:
        """Manually clear the override."""
        _LOGGER.info("Manual override cleared by user")
        self._manual_override = ManualOverride()
        self.hass.async_create_task(self._save_manual_override())

    # --------------------
    # Presence Computation
    # --------------------
    def _any_home(self, entity_ids: list[str]) -> Optional[bool]:
        """Check if any entity indicates 'home' state.

        Returns:
            True if any entity is home/on
            False if all known entities are not home
            None if no entities configured or all unavailable
        """
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

        return False if any_known else None

    def _presence_compute(self) -> tuple[str, str, list[str]]:
        """Compute presence status from configured mode.

        Returns:
            (status, source, contributing_entities)
            status: "Home" or "Away"
            source: "GPS", "WiFi", "Motion", "Calendar"
            contributing_entities: list of entity IDs used
        """
        mode = self.entry.data.get(CONF_PRESENCE_MODE, "GPS")
        if mode not in PRESENCE_MODES:
            mode = "GPS"

        if mode == "GPS":
            ids = self.entry.data.get(CONF_GPS_ENTITIES, []) or []
            any_home = self._any_home(ids)
            status = "Home" if any_home else "Away"
            return (status, "GPS", ids)

        if mode == "WiFi":
            ids = self.entry.data.get(CONF_WIFI_ENTITIES, []) or []
            any_home = self._any_home(ids)
            status = "Home" if any_home else "Away"
            return (status, "WiFi", ids)

        if mode == "Motion":
            ids = self.entry.data.get(CONF_MOTION_ENTITIES, []) or []
            if not ids:
                return ("Away", "Motion", [])
            any_on = any(self._state(eid) == "on" for eid in ids)
            status = "Home" if any_on else "Away"
            return (status, "Motion", ids)

        if mode == "Calendar":
            # Calendar mode uses calendar events as primary indicator
            return ("Away", "Calendar", [])

        return ("Away", "Unknown", [])

    def _calendar_status(self) -> tuple[Optional[str], bool]:
        """Check calendar for Holiday/Guests indicators.

        Returns:
            (status, ok)
            status: "Holiday", "Guests", or None
            ok: True if calendar is available, False otherwise
        """
        cal = self.entry.data.get(CONF_CALENDAR_ENTITY, DEFAULT_CALENDAR)
        st = self.hass.states.get(cal) if cal else None
        if st is None or st.state in ("unknown", "unavailable"):
            return (None, False)

        msg = (st.attributes.get("message") or "").lower()
        summ = (st.attributes.get("summary") or "").lower()
        combined = f"{msg} {summ}"

        if "guests" in combined or "guest" in combined:
            return ("Guests", True)
        if "holiday" in combined or "vacation" in combined:
            return ("Holiday", True)

        return (None, True)

    # --------------------
    # Health Checks
    # --------------------
    def _presence_inputs_ok(self) -> bool:
        """Check if presence inputs are available."""
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
            return True  # No entities configured -> no gap

        for eid in ids:
            st = self.hass.states.get(eid)
            if st is None or st.state in ("unknown", "unavailable"):
                return False
        return True

    def _kpi_inputs_ok(self) -> bool:
        """Check if KPI inputs are available."""
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

        # If nothing mapped, don't report gap
        return True

    def _should_send_warning(self, warn_key: str) -> bool:
        """Check if warning cooldown has elapsed."""
        last = self._last_warn_sent.get(warn_key)
        now = dt_util.utcnow()
        if last is None:
            return True
        return (now - last) >= WARNING_COOLDOWN

    def _should_send_notification(self, level: str, is_push: bool) -> bool:
        """Check if notification should be sent based on level filtering."""
        # Check if notifications are enabled
        if not self._opt(OPT_NOTIFICATIONS_ENABLED, DEFAULT_NOTIFICATIONS_ENABLED):
            return False

        # Normalize level
        level_lower = level.lower()
        level_value = LEVEL_HIERARCHY.get(level_lower, 0)

        if is_push:
            # Check push enabled
            if not self._opt(OPT_PUSH_ENABLED, DEFAULT_PUSH_ENABLED):
                return False

            # Check push level threshold
            push_level = self._opt(OPT_PUSH_LEVEL, DEFAULT_PUSH_LEVEL)
            if push_level == "All":
                return True

            threshold = LEVEL_HIERARCHY.get(push_level.lower(), 999)
            return level_value >= threshold
        else:
            # Check notification level threshold
            notif_level = self._opt(OPT_NOTIFICATION_LEVEL, DEFAULT_NOTIFICATION_LEVEL)
            if notif_level == "All":
                return True

            threshold = LEVEL_HIERARCHY.get(notif_level.lower(), 999)
            return level_value >= threshold

    async def _publish_homie_warning(
        self, warn_key: str, title: str, message: str
    ) -> None:
        """Publish a data gap warning with cooldown and level filtering."""
        if not self._should_send_warning(warn_key):
            return

        # Determine if push should be sent
        push = self._should_send_notification(DATA_GAP_LEVEL, is_push=True)

        # Determine if persistent notification should be created
        persistent = self._should_send_notification(DATA_GAP_LEVEL, is_push=False)

        if not push and not persistent:
            return

        await self.hass.services.async_call(
            DOMAIN,
            "notify",
            {
                "title": title,
                "message": message,
                "level": DATA_GAP_LEVEL,
                "source": DOMAIN,
                "entry_options": dict(self.entry.options),
                "push": push,
                "email": False,  # Email only for critical alerts
                "persistent": persistent,
            },
            blocking=False,
        )

        self._last_warn_sent[warn_key] = dt_util.utcnow()
        _LOGGER.debug("Published warning: %s", warn_key)

    # --------------------
    # Main Update Loop
    # --------------------
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch and compute all Homie Main state."""
        self.manual_override_clear_if_expired()
        now_utc = dt_util.utcnow()

        # Compute base presence
        base_status, source, contributing_entities = self._presence_compute()

        # Check calendar overlay (Holiday/Guests)
        cal_status, cal_ok = self._calendar_status()

        final_status = base_status
        final_source = source

        # Manual override takes priority
        if self._manual_override.active and self._manual_override.status:
            final_status = self._manual_override.status
            final_source = "Manual"
        # Then calendar overlay
        elif cal_status in ("Holiday", "Guests"):
            final_status = cal_status
            final_source = "Calendar"

        # Update last OK timestamps
        presence_ok = self._presence_inputs_ok()
        if presence_ok:
            self._last_ok["presence"] = now_utc

        if cal_ok:
            self._last_ok["calendar"] = now_utc

        main_ok = self._kpi_inputs_ok()
        if main_ok:
            self._last_ok["main"] = now_utc

        # Compute gaps
        gap_presence = (now_utc - self._last_ok["presence"]) > WARNING_GAP_THRESHOLD
        gap_calendar = (now_utc - self._last_ok["calendar"]) > WARNING_GAP_THRESHOLD
        gap_main = (now_utc - self._last_ok["main"]) > WARNING_GAP_THRESHOLD

        # Publish warnings with cooldown
        if gap_presence:
            await self._publish_homie_warning(
                WARN_PRESENCE_GAP,
                "Presence Data Gap",
                "One or more presence inputs have been unavailable for over 1 hour.",
            )

        if gap_calendar:
            cal_entity = self.entry.data.get(CONF_CALENDAR_ENTITY, DEFAULT_CALENDAR)
            await self._publish_homie_warning(
                WARN_CALENDAR_GAP,
                "Calendar Data Gap",
                f"Calendar entity {cal_entity} has been unavailable for over 1 hour.",
            )

        if gap_main:
            await self._publish_homie_warning(
                WARN_MAIN_GAP,
                "KPI Data Gap",
                "One or more KPI inputs have been unavailable for over 1 hour.",
            )

        # Return computed state for sensors
        return {
            "site_name": self.site_name,
            "presence_status": final_status,
            "presence_source": final_source,
            "presence_entities": contributing_entities,
            "manual_override_active": self._manual_override.active,
            "manual_override_until": (
                self._manual_override.until.isoformat()
                if self._manual_override.until
                else None
            ),
            "manual_override_status": self._manual_override.status,
            "gap_presence": gap_presence,
            "gap_calendar": gap_calendar,
            "gap_main": gap_main,
            "calendar_status": cal_status,
            "last_updated": now_utc.isoformat(),
        }

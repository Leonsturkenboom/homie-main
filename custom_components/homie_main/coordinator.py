# custom_components/homie_main/coordinator.py
"""DataUpdateCoordinator for Homie Main."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback, Event, State
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.event import async_track_time_change, async_track_state_change_event
from homeassistant.util import dt as dt_util
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    STATE_HOME,
    STATE_NOT_HOME,
)

from .const import (
    DOMAIN,
    PRESENCE_HOME,
    PRESENCE_AWAY,
    PRESENCE_HOLIDAY,
    PRESENCE_GUESTS,
    PRESENCE_WORK,
    SOURCE_MANUAL,
    SOURCE_LAST_KNOWN,
    SOURCE_GPS,
    SOURCE_WIFI,
    SOURCE_MOTION,
    SOURCE_GPS_WIFI,
    SOURCE_CALENDAR,
    SOURCE_SCHEDULE,
    VIS_POWER,
    VIS_DAY_ENERGY,
    VIS_DAY_PRICE,
    LEVEL_INFO,
    LEVEL_WARNING,
    LEVEL_ALERT,
    CONF_PRESENCE_DETECTION,
    CONF_USE_GPS,
    CONF_USE_WIFI,
    CONF_USE_MOTION,
    CONF_USE_CALENDAR,
    CONF_USE_SCHEDULE,
    CONF_SCHEDULE,
    CONF_LOCATION_TYPE,
    CONF_GPS_ENTITIES,
    CONF_GPS_DISTANCE,
    CONF_PING_ENTITIES,
    CONF_MOTION_ENTITIES,
    CONF_MOTION_AWAY_HOURS,
    CONF_CALENDAR_ENTITIES,
    CONF_KPI_POWER_USE,
    CONF_KPI_DAY_ENERGY_USE,
    CONF_KPI_SOLAR_POWER,
    CONF_KPI_SOLAR_DAY_ENERGY,
    CONF_KPI_PURCHASE_PRICE,
    DEFAULT_GPS_DISTANCE,
    DEFAULT_MOTION_AWAY_HOURS,
    DEFAULT_SCHEDULE,
    LOCATION_BUSINESS,
    LOCATION_HOME,
    CALENDAR_HOLIDAY_KEYWORDS,
    CALENDAR_AWAY_KEYWORDS,
    CALENDAR_GUESTS_KEYWORDS,
    OP_MODE_ACTIVE,
    OP_MODE_STANDBY,
    OP_MODE_HIBERNATION,
    WEATHER_API_URL,
    WEATHER_TIMEZONE,
    WEATHER_FORECAST_DAYS,
    WEATHER_UPDATE_INTERVAL_MINUTES,
)
from .notifications import NotificationService

_LOGGER = logging.getLogger(__name__)

# Earth radius in meters
EARTH_RADIUS_M = 6371000


@dataclass
class PresenceState:
    """Represents the current presence state."""

    status: str = PRESENCE_HOME  # "Home", "Away", "Holiday", "Guests"
    source: str = SOURCE_LAST_KNOWN  # "Calendar", "Manual", "GPS", "WiFi", "Motion", "GPS+WiFi", "LastKnown"
    last_updated: datetime = field(default_factory=dt_util.now)
    active_methods: list[str] = field(default_factory=list)  # Which methods are enabled


@dataclass
class ManualOverride:
    """Represents a manual override of presence status."""

    active: bool = False
    status: str = PRESENCE_HOME  # "Home", "Away", "Holiday", "Guests"
    previous_status: str = PRESENCE_HOME  # Status before override was set
    expires_at: datetime | None = None  # Next midnight


@dataclass
class GPSState:
    """Tracks GPS detection state."""

    home_latitude: float | None = None
    home_longitude: float | None = None
    entities_home: set[str] = field(default_factory=set)  # GPS entities currently at home
    max_distance: float = DEFAULT_GPS_DISTANCE  # meters


@dataclass
class WiFiState:
    """Tracks WiFi detection state (via ping binary_sensors)."""

    entities_home: set[str] = field(default_factory=set)  # Ping entities currently responding


@dataclass
class MotionState:
    """Tracks Motion detection state."""

    entities_active: set[str] = field(default_factory=set)  # Motion sensors currently detecting motion
    last_motion: datetime | None = None  # Last time motion was detected
    away_hours: int = DEFAULT_MOTION_AWAY_HOURS  # Hours without motion = away


@dataclass
class CalendarState:
    """Tracks Calendar detection state."""

    current_status: str | None = None  # "Holiday", "Guests", "Away" or None if no relevant event
    current_event: str | None = None  # Name of the active calendar event
    expires_at: datetime | None = None  # When the current event ends


@dataclass
class ScheduleState:
    """Tracks Schedule detection state (for business locations)."""

    enabled: bool = False  # Whether schedule detection is enabled
    schedule: dict = field(default_factory=lambda: DEFAULT_SCHEDULE.copy())
    current_status: str | None = None  # "Work" or "Away" based on schedule
    is_within_hours: bool = False  # Currently within work hours


@dataclass
class PriceSeriesState:
    """Tracks price series data for day curve visualization.

    Uses hourly purchase prices from the EP Purchase Price sensor
    (purchase_prices_today / purchase_prices_tomorrow attributes)
    to provide a rolling -12h/+12h window.
    """

    current_price: float | None = None
    last_updated: datetime | None = None
    purchase_prices_today: list[dict] = field(default_factory=list)  # [{"start": "...", "end": "...", "price": 0.25}, ...]
    purchase_prices_tomorrow: list[dict] = field(default_factory=list)


@dataclass
class WeatherForecastState:
    """Tracks weather forecast data from Open-Meteo API."""

    # Current values (latest hourly data)
    temperature: float | None = None  # °C
    wind_speed: float | None = None  # km/h
    solar_radiation: float | None = None  # W/m²

    # 7-day hourly forecast: dict of timestamp -> value
    temperature_forecast: dict[str, float] = field(default_factory=dict)
    wind_forecast: dict[str, float] = field(default_factory=dict)
    solar_forecast: dict[str, float] = field(default_factory=dict)

    # Metadata
    last_updated: datetime | None = None
    latitude: float | None = None
    longitude: float | None = None
    error: str | None = None  # Last error message if fetch failed


@dataclass
class HomieMainData:
    """Data class holding all Homie Main state."""

    presence: PresenceState
    manual_override: ManualOverride
    gps_state: GPSState
    wifi_state: WiFiState  # WiFi detection via ping binary_sensors
    motion_state: MotionState  # Motion detection
    calendar_state: CalendarState  # Calendar detection
    schedule_state: ScheduleState  # Schedule detection (business only)
    price_series_state: PriceSeriesState  # 24-hour price series for visualization
    weather_state: WeatherForecastState  # Weather forecast from Open-Meteo
    location_type: str = LOCATION_HOME  # "home" or "business"
    operating_mode: str = OP_MODE_ACTIVE  # Active, Stand-by, Hibernation
    operating_mode_override: str | None = None  # Manual operating mode override
    home_status_selection: str = PRESENCE_HOME  # Current select value
    visualization_selection: str = VIS_POWER  # W / kWh/day / €/day


class HomieMainCoordinator(DataUpdateCoordinator[HomieMainData]):
    """Coordinator for Homie Main integration."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
        )
        self.config_entry = entry
        self._config = {**entry.data, **entry.options}

        # Determine location type and active methods from config
        location_type = self._config.get(CONF_LOCATION_TYPE, LOCATION_HOME)
        active_methods: list[str] = []
        if self._config.get(CONF_PRESENCE_DETECTION, False):
            if self._config.get(CONF_USE_GPS, False):
                active_methods.append("GPS")
            if self._config.get(CONF_USE_WIFI, False):
                active_methods.append("WiFi")
            if self._config.get(CONF_USE_MOTION, False):
                active_methods.append("Motion")
            if self._config.get(CONF_USE_CALENDAR, False):
                active_methods.append("Calendar")
            if self._config.get(CONF_USE_SCHEDULE, False) and location_type == LOCATION_BUSINESS:
                active_methods.append("Schedule")

        # Determine initial status based on location type
        initial_status = PRESENCE_WORK if location_type == LOCATION_BUSINESS else PRESENCE_HOME

        # Initialize data
        self.data = HomieMainData(
            presence=PresenceState(
                status=initial_status,
                source=SOURCE_LAST_KNOWN,
                last_updated=dt_util.now(),
                active_methods=active_methods,
            ),
            manual_override=ManualOverride(),
            gps_state=GPSState(
                max_distance=self._config.get(CONF_GPS_DISTANCE, DEFAULT_GPS_DISTANCE),
            ),
            wifi_state=WiFiState(),
            motion_state=MotionState(
                away_hours=int(self._config.get(CONF_MOTION_AWAY_HOURS, DEFAULT_MOTION_AWAY_HOURS)),
            ),
            calendar_state=CalendarState(),
            schedule_state=ScheduleState(
                enabled=self._config.get(CONF_USE_SCHEDULE, False),
                schedule=self._config.get(CONF_SCHEDULE, DEFAULT_SCHEDULE),
            ),
            price_series_state=PriceSeriesState(
                date=dt_util.now().strftime("%Y-%m-%d"),
            ),
            weather_state=WeatherForecastState(),
            location_type=location_type,
            operating_mode=OP_MODE_ACTIVE,
            home_status_selection=initial_status,
            visualization_selection=VIS_POWER,
        )

        # Track listeners for cleanup
        self._unsub_midnight: callback | None = None
        self._unsub_gps_listeners: list[callback] = []
        self._unsub_wifi_listeners: list[callback] = []
        self._unsub_motion_listeners: list[callback] = []
        self._unsub_calendar_listeners: list[callback] = []
        self._unsub_schedule_timer: callback | None = None
        self._unsub_price_listener: callback | None = None
        self._unsub_weather_timer: callback | None = None

        # Initialize notification service
        self.notifications = NotificationService(hass, self._config)

    async def async_setup(self) -> None:
        """Set up the coordinator."""
        _LOGGER.info("Setting up Homie Main coordinator")

        # Schedule midnight callback
        self._unsub_midnight = async_track_time_change(
            self.hass,
            self._handle_midnight,
            hour=0,
            minute=0,
            second=0,
        )

        # Set up GPS detection if enabled
        if "GPS" in self.data.presence.active_methods:
            await self._setup_gps_detection()

        # Set up WiFi detection if enabled (uses ping binary_sensors)
        if "WiFi" in self.data.presence.active_methods:
            await self._setup_wifi_detection()

        # Set up Motion detection if enabled
        if "Motion" in self.data.presence.active_methods:
            await self._setup_motion_detection()

        # Set up Calendar detection if enabled
        if "Calendar" in self.data.presence.active_methods:
            await self._setup_calendar_detection()

        # Set up Schedule detection if enabled (business only)
        if "Schedule" in self.data.presence.active_methods:
            await self._setup_schedule_detection()

        # Set up price tracking for 24h series
        await self._setup_price_tracking()

        # Set up weather forecast tracking
        await self._setup_weather_tracking()

        _LOGGER.info(
            "Homie Main coordinator setup complete. Location type: %s, Active methods: %s",
            self.data.location_type,
            self.data.presence.active_methods,
        )

    async def _setup_gps_detection(self) -> None:
        """Set up GPS detection listeners."""
        # Get zone.home coordinates
        zone_home = self.hass.states.get("zone.home")
        if zone_home:
            self.data.gps_state.home_latitude = zone_home.attributes.get(ATTR_LATITUDE)
            self.data.gps_state.home_longitude = zone_home.attributes.get(ATTR_LONGITUDE)
            _LOGGER.info(
                "GPS detection enabled. Home location: %s, %s",
                self.data.gps_state.home_latitude,
                self.data.gps_state.home_longitude,
            )
        else:
            _LOGGER.warning("zone.home not found, GPS detection may not work correctly")

        # Get configured GPS entities
        gps_entities = self._config.get(CONF_GPS_ENTITIES, [])
        if not gps_entities:
            _LOGGER.warning("GPS detection enabled but no GPS entities configured")
            return

        _LOGGER.info("Setting up GPS listeners for: %s", gps_entities)

        # Check initial state of all GPS entities
        for entity_id in gps_entities:
            state = self.hass.states.get(entity_id)
            if state:
                self._process_gps_state(entity_id, state)

        # Set up state change listeners
        unsub = async_track_state_change_event(
            self.hass,
            gps_entities,
            self._handle_gps_state_change,
        )
        self._unsub_gps_listeners.append(unsub)

        # Recalculate after checking initial states
        self._recalculate_presence()

    @callback
    def _handle_gps_state_change(self, event: Event) -> None:
        """Handle GPS tracker state change."""
        entity_id = event.data.get("entity_id")
        new_state: State | None = event.data.get("new_state")

        if not new_state:
            return

        _LOGGER.debug("GPS state change for %s: %s", entity_id, new_state.state)
        self._process_gps_state(entity_id, new_state)
        self._recalculate_presence()
        self.async_set_updated_data(self.data)

    def _process_gps_state(self, entity_id: str, state: State) -> None:
        """Process GPS entity state and update tracking."""
        # Unavailable/unknown = can't confirm presence, treat as away
        if state.state in ("unavailable", "unknown", None):
            self.data.gps_state.entities_home.discard(entity_id)
            _LOGGER.debug("GPS %s is %s, treating as away", entity_id, state.state)
            return

        # Check if entity reports home/not_home directly
        if state.state == STATE_HOME:
            self.data.gps_state.entities_home.add(entity_id)
            _LOGGER.debug("GPS %s reports home", entity_id)
            return
        elif state.state == STATE_NOT_HOME:
            self.data.gps_state.entities_home.discard(entity_id)
            _LOGGER.debug("GPS %s reports not_home", entity_id)
            return

        # Check by GPS coordinates if available
        lat = state.attributes.get(ATTR_LATITUDE)
        lon = state.attributes.get(ATTR_LONGITUDE)

        if lat is None or lon is None:
            _LOGGER.debug("GPS %s has no coordinates", entity_id)
            return

        if self.data.gps_state.home_latitude is None or self.data.gps_state.home_longitude is None:
            _LOGGER.debug("Home coordinates not available")
            return

        # Calculate distance from home
        distance = self._calculate_distance(
            lat, lon,
            self.data.gps_state.home_latitude,
            self.data.gps_state.home_longitude,
        )

        if distance <= self.data.gps_state.max_distance:
            self.data.gps_state.entities_home.add(entity_id)
            _LOGGER.debug("GPS %s is %.0fm from home (within range)", entity_id, distance)
        else:
            self.data.gps_state.entities_home.discard(entity_id)
            _LOGGER.debug("GPS %s is %.0fm from home (out of range)", entity_id, distance)

    @staticmethod
    def _calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two GPS coordinates using Haversine formula."""
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = (
            math.sin(delta_lat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return EARTH_RADIUS_M * c

    async def _setup_wifi_detection(self) -> None:
        """Set up WiFi detection listeners (using ping binary_sensors)."""
        ping_entities = self._config.get(CONF_PING_ENTITIES, [])
        if not ping_entities:
            _LOGGER.warning("WiFi detection enabled but no ping entities configured")
            return

        _LOGGER.info("Setting up WiFi (ping) listeners for: %s", ping_entities)

        # Check initial state of all ping entities
        for entity_id in ping_entities:
            state = self.hass.states.get(entity_id)
            if state:
                self._process_wifi_state(entity_id, state)

        # Set up state change listeners
        unsub = async_track_state_change_event(
            self.hass,
            ping_entities,
            self._handle_wifi_state_change,
        )
        self._unsub_wifi_listeners.append(unsub)

        # Recalculate after checking initial states
        self._recalculate_presence()

    @callback
    def _handle_wifi_state_change(self, event: Event) -> None:
        """Handle WiFi (ping) sensor state change."""
        entity_id = event.data.get("entity_id")
        new_state: State | None = event.data.get("new_state")

        if not new_state:
            return

        _LOGGER.debug("WiFi (ping) state change for %s: %s", entity_id, new_state.state)
        self._process_wifi_state(entity_id, new_state)
        self._recalculate_presence()
        self.async_set_updated_data(self.data)

    def _process_wifi_state(self, entity_id: str, state: State) -> None:
        """Process WiFi (ping) entity state and update tracking."""
        # Ping binary_sensors: on = device responding = home, off = not responding = away
        if state.state == "on":
            self.data.wifi_state.entities_home.add(entity_id)
            _LOGGER.debug("WiFi %s is responding (home)", entity_id)
        elif state.state == "off":
            self.data.wifi_state.entities_home.discard(entity_id)
            _LOGGER.debug("WiFi %s is not responding (away)", entity_id)
        elif state.state in ("unavailable", "unknown"):
            # Unavailable/unknown - treat as away (device not reachable)
            self.data.wifi_state.entities_home.discard(entity_id)
            _LOGGER.debug("WiFi %s is %s (treating as away)", entity_id, state.state)

    async def _setup_motion_detection(self) -> None:
        """Set up Motion detection listeners."""
        motion_entities = self._config.get(CONF_MOTION_ENTITIES, [])
        if not motion_entities:
            _LOGGER.warning("Motion detection enabled but no motion entities configured")
            return

        _LOGGER.info("Setting up Motion listeners for: %s", motion_entities)

        # Check initial state of all motion entities
        for entity_id in motion_entities:
            state = self.hass.states.get(entity_id)
            if state:
                self._process_motion_state(entity_id, state)

        # Set up state change listeners
        unsub = async_track_state_change_event(
            self.hass,
            motion_entities,
            self._handle_motion_state_change,
        )
        self._unsub_motion_listeners.append(unsub)

        # Recalculate after checking initial states
        self._recalculate_presence()

    @callback
    def _handle_motion_state_change(self, event: Event) -> None:
        """Handle Motion sensor state change."""
        entity_id = event.data.get("entity_id")
        new_state: State | None = event.data.get("new_state")

        if not new_state:
            return

        _LOGGER.debug("Motion state change for %s: %s", entity_id, new_state.state)
        self._process_motion_state(entity_id, new_state)
        self._recalculate_presence()
        self.async_set_updated_data(self.data)

    def _process_motion_state(self, entity_id: str, state: State) -> None:
        """Process Motion entity state and update tracking."""
        # Motion binary_sensors: on = motion detected = someone home
        if state.state == "on":
            self.data.motion_state.entities_active.add(entity_id)
            self.data.motion_state.last_motion = dt_util.now()
            _LOGGER.debug("Motion %s detected motion (home)", entity_id)
        elif state.state == "off":
            self.data.motion_state.entities_active.discard(entity_id)
            _LOGGER.debug("Motion %s no motion", entity_id)
        elif state.state in ("unavailable", "unknown"):
            # Unavailable/unknown - ignore, don't change state
            _LOGGER.debug("Motion %s is %s, ignoring", entity_id, state.state)

    async def _setup_calendar_detection(self) -> None:
        """Set up Calendar detection listeners."""
        calendar_entities = self._config.get(CONF_CALENDAR_ENTITIES, [])
        if not calendar_entities:
            _LOGGER.warning("Calendar detection enabled but no calendar entities configured")
            return

        _LOGGER.info("Setting up Calendar listeners for: %s", calendar_entities)

        # Check initial state of all calendar entities
        for entity_id in calendar_entities:
            state = self.hass.states.get(entity_id)
            if state:
                await self._process_calendar_state(entity_id, state)

        # Set up state change listeners
        unsub = async_track_state_change_event(
            self.hass,
            calendar_entities,
            self._handle_calendar_state_change,
        )
        self._unsub_calendar_listeners.append(unsub)

        # Recalculate after checking initial states
        self._recalculate_presence()

    @callback
    def _handle_calendar_state_change(self, event: Event) -> None:
        """Handle Calendar entity state change."""
        entity_id = event.data.get("entity_id")
        new_state: State | None = event.data.get("new_state")

        if not new_state:
            return

        _LOGGER.debug("Calendar state change for %s: %s", entity_id, new_state.state)
        self.hass.async_create_task(self._process_calendar_state(entity_id, new_state))

    async def _process_calendar_state(self, entity_id: str, state: State) -> None:
        """Process Calendar entity state and update tracking."""
        # Calendar entities have state "on" when an event is active
        if state.state != "on":
            # No active event, clear calendar state if this was the source
            if self.data.calendar_state.current_event:
                _LOGGER.debug("Calendar %s: no active event", entity_id)
                self.data.calendar_state.current_status = None
                self.data.calendar_state.current_event = None
                self.data.calendar_state.expires_at = None
                self._recalculate_presence()
                self.async_set_updated_data(self.data)
            return

        # Get event details from attributes
        message = state.attributes.get("message", "").lower()
        description = state.attributes.get("description", "").lower()
        end_time = state.attributes.get("end_time")

        # Combine message and description for keyword matching
        event_text = f"{message} {description}"
        _LOGGER.debug("Calendar %s: active event '%s'", entity_id, message)

        # Check for Holiday keywords
        if any(keyword in event_text for keyword in CALENDAR_HOLIDAY_KEYWORDS):
            self.data.calendar_state.current_status = PRESENCE_HOLIDAY
            self.data.calendar_state.current_event = state.attributes.get("message", "Holiday")
            _LOGGER.info("Calendar detected Holiday: %s", self.data.calendar_state.current_event)

        # Check for Away keywords
        elif any(keyword in event_text for keyword in CALENDAR_AWAY_KEYWORDS):
            self.data.calendar_state.current_status = PRESENCE_AWAY
            self.data.calendar_state.current_event = state.attributes.get("message", "Away")
            _LOGGER.info("Calendar detected Away: %s", self.data.calendar_state.current_event)

        # Check for Guests keywords
        elif any(keyword in event_text for keyword in CALENDAR_GUESTS_KEYWORDS):
            self.data.calendar_state.current_status = PRESENCE_GUESTS
            self.data.calendar_state.current_event = state.attributes.get("message", "Guests")
            _LOGGER.info("Calendar detected Guests: %s", self.data.calendar_state.current_event)

        else:
            # No matching keywords, ignore this event
            _LOGGER.debug("Calendar %s: event '%s' has no presence keywords", entity_id, message)
            return

        # Parse end time if available
        if end_time:
            try:
                self.data.calendar_state.expires_at = dt_util.parse_datetime(end_time)
            except (ValueError, TypeError):
                self.data.calendar_state.expires_at = None

        self._recalculate_presence()
        self.async_set_updated_data(self.data)

    async def _setup_schedule_detection(self) -> None:
        """Set up Schedule detection (for business locations)."""
        _LOGGER.info("Setting up Schedule detection for business location")

        # Check initial schedule state
        self._evaluate_schedule()

        # Set up timer to check schedule every minute
        self._unsub_schedule_timer = async_track_time_change(
            self.hass,
            self._handle_schedule_check,
            second=0,  # Check every minute at :00
        )

        # Recalculate after checking initial state
        self._recalculate_presence()

    @callback
    def _handle_schedule_check(self, now: datetime) -> None:
        """Handle periodic schedule check."""
        self._evaluate_schedule()
        self._recalculate_presence()
        self.async_set_updated_data(self.data)

    def _evaluate_schedule(self) -> None:
        """Evaluate current schedule state."""
        if not self.data.schedule_state.enabled:
            return

        now = dt_util.now()
        weekday = now.strftime("%A").lower()  # monday, tuesday, etc.
        current_time = now.time()

        schedule = self.data.schedule_state.schedule
        day_schedule = schedule.get(weekday, {})

        if not day_schedule.get("enabled", False):
            # This day is not a work day
            self.data.schedule_state.is_within_hours = False
            self.data.schedule_state.current_status = PRESENCE_AWAY
            _LOGGER.debug("Schedule: %s is not a work day", weekday)
            return

        # Parse start and end times
        try:
            start_str = day_schedule.get("start", "09:00")
            end_str = day_schedule.get("end", "17:00")

            start_parts = start_str.split(":")
            end_parts = end_str.split(":")

            start_time = time(int(start_parts[0]), int(start_parts[1]))
            end_time = time(int(end_parts[0]), int(end_parts[1]))

            # Check if current time is within work hours
            if start_time <= current_time <= end_time:
                self.data.schedule_state.is_within_hours = True
                self.data.schedule_state.current_status = PRESENCE_WORK
                _LOGGER.debug(
                    "Schedule: within work hours (%s - %s)",
                    start_str, end_str
                )
            else:
                self.data.schedule_state.is_within_hours = False
                self.data.schedule_state.current_status = PRESENCE_AWAY
                _LOGGER.debug(
                    "Schedule: outside work hours (%s - %s)",
                    start_str, end_str
                )
        except (ValueError, TypeError, IndexError) as err:
            _LOGGER.error("Error parsing schedule times: %s", err)
            self.data.schedule_state.is_within_hours = False
            self.data.schedule_state.current_status = None

    async def _setup_price_tracking(self) -> None:
        """Set up price tracking for day curve visualization."""
        price_entity = self._config.get(CONF_KPI_PURCHASE_PRICE)
        if not price_entity:
            _LOGGER.debug("No purchase price sensor configured, skipping price tracking")
            return

        _LOGGER.info("Setting up price tracking for: %s", price_entity)

        # Get initial price state
        state = self.hass.states.get(price_entity)
        if state and state.state not in ("unavailable", "unknown", None):
            self._update_price_from_state(state)

        # Set up listener for price changes
        self._unsub_price_listener = async_track_state_change_event(
            self.hass,
            [price_entity],
            self._handle_price_change,
        )

    @callback
    def _handle_price_change(self, event: Event) -> None:
        """Handle price sensor state change."""
        new_state: State | None = event.data.get("new_state")
        if not new_state or new_state.state in ("unavailable", "unknown", None):
            return

        self._update_price_from_state(new_state)
        self.async_set_updated_data(self.data)

    def _update_price_from_state(self, state: State) -> None:
        """Update price series state from EP Purchase Price sensor state."""
        try:
            self.data.price_series_state.current_price = float(state.state)
        except (ValueError, TypeError):
            return

        self.data.price_series_state.last_updated = dt_util.now()

        # Read hourly price arrays from sensor attributes
        attrs = state.attributes or {}
        today = attrs.get("purchase_prices_today")
        tomorrow = attrs.get("purchase_prices_tomorrow")

        if isinstance(today, list):
            self.data.price_series_state.purchase_prices_today = today
        if isinstance(tomorrow, list):
            self.data.price_series_state.purchase_prices_tomorrow = tomorrow

    async def _setup_weather_tracking(self) -> None:
        """Set up weather forecast tracking from Open-Meteo API."""
        # Get home location from zone.home
        zone_home = self.hass.states.get("zone.home")
        if zone_home:
            self.data.weather_state.latitude = zone_home.attributes.get(ATTR_LATITUDE)
            self.data.weather_state.longitude = zone_home.attributes.get(ATTR_LONGITUDE)
            _LOGGER.info(
                "Weather tracking enabled. Location: %s, %s",
                self.data.weather_state.latitude,
                self.data.weather_state.longitude,
            )
        else:
            _LOGGER.warning("zone.home not found, weather tracking disabled")
            return

        # Fetch initial weather data
        await self._fetch_weather_forecast()

        # Set up hourly weather update
        self._unsub_weather_timer = async_track_time_change(
            self.hass,
            self._handle_weather_update,
            minute=5,  # Update at 5 minutes past each hour
            second=0,
        )

    @callback
    def _handle_weather_update(self, now: datetime) -> None:
        """Handle hourly weather update."""
        self.hass.async_create_task(self._fetch_weather_forecast())

    async def _fetch_weather_forecast(self) -> None:
        """Fetch weather forecast from Open-Meteo API."""
        lat = self.data.weather_state.latitude
        lon = self.data.weather_state.longitude

        if lat is None or lon is None:
            _LOGGER.warning("Cannot fetch weather: no location configured")
            return

        try:
            params = {
                "latitude": lat,
                "longitude": lon,
                "hourly": "temperature_2m,wind_speed_10m,direct_radiation",
                "timezone": WEATHER_TIMEZONE,
                "forecast_days": WEATHER_FORECAST_DAYS,
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(WEATHER_API_URL, params=params, timeout=30) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        _LOGGER.error("Weather API error %s: %s", response.status, error_text)
                        self.data.weather_state.error = f"API error {response.status}"
                        return

                    data = await response.json()

            # Parse hourly data
            hourly = data.get("hourly", {})
            times = hourly.get("time", [])
            temperatures = hourly.get("temperature_2m", [])
            wind_speeds = hourly.get("wind_speed_10m", [])
            solar_radiations = hourly.get("direct_radiation", [])

            # Build forecast dicts with ISO format timestamps (without seconds)
            temp_forecast = {}
            wind_forecast = {}
            solar_forecast = {}

            for i, time_str in enumerate(times):
                # Convert to ISO format without seconds: "2026-01-20T08:00"
                ts = time_str[:16] if len(time_str) >= 16 else time_str

                if i < len(temperatures) and temperatures[i] is not None:
                    temp_forecast[ts] = round(temperatures[i], 1)
                if i < len(wind_speeds) and wind_speeds[i] is not None:
                    wind_forecast[ts] = round(wind_speeds[i], 1)
                if i < len(solar_radiations) and solar_radiations[i] is not None:
                    solar_forecast[ts] = round(solar_radiations[i], 1)

            # Update state
            self.data.weather_state.temperature_forecast = temp_forecast
            self.data.weather_state.wind_forecast = wind_forecast
            self.data.weather_state.solar_forecast = solar_forecast
            self.data.weather_state.last_updated = dt_util.now()
            self.data.weather_state.error = None

            # Set current values (first entry or closest to now)
            now_str = dt_util.now().strftime("%Y-%m-%dT%H:00")
            if now_str in temp_forecast:
                self.data.weather_state.temperature = temp_forecast[now_str]
            elif temp_forecast:
                self.data.weather_state.temperature = list(temp_forecast.values())[0]

            if now_str in wind_forecast:
                self.data.weather_state.wind_speed = wind_forecast[now_str]
            elif wind_forecast:
                self.data.weather_state.wind_speed = list(wind_forecast.values())[0]

            if now_str in solar_forecast:
                self.data.weather_state.solar_radiation = solar_forecast[now_str]
            elif solar_forecast:
                self.data.weather_state.solar_radiation = list(solar_forecast.values())[0]

            _LOGGER.info(
                "Weather forecast updated: %d temperature, %d wind, %d solar entries",
                len(temp_forecast), len(wind_forecast), len(solar_forecast)
            )

            self.async_set_updated_data(self.data)

        except aiohttp.ClientError as err:
            _LOGGER.error("Weather API connection error: %s", err)
            self.data.weather_state.error = str(err)
        except Exception as err:
            _LOGGER.error("Weather fetch error: %s", err)
            self.data.weather_state.error = str(err)

    def get_kpi_value(self, sensor_key: str) -> float | None:
        """Get the current value of a KPI sensor."""
        entity_id = self._config.get(sensor_key)
        if not entity_id:
            return None

        state = self.hass.states.get(entity_id)
        if not state or state.state in ("unavailable", "unknown", None):
            return None

        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

    async def async_shutdown(self) -> None:
        """Shut down the coordinator."""
        if self._unsub_midnight:
            self._unsub_midnight()
            self._unsub_midnight = None

        if self._unsub_schedule_timer:
            self._unsub_schedule_timer()
            self._unsub_schedule_timer = None

        if self._unsub_price_listener:
            self._unsub_price_listener()
            self._unsub_price_listener = None

        if self._unsub_weather_timer:
            self._unsub_weather_timer()
            self._unsub_weather_timer = None

        for unsub in self._unsub_gps_listeners:
            unsub()
        self._unsub_gps_listeners.clear()

        for unsub in self._unsub_wifi_listeners:
            unsub()
        self._unsub_wifi_listeners.clear()

        for unsub in self._unsub_motion_listeners:
            unsub()
        self._unsub_motion_listeners.clear()

        for unsub in self._unsub_calendar_listeners:
            unsub()
        self._unsub_calendar_listeners.clear()

    @callback
    def _handle_midnight(self, now: datetime) -> None:
        """Handle midnight - allow override again."""
        _LOGGER.info("Midnight reached, override can be changed again")
        self.data.manual_override.active = False
        self.data.manual_override.expires_at = None
        self._recalculate_presence()
        self.async_set_updated_data(self.data)

    def set_home_status(self, status: str) -> None:
        """Set the home status (updates presence)."""
        previous = self.data.home_status_selection

        now = dt_util.now()
        tomorrow = now.date() + __import__("datetime").timedelta(days=1)
        midnight = dt_util.as_local(
            datetime.combine(tomorrow, time.min)
        )

        self.data.manual_override.active = True
        self.data.manual_override.status = status
        self.data.manual_override.previous_status = previous
        self.data.manual_override.expires_at = midnight
        self.data.home_status_selection = status
        _LOGGER.info("Home status set to '%s' until %s (previous: %s)", status, midnight, previous)

        self._recalculate_presence()
        self.async_set_updated_data(self.data)

    def clear_manual_override(self) -> None:
        """Clear the manual override - allow changing again."""
        self.data.manual_override.active = False
        self.data.manual_override.expires_at = None
        _LOGGER.info("Manual override cleared, can be changed again")
        self._recalculate_presence()
        self.async_set_updated_data(self.data)

    def set_visualization(self, selection: str) -> None:
        """Set the visualization mode."""
        self.data.visualization_selection = selection
        self.async_set_updated_data(self.data)

    def set_operating_mode_override(self, mode: str) -> None:
        """Set a manual operating mode override.

        Note: This will be cleared when presence status changes,
        as presence changes always override manual operating mode input.
        """
        self.data.operating_mode_override = mode
        self.data.operating_mode = mode
        _LOGGER.info("Operating mode manually set to: %s", mode)
        self.async_set_updated_data(self.data)

    def _recalculate_presence(self) -> None:
        """Recalculate presence based on all inputs.

        Priority order:
        1. Manual override (when active/locked)
        2. Detection (GPS/WiFi/Motion) - overrules schedule
        3. Calendar (Holiday/Guests/Away) - priority above schedule
        4. Schedule (Work/Away for businesses)
        5. LastKnown
        """
        now = dt_util.now()
        is_business = self.data.location_type == LOCATION_BUSINESS

        # Determine the "at location" status based on location type
        at_location_status = PRESENCE_WORK if is_business else PRESENCE_HOME

        # Priority 1: Manual override (when active/locked)
        if self.data.manual_override.active:
            self.data.presence.status = self.data.manual_override.status
            self.data.presence.source = SOURCE_MANUAL
            self.data.presence.last_updated = now
            self._update_operating_mode()
            return

        # Priority 2: Detection (GPS, WiFi, Motion) - overrules calendar and schedule
        gps_enabled = "GPS" in self.data.presence.active_methods
        wifi_enabled = "WiFi" in self.data.presence.active_methods
        motion_enabled = "Motion" in self.data.presence.active_methods

        gps_home = bool(self.data.gps_state.entities_home) if gps_enabled else False
        wifi_home = bool(self.data.wifi_state.entities_home) if wifi_enabled else False

        # Motion detection: active motion = at location, no motion for X hours = away
        motion_home = False
        motion_away = False
        if motion_enabled:
            if self.data.motion_state.entities_active:
                motion_home = True
            elif self.data.motion_state.last_motion:
                timeout = timedelta(hours=self.data.motion_state.away_hours)
                if now - self.data.motion_state.last_motion > timeout:
                    motion_away = True
                    _LOGGER.debug(
                        "Motion timeout expired: last motion %s, threshold %s hours",
                        self.data.motion_state.last_motion,
                        self.data.motion_state.away_hours,
                    )

        # Check if at least one detection method says "at location"
        if gps_home or wifi_home or motion_home:
            self.data.presence.status = at_location_status
            sources = []
            if gps_home:
                sources.append("GPS")
            if wifi_home:
                sources.append("WiFi")
            if motion_home:
                sources.append("Motion")

            if len(sources) == 1:
                if sources[0] == "GPS":
                    self.data.presence.source = SOURCE_GPS
                elif sources[0] == "WiFi":
                    self.data.presence.source = SOURCE_WIFI
                else:
                    self.data.presence.source = SOURCE_MOTION
            elif "GPS" in sources and "WiFi" in sources:
                self.data.presence.source = SOURCE_GPS_WIFI
            elif "GPS" in sources:
                self.data.presence.source = SOURCE_GPS
            elif "WiFi" in sources:
                self.data.presence.source = SOURCE_WIFI
            else:
                self.data.presence.source = SOURCE_MOTION

            self.data.presence.last_updated = now
            self.data.home_status_selection = at_location_status
            self._update_operating_mode()
            return

        # Check if detection says away
        gps_entities = self._config.get(CONF_GPS_ENTITIES, []) if gps_enabled else []
        wifi_entities = self._config.get(CONF_PING_ENTITIES, []) if wifi_enabled else []
        motion_entities = self._config.get(CONF_MOTION_ENTITIES, []) if motion_enabled else []

        gps_says_away = bool(gps_entities) and not gps_home
        wifi_says_away = bool(wifi_entities) and not wifi_home
        motion_says_away = bool(motion_entities) and motion_away

        if gps_says_away or wifi_says_away or motion_says_away:
            # Detection says away - check calendar for Holiday/Guests status
            if self.data.calendar_state.current_status in (PRESENCE_HOLIDAY, PRESENCE_GUESTS):
                self.data.presence.status = self.data.calendar_state.current_status
                self.data.presence.source = SOURCE_CALENDAR
                self.data.presence.last_updated = now
                self.data.home_status_selection = self.data.calendar_state.current_status
                _LOGGER.info(
                    "Away detected by detection, calendar sets status to: %s",
                    self.data.calendar_state.current_status,
                )
                self._update_operating_mode()
                return

            # No calendar override, just Away
            self.data.presence.status = PRESENCE_AWAY
            if gps_says_away and wifi_says_away:
                self.data.presence.source = SOURCE_GPS_WIFI
            elif gps_says_away:
                self.data.presence.source = SOURCE_GPS
            elif wifi_says_away:
                self.data.presence.source = SOURCE_WIFI
            else:
                self.data.presence.source = SOURCE_MOTION
            self.data.presence.last_updated = now
            self.data.home_status_selection = PRESENCE_AWAY
            self._update_operating_mode()
            return

        # Priority 3: Calendar (Holiday/Guests/Away) - priority above schedule
        if self.data.calendar_state.current_status:
            self.data.presence.status = self.data.calendar_state.current_status
            self.data.presence.source = SOURCE_CALENDAR
            self.data.presence.last_updated = now
            self.data.home_status_selection = self.data.calendar_state.current_status
            self._update_operating_mode()
            return

        # Priority 4: Schedule (for business locations)
        if self.data.schedule_state.enabled and self.data.schedule_state.current_status:
            self.data.presence.status = self.data.schedule_state.current_status
            self.data.presence.source = SOURCE_SCHEDULE
            self.data.presence.last_updated = now
            self.data.home_status_selection = self.data.schedule_state.current_status
            self._update_operating_mode()
            return

        # Priority 5: LastKnown - use current selection
        self.data.presence.status = self.data.home_status_selection
        self.data.presence.source = SOURCE_LAST_KNOWN
        self.data.presence.last_updated = now
        self._update_operating_mode()

    def _update_operating_mode(self) -> None:
        """Update operating mode based on current presence status.

        Operating modes:
        - Active: People are present at the location (Home/Work with active detection)
        - Stand-by: At location but no recent activity (e.g., motion timeout approaching)
        - Hibernation: Away, Holiday, or Guests (no people expected)

        Note: Manual operating mode override is cleared here, as presence
        changes always override manual operating mode input.
        """
        # Clear any manual operating mode override when presence changes
        if self.data.operating_mode_override is not None:
            _LOGGER.debug("Clearing manual operating mode override due to presence recalculation")
            self.data.operating_mode_override = None

        presence = self.data.presence.status
        is_business = self.data.location_type == LOCATION_BUSINESS

        # Hibernation: Away, Holiday, or Guests (for home locations)
        if presence in (PRESENCE_AWAY, PRESENCE_HOLIDAY):
            self.data.operating_mode = OP_MODE_HIBERNATION
            return

        # Guests at home location = people present = Active
        if presence == PRESENCE_GUESTS:
            self.data.operating_mode = OP_MODE_ACTIVE
            return

        # At location (Home or Work)
        at_location = presence in (PRESENCE_HOME, PRESENCE_WORK)

        if at_location:
            # Check if we have active detection indicating people
            source = self.data.presence.source

            # Manual, Detection sources = Active (people confirmed)
            if source in (SOURCE_MANUAL, SOURCE_GPS, SOURCE_WIFI, SOURCE_GPS_WIFI, SOURCE_MOTION):
                self.data.operating_mode = OP_MODE_ACTIVE
                return

            # Schedule says work hours but no detection = Stand-by
            if source == SOURCE_SCHEDULE:
                # During schedule, assume people are coming/present
                self.data.operating_mode = OP_MODE_STANDBY
                return

            # Calendar or LastKnown with at location status
            # Check motion state to determine activity level
            motion_enabled = "Motion" in self.data.presence.active_methods
            if motion_enabled and self.data.motion_state.last_motion:
                now = dt_util.now()
                timeout = timedelta(hours=self.data.motion_state.away_hours)
                half_timeout = timeout / 2

                time_since_motion = now - self.data.motion_state.last_motion

                if time_since_motion < half_timeout:
                    # Recent motion = Active
                    self.data.operating_mode = OP_MODE_ACTIVE
                else:
                    # No recent motion but not away yet = Stand-by
                    self.data.operating_mode = OP_MODE_STANDBY
                return

            # Default for at location without motion detection
            self.data.operating_mode = OP_MODE_ACTIVE
            return

        # Fallback
        self.data.operating_mode = OP_MODE_STANDBY

    async def _async_update_data(self) -> HomieMainData:
        """Fetch data - called by coordinator refresh."""
        return self.data

    @property
    def config(self) -> dict[str, Any]:
        """Return the current config."""
        return self._config

    async def send_notification(
        self,
        title: str,
        message: str,
        level: str = LEVEL_INFO,
        push: bool | None = None,
        email: bool | None = None,
    ) -> dict[str, Any]:
        """Send a notification via configured channels.

        Args:
            title: Notification title
            message: Notification message body
            level: Notification level (Info, Tip, Warning, Alert, Award)
            push: Override push setting (None = use config)
            email: Override email setting (None = use config)

        Returns:
            Dict with results for each channel
        """
        return await self.notifications.send_notification(
            title=title,
            message=message,
            level=level,
            push=push,
            email=email,
        )

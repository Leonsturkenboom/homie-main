# custom_components/homie_main/const.py
"""Constants for the Homie Main integration."""

from __future__ import annotations

# Domain
DOMAIN = "homie_main"
VERSION = "0.1.0"

# Platforms
PLATFORMS: list[str] = ["sensor", "select", "button", "binary_sensor", "switch"]

# =============================================================================
# CONFIG FLOW - Step 1 (General)
# =============================================================================
CONF_SITE_NAME = "site_name"
CONF_ADMIN_EMAILS = "admin_emails"
CONF_LOCATION_TYPE = "location_type"
CONF_PUSH_ENABLED = "push_enabled"  # Master switch for push notifications
CONF_PUSH_GENERAL = "push_general"
CONF_PUSH_ALERTS = "push_alerts"
CONF_PUSH_WARNINGS = "push_warnings"
CONF_MAIL_ENABLED = "mail_enabled"  # Master switch for email notifications
CONF_MAIL_WARNINGS = "mail_warnings"
CONF_MAIL_ALERTS = "mail_alerts"
CONF_PRESENCE_DETECTION = "presence_detection"

# Location types
LOCATION_HOME = "home"
LOCATION_BUSINESS = "business"
LOCATION_TYPES = [LOCATION_HOME, LOCATION_BUSINESS]

# CONFIG FLOW - Step 2 (Presence)
CONF_USE_GPS = "use_gps"
CONF_USE_WIFI = "use_wifi"
CONF_USE_MOTION = "use_motion"
CONF_USE_CALENDAR = "use_calendar"
CONF_USE_SCHEDULE = "use_schedule"  # Business only: use work schedule

# CONFIG FLOW - Step 3 (Presence follow-up)
CONF_GPS_ENTITIES = "gps_entities"
CONF_GPS_DISTANCE = "gps_distance"
CONF_PING_ENTITIES = "ping_entities"  # WiFi detection uses ping binary_sensors
CONF_MOTION_ENTITIES = "motion_entities"
CONF_MOTION_AWAY_HOURS = "motion_away_hours"  # Hours without motion = away
CONF_CALENDAR_ENTITIES = "calendar_entities"

# CONFIG FLOW - Schedule (Business only)
CONF_SCHEDULE = "schedule"  # dict with weekday schedules
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

# CONFIG FLOW - Step 4 (KPI mapping)
CONF_KPI_POWER_USE = "kpi_power_use"
CONF_KPI_DAY_ENERGY_USE = "kpi_day_energy_use"
CONF_KPI_SOLAR_POWER = "kpi_solar_power"
CONF_KPI_SOLAR_DAY_ENERGY = "kpi_solar_day_energy"
CONF_KPI_FORECAST_USE = "kpi_forecast_use"
CONF_KPI_SOLAR_FORECAST = "kpi_solar_forecast"
CONF_KPI_PURCHASE_PRICE = "kpi_purchase_price"

# =============================================================================
# OPTIONS FLOW - SMTP Settings
# =============================================================================
OPT_SMTP_HOST = "smtp_host"
OPT_SMTP_PORT = "smtp_port"
OPT_SMTP_SSL = "smtp_ssl"
OPT_SMTP_STARTTLS = "smtp_starttls"
OPT_SMTP_USERNAME = "smtp_username"
OPT_SMTP_PASSWORD = "smtp_password"
OPT_SMTP_TO = "smtp_to"

# =============================================================================
# DEFAULTS - General
# =============================================================================
DEFAULT_SITE_NAME = "Home"
DEFAULT_ADMIN_EMAILS = ""
DEFAULT_LOCATION_TYPE = LOCATION_HOME
DEFAULT_PUSH_ENABLED = True
DEFAULT_PUSH_GENERAL = True
DEFAULT_PUSH_ALERTS = True
DEFAULT_PUSH_WARNINGS = True
DEFAULT_MAIL_ENABLED = True
DEFAULT_MAIL_WARNINGS = True
DEFAULT_MAIL_ALERTS = True
DEFAULT_PRESENCE_DETECTION = True

# DEFAULTS - Presence
DEFAULT_USE_GPS = False
DEFAULT_USE_WIFI = False
DEFAULT_USE_MOTION = False
DEFAULT_USE_CALENDAR = False
DEFAULT_USE_SCHEDULE = False
DEFAULT_GPS_DISTANCE = 100  # meters
DEFAULT_MOTION_AWAY_HOURS = 4  # Hours without motion before marking as away

# DEFAULT - Schedule (business default hours)
DEFAULT_SCHEDULE = {
    "monday": {"enabled": True, "start": "09:00", "end": "17:00"},
    "tuesday": {"enabled": True, "start": "09:00", "end": "17:00"},
    "wednesday": {"enabled": True, "start": "09:00", "end": "17:00"},
    "thursday": {"enabled": True, "start": "09:00", "end": "17:00"},
    "friday": {"enabled": True, "start": "09:00", "end": "17:00"},
    "saturday": {"enabled": False, "start": "09:00", "end": "17:00"},
    "sunday": {"enabled": False, "start": "09:00", "end": "17:00"},
}

# DEFAULTS - KPI mappings
DEFAULT_KPI_POWER_USE = "sensor.ec_net_power"
DEFAULT_KPI_DAY_ENERGY_USE = "sensor.ec_net_energy_use_pday"
DEFAULT_KPI_SOLAR_POWER = "sensor.ec_production_power"
DEFAULT_KPI_SOLAR_DAY_ENERGY = "sensor.ec_produced_energy_pday"
DEFAULT_KPI_FORECAST_USE = "sensor.ef_forecast_parametersincluded"
DEFAULT_KPI_SOLAR_FORECAST = "sensor.ss_solar_production_forecast"
DEFAULT_KPI_PURCHASE_PRICE = "sensor.ep_purchase_price"

# DEFAULTS - SMTP (from PRD p.15)
DEFAULT_SMTP_HOST = "smtp.gmail.com"
DEFAULT_SMTP_PORT = 587
DEFAULT_SMTP_SSL = False  # Port 587 uses STARTTLS, not SSL
DEFAULT_SMTP_STARTTLS = True  # Required for port 587
DEFAULT_SMTP_USERNAME = "leonsturkenboom@gmail.com"
DEFAULT_SMTP_PASSWORD = "qgnd enqs idlz vcfd"
DEFAULT_SMTP_TO = ""

# =============================================================================
# PRESENCE STATES
# =============================================================================
PRESENCE_HOME = "Home"
PRESENCE_AWAY = "Away"
PRESENCE_HOLIDAY = "Holiday"
PRESENCE_GUESTS = "Guests"
PRESENCE_WORK = "Work"  # Business only

PRESENCE_STATES = [PRESENCE_HOME, PRESENCE_AWAY, PRESENCE_HOLIDAY, PRESENCE_GUESTS, PRESENCE_WORK]

# Home status options (for manual selection) - per location type
HOME_STATUS_OPTIONS = [PRESENCE_HOME, PRESENCE_AWAY, PRESENCE_HOLIDAY, PRESENCE_GUESTS]
HOME_STATUS_OPTIONS_HOME = [PRESENCE_HOME, PRESENCE_AWAY, PRESENCE_HOLIDAY, PRESENCE_GUESTS]
HOME_STATUS_OPTIONS_BUSINESS = [PRESENCE_WORK, PRESENCE_AWAY, PRESENCE_HOLIDAY]

# =============================================================================
# OPERATING MODES
# =============================================================================
OP_MODE_ACTIVE = "Active"
OP_MODE_STANDBY = "Stand-by"
OP_MODE_HIBERNATION = "Hibernation"

OPERATING_MODES = [OP_MODE_ACTIVE, OP_MODE_STANDBY, OP_MODE_HIBERNATION]

# =============================================================================
# PRESENCE SOURCES
# =============================================================================
SOURCE_CALENDAR = "Calendar"
SOURCE_MANUAL = "Manual"
SOURCE_GPS = "GPS"
SOURCE_WIFI = "WiFi"
SOURCE_MOTION = "Motion"
SOURCE_GPS_WIFI = "GPS+WiFi"
SOURCE_SCHEDULE = "Schedule"
SOURCE_LAST_KNOWN = "LastKnown"

# =============================================================================
# NOTIFICATION LEVELS
# =============================================================================
LEVEL_INFO = "Info"
LEVEL_TIP = "Tip"
LEVEL_WARNING = "Warning"
LEVEL_ALERT = "Alert"
LEVEL_AWARD = "Award"

NOTIFICATION_LEVELS = [LEVEL_INFO, LEVEL_TIP, LEVEL_WARNING, LEVEL_ALERT, LEVEL_AWARD]

# Level hierarchy for filtering (higher = more important)
LEVEL_HIERARCHY = {
    "info": 1,
    "tip": 2,
    "warning": 3,
    "alert": 4,
    "award": 5,
}

# =============================================================================
# VISUALIZATION OPTIONS
# =============================================================================
VIS_POWER = "W"
VIS_DAY_ENERGY = "kWh/day"
VIS_DAY_PRICE = "€/day"

VISUALIZATION_OPTIONS = [VIS_POWER, VIS_DAY_ENERGY, VIS_DAY_PRICE]

# =============================================================================
# CALENDAR KEYWORDS (for presence detection)
# =============================================================================
CALENDAR_HOLIDAY_KEYWORDS = ["holiday", "vakantie", "vacation"]
CALENDAR_AWAY_KEYWORDS = ["away", "afwezig", "absent"]
CALENDAR_GUESTS_KEYWORDS = ["guests", "gasten", "visitors"]

# =============================================================================
# TIMING
# =============================================================================
DATA_GAP_THRESHOLD_HOURS = 1  # Hours before data gap warning triggers
PRESENCE_UPDATE_INTERVAL_MINUTES = 15  # How often to check presence
WEATHER_UPDATE_INTERVAL_MINUTES = 60  # How often to fetch weather forecast

# =============================================================================
# WEATHER FORECAST (Open-Meteo API)
# =============================================================================
WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"
WEATHER_TIMEZONE = "Europe/Amsterdam"
WEATHER_FORECAST_DAYS = 7

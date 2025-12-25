# custom_components/homie_main/const.py
"""Constants for the Homie Main integration."""

from __future__ import annotations

# Integration metadata
DOMAIN = "homie_main"
VERSION = "0.3.0"

# Configuration keys (locked after installation, stored in entry.data)
CONF_SITE_NAME = "site_name"
CONF_PRESENCE_MODE = "presence_mode"
CONF_GPS_ENTITIES = "gps_entities"
CONF_WIFI_ENTITIES = "wifi_entities"
CONF_MOTION_ENTITIES = "motion_entities"
CONF_CALENDAR_ENTITY = "calendar_entity"

# Presence modes
PRESENCE_MODES = ["GPS", "WiFi", "Motion", "Calendar"]

# Default values for configuration
DEFAULT_CALENDAR = "calendar.homie"
DEFAULT_SITE_NAME = "Home"

# Options keys (user-configurable, stored in entry.options)
# Notification settings
OPT_NOTIFICATIONS_ENABLED = "notifications_enabled"
OPT_PUSH_ENABLED = "push_enabled"
OPT_EMAIL_ENABLED = "email_enabled"
OPT_NOTIFICATION_LEVEL = "notification_level"
OPT_PUSH_LEVEL = "push_level"
OPT_NOTIFY_TARGET_PUSH = "notify_target"

# SMTP configuration
OPT_SMTP_HOST = "smtp_host"
OPT_SMTP_PORT = "smtp_port"
OPT_SMTP_SSL = "smtp_ssl"
OPT_SMTP_STARTTLS = "smtp_starttls"
OPT_SMTP_USERNAME = "smtp_username"
OPT_SMTP_PASSWORD = "smtp_password"
OPT_SMTP_FROM = "smtp_from"
OPT_SMTP_TO_WARNINGS = "smtp_to_warnings"
OPT_SMTP_TO_ALERTS = "smtp_to_alerts"

# KPI configuration keys
CONF_KPI_POWER_USE = "kpi_power_use"
CONF_KPI_DAY_ENERGY_USE = "kpi_day_energy_use"
CONF_KPI_SOLAR_POWER = "kpi_solar_power"
CONF_KPI_SOLAR_DAY_ENERGY = "kpi_solar_day_energy"
CONF_KPI_FORECAST_USE = "kpi_forecast_use"
CONF_KPI_SOLAR_FORECAST = "kpi_solar_forecast"
CONF_KPI_PURCHASE_PRICE = "kpi_purchase_price"

# Default notification settings
DEFAULT_NOTIFICATIONS_ENABLED = True
DEFAULT_PUSH_ENABLED = True
DEFAULT_EMAIL_ENABLED = False
DEFAULT_NOTIFICATION_LEVEL = "Warning"
DEFAULT_PUSH_LEVEL = "Alert"
DEFAULT_NOTIFY_TARGET_PUSH = "notify.notify"

# Default SMTP settings
DEFAULT_SMTP_HOST = ""
DEFAULT_SMTP_PORT = 587
DEFAULT_SMTP_SSL = False
DEFAULT_SMTP_STARTTLS = True
DEFAULT_SMTP_USERNAME = ""
DEFAULT_SMTP_PASSWORD = ""
DEFAULT_SMTP_FROM = ""
DEFAULT_SMTP_TO_WARNINGS = ""
DEFAULT_SMTP_TO_ALERTS = ""

# Notification and push levels
NOTIFICATION_LEVELS = ["All", "Info", "Tip", "Warning", "Alert"]
PUSH_LEVELS = ["All", "Info", "Tip", "Warning", "Alert"]

# Level hierarchy for filtering (lower number = less important)
LEVEL_HIERARCHY = {
    "info": 0,
    "tip": 1,
    "warning": 2,
    "alert": 3,
}

# Home status options
HOME_STATUS_OPTIONS = ["Auto", "Home", "Away", "Holiday", "Guests"]
DEFAULT_HOME_STATUS = "Auto"

# Default KPI mappings (placeholder entity IDs)
DEFAULT_KPIS = {
    CONF_KPI_POWER_USE: "sensor.ec_use_power",
    CONF_KPI_DAY_ENERGY_USE: "sensor.ec_use_day_energy",
    CONF_KPI_SOLAR_POWER: "sensor.ec_solar_power",
    CONF_KPI_SOLAR_DAY_ENERGY: "sensor.ec_solar_day_energy",
    CONF_KPI_FORECAST_USE: "sensor.ec_use_day_forecast",
    CONF_KPI_SOLAR_FORECAST: "sensor.ec_solar_day_forecast",
    CONF_KPI_PURCHASE_PRICE: "sensor.ec_purchase_price",
}

# Coordinator settings
UPDATE_INTERVAL_SECONDS = 30
DATA_GAP_THRESHOLD_HOURS = 1
WARNING_COOLDOWN_HOURS = 6

# Storage keys
STORE_VERSION = 1
STORE_MANUAL_OVERRIDE_KEY = f"{DOMAIN}.manual_override"

# Entity IDs
ENTITY_ID_PREFIX = "homie_main"

# Icons
ICON_HOME = "mdi:home"
ICON_AWAY = "mdi:home-export-outline"
ICON_HOLIDAY = "mdi:beach"
ICON_GUESTS = "mdi:account-multiple"
ICON_PRESENCE = "mdi:home-account"
ICON_GPS = "mdi:map-marker"
ICON_WIFI = "mdi:wifi"
ICON_MOTION = "mdi:motion-sensor"
ICON_CALENDAR = "mdi:calendar"
ICON_MANUAL = "mdi:hand-back-right"
ICON_NOTIFICATION = "mdi:bell"
ICON_EMAIL = "mdi:email"
ICON_PUSH = "mdi:cellphone-message"
ICON_DATA_GAP = "mdi:alert-circle"
ICON_CLEAR = "mdi:close-circle"

# Notification event and service
EVENT_HOMIE_NOTIFICATION = "homie_notification"
SERVICE_NOTIFY = "notify"

# Notification store
NOTIFICATION_STORE_KEY = "homie_notification_store"
NOTIFICATION_HISTORY_SIZE = 100

# Warning keys (for cooldown tracking)
WARN_PRESENCE_GAP = "presence_data_gap"
WARN_CALENDAR_GAP = "calendar_data_gap"
WARN_MAIN_GAP = "main_kpi_data_gap"

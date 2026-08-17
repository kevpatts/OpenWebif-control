"""Constants for the OpenWebif Control integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "openwebif_control"

# Config keys
CONF_HOST = "host"
CONF_PORT = "port"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SSL = "ssl"
CONF_VERIFY_SSL = "verify_ssl"

# Options
CONF_SCAN_INTERVAL = "scan_interval"
CONF_BOUQUET = "bouquet"

DEFAULT_PORT = 80
DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True
DEFAULT_SCAN_INTERVAL = 60  # seconds

# Coordinators poll at this cadence unless overridden in options.
DEFAULT_UPDATE_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

# How far ahead (seconds) "next" EPG lookups look. Not strictly needed but documented.
PLATFORMS = ["sensor", "binary_sensor"]

# Service names
SERVICE_ZAP = "zap"
SERVICE_SEND_MESSAGE = "send_message"
SERVICE_REMOTE_CONTROL = "remote_control"
SERVICE_ADD_TIMER = "add_timer"
SERVICE_TOGGLE_STANDBY = "toggle_standby"
SERVICE_GET_EPG = "get_epg"
SERVICE_PLAY_RECORDING = "play_recording"

ATTR_BOUQUET_REFERENCE = "bouquet_reference"
ATTR_POSITION_PERCENT = "position_percent"

# Enigma2 remote key codes for numeric keys (movie playback jumps by decile).
# KEY_1..KEY_9 = codes 2..10, KEY_0 = 11.
NUMERIC_KEY_CODES = {
    1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7, 7: 8, 8: 9, 9: 10, 0: 11,
}

ATTR_SERVICE_REFERENCE = "service_reference"
ATTR_TEXT = "text"
ATTR_MESSAGE_TYPE = "message_type"
ATTR_TIMEOUT = "timeout"
ATTR_COMMAND = "command"
ATTR_EVENT_ID = "event_id"

# OpenWebif message types
MESSAGE_TYPE_MAP = {
    "yesno": 0,
    "info": 1,
    "message": 2,
    "attention": 3,
}

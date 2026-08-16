"""Sensor entities for OpenWebif Control."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import OpenWebifCoordinator
from .entity import OpenWebifEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OpenWebif sensors from a config entry."""
    coordinator: OpenWebifCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            CurrentProgrammeSensor(coordinator),
            NextProgrammeSensor(coordinator),
            TimerCountSensor(coordinator),
            RecordingCountSensor(coordinator),
            ChannelsSensor(coordinator),
        ]
    )


class CurrentProgrammeSensor(OpenWebifEntity, SensorEntity):
    """Now-playing programme title on the current channel."""

    _attr_icon = "mdi:television-classic"
    _attr_translation_key = "current_programme"

    def __init__(self, coordinator: OpenWebifCoordinator) -> None:
        super().__init__(coordinator, "current_programme")

    @property
    def native_value(self) -> str | None:
        status = self.coordinator.data.get("status", {})
        name = status.get("currservice_name")
        if not name or name == "N/A":
            return None
        return name

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        status = self.coordinator.data.get("status", {})
        return {
            "channel": status.get("currservice_station")
            or status.get("currservice_name"),
            "description": status.get("currservice_description"),
            "begin": status.get("currservice_begin"),
            "end": status.get("currservice_end"),
            "service_reference": status.get("currservice_serviceref"),
        }


class NextProgrammeSensor(OpenWebifEntity, SensorEntity):
    """The next programme on the current channel (from now/next EPG)."""

    _attr_icon = "mdi:television-guide"
    _attr_translation_key = "next_programme"

    def __init__(self, coordinator: OpenWebifCoordinator) -> None:
        super().__init__(coordinator, "next_programme")

    def _current_sref(self) -> str | None:
        status = self.coordinator.data.get("status", {})
        return status.get("currservice_serviceref")

    @property
    def native_value(self) -> str | None:
        sref = self._current_sref()
        epg = self.coordinator.data.get("epg", [])
        # epgnownext returns two entries per service; the second is "next".
        matches = [e for e in epg if e.get("sref") == sref]
        if len(matches) >= 2:
            return matches[1].get("title")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        sref = self._current_sref()
        epg = self.coordinator.data.get("epg", [])
        matches = [e for e in epg if e.get("sref") == sref]
        if len(matches) >= 2:
            nxt = matches[1]
            return {
                "description": nxt.get("shortdesc"),
                "begin_timestamp": nxt.get("begin_timestamp"),
                "duration_sec": nxt.get("duration_sec"),
            }
        return {}


class TimerCountSensor(OpenWebifEntity, SensorEntity):
    """Number of scheduled timers."""

    _attr_icon = "mdi:timer-outline"
    _attr_translation_key = "timer_count"
    _attr_native_unit_of_measurement = "timers"

    def __init__(self, coordinator: OpenWebifCoordinator) -> None:
        super().__init__(coordinator, "timer_count")

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.get("timers", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        timers = self.coordinator.data.get("timers", [])
        return {
            "timers": [
                {
                    "name": t.get("name"),
                    "service": t.get("servicename"),
                    "begin": t.get("begin"),
                    "end": t.get("end"),
                    "disabled": t.get("disabled"),
                }
                for t in timers[:50]
            ]
        }


class ChannelsSensor(OpenWebifEntity, SensorEntity):
    """Full list of real channels across all bouquets.

    State is the channel count; the ``channels`` attribute carries the list
    (name, sref, bouquet) that the Lovelace card renders as a grid. The
    ``stream_base`` and ``picon_base`` attributes let the card build URLs.
    """

    _attr_icon = "mdi:television-guide"
    _attr_translation_key = "channels"
    _attr_native_unit_of_measurement = "channels"

    def __init__(self, coordinator: OpenWebifCoordinator) -> None:
        super().__init__(coordinator, "channels")

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.get("channels", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "channels": self.coordinator.data.get("channels", []),
            "stream_base": f"http://{self.coordinator.client.host}:8001/",
            "picon_base": f"{self.coordinator.client.base_url}/picon/",
        }


class RecordingCountSensor(OpenWebifEntity, SensorEntity):
    """Number of recordings available on the receiver's storage."""

    _attr_icon = "mdi:filmstrip"
    _attr_translation_key = "recording_count"
    _attr_native_unit_of_measurement = "recordings"

    def __init__(self, coordinator: OpenWebifCoordinator) -> None:
        super().__init__(coordinator, "recording_count")

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.get("movies", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        movies = self.coordinator.data.get("movies", [])
        return {
            "recordings": [
                {
                    "name": m.get("eventname"),
                    "channel": m.get("servicename"),
                    "length": m.get("length"),
                    "begin": m.get("begintime"),
                    "size": m.get("filesize_readable"),
                    "description": m.get("description"),
                    "serviceref": m.get("serviceref"),
                }
                for m in movies[:100]
            ]
        }

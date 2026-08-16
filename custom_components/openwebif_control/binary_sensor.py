"""Binary sensors for OpenWebif Control."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import OpenWebifCoordinator
from .entity import OpenWebifEntity


def _as_bool(value) -> bool:
    """OpenWebif returns booleans as strings ('true'/'false') in some fields."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return bool(value)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OpenWebif binary sensors."""
    coordinator: OpenWebifCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            RecordingBinarySensor(coordinator),
            StandbyBinarySensor(coordinator),
        ]
    )


class RecordingBinarySensor(OpenWebifEntity, BinarySensorEntity):
    """On when the receiver is actively recording."""

    _attr_translation_key = "recording"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:record-rec"

    def __init__(self, coordinator: OpenWebifCoordinator) -> None:
        super().__init__(coordinator, "recording")

    @property
    def is_on(self) -> bool:
        return _as_bool(self.coordinator.data.get("status", {}).get("isRecording"))


class StandbyBinarySensor(OpenWebifEntity, BinarySensorEntity):
    """On when the receiver is in standby."""

    _attr_translation_key = "standby"
    _attr_icon = "mdi:power-standby"

    def __init__(self, coordinator: OpenWebifCoordinator) -> None:
        super().__init__(coordinator, "standby")

    @property
    def is_on(self) -> bool:
        return _as_bool(self.coordinator.data.get("status", {}).get("inStandby"))

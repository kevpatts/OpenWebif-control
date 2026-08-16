"""Base entity for OpenWebif Control."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OpenWebifCoordinator


class OpenWebifEntity(CoordinatorEntity[OpenWebifCoordinator]):
    """Base class wiring entities to the shared coordinator + device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: OpenWebifCoordinator, key: str) -> None:
        """Initialise the base entity."""
        super().__init__(coordinator)
        self._key = key
        entry_id = coordinator.entry.entry_id
        self._attr_unique_id = f"{entry_id}_{key}"

        about = coordinator.about or {}
        ifaces = about.get("ifaces") or []
        mac = ifaces[0].get("mac") if ifaces else None
        identifiers = {(DOMAIN, mac or entry_id)}

        self._attr_device_info = DeviceInfo(
            identifiers=identifiers,
            name=about.get("model") or "OpenWebif Receiver",
            manufacturer=about.get("brand") or "Enigma2",
            model=about.get("model"),
            sw_version=about.get("imagever"),
            configuration_url=coordinator.client.base_url,
        )

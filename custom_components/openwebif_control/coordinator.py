"""Data update coordinator for OpenWebif Control."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import OpenWebifClient, OpenWebifError
from .const import CONF_BOUQUET, DOMAIN

_LOGGER = logging.getLogger(__name__)


class OpenWebifCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate polling of the receiver.

    A single coordinator fetches status, now/next EPG, recordings and timers so
    all entities share one set of HTTP calls per interval.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: OpenWebifClient,
        about: dict[str, Any],
        update_interval: timedelta,
    ) -> None:
        """Initialise the coordinator."""
        self.client = client
        self.entry = entry
        self.about = about
        self._bouquet: str | None = entry.options.get(CONF_BOUQUET)
        # Channel list changes rarely; fetch once and cache across updates.
        self._channels: list[dict[str, Any]] | None = None
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest snapshot from the receiver."""
        try:
            status = await self.client.get_status()

            # Resolve a default bouquet on first run if the user hasn't picked one.
            if self._bouquet is None:
                bouquets = await self.client.get_bouquets()
                if bouquets:
                    self._bouquet = bouquets[0]["servicereference"]

            epg: list[dict[str, Any]] = []
            if self._bouquet:
                try:
                    epg = await self.client.get_epg_now_next(self._bouquet)
                except OpenWebifError as err:
                    _LOGGER.debug("EPG fetch failed: %s", err)

            timers = await self.client.get_timers()
            movies = await self.client.get_movies()

            # Populate the channel list once (first successful update).
            if self._channels is None:
                try:
                    self._channels = await self.client.get_all_channels()
                except OpenWebifError as err:
                    _LOGGER.debug("Channel list fetch failed: %s", err)
                    self._channels = []

            return {
                "status": status,
                "epg": epg,
                "timers": timers,
                "movies": movies,
                "channels": self._channels or [],
                "bouquet": self._bouquet,
            }
        except OpenWebifError as err:
            raise UpdateFailed(str(err)) from err

    @property
    def now_event(self) -> dict[str, Any] | None:
        """Return the 'now' EPG event for the current service, if known."""
        status = self.data.get("status", {})
        sref = status.get("currservice_serviceref") or status.get(
            "currservice_id"
        )
        name = status.get("currservice_name")
        if not name or name == "N/A":
            return None
        return {
            "title": status.get("currservice_name"),
            "description": status.get("currservice_description"),
            "begin": status.get("currservice_begin"),
            "end": status.get("currservice_end"),
            "sref": sref,
        }

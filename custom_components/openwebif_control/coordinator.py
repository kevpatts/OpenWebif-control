"""Data update coordinator for OpenWebif Control."""

from __future__ import annotations

import logging
import time
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
        self._bouquet_refs: dict[str, str] = {}
        # Slow-changing data (recordings, timers) is refreshed on a longer
        # cadence than status to keep box load low.
        self._movies: list[dict[str, Any]] = []
        self._timers: list[dict[str, Any]] = []
        self._next_event: dict[str, Any] | None = None
        self._slow_last = 0.0
        self._slow_interval = 300.0  # seconds between recordings/timers refresh
        self._last_current_sref: str | None = None
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest snapshot from the receiver.

        Kept deliberately light: every poll fetches only ``statusinfo`` (small).
        The now/next programme for the *current* channel is fetched only when
        the channel changes (a tiny single-service EPG call, not a whole
        bouquet). Recordings and timers refresh on a slower cadence. The full
        channel list is fetched once. This avoids hammering the receiver with
        large multi-hundred-KB bouquet EPG requests every interval.
        """
        try:
            status = await self.client.get_status()
            now = time.monotonic()

            # Channel list + bouquet refs: fetch once.
            if self._channels is None:
                try:
                    self._channels, self._bouquet_refs = (
                        await self.client.get_all_channels()
                    )
                except OpenWebifError as err:
                    _LOGGER.debug("Channel list fetch failed: %s", err)
                    self._channels = []

            # Next-programme: only refetch when the tuned channel changes, and
            # only for that single service (cheap).
            current_sref = status.get("currservice_serviceref")
            if current_sref and current_sref != self._last_current_sref:
                self._last_current_sref = current_sref
                try:
                    events = await self.client.get_epg_service(current_sref)
                    # The first future event after now is "next".
                    nowts = int(time.time())
                    upcoming = [
                        e for e in events
                        if (e.get("begin_timestamp") or 0) > nowts
                    ]
                    self._next_event = upcoming[0] if upcoming else None
                except OpenWebifError as err:
                    _LOGGER.debug("Next-EPG fetch failed: %s", err)
                    self._next_event = None

            # Recordings + timers: refresh on the slow cadence (or first run).
            if now - self._slow_last >= self._slow_interval or not self._slow_last:
                try:
                    self._timers = await self.client.get_timers()
                    self._movies = await self.client.get_movies()
                    self._slow_last = now
                except OpenWebifError as err:
                    _LOGGER.debug("Slow-data fetch failed: %s", err)

            return {
                "status": status,
                "next_event": self._next_event,
                "timers": self._timers,
                "movies": self._movies,
                "channels": self._channels or [],
                "bouquet_refs": self._bouquet_refs,
                "bouquet": self._bouquet,
            }
        except OpenWebifError as err:
            raise UpdateFailed(str(err)) from err

    async def async_refresh_slow(self) -> None:
        """Force recordings/timers to refresh on the next update."""
        self._slow_last = 0.0
        await self.async_request_refresh()

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

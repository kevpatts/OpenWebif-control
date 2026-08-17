"""Data update coordinator for OpenWebif Control."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
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
        # Background EPG cache: raw epgmulti events per bouquet reference, kept
        # fresh so the card reads instantly without hitting the box per action.
        self._epg_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
        self.epg_horizon_hours = 5  # how far ahead the grid data spans
        self._epg_refresh_interval = timedelta(minutes=10)
        self._epg_unsub = None
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

    # ---- Background EPG cache ----------------------------------------------

    def start_epg_refresh(self) -> None:
        """Begin the periodic background refresh of cached bouquets."""
        if self._epg_unsub is None:
            self._epg_unsub = async_track_time_interval(
                self.hass, self._async_refresh_epg_cache, self._epg_refresh_interval
            )

    def stop_epg_refresh(self) -> None:
        """Stop the periodic EPG refresh."""
        if self._epg_unsub is not None:
            self._epg_unsub()
            self._epg_unsub = None

    async def _async_refresh_epg_cache(self, _now=None) -> None:
        """Refresh every bouquet already in the cache (the ones actually used).

        Only bouquets the user has opened get refreshed, so the box is touched
        just for what's in use, once per interval.
        """
        for bref in list(self._epg_cache):
            try:
                events = await self.client.get_epg_multi(bref)
                self._epg_cache[bref] = (time.time(), events)
            except OpenWebifError as err:
                _LOGGER.debug("Background EPG refresh failed for %s: %s", bref, err)
            # Be gentle: small gap between bouquets.
            await asyncio.sleep(1.0)

    async def async_get_epg(
        self, bouquet_ref: str, hours: int | None = None
    ) -> list[dict[str, Any]]:
        """Return windowed EPG for a bouquet, fetching + caching on first use.

        Subsequent reads are served from the background-refreshed cache, so the
        card is instant and the box is not hit per interaction.
        """
        cached = self._epg_cache.get(bouquet_ref)
        # Serve from cache unless we've never fetched this bouquet. Freshness is
        # maintained by the 10-minute background refresh; a stale-but-present
        # entry is still returned immediately (and will refresh in the bg).
        if cached is None:
            events = await self.client.get_epg_multi(bouquet_ref)
            self._epg_cache[bouquet_ref] = (time.time(), events)
        else:
            events = cached[1]

        horizon_hours = hours or self.epg_horizon_hours
        now = int(time.time())
        horizon = now + horizon_hours * 3600
        trimmed: list[dict[str, Any]] = []
        for e in events:
            if e.get("title") in (None, "", "N/A"):
                continue
            begin = e.get("begin_timestamp") or 0
            dur = e.get("duration_sec") or 0
            if begin + dur < now or begin > horizon:
                continue
            trimmed.append(
                {
                    "sref": e.get("sref"),
                    "sname": e.get("sname"),
                    "title": e.get("title"),
                    "begin": begin,
                    "duration": dur,
                    "shortdesc": e.get("shortdesc"),
                    "id": e.get("id"),
                }
            )
        return trimmed

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

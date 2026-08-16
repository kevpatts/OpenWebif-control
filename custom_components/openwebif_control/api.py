"""Thin async client for the OpenWebif HTTP API.

All data the integration consumes comes through this client, which talks to the
receiver's OpenWebif interface (the same API the box's web UI uses). No SSH and
no third-party EPG source: the receiver itself is the source of truth.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import quote

import aiohttp
from aiohttp import BasicAuth, ClientTimeout

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = ClientTimeout(total=15)


class OpenWebifError(Exception):
    """Base error for OpenWebif API problems."""


class OpenWebifAuthError(OpenWebifError):
    """Raised when authentication fails."""


class OpenWebifConnectionError(OpenWebifError):
    """Raised when the box cannot be reached."""


class OpenWebifClient:
    """Minimal async wrapper around the OpenWebif JSON API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int = 80,
        username: str | None = None,
        password: str | None = None,
        use_ssl: bool = False,
        verify_ssl: bool = True,
    ) -> None:
        """Initialise the client."""
        self._session = session
        self._host = host
        self._port = port
        self._auth: BasicAuth | None = (
            BasicAuth(username, password) if username else None
        )
        scheme = "https" if use_ssl else "http"
        self._base = f"{scheme}://{host}:{port}"
        self._verify_ssl = verify_ssl

    @property
    def base_url(self) -> str:
        """Return the base URL of the receiver."""
        return self._base

    def picon_url(self, service_reference: str) -> str:
        """Return the box-served picon URL for a service reference.

        OpenWebif serves picons at /picon/<sref-with-underscores>.png where the
        trailing colon is dropped and colons become underscores.
        """
        sref = service_reference.rstrip(":").replace(":", "_")
        return f"{self._base}/picon/{sref}.png"

    def stream_url(self, service_reference: str) -> str:
        """Return the live stream URL for a service reference (port 8001)."""
        return f"http://{self._host}:8001/{service_reference}"

    async def _get(self, path: str, **params: Any) -> dict[str, Any]:
        """Perform a GET against an OpenWebif API path and return parsed JSON."""
        url = f"{self._base}/{path.lstrip('/')}"
        try:
            async with self._session.get(
                url,
                params=params or None,
                auth=self._auth,
                timeout=REQUEST_TIMEOUT,
                ssl=self._verify_ssl if self._base.startswith("https") else None,
            ) as resp:
                if resp.status in (401, 403):
                    raise OpenWebifAuthError(f"Auth failed ({resp.status})")
                resp.raise_for_status()
                return await resp.json(content_type=None)
        except OpenWebifAuthError:
            raise
        except aiohttp.ClientResponseError as err:
            raise OpenWebifConnectionError(f"HTTP {err.status} for {path}") from err
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise OpenWebifConnectionError(str(err)) from err

    # --- Discovery / health -------------------------------------------------

    async def get_about(self) -> dict[str, Any]:
        """Return /api/about (device info). Used for validation + device info."""
        data = await self._get("api/about")
        return data.get("info", data)

    async def get_status(self) -> dict[str, Any]:
        """Return /api/statusinfo (now-playing, standby, recording, volume)."""
        return await self._get("api/statusinfo")

    async def get_powerstate(self) -> dict[str, Any]:
        """Return /api/powerstate."""
        return await self._get("api/powerstate")

    # --- Channels / bouquets ------------------------------------------------

    async def get_bouquets(self) -> list[dict[str, Any]]:
        """Return the list of TV bouquets."""
        data = await self._get("api/bouquets")
        # /api/bouquets returns {"bouquets": [[ref, name], ...]}
        result = []
        for entry in data.get("bouquets", []):
            if isinstance(entry, list) and len(entry) >= 2:
                result.append({"servicereference": entry[0], "servicename": entry[1]})
            elif isinstance(entry, dict):
                result.append(entry)
        return result

    async def get_services(self, bouquet_ref: str) -> list[dict[str, Any]]:
        """Return the services (channels) within a bouquet."""
        data = await self._get("api/getservices", sRef=bouquet_ref)
        return data.get("services", [])

    # --- EPG ----------------------------------------------------------------

    async def get_epg_now_next(self, bouquet_ref: str) -> list[dict[str, Any]]:
        """Return now/next EPG for every channel in a bouquet."""
        data = await self._get("api/epgnownext", bRef=bouquet_ref)
        return data.get("events", [])

    async def get_epg_now(self, bouquet_ref: str) -> list[dict[str, Any]]:
        """Return 'now' EPG for every channel in a bouquet."""
        data = await self._get("api/epgnow", bRef=bouquet_ref)
        return data.get("events", [])

    async def get_epg_service(self, service_ref: str) -> list[dict[str, Any]]:
        """Return the full forward EPG for a single service (up to ~7 days)."""
        data = await self._get("api/epgservice", sRef=service_ref)
        return data.get("events", [])

    # --- Recordings ---------------------------------------------------------

    async def get_movies(self, directory: str | None = None) -> list[dict[str, Any]]:
        """Return the recordings list from the receiver's configured storage."""
        params: dict[str, Any] = {}
        if directory:
            params["dirname"] = directory
        data = await self._get("api/movielist", **params)
        return data.get("movies", [])

    # --- Timers -------------------------------------------------------------

    async def get_timers(self) -> list[dict[str, Any]]:
        """Return the current timer list."""
        data = await self._get("api/timerlist")
        return data.get("timers", [])

    async def add_timer_by_eventid(
        self, service_ref: str, event_id: int, justplay: int = 0
    ) -> dict[str, Any]:
        """Add a recording timer from an EPG event id."""
        return await self._get(
            "api/timeraddbyeventid",
            sRef=service_ref,
            eventid=event_id,
            justplay=justplay,
        )

    # --- Control ------------------------------------------------------------

    async def zap(self, service_ref: str) -> dict[str, Any]:
        """Zap (change) to a service reference."""
        return await self._get("api/zap", sRef=service_ref)

    async def send_message(
        self, text: str, message_type: int = 1, timeout: int = 10
    ) -> dict[str, Any]:
        """Show an on-screen message on the TV."""
        return await self._get(
            "api/message", text=text, type=message_type, timeout=timeout
        )

    async def remote_control(self, command: int) -> dict[str, Any]:
        """Send a remote-control key code to the receiver."""
        return await self._get("api/remotecontrol", command=command)

    async def set_powerstate(self, state: int) -> dict[str, Any]:
        """Set power state. 0=toggle standby, 4=toggle, 5=wakeup, etc."""
        return await self._get("api/powerstate", newstate=state)

    async def toggle_standby(self) -> dict[str, Any]:
        """Toggle standby (newstate=0)."""
        return await self.set_powerstate(0)

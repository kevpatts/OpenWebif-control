"""Services for OpenWebif Control."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .api import OpenWebifError
from .const import (
    ATTR_BOUQUET_REFERENCE,
    ATTR_COMMAND,
    ATTR_EVENT_ID,
    ATTR_MESSAGE_TYPE,
    ATTR_SERVICE_REFERENCE,
    ATTR_TEXT,
    ATTR_TIMEOUT,
    DOMAIN,
    MESSAGE_TYPE_MAP,
    SERVICE_ADD_TIMER,
    SERVICE_GET_EPG,
    SERVICE_REMOTE_CONTROL,
    SERVICE_SEND_MESSAGE,
    SERVICE_TOGGLE_STANDBY,
    SERVICE_ZAP,
)
from .coordinator import OpenWebifCoordinator

_LOGGER = logging.getLogger(__name__)

ZAP_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_SERVICE_REFERENCE): cv.string,
    }
)

MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TEXT): cv.string,
        vol.Optional(ATTR_MESSAGE_TYPE, default="info"): vol.In(
            list(MESSAGE_TYPE_MAP)
        ),
        vol.Optional(ATTR_TIMEOUT, default=10): vol.All(
            int, vol.Range(min=0, max=120)
        ),
    }
)

REMOTE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_COMMAND): vol.All(int, vol.Range(min=0, max=999)),
    }
)

TIMER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_SERVICE_REFERENCE): cv.string,
        vol.Required(ATTR_EVENT_ID): int,
    }
)

GET_EPG_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_BOUQUET_REFERENCE): cv.string,
        vol.Optional("hours", default=24): vol.All(int, vol.Range(min=1, max=168)),
    }
)


def _first_coordinator(hass: HomeAssistant) -> OpenWebifCoordinator:
    """Return the first configured coordinator (single-box common case)."""
    data = hass.data.get(DOMAIN, {})
    if not data:
        raise HomeAssistantError("OpenWebif Control is not configured")
    return next(iter(data.values()))


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register integration services (idempotent)."""
    if hass.services.has_service(DOMAIN, SERVICE_ZAP):
        return

    async def _zap(call: ServiceCall) -> None:
        coord = _first_coordinator(hass)
        try:
            await coord.client.zap(call.data[ATTR_SERVICE_REFERENCE])
        except OpenWebifError as err:
            raise HomeAssistantError(f"Zap failed: {err}") from err
        await coord.async_request_refresh()

    async def _send_message(call: ServiceCall) -> None:
        coord = _first_coordinator(hass)
        mtype = MESSAGE_TYPE_MAP[call.data[ATTR_MESSAGE_TYPE]]
        try:
            await coord.client.send_message(
                call.data[ATTR_TEXT], mtype, call.data[ATTR_TIMEOUT]
            )
        except OpenWebifError as err:
            raise HomeAssistantError(f"Send message failed: {err}") from err

    async def _remote(call: ServiceCall) -> None:
        coord = _first_coordinator(hass)
        try:
            await coord.client.remote_control(call.data[ATTR_COMMAND])
        except OpenWebifError as err:
            raise HomeAssistantError(f"Remote control failed: {err}") from err

    async def _add_timer(call: ServiceCall) -> None:
        coord = _first_coordinator(hass)
        try:
            await coord.client.add_timer_by_eventid(
                call.data[ATTR_SERVICE_REFERENCE], call.data[ATTR_EVENT_ID]
            )
        except OpenWebifError as err:
            raise HomeAssistantError(f"Add timer failed: {err}") from err
        await coord.async_request_refresh()

    async def _toggle_standby(call: ServiceCall) -> None:
        coord = _first_coordinator(hass)
        try:
            await coord.client.toggle_standby()
        except OpenWebifError as err:
            raise HomeAssistantError(f"Toggle standby failed: {err}") from err
        await coord.async_request_refresh()

    hass.services.async_register(DOMAIN, SERVICE_ZAP, _zap, schema=ZAP_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_SEND_MESSAGE, _send_message, schema=MESSAGE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REMOTE_CONTROL, _remote, schema=REMOTE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_ADD_TIMER, _add_timer, schema=TIMER_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_TOGGLE_STANDBY, _toggle_standby, schema=vol.Schema({})
    )

    async def _get_epg(call: ServiceCall) -> ServiceResponse:
        import time

        coord = _first_coordinator(hass)
        try:
            events = await coord.client.get_epg_multi(
                call.data[ATTR_BOUQUET_REFERENCE]
            )
        except OpenWebifError as err:
            raise HomeAssistantError(f"Get EPG failed: {err}") from err
        # Window the EPG: keep events overlapping [now, now + hours] so the
        # grid stays lightweight even for large 7-day bouquets.
        now = int(time.time())
        horizon = now + call.data.get("hours", 24) * 3600
        trimmed = []
        for e in events:
            if e.get("title") in (None, "", "N/A"):
                continue
            begin = e.get("begin_timestamp") or 0
            dur = e.get("duration_sec") or 0
            end = begin + dur
            if end < now or begin > horizon:
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
        return {"events": trimmed}

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_EPG,
        _get_epg,
        schema=GET_EPG_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unregister integration services."""
    for service in (
        SERVICE_ZAP,
        SERVICE_SEND_MESSAGE,
        SERVICE_REMOTE_CONTROL,
        SERVICE_ADD_TIMER,
        SERVICE_TOGGLE_STANDBY,
        SERVICE_GET_EPG,
    ):
        hass.services.async_remove(DOMAIN, service)

"""Config flow for OpenWebif Control."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    OpenWebifAuthError,
    OpenWebifClient,
    OpenWebifConnectionError,
    OpenWebifError,
)
from .const import (
    CONF_BOUQUET,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _user_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Build the user-step schema, pre-filled with defaults when reconfiguring."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
            vol.Optional(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): int,
            vol.Optional(
                CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")
            ): str,
            vol.Optional(
                CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, "")
            ): str,
            vol.Optional(CONF_SSL, default=defaults.get(CONF_SSL, DEFAULT_SSL)): bool,
            vol.Optional(
                CONF_VERIFY_SSL,
                default=defaults.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
            ): bool,
        }
    )


async def _validate(hass, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input by hitting /api/about. Returns device info."""
    session = async_get_clientsession(hass)
    client = OpenWebifClient(
        session=session,
        host=data[CONF_HOST],
        port=data.get(CONF_PORT, DEFAULT_PORT),
        username=data.get(CONF_USERNAME) or None,
        password=data.get(CONF_PASSWORD) or None,
        use_ssl=data.get(CONF_SSL, DEFAULT_SSL),
        verify_ssl=data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
    )
    return await client.get_about()


class OpenWebifConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenWebif Control."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                about = await _validate(self.hass, user_input)
            except OpenWebifAuthError:
                errors["base"] = "invalid_auth"
            except OpenWebifConnectionError:
                errors["base"] = "cannot_connect"
            except OpenWebifError:
                errors["base"] = "unknown"
            else:
                # Use the box MAC (from ifaces) as unique id when available.
                unique = None
                ifaces = about.get("ifaces") or []
                if ifaces and isinstance(ifaces, list):
                    unique = ifaces[0].get("mac")
                if unique:
                    await self.async_set_unique_id(unique)
                    self._abort_if_unique_id_configured()

                title = about.get("model") or about.get("brand") or "OpenWebif"
                return self.async_create_entry(title=str(title), data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=_user_schema(user_input), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler."""
        return OpenWebifOptionsFlow(entry)


class OpenWebifOptionsFlow(OptionsFlow):
    """Handle options: default bouquet + poll interval."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialise options flow."""
        self._entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Try to offer the list of bouquets as choices.
        bouquet_choices: dict[str, str] = {}
        try:
            session = async_get_clientsession(self.hass)
            client = OpenWebifClient(
                session=session,
                host=self._entry.data[CONF_HOST],
                port=self._entry.data.get(CONF_PORT, DEFAULT_PORT),
                username=self._entry.data.get(CONF_USERNAME) or None,
                password=self._entry.data.get(CONF_PASSWORD) or None,
                use_ssl=self._entry.data.get(CONF_SSL, DEFAULT_SSL),
                verify_ssl=self._entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
            )
            for b in await client.get_bouquets():
                bouquet_choices[b["servicereference"]] = b["servicename"]
        except OpenWebifError:
            _LOGGER.debug("Could not fetch bouquets for options flow")

        current_bouquet = self._entry.options.get(CONF_BOUQUET)
        current_scan = self._entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

        if bouquet_choices:
            bouquet_selector: Any = vol.In(bouquet_choices)
        else:
            bouquet_selector = str

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_BOUQUET,
                    default=current_bouquet
                    or next(iter(bouquet_choices), ""),
                ): bouquet_selector,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=current_scan
                ): vol.All(int, vol.Range(min=10, max=3600)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

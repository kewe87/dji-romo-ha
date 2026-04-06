"""Config flow for the DJI Romo integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .pyromo import RomoClient
from .pyromo.api import RomoAuthError, RomoConnectionError

from .const import (
    CONF_DEVICE_SN, CONF_USER_TOKEN, DOMAIN,
    OPT_POSITION_INTERVAL, OPT_MAP_INTERVAL, OPT_DOCK_INTERVAL,
    DEFAULT_POSITION_INTERVAL, DEFAULT_MAP_INTERVAL, DEFAULT_DOCK_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USER_TOKEN): str,
        vol.Required(CONF_DEVICE_SN): str,
    }
)


class DjiRomoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DJI Romo."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return DjiRomoOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            device_sn = user_input[CONF_DEVICE_SN]

            await self.async_set_unique_id(device_sn)
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            client = RomoClient(
                user_token=user_input[CONF_USER_TOKEN],
                device_sn=device_sn,
                session=session,
            )
            try:
                await client.async_get_mqtt_credentials()
            except RomoAuthError:
                errors["base"] = "invalid_auth"
            except RomoConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during validation")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"DJI Romo ({device_sn})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


POSITION_INTERVALS = {5: "5 seconds", 10: "10 seconds", 30: "30 seconds", 60: "1 minute"}
MAP_INTERVALS = {60: "1 minute", 300: "5 minutes", 900: "15 minutes", 1800: "30 minutes"}
DOCK_INTERVALS = {60: "1 minute", 300: "5 minutes", 900: "15 minutes"}


class DjiRomoOptionsFlow(OptionsFlow):
    """Handle options for DJI Romo."""

    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        opts = self._config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    OPT_POSITION_INTERVAL,
                    default=opts.get(OPT_POSITION_INTERVAL, DEFAULT_POSITION_INTERVAL),
                ): vol.In(POSITION_INTERVALS),
                vol.Optional(
                    OPT_MAP_INTERVAL,
                    default=opts.get(OPT_MAP_INTERVAL, DEFAULT_MAP_INTERVAL),
                ): vol.In(MAP_INTERVALS),
                vol.Optional(
                    OPT_DOCK_INTERVAL,
                    default=opts.get(OPT_DOCK_INTERVAL, DEFAULT_DOCK_INTERVAL),
                ): vol.In(DOCK_INTERVALS),
            }),
        )

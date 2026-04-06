"""Config flow for the DJI Romo integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .pyromo import RomoClient
from .pyromo.api import RomoAuthError, RomoConnectionError

from .const import CONF_DEVICE_SN, CONF_USER_TOKEN, DOMAIN

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

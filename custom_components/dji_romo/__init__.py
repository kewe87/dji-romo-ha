"""The DJI Romo integration.

Uses MQTT for real-time device state (device_osd ~1Hz, room_clean_progress).
Uses REST for auth (MQTT token refresh) and commands (goHome).
"""

from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later

from .pyromo import RomoClient, RomoMqttClient, RomoState
from .pyromo.api import RomoAuthError, RomoConnectionError

from .const import CONF_DEVICE_SN, CONF_USER_TOKEN, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.VACUUM, Platform.SENSOR, Platform.BINARY_SENSOR,
    Platform.BUTTON, Platform.CAMERA, Platform.SELECT,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up DJI Romo from a config entry."""
    session = async_get_clientsession(hass)
    client = RomoClient(
        user_token=entry.data[CONF_USER_TOKEN],
        device_sn=entry.data[CONF_DEVICE_SN],
        session=session,
    )

    coordinator = RomoStateCoordinator(hass, client)
    await coordinator.async_connect()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a DJI Romo config entry."""
    coordinator: RomoStateCoordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_disconnect()
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class RomoStateCoordinator:
    """Manages MQTT connection and distributes state updates to entities.

    Not a DataUpdateCoordinator because state is pushed via MQTT, not polled.
    Entities register listeners and get notified on each state change.
    """

    def __init__(self, hass: HomeAssistant, client: RomoClient) -> None:
        self.hass = hass
        self.client = client
        self._mqtt: RomoMqttClient | None = None
        self._listeners: list[callback] = []
        self._state = RomoState()
        self._last_update: datetime | None = None
        self._connected = False
        self.selected_shortcut: dict | None = None

    @property
    def data(self) -> RomoState:
        return self._state

    @property
    def last_update_time(self) -> datetime | None:
        return self._last_update

    @property
    def connected(self) -> bool:
        return self._connected

    async def async_connect(self) -> None:
        """Start the MQTT connection and fetch initial stats."""
        self._mqtt = RomoMqttClient(
            device_sn=self.client.device_sn,
            get_mqtt_creds=self.client.async_get_mqtt_credentials,
            on_state_update=self._handle_state_update,
        )
        await self._mqtt.async_connect()
        self._connected = True
        await self._fetch_stats()

    async def _fetch_stats(self) -> None:
        """Fetch cleaning statistics from REST API."""
        try:
            stats = await self.client.async_get_cleaning_stats()
            self._state.total_cleans = stats.get("total_count")
            self._state.total_area = stats.get("total_acreage")
            self._state.total_duration = stats.get("total_duration")
        except Exception:
            _LOGGER.debug("Could not fetch cleaning stats")

    async def async_disconnect(self) -> None:
        """Stop the MQTT connection."""
        if self._mqtt:
            await self._mqtt.async_disconnect()
        self._connected = False

    def _handle_state_update(self, state: RomoState) -> None:
        """Called from MQTT thread via call_soon_threadsafe."""
        self._state = state
        self._last_update = datetime.now()
        self._connected = self._mqtt.connected if self._mqtt else False
        for listener in self._listeners:
            listener()

    @callback
    def async_add_listener(self, update_callback: callback) -> callback:
        """Register a listener for state updates. Returns unsubscribe callable."""
        self._listeners.append(update_callback)

        @callback
        def remove_listener() -> None:
            self._listeners.remove(update_callback)

        return remove_listener

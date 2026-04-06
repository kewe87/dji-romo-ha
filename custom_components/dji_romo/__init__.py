"""The DJI Romo integration.

Uses MQTT for real-time device state (device_osd ~1Hz, room_clean_progress).
Uses REST for auth (MQTT token refresh) and commands (goHome).
"""

from __future__ import annotations

import logging
from datetime import datetime

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
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
    _register_services(hass)
    return True


def _register_services(hass: HomeAssistant) -> None:
    """Register custom services (only once)."""
    if hass.services.has_service(DOMAIN, "clean_rooms"):
        return

    async def handle_clean_rooms(call: ServiceCall) -> None:
        """Handle the clean_rooms service call."""
        entity_id = call.data["entity_id"]
        rooms_input = call.data["rooms"]

        # Find the coordinator for this entity
        coordinator = None
        for coord in hass.data.get(DOMAIN, {}).values():
            if isinstance(coord, RomoStateCoordinator):
                coordinator = coord
                break
        if not coordinator:
            return

        await coordinator.client.async_start_clean_rooms(rooms_input)

    hass.services.async_register(
        DOMAIN,
        "clean_rooms",
        handle_clean_rooms,
        schema=vol.Schema({
            vol.Required("entity_id"): str,
            vol.Required("rooms"): list,
        }),
    )


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
        self.device_info: dict | None = None

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
        """Start the MQTT connection and fetch initial state from REST."""
        self._mqtt = RomoMqttClient(
            device_sn=self.client.device_sn,
            get_mqtt_creds=self.client.async_get_mqtt_credentials,
            on_state_update=self._handle_state_update,
        )
        await self._mqtt.async_connect()
        self._connected = True
        await self._fetch_initial_state()

    async def _fetch_initial_state(self) -> None:
        """Fetch all available state from REST API to avoid 'unknown' entities."""
        # Properties (battery, charger, mission status, device info)
        try:
            props = await self.client.async_get_properties()
            self._state.battery = props.get("battery")
            if props.get("charger_connected") is not None:
                self._state.charger_connected = bool(props["charger_connected"])
            ti = props.get("task_info", {})
            self._state.mission_status = props.get("mission_status") or ti.get("mission_status")
            if props.get("battery_care_active") is not None:
                self._state.battery_care_active = bool(props["battery_care_active"])
            self._state.hatch_status = props.get("hatch_status")
            self._state.dust_bag_uv_enable = props.get("dust_bag_uv_enable")
            # Device info for HA device registry
            bi = props.get("device_base_info", {})
            dv = bi.get("device_version", {})
            self.device_info = {
                "name": bi.get("name", "ROMO"),
                "firmware_version": dv.get("firmware_version"),
                "dock_sn": props.get("dock_sn"),
                "device_ip": bi.get("device_ip"),
            }
        except Exception:
            _LOGGER.debug("Could not fetch properties")

        # Settings (carpet mode, AI, DND, volume, etc.)
        try:
            settings = await self.client.async_get_settings()
            self._state.carpet_mode = bool(settings.get("meet_carpet_mode"))
            ai = settings.get("ai_recognition", {})
            self._state.ai_recognition = bool(ai.get("is_open")) if isinstance(ai, dict) else None
            self._state.child_lock = bool(settings.get("is_child_lock_open"))
            nd = settings.get("no_disturb", {})
            self._state.no_disturb = bool(nd.get("is_open")) if isinstance(nd, dict) else None
            self._state.pet_care = bool(settings.get("is_pet_care"))
            self._state.stair_mode = bool(settings.get("is_no_stair_mode"))
            self._state.hot_water_mop = bool(settings.get("wash_mop_with_hot_water"))
            self._state.enhance_particle_clean = bool(settings.get("enhance_particle_clean"))
            self._state.battery_care_setting = bool(settings.get("battery_care"))
            self._state.device_volume = settings.get("device_volume")
            self._state.device_language = settings.get("device_language")
            # Extended settings
            ai = settings.get("ai_recognition", {})
            if isinstance(ai, dict):
                self._state.liquid_avoid = bool(ai.get("liquid_avoid"))
            self._state.carpet_deep_clean = bool(
                settings.get("carpet_mode_extra", {}).get("carpet_pressure_extra_clean")
            )
            dc = settings.get("dust_collect", {})
            self._state.auto_dust_collect = bool(dc.get("collect_mode")) if isinstance(dc, dict) else None
            self._state.dust_collect_mode = dc.get("collect_mode") if isinstance(dc, dict) else None
            dry = settings.get("drying", {})
            self._state.auto_dry = bool(dry.get("auto_enable")) if isinstance(dry, dict) else None
            self._state.drying_mode = dry.get("mode") if isinstance(dry, dict) else None
            add = settings.get("add_cleaner_auto", {})
            self._state.auto_add_solution = bool(add.get("is_add_in_mop")) if isinstance(add, dict) else None
            self._state.auto_wash_mop = bool(settings.get("auto_wash"))
            nd = settings.get("no_disturb", {})
            if isinstance(nd, dict):
                self._state.dnd_start_hour = nd.get("start_hour")
                self._state.dnd_start_min = nd.get("start_minute")
                self._state.dnd_end_hour = nd.get("end_hour")
                self._state.dnd_end_min = nd.get("end_minute")
            wb = settings.get("wash_back", {})
            self._state.wash_back_area = wb.get("wash_back_area") if isinstance(wb, dict) else None
        except Exception:
            _LOGGER.debug("Could not fetch settings")

        # Consumables (with pre-calculated percentages from server)
        try:
            data = await self.client.async_get_consumables()
            for item in data:
                code = item.get("code", "")
                pct = item.get("percentage")
                if pct is not None:
                    self._state.consumable_rest_pct[code] = pct
        except Exception:
            _LOGGER.debug("Could not fetch consumables")

        # Cleaning statistics
        try:
            stats = await self.client.async_get_cleaning_stats()
            self._state.total_cleans = stats.get("total_count")
            self._state.total_area = stats.get("total_acreage")
            self._state.total_duration = stats.get("total_duration")
        except Exception:
            _LOGGER.debug("Could not fetch cleaning stats")

        _LOGGER.info(
            "Initial state loaded: battery=%s, carpet=%s, volume=%s, language=%s, charger=%s",
            self._state.battery, self._state.carpet_mode,
            self._state.device_volume, self._state.device_language,
            self._state.charger_connected,
        )

        # Notify listeners
        for listener in self._listeners:
            listener()

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

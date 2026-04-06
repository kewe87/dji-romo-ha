"""MQTT client for receiving DJI Romo device state in real-time.

Subscribes to:
  forward/cr800/thing/product/{SN}/property  -> device_osd (~1Hz), device_state (on change)
  forward/cr800/thing/product/{SN}/events    -> room_clean_progress, go_home, drying, brush_clean, hms
"""

from __future__ import annotations

import asyncio
import json
import logging
import ssl
import time
from typing import Any, Callable

import paho.mqtt.client as mqtt

from .models import RomoState

_LOGGER = logging.getLogger(__name__)

MQTT_KEEPALIVE = 60
TOKEN_REFRESH_MARGIN = 300


class RomoMqttClient:
    """Async MQTT client for real-time device state."""

    def __init__(
        self,
        device_sn: str,
        get_mqtt_creds: Callable[[], Any],
        on_state_update: Callable[[RomoState], None],
    ) -> None:
        self._device_sn = device_sn
        self._get_mqtt_creds = get_mqtt_creds
        self._on_state_update = on_state_update
        self._client: mqtt.Client | None = None
        self._state = RomoState()
        self._connected = False
        self._token_expire_at: float = 0
        self._refresh_task: asyncio.Task | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._user_uuid: str = ""

    @property
    def state(self) -> RomoState:
        return self._state

    @property
    def connected(self) -> bool:
        return self._connected

    async def async_connect(self) -> None:
        self._loop = asyncio.get_running_loop()
        creds = await self._get_mqtt_creds()
        self._setup_client(creds)
        self._client.connect_async(
            creds["mqtt_domain"], creds["mqtt_port"], keepalive=MQTT_KEEPALIVE,
        )
        self._client.loop_start()
        self._token_expire_at = time.time() + creds.get("expire", 14400)
        self._refresh_task = asyncio.create_task(self._token_refresh_loop())

    async def async_disconnect(self) -> None:
        if self._refresh_task:
            self._refresh_task.cancel()
            self._refresh_task = None
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None
        self._connected = False

    def _setup_client(self, creds: dict[str, Any]) -> None:
        self._user_uuid = creds["user_uuid"]
        self._client = mqtt.Client(
            client_id=creds["client_id"],
            protocol=mqtt.MQTTv311,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        self._client.username_pw_set(creds["user_uuid"], creds["user_token"])
        self._client.tls_set(cert_reqs=ssl.CERT_NONE)
        self._client.tls_insecure_set(True)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code != 0 and str(reason_code) != "Success":
            _LOGGER.error("MQTT connect failed: %s", reason_code)
            return
        self._connected = True
        sn = self._device_sn
        client.subscribe(f"forward/cr800/thing/product/{sn}/property", 0)
        client.subscribe(f"forward/cr800/thing/product/{sn}/events", 0)
        _LOGGER.info("MQTT connected and subscribed")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties) -> None:
        self._connected = False
        _LOGGER.warning("MQTT disconnected: %s", reason_code)

    def _on_message(self, client, userdata, msg) -> None:
        try:
            payload = json.loads(msg.payload)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return

        method = payload.get("method", "")
        data = payload.get("data", {})

        handler = {
            "device_osd": self._handle_device_osd,
            "device_state": self._handle_device_state,
            "room_clean_progress": self._handle_clean_progress,
            "go_home": self._handle_go_home,
            "drying_progress": self._handle_drying,
            "brush_clean": self._handle_brush_clean,
            "hms": self._handle_hms,
        }.get(method)

        if handler:
            handler(data)
        elif method != "live_map_update":
            _LOGGER.debug("Unhandled MQTT method: %s", method)
            return

        if self._loop and self._on_state_update:
            self._loop.call_soon_threadsafe(self._on_state_update, self._state)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _handle_device_osd(self, data: dict[str, Any]) -> None:
        host = data.get("host", {})
        if not host:
            return
        self._state.battery = host.get("battery", self._state.battery)
        self._state.charger_connected = bool(host.get("charger_connected", 0))
        self._state.mission_status = host.get("mission_status", self._state.mission_status)
        self._state.battery_care_active = bool(host.get("battery_care_active", 0))
        self._state.actuator_status = host.get("actuator_status", self._state.actuator_status)
        self._state.hatch_status = host.get("hatch_status", self._state.hatch_status)
        self._state.dust_bag_uv_enable = host.get("dust_bag_uv_enable", self._state.dust_bag_uv_enable)
        map_info = host.get("map_info", {})
        if map_info:
            self._state.robot_has_map = map_info.get("robot_has_map", self._state.robot_has_map)

    def _handle_device_state(self, data: dict[str, Any]) -> None:
        host = data.get("host", {})
        if not host:
            return
        self._state.device_volume = host.get("device_volume", self._state.device_volume)
        self._state.device_language = host.get("device_language", self._state.device_language)
        self._state.battery_care_setting = bool(host.get("battery_care", 0))
        self._state.carpet_mode = bool(host.get("meet_carpet_mode", 0))
        self._state.hot_water_mop = bool(host.get("wash_mop_with_hot_water", 0))
        self._state.enhance_particle_clean = bool(host.get("enhance_particle_clean", 0))
        self._state.child_lock = bool(host.get("is_child_lock_open", 0))
        self._state.pet_care = bool(host.get("is_pet_care", 0))
        self._state.stair_mode = bool(host.get("is_no_stair_mode", 0))
        ai = host.get("ai_recognition", {})
        if ai:
            self._state.ai_recognition = bool(ai.get("is_open", 0))
        nd = host.get("no_disturb", {})
        if nd:
            self._state.no_disturb = bool(nd.get("is_open", 0))
        cons = host.get("consumables", {})
        if cons:
            self._state.dust_bag_life = cons.get("dust_bag_life", self._state.dust_bag_life)
            self._state.dust_box_filter_life = cons.get("dust_box_filter_life", self._state.dust_box_filter_life)
            self._state.mid_brush_runtime = cons.get("mid_brush_runtime", self._state.mid_brush_runtime)
            self._state.mop_runtime = cons.get("mop_runtime", self._state.mop_runtime)
            self._state.side_brush_runtime = cons.get("side_brush_runtime", self._state.side_brush_runtime)
            self._state.self_clean_count = cons.get("self_clean_cnt", self._state.self_clean_count)

    def _handle_clean_progress(self, data: dict[str, Any]) -> None:
        status = data.get("status", self._state.event_status)
        self._state.event_status = status

        if status in ("canceled", "ok", "idle"):
            self._reset_cleaning_state()
            return

        sub = data.get("sub_job_status", {})
        self._state.sub_job_name = sub.get("cur_submission", self._state.sub_job_name)
        self._state.sub_job_state = sub.get("submission_state", self._state.sub_job_state)
        progress = data.get("progress", {})
        self._state.progress_percent = progress.get("percent", self._state.progress_percent)
        duration = data.get("duration", {})
        self._state.spent_duration = duration.get("spent_duration", self._state.spent_duration)
        self._state.estimated_remaining = duration.get("estimated_remaining_duration", self._state.estimated_remaining)
        self._state.startup_type = data.get("startup_type", self._state.startup_type)
        ext = data.get("ext", {})
        plan = ext.get("plan_content", {})
        configs = plan.get("plan_area_configs", [])
        if configs:
            cfg = configs[0]
            self._state.fan_speed = cfg.get("fan_speed", self._state.fan_speed)
            self._state.clean_mode = cfg.get("clean_mode", self._state.clean_mode)
            self._state.clean_speed = cfg.get("clean_speed", self._state.clean_speed)

    def _reset_cleaning_state(self) -> None:
        """Reset all cleaning-related fields when a job ends."""
        self._state.progress_percent = None
        self._state.spent_duration = None
        self._state.estimated_remaining = None
        self._state.fan_speed = None
        self._state.clean_mode = None
        self._state.clean_speed = None
        self._state.sub_job_name = None
        self._state.sub_job_state = None
        self._state.startup_type = None
        self._state.error = None

    def _handle_go_home(self, data: dict[str, Any]) -> None:
        status = data.get("status", "")
        if status == "in_progress":
            self._state.event_status = "returning"
            self._reset_cleaning_state()
        elif status == "ok":
            self._state.event_status = "idle"
        sub = data.get("sub_job_status", {})
        self._state.sub_job_name = sub.get("cur_submission", self._state.sub_job_name)
        self._state.sub_job_state = sub.get("submission_state", self._state.sub_job_state)

    def _handle_drying(self, data: dict[str, Any]) -> None:
        status = data.get("status", "")
        if status == "in_progress":
            self._state.event_status = "drying"
        elif status in ("canceled", "ok"):
            self._state.event_status = None
            self._reset_cleaning_state()
        sub = data.get("sub_job_status", {})
        self._state.sub_job_name = sub.get("cur_submission", self._state.sub_job_name)
        self._state.sub_job_state = sub.get("submission_state", self._state.sub_job_state)

    def _handle_brush_clean(self, data: dict[str, Any]) -> None:
        status = data.get("status", "")
        if status == "in_progress":
            self._state.event_status = "in_progress"
        elif status == "paused":
            self._state.event_status = "paused"
        elif status in ("canceled", "ok"):
            self._state.event_status = None
            self._reset_cleaning_state()
        sub = data.get("sub_job_status", {})
        self._state.sub_job_name = sub.get("cur_submission", self._state.sub_job_name)
        self._state.sub_job_state = sub.get("submission_state", self._state.sub_job_state)

    def _handle_hms(self, data: dict[str, Any]) -> None:
        self._state.hms_alerts = data.get("list", [])

    # ------------------------------------------------------------------
    # Token refresh
    # ------------------------------------------------------------------

    async def _token_refresh_loop(self) -> None:
        while True:
            wait = max(60, self._token_expire_at - time.time() - TOKEN_REFRESH_MARGIN)
            await asyncio.sleep(wait)
            try:
                await self._reconnect_with_fresh_token()
            except Exception:
                _LOGGER.exception("MQTT token refresh failed, retrying in 60s")
                await asyncio.sleep(60)

    async def _reconnect_with_fresh_token(self) -> None:
        _LOGGER.info("Refreshing MQTT token")
        creds = await self._get_mqtt_creds()
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
        self._setup_client(creds)
        self._client.connect_async(
            creds["mqtt_domain"], creds["mqtt_port"], keepalive=MQTT_KEEPALIVE,
        )
        self._client.loop_start()
        self._token_expire_at = time.time() + creds.get("expire", 14400)

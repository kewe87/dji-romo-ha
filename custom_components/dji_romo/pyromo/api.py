"""REST API client for DJI Romo - auth, commands, job control.

Verified endpoints:
  GET  /app/api/v1/users/auth/token?reason=mqtt       -> MQTT credentials
  POST /cr/app/api/v1/devices/{sn}/jobs/cleans/start   -> start cleaning
  POST /cr/app/api/v1/devices/{sn}/jobs/goHomes/start  -> return to base
  POST /cr/app/api/v1/devices/{sn}/jobs/brushCleans/startWithMode -> wash mop pads
  POST /cr/app/api/v1/devices/{sn}/jobs/cleans/{uuid}/pause   -> pause cleaning
  POST /cr/app/api/v1/devices/{sn}/jobs/cleans/{uuid}/resume  -> resume cleaning
  POST /cr/app/api/v1/devices/{sn}/jobs/cleans/{uuid}/stop    -> stop cleaning
  GET  /cr/app/api/v1/devices/{sn}/jobs/cleans/job/list       -> active job list
  GET  /cr/app/api/v1/devices/{sn}/jobs/cleans/statistic      -> cleaning stats
  GET  /cr/app/api/v1/devices/{sn}/shortcuts/list              -> cleaning presets
  GET  /cr/app/api/v1/devices/{sn}/maps/list                   -> map data
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://home-api-vg.djigate.com"
DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=15)

_COMMON_HEADERS = {
    "X-DJI-locale": "en_US",
    "Content-Type": "application/json",
    "User-Agent": "DJI-Home/1.5.13",
}


class RomoAuthError(Exception):
    """Raised when the user token is invalid or expired."""


class RomoConnectionError(Exception):
    """Raised when the API is unreachable."""


class RomoClient:
    """REST client for auth and device commands."""

    def __init__(
        self,
        user_token: str,
        device_sn: str,
        session: aiohttp.ClientSession | None = None,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        self._user_token = user_token
        self._device_sn = device_sn
        self._base_url = base_url.rstrip("/")
        self._session = session
        self._owns_session = session is None

    @property
    def device_sn(self) -> str:
        return self._device_sn

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=DEFAULT_TIMEOUT)
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    def _headers(self) -> dict[str, str]:
        return {**_COMMON_HEADERS, "x-member-token": self._user_token}

    async def _post_device(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        session = await self._get_session()
        url = f"{self._base_url}/cr/app/api/v1/devices/{self._device_sn}/{path}"
        try:
            async with session.post(url, headers=self._headers(), json=body or {}) as resp:
                if resp.status == 401:
                    raise RomoAuthError("Invalid or expired user token")
                resp.raise_for_status()
                data: dict[str, Any] = await resp.json()
        except aiohttp.ClientError as exc:
            raise RomoConnectionError(f"API request failed: {exc}") from exc
        result_code = data.get("result", {}).get("code", -1)
        if result_code != 0:
            msg = data.get("result", {}).get("message", "unknown")
            _LOGGER.warning("API error %s for %s: %s", result_code, path, msg)
        return data

    async def _get_device(self, path: str) -> dict[str, Any]:
        session = await self._get_session()
        url = f"{self._base_url}/cr/app/api/v1/devices/{self._device_sn}/{path}"
        try:
            async with session.get(url, headers=self._headers()) as resp:
                if resp.status == 401:
                    raise RomoAuthError("Invalid or expired user token")
                resp.raise_for_status()
                return await resp.json()
        except aiohttp.ClientError as exc:
            raise RomoConnectionError(f"API request failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    async def async_get_mqtt_credentials(self) -> dict[str, Any]:
        """Fetch MQTT credentials. Token valid for ~4h (expire field in seconds)."""
        session = await self._get_session()
        url = f"{self._base_url}/app/api/v1/users/auth/token?reason=mqtt"
        try:
            async with session.get(url, headers=self._headers()) as resp:
                if resp.status == 401:
                    raise RomoAuthError("Invalid or expired user token")
                resp.raise_for_status()
                data = await resp.json()
        except aiohttp.ClientError as exc:
            raise RomoConnectionError(f"MQTT auth failed: {exc}") from exc
        if data.get("result", {}).get("code") != 0:
            raise RomoAuthError(f"MQTT auth error: {data.get('result', {}).get('message')}")
        return data["data"]

    async def async_validate_token(self) -> bool:
        try:
            await self.async_get_mqtt_credentials()
            return True
        except (RomoAuthError, RomoConnectionError):
            return False

    # ------------------------------------------------------------------
    # Job queries
    # ------------------------------------------------------------------

    async def async_get_active_job(self) -> dict[str, Any] | None:
        """Get the most recent active job, or None."""
        data = await self._get_device("jobs/cleans/job/list")
        jobs = data.get("data", {}).get("job_list", [])
        for job in jobs:
            if job.get("status") in ("in_progress", "paused"):
                return job
        return jobs[0] if jobs else None

    async def async_get_cleaning_stats(self) -> dict[str, Any]:
        """Get total cleaning statistics."""
        data = await self._get_device("jobs/cleans/statistic")
        return data.get("data", {})

    # ------------------------------------------------------------------
    # Map & Shortcuts
    # ------------------------------------------------------------------

    async def async_get_settings(self) -> dict[str, Any]:
        """Fetch all device settings (carpet mode, AI, DND, volume, etc.)."""
        data = await self._get_device("settings")
        return data.get("data", {})

    async def async_get_properties(self) -> dict[str, Any]:
        """Fetch device properties including robot/dock position, firmware, tank levels."""
        data = await self._get_device("things/properties")
        return data.get("data", {})

    async def async_get_consumables(self) -> list[dict[str, Any]]:
        """Fetch robot consumables with server-calculated percentages."""
        data = await self._get_device("consumables")
        return data.get("data", {}).get("list", [])

    async def async_get_dock_consumables(self) -> dict[str, Any]:
        """Fetch dock consumables (water tanks, dust bag, cleaning solution)."""
        data = await self._get_device("consumables/dock")
        return data.get("data", {})

    async def async_get_next_timer(self) -> dict[str, Any] | None:
        """Fetch next scheduled cleaning timer."""
        data = await self._get_device("timers/next?slot_id=0")
        return data.get("data")

    async def async_get_shortcuts(self) -> list[dict[str, Any]]:
        """Fetch cleaning presets (shortcuts). Each contains plan_area_configs and room_map."""
        data = await self._get_device("shortcuts/list?plan_data_version=0&slot_id=0")
        return data.get("data", {}).get("plan_list", [])

    async def async_get_maps(self) -> list[dict[str, Any]]:
        """Fetch map metadata (file_url, encryption headers, room polygons)."""
        data = await self._get_device("maps/list?map_data_version=0")
        return data.get("data", {}).get("map_list", [])

    async def async_get_map_data(self) -> dict[str, Any] | None:
        """Download and return the full map JSON from S3.

        Returns dict with keys: grid_map, seg_map, carpet_layer,
        restricted_layer, virtual_wall, obstacle_layer, pet_layer.
        seg_map.poly_info contains room polygons with vertices in meters.
        """
        maps = await self.async_get_maps()
        if not maps:
            return None
        current = next((m for m in maps if m.get("is_current")), maps[0])
        file_url = current.get("file_url")
        file_header = current.get("file_header", {})
        if not file_url:
            return None
        session = await self._get_session()
        try:
            async with session.get(file_url, headers=file_header) as resp:
                resp.raise_for_status()
                import json
                return json.loads(await resp.read())
        except aiohttp.ClientError as exc:
            _LOGGER.warning("Map download failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    async def async_start_clean(
        self,
        fan_speed: int = 2,
        clean_mode: int = 0,
        water_level: int = 2,
        clean_num: int = 1,
    ) -> None:
        """Start a cleaning job.

        Fetches current shortcuts to get room configs and map data,
        then sends the start command with the specified settings.

        Args:
            fan_speed: 1=Quiet, 2=Standard, 3=Max
            clean_mode: 0=Vacuum+Mop, 1=Vacuum then Mop, 2=Vacuum, 3=Mop
            water_level: 1-3
            clean_num: Number of passes (1-3)
        """
        shortcuts = await self.async_get_shortcuts()
        if not shortcuts:
            _LOGGER.error("No cleaning shortcuts found - cannot determine room layout")
            return

        # Use the first shortcut as template (it contains all rooms and map info)
        plan = shortcuts[0]
        plan_configs = plan.get("plan_area_configs", [])
        room_map = plan.get("room_map", {})

        if not plan_configs:
            _LOGGER.error("Shortcut has no plan_area_configs")
            return

        # Apply user-selected settings to each room config
        area_configs = []
        for cfg in plan_configs:
            area_configs.append({
                "config_uuid": str(uuid.uuid4()),
                "clean_mode": clean_mode,
                "fan_speed": fan_speed,
                "water_level": water_level,
                "clean_num": clean_num,
                "storm_mode": 0,
                "secondary_clean_num": 1,
                "clean_speed": 2,
                "order_id": cfg.get("order_id", 1),
                "poly_type": cfg.get("poly_type", 2),
                "poly_index": cfg.get("poly_index", 0),
                "poly_label": cfg.get("poly_label", 0),
                "user_label": cfg.get("user_label", 0),
                "poly_name_index": cfg.get("poly_name_index", 0),
                "skip_area": 0,
                "floor_cleaner_type": 0,
                "repeat_mop": False,
            })

        body = {
            "sn": self._device_sn,
            "job_timeout": 3600,
            "method": "room_clean",
            "data": {
                "action": "start",
                "name": "",
                "plan_name_key": "",
                "plan_uuid": str(uuid.uuid4()),
                "plan_type": 2,
                "clean_area_type": 2,
                "is_valid": True,
                "plan_area_configs": area_configs,
                "room_map": {
                    "map_index": room_map.get("map_index", 0),
                    "map_version": room_map.get("map_version", 0),
                    "file_id": room_map.get("file_id", ""),
                    "slot_id": room_map.get("slot_id", 0),
                },
                "area_config_type": 0,
            },
        }

        await self._post_device("jobs/cleans/start", body)

    async def async_start_clean_from_shortcut(
        self,
        shortcut: dict[str, Any],
        fan_speed: int | None = None,
    ) -> None:
        """Start cleaning using a shortcut (pre-configured plan from the app).

        Preserves all room configs from the shortcut, optionally overriding fan_speed.
        """
        plan_configs = shortcut.get("plan_area_configs", [])
        room_map = shortcut.get("room_map", {})

        if not plan_configs:
            _LOGGER.error("Shortcut has no plan_area_configs")
            return

        area_configs = []
        for cfg in plan_configs:
            entry = {
                "config_uuid": str(uuid.uuid4()),
                "clean_mode": cfg.get("clean_mode", 0),
                "fan_speed": fan_speed if fan_speed is not None else cfg.get("fan_speed", 2),
                "water_level": cfg.get("water_level", 2),
                "clean_num": cfg.get("clean_num", 1),
                "storm_mode": cfg.get("storm_mode", 0),
                "secondary_clean_num": cfg.get("secondary_clean_num", 1),
                "clean_speed": cfg.get("clean_speed", 2),
                "order_id": cfg.get("order_id", 1),
                "poly_type": cfg.get("poly_type", 2),
                "poly_index": cfg.get("poly_index", 0),
                "poly_label": cfg.get("poly_label", 0),
                "user_label": cfg.get("user_label", 0),
                "poly_name_index": cfg.get("poly_name_index", 0),
                "skip_area": 0,
                "floor_cleaner_type": cfg.get("floor_cleaner_type", 0),
                "repeat_mop": cfg.get("repeat_mop", False),
            }
            area_configs.append(entry)

        body = {
            "sn": self._device_sn,
            "job_timeout": 3600,
            "method": "room_clean",
            "data": {
                "action": "start",
                "name": shortcut.get("plan_name", ""),
                "plan_name_key": shortcut.get("plan_name_key", ""),
                "plan_uuid": shortcut.get("plan_uuid", str(uuid.uuid4())),
                "plan_type": shortcut.get("plan_type", 2),
                "clean_area_type": shortcut.get("clean_area_type", 2),
                "is_valid": True,
                "plan_area_configs": area_configs,
                "room_map": {
                    "map_index": room_map.get("map_index", 0),
                    "map_version": room_map.get("map_version", 0),
                    "file_id": room_map.get("file_id", ""),
                    "slot_id": room_map.get("slot_id", 0),
                },
                "area_config_type": shortcut.get("area_config_type", 0),
            },
        }

        await self._post_device("jobs/cleans/start", body)

    async def async_return_to_base(self) -> None:
        """Verified: POST .../jobs/goHomes/start"""
        await self._post_device("jobs/goHomes/start")

    async def async_wash_mop_pads(self) -> None:
        """Verified: POST .../jobs/brushCleans/startWithMode"""
        await self._post_device("jobs/brushCleans/startWithMode")

    async def async_dust_collect(self) -> None:
        """Verified: POST .../jobs/dustCollects/start"""
        await self._post_device("jobs/dustCollects/start")

    async def async_start_drying(self) -> None:
        """Verified: POST .../jobs/drying/start"""
        await self._post_device("jobs/drying/start")

    async def async_start_drain(self) -> None:
        """Verified: POST .../jobs/drains/start"""
        await self._post_device("jobs/drains/start")

    async def async_pause(self) -> None:
        """Verified: POST .../jobs/cleans/{uuid}/pause"""
        job = await self.async_get_active_job()
        if not job:
            _LOGGER.warning("No active job to pause")
            return
        await self._post_device(f"jobs/cleans/{job['uuid']}/pause")

    async def async_resume(self) -> None:
        """Verified: POST .../jobs/cleans/{uuid}/resume"""
        job = await self.async_get_active_job()
        if not job:
            _LOGGER.warning("No active job to resume")
            return
        await self._post_device(f"jobs/cleans/{job['uuid']}/resume")

    async def async_stop(self) -> None:
        """Verified: POST .../jobs/cleans/{uuid}/stop"""
        job = await self.async_get_active_job()
        if not job:
            _LOGGER.warning("No active job to stop")
            return
        await self._post_device(f"jobs/cleans/{job['uuid']}/stop")

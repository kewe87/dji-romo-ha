"""REST API client for DJI Romo - auth, commands, job control.

Verified endpoints:
  GET  /app/api/v1/users/auth/token?reason=mqtt       -> MQTT credentials
  POST /cr/app/api/v1/devices/{sn}/jobs/goHomes/start  -> return to base
  POST /cr/app/api/v1/devices/{sn}/jobs/brushCleans/startWithMode -> wash mop pads
  POST /cr/app/api/v1/devices/{sn}/jobs/cleans/{uuid}/pause   -> pause cleaning
  POST /cr/app/api/v1/devices/{sn}/jobs/cleans/{uuid}/resume  -> resume cleaning
  POST /cr/app/api/v1/devices/{sn}/jobs/cleans/{uuid}/stop    -> stop cleaning
  GET  /cr/app/api/v1/devices/{sn}/jobs/cleans/job/list       -> active job list
  GET  /cr/app/api/v1/devices/{sn}/jobs/cleans/statistic      -> cleaning stats

Not yet working:
  POST /cr/app/api/v1/devices/{sn}/jobs/cleans/start  -> start cleaning (body format unknown)
"""

from __future__ import annotations

import logging
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
    # Commands
    # ------------------------------------------------------------------

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

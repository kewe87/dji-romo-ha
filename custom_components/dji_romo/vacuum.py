"""Vacuum platform for the DJI Romo integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.vacuum import StateVacuumEntity, VacuumEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .pyromo.models import FAN_SPEED_NAMES, RomoStatus
from . import RomoStateCoordinator
from .const import CONF_DEVICE_SN, DOMAIN
from .entity import RomoEntity

_STATUS_TO_HA: dict[RomoStatus, str] = {
    RomoStatus.IDLE: "idle",
    RomoStatus.CLEANING: "cleaning",
    RomoStatus.PAUSED: "paused",
    RomoStatus.RETURNING: "returning",
    RomoStatus.DOCKED: "docked",
    RomoStatus.ERROR: "error",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: RomoStateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([RomoVacuumEntity(coordinator, entry.data[CONF_DEVICE_SN])])


class RomoVacuumEntity(RomoEntity, StateVacuumEntity):
    """DJI Romo robot vacuum."""

    _attr_name = None
    _attr_supported_features = (
        VacuumEntityFeature.START
        | VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.BATTERY
        | VacuumEntityFeature.STATE
        | VacuumEntityFeature.FAN_SPEED
    )
    _attr_fan_speed_list = ["quiet", "standard", "max"]

    def __init__(self, coordinator: RomoStateCoordinator, device_sn: str) -> None:
        super().__init__(coordinator, device_sn)
        self._attr_unique_id = device_sn

    @property
    def state(self) -> str | None:
        s = self.coordinator.data.status
        return _STATUS_TO_HA.get(s) if s else None

    @property
    def battery_level(self) -> int | None:
        return self.coordinator.data.battery

    @property
    def fan_speed(self) -> str | None:
        return self.coordinator.data.fan_speed_name

    async def async_start(self, **kwargs: Any) -> None:
        """Start cleaning all rooms with current fan speed setting."""
        speed_map = {v: k for k, v in FAN_SPEED_NAMES.items()}
        fan = speed_map.get(self.fan_speed, 2)
        await self.coordinator.client.async_start_clean(fan_speed=fan)

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed for next cleaning run."""
        speed_map = {v: k for k, v in FAN_SPEED_NAMES.items()}
        fan = speed_map.get(fan_speed, 2)
        await self.coordinator.client.async_start_clean(fan_speed=fan)

    async def async_pause(self, **kwargs: Any) -> None:
        await self.coordinator.client.async_pause()

    async def async_stop(self, **kwargs: Any) -> None:
        await self.coordinator.client.async_stop()

    async def async_return_to_base(self, **kwargs: Any) -> None:
        await self.coordinator.client.async_return_to_base()

"""Vacuum platform for the DJI Romo integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.vacuum import StateVacuumEntity, VacuumEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .pyromo.models import RomoStatus
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
        VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.BATTERY
        | VacuumEntityFeature.STATE
    )

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

    async def async_pause(self, **kwargs: Any) -> None:
        """Verified: POST .../jobs/cleans/{uuid}/pause"""
        await self.coordinator.client.async_pause()

    async def async_stop(self, **kwargs: Any) -> None:
        """Verified: POST .../jobs/cleans/{uuid}/stop"""
        await self.coordinator.client.async_stop()

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Verified: POST .../jobs/goHomes/start"""
        await self.coordinator.client.async_return_to_base()

    # TODO: async_start blocked on finding the request body for jobs/cleans/start
    # See: https://github.com/kewe87/dji-romo-ha/issues/1

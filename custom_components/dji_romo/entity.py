"""Base entity for DJI Romo integration (MQTT push-based)."""

from __future__ import annotations

from homeassistant.helpers.entity import Entity

from . import RomoStateCoordinator
from .const import DOMAIN


class RomoEntity(Entity):
    """Base class for entities that receive state via MQTT push."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator: RomoStateCoordinator, device_sn: str) -> None:
        self.coordinator = coordinator
        self._device_sn = device_sn
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_sn)},
            "name": f"DJI Romo {device_sn}",
            "manufacturer": "DJI",
            "model": "Romo",
        }

    @property
    def available(self) -> bool:
        return self.coordinator.connected

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

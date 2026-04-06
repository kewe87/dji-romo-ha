"""Select platform for DJI Romo – choose cleaning program (shortcut)."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RomoStateCoordinator
from .const import CONF_DEVICE_SN, DOMAIN
from .entity import RomoEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: RomoStateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([RomoCleaningProgramSelect(coordinator, entry.data[CONF_DEVICE_SN])])


class RomoCleaningProgramSelect(RomoEntity, SelectEntity):
    """Select entity for choosing a cleaning program (shortcut) before starting."""

    _attr_name = "Cleaning program"
    _attr_icon = "mdi:clipboard-list"
    _attr_should_poll = True

    def __init__(self, coordinator: RomoStateCoordinator, device_sn: str) -> None:
        super().__init__(coordinator, device_sn)
        self._attr_unique_id = f"{device_sn}_cleaning_program"
        self._shortcuts: list[dict[str, Any]] = []
        self._attr_options = []
        self._attr_current_option = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await self._async_refresh_shortcuts()

    async def async_update(self) -> None:
        """Refresh shortcuts periodically."""
        await self._async_refresh_shortcuts()

    async def _async_refresh_shortcuts(self) -> None:
        try:
            shortcuts = await self.coordinator.client.async_get_shortcuts()
            if not shortcuts:
                return
            self._shortcuts = shortcuts
            self._attr_options = [s.get("plan_name") or f"Plan {i+1}" for i, s in enumerate(shortcuts)]
            if self._attr_current_option not in self._attr_options:
                self._attr_current_option = self._attr_options[0] if self._attr_options else None
        except Exception:
            _LOGGER.debug("Could not fetch cleaning shortcuts")

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self._update_coordinator()

    def _update_coordinator(self) -> None:
        """Push selected shortcut data to coordinator for vacuum entity to use."""
        if not self._attr_current_option or not self._shortcuts:
            self.coordinator.selected_shortcut = None
            return
        try:
            idx = self._attr_options.index(self._attr_current_option)
            self.coordinator.selected_shortcut = self._shortcuts[idx]
        except (ValueError, IndexError):
            self.coordinator.selected_shortcut = None

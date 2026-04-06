"""Button platform for the DJI Romo integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RomoStateCoordinator
from .const import CONF_DEVICE_SN, DOMAIN
from .entity import RomoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: RomoStateCoordinator = hass.data[DOMAIN][entry.entry_id]
    sn: str = entry.data[CONF_DEVICE_SN]
    async_add_entities([
        RomoGoHomeButton(coordinator, sn),
        RomoWashMopButton(coordinator, sn),
        RomoDustCollectButton(coordinator, sn),
        RomoDryingButton(coordinator, sn),
        # RomoDrainButton not included - drain cannot be stopped via API
        # See ISSUES.md #11
    ])


class RomoGoHomeButton(RomoEntity, ButtonEntity):
    """Button to send robot back to base."""

    def __init__(self, coordinator: RomoStateCoordinator, device_sn: str) -> None:
        super().__init__(coordinator, device_sn)
        self.entity_description = ButtonEntityDescription(
            key="go_home", translation_key="go_home", icon="mdi:home-import-outline",
        )
        self._attr_unique_id = f"{device_sn}_go_home"

    async def async_press(self) -> None:
        await self.coordinator.client.async_return_to_base()


class RomoWashMopButton(RomoEntity, ButtonEntity):
    """Button to start mop pad washing."""

    def __init__(self, coordinator: RomoStateCoordinator, device_sn: str) -> None:
        super().__init__(coordinator, device_sn)
        self.entity_description = ButtonEntityDescription(
            key="wash_mop", translation_key="wash_mop", icon="mdi:water-sync",
        )
        self._attr_unique_id = f"{device_sn}_wash_mop"

    async def async_press(self) -> None:
        await self.coordinator.client.async_wash_mop_pads()


class RomoDustCollectButton(RomoEntity, ButtonEntity):
    """Button to start dust collection."""

    def __init__(self, coordinator: RomoStateCoordinator, device_sn: str) -> None:
        super().__init__(coordinator, device_sn)
        self.entity_description = ButtonEntityDescription(
            key="dust_collect", translation_key="dust_collect", icon="mdi:vacuum",
        )
        self._attr_unique_id = f"{device_sn}_dust_collect"

    async def async_press(self) -> None:
        await self.coordinator.client.async_dust_collect()


class RomoDryingButton(RomoEntity, ButtonEntity):
    """Button to start mop drying."""

    def __init__(self, coordinator: RomoStateCoordinator, device_sn: str) -> None:
        super().__init__(coordinator, device_sn)
        self.entity_description = ButtonEntityDescription(
            key="drying", translation_key="drying", icon="mdi:fan",
        )
        self._attr_unique_id = f"{device_sn}_drying"

    async def async_press(self) -> None:
        await self.coordinator.client.async_start_drying()


class RomoDrainButton(RomoEntity, ButtonEntity):
    """Button to start water drain."""

    def __init__(self, coordinator: RomoStateCoordinator, device_sn: str) -> None:
        super().__init__(coordinator, device_sn)
        self.entity_description = ButtonEntityDescription(
            key="drain", translation_key="drain", icon="mdi:water-pump",
        )
        self._attr_unique_id = f"{device_sn}_drain"

    async def async_press(self) -> None:
        await self.coordinator.client.async_start_drain()

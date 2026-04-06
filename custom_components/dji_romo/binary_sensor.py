"""Binary sensor platform for the DJI Romo integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
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
        # Core state
        RomoBoolSensor(coordinator, sn, "docked", "is_docked", "mdi:home-circle", BinarySensorDeviceClass.PLUG, None),
        RomoBoolSensor(coordinator, sn, "charging", "charger_connected", None, BinarySensorDeviceClass.BATTERY_CHARGING, None),
        RomoBoolSensor(coordinator, sn, "cleaning", "is_cleaning", "mdi:broom", None, None),
        RomoBoolSensor(coordinator, sn, "battery_care_active", "battery_care_active", "mdi:battery-heart-variant", None, None),
        # Device settings (from device_state, disabled by default - data arrives only on status changes)
        RomoBoolSensor(coordinator, sn, "battery_care", "battery_care_setting", "mdi:battery-heart", None, EntityCategory.DIAGNOSTIC),
        RomoBoolSensor(coordinator, sn, "carpet_mode", "carpet_mode", "mdi:rug", None, EntityCategory.DIAGNOSTIC),
        RomoBoolSensor(coordinator, sn, "ai_recognition", "ai_recognition", "mdi:robot", None, EntityCategory.DIAGNOSTIC),
        RomoBoolSensor(coordinator, sn, "hot_water_mop", "hot_water_mop", "mdi:water-thermometer", None, EntityCategory.DIAGNOSTIC),
        RomoBoolSensor(coordinator, sn, "do_not_disturb", "no_disturb", "mdi:moon-waning-crescent", None, EntityCategory.DIAGNOSTIC),
        RomoBoolSensor(coordinator, sn, "child_lock", "child_lock", "mdi:lock", None, EntityCategory.DIAGNOSTIC),
        RomoBoolSensor(coordinator, sn, "particle_clean", "enhance_particle_clean", "mdi:grain", None, EntityCategory.DIAGNOSTIC),
        RomoBoolSensor(coordinator, sn, "pet_care", "pet_care", "mdi:paw", None, EntityCategory.DIAGNOSTIC),
        RomoBoolSensor(coordinator, sn, "stair_mode", "stair_mode", "mdi:stairs", None, EntityCategory.DIAGNOSTIC),
        # Extended settings (from REST /settings)
        RomoBoolSensor(coordinator, sn, "liquid_avoid", "liquid_avoid", "mdi:water-alert", None, EntityCategory.DIAGNOSTIC),
        RomoBoolSensor(coordinator, sn, "carpet_deep_clean", "carpet_deep_clean", "mdi:rug", None, EntityCategory.DIAGNOSTIC),
        RomoBoolSensor(coordinator, sn, "auto_dust_collect", "auto_dust_collect", "mdi:delete-sweep", None, EntityCategory.DIAGNOSTIC),
        RomoBoolSensor(coordinator, sn, "auto_dry", "auto_dry", "mdi:fan", None, EntityCategory.DIAGNOSTIC),
        RomoBoolSensor(coordinator, sn, "auto_add_solution", "auto_add_solution", "mdi:bottle-tonic-plus", None, EntityCategory.DIAGNOSTIC),
        RomoBoolSensor(coordinator, sn, "auto_wash_mop", "auto_wash_mop", "mdi:washing-machine", None, EntityCategory.DIAGNOSTIC),
    ])


class RomoBoolSensor(RomoEntity, BinarySensorEntity):
    """Generic binary sensor that reads a bool attribute from state."""

    def __init__(
        self,
        coordinator: RomoStateCoordinator,
        device_sn: str,
        key: str,
        attr: str,
        icon: str | None,
        device_class: BinarySensorDeviceClass | None,
        entity_category: EntityCategory | None,
        enabled_default: bool = True,
    ) -> None:
        super().__init__(coordinator, device_sn)
        self.entity_description = BinarySensorEntityDescription(
            key=key,
            translation_key=key,
            icon=icon,
            device_class=device_class,
            entity_category=entity_category,
            entity_registry_enabled_default=enabled_default,
        )
        self._attr_unique_id = f"{device_sn}_{key}"
        self._attr_field = attr

    @property
    def is_on(self) -> bool | None:
        return getattr(self.coordinator.data, self._attr_field, None)

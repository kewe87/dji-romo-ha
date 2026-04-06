"""Sensor platform for the DJI Romo integration."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RomoStateCoordinator
from .const import (
    CONF_DEVICE_SN, DOMAIN,
    OPT_DOCK_INTERVAL, DEFAULT_DOCK_INTERVAL,
)
from .entity import RomoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: RomoStateCoordinator = hass.data[DOMAIN][entry.entry_id]
    sn: str = entry.data[CONF_DEVICE_SN]

    async_add_entities([
        # Core sensors
        RomoBatterySensor(coordinator, sn),
        RomoFanSpeedSensor(coordinator, sn),
        RomoCleanModeSensor(coordinator, sn),
        RomoProgressSensor(coordinator, sn),
        RomoCleanDurationSensor(coordinator, sn),
        RomoRemainingTimeSensor(coordinator, sn),
        RomoSubJobSensor(coordinator, sn),
        # Consumables
        RomoAttrSensor(coordinator, sn, "dust_bag_life", "dust_bag", "mdi:delete-variant", None),
        RomoConsumableSensor(coordinator, sn, "dust_box_filter_life", "filter", "mdi:air-filter"),
        RomoConsumableSensor(coordinator, sn, "mid_brush_runtime", "mid_brush", "mdi:brush"),
        RomoConsumableSensor(coordinator, sn, "mop_runtime", "mop", "mdi:wiper-wash"),
        RomoConsumableSensor(coordinator, sn, "side_brush_runtime", "side_brush", "mdi:pinwheel-outline"),
        RomoAttrSensor(coordinator, sn, "self_clean_count", "self_clean_count", "mdi:counter", None),
        # Device info
        RomoAttrSensor(coordinator, sn, "device_volume", "volume", "mdi:volume-high", PERCENTAGE),
        RomoAttrSensor(coordinator, sn, "device_language", "language", "mdi:translate", None),
        # Diagnostics
        RomoErrorSensor(coordinator, sn),
        RomoMqttStatusSensor(coordinator, sn),
        RomoLastUpdateSensor(coordinator, sn),
        RomoHmsAlertsSensor(coordinator, sn),
        # Cleaning statistics (from REST)
        RomoAttrSensor(coordinator, sn, "total_cleans", "total_cleans", "mdi:counter", None),
        RomoAttrSensor(coordinator, sn, "total_area", "total_area", "mdi:texture-box", "m²"),
        RomoAttrSensor(coordinator, sn, "total_duration", "total_duration", "mdi:clock-outline", UnitOfTime.SECONDS),
        # Dock consumables (from REST, polled)
        dock_interval = timedelta(seconds=entry.options.get(OPT_DOCK_INTERVAL, DEFAULT_DOCK_INTERVAL))
        RomoDockSensor(coordinator, sn, "clean_water_tank", "Clean water tank", "mdi:water", "clean_water_tank", dock_interval),
        RomoDockSensor(coordinator, sn, "dirty_water_tank", "Dirty water tank", "mdi:water-off", "dirty_water_tank", dock_interval),
        RomoDockSensor(coordinator, sn, "cleaning_solution", "Cleaning solution", "mdi:bottle-tonic", "main_cleaner", dock_interval),
        RomoDockSensor(coordinator, sn, "dust_bag_dock", "Dust bag", "mdi:delete-variant", "dust_bag_consumable", dock_interval),
        # Next scheduled timer (from REST, polled)
        RomoNextTimerSensor(coordinator, sn, dock_interval),
    ])


class RomoSensor(RomoEntity, SensorEntity):
    """Base Romo sensor."""

    def __init__(
        self,
        coordinator: RomoStateCoordinator,
        device_sn: str,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, device_sn)
        self.entity_description = description
        self._attr_unique_id = f"{device_sn}_{description.key}"


class RomoBatterySensor(RomoSensor):
    def __init__(self, coordinator, sn):
        super().__init__(coordinator, sn, SensorEntityDescription(
            key="battery", translation_key="battery",
            device_class=SensorDeviceClass.BATTERY,
            native_unit_of_measurement=PERCENTAGE,
        ))

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.battery


class RomoFanSpeedSensor(RomoSensor):
    def __init__(self, coordinator, sn):
        super().__init__(coordinator, sn, SensorEntityDescription(
            key="fan_speed", translation_key="fan_speed", icon="mdi:fan",
            device_class=SensorDeviceClass.ENUM,
            options=["quiet", "standard", "max"],
        ))

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.fan_speed_name


class RomoCleanModeSensor(RomoSensor):
    def __init__(self, coordinator, sn):
        super().__init__(coordinator, sn, SensorEntityDescription(
            key="clean_mode", translation_key="clean_mode", icon="mdi:robot-vacuum",
            device_class=SensorDeviceClass.ENUM,
            options=["vacuum_and_mop", "vacuum_then_mop", "vacuum", "mop"],
        ))

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.clean_mode_name


class RomoProgressSensor(RomoSensor):
    def __init__(self, coordinator, sn):
        super().__init__(coordinator, sn, SensorEntityDescription(
            key="progress", translation_key="progress", icon="mdi:progress-check",
            native_unit_of_measurement=PERCENTAGE,
        ))

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.progress_percent


class RomoCleanDurationSensor(RomoSensor):
    def __init__(self, coordinator, sn):
        super().__init__(coordinator, sn, SensorEntityDescription(
            key="clean_duration", translation_key="clean_duration",
            icon="mdi:timer-outline",
            device_class=SensorDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.SECONDS,
        ))

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.spent_duration


class RomoRemainingTimeSensor(RomoSensor):
    def __init__(self, coordinator, sn):
        super().__init__(coordinator, sn, SensorEntityDescription(
            key="remaining_time", translation_key="remaining_time",
            icon="mdi:timer-sand",
            device_class=SensorDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.SECONDS,
        ))

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.estimated_remaining


class RomoSubJobSensor(RomoSensor):
    def __init__(self, coordinator, sn):
        super().__init__(coordinator, sn, SensorEntityDescription(
            key="sub_job", translation_key="sub_job", icon="mdi:cog-outline",
            device_class=SensorDeviceClass.ENUM,
            options=[
                "idle", "exit_base", "cover_tree", "dust_collect",
                "go_home", "assist_relocalization", "drying",
                "base_inject_water",
            ],
        ))

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.sub_job_name


class RomoConsumableSensor(RomoSensor):
    """Sensor showing remaining % for a consumable.

    Max values calculated from DJI Home app display vs raw MQTT values.
    Data comes from device_state MQTT event (on status changes).
    """

    def __init__(self, coordinator, sn, attr: str, key: str, icon: str):
        super().__init__(coordinator, sn, SensorEntityDescription(
            key=key, translation_key=key, icon=icon,
            native_unit_of_measurement=PERCENTAGE,
            entity_category=EntityCategory.DIAGNOSTIC,
        ))
        self._attr_field = attr

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.consumable_percent(self._attr_field)


class RomoAttrSensor(RomoSensor):
    """Generic sensor that reads a single attribute from state."""

    def __init__(self, coordinator, sn, attr: str, key: str, icon: str, unit: str | None):
        super().__init__(coordinator, sn, SensorEntityDescription(
            key=key, translation_key=key, icon=icon,
            native_unit_of_measurement=unit,
            entity_category=EntityCategory.DIAGNOSTIC if key in ("volume", "language") else None,
        ))
        self._attr_field = attr

    @property
    def native_value(self):
        return getattr(self.coordinator.data, self._attr_field, None)


class RomoErrorSensor(RomoSensor):
    def __init__(self, coordinator, sn):
        super().__init__(coordinator, sn, SensorEntityDescription(
            key="error", translation_key="error", icon="mdi:alert-circle-outline",
            ))

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.error


class RomoMqttStatusSensor(RomoSensor):
    def __init__(self, coordinator, sn):
        super().__init__(coordinator, sn, SensorEntityDescription(
            key="mqtt_status", translation_key="mqtt_status", icon="mdi:lan-connect",
            entity_category=EntityCategory.DIAGNOSTIC,
        ))

    @property
    def native_value(self) -> str:
        return "connected" if self.coordinator.connected else "disconnected"


class RomoLastUpdateSensor(RomoSensor):
    def __init__(self, coordinator, sn):
        super().__init__(coordinator, sn, SensorEntityDescription(
            key="last_update", translation_key="last_update",
            device_class=SensorDeviceClass.TIMESTAMP,
            entity_category=EntityCategory.DIAGNOSTIC,
        ))

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.last_update_time


class RomoHmsAlertsSensor(RomoSensor):
    def __init__(self, coordinator, sn):
        super().__init__(coordinator, sn, SensorEntityDescription(
            key="hms_alerts", translation_key="hms_alerts", icon="mdi:alert-outline",
            entity_category=EntityCategory.DIAGNOSTIC,
            ))

    @property
    def native_value(self) -> int:
        alerts = self.coordinator.data.hms_alerts
        return len(alerts) if alerts else 0

    @property
    def extra_state_attributes(self) -> dict:
        alerts = self.coordinator.data.hms_alerts
        return {"alerts": alerts} if alerts else {}


class RomoDockSensor(RomoEntity, SensorEntity):
    """Dock consumable sensor (REST-polled)."""

    _attr_should_poll = True
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator, sn, key: str, name: str, icon: str, data_key: str, scan_interval: timedelta | None = None):
        super().__init__(coordinator, sn)
        self._attr_unique_id = f"{sn}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._data_key = data_key
        self._dock_data: dict | None = None
        if scan_interval:
            self._attr_scan_interval = scan_interval

    async def async_update(self) -> None:
        try:
            self._dock_data = await self.coordinator.client.async_get_dock_consumables()
        except Exception:
            pass

    @property
    def native_value(self) -> int | None:
        if not self._dock_data:
            return None
        item = self._dock_data.get(self._data_key)
        if isinstance(item, dict):
            return item.get("percentage")
        return None

    @property
    def extra_state_attributes(self) -> dict:
        if not self._dock_data:
            return {}
        item = self._dock_data.get(self._data_key)
        if not isinstance(item, dict):
            return {}
        attrs = {}
        if "installed" in item:
            attrs["installed"] = item["installed"] == 1
        # For dust bag / cleaning solution with consumable sub-dict
        consumable = item.get("cleaner_consumable") or item
        if isinstance(consumable, dict):
            if consumable.get("alarm"):
                attrs["alarm"] = True
                attrs["alarm_message"] = consumable.get("alarm_message", "")
            if consumable.get("name"):
                attrs["product_name"] = consumable["name"]
        return attrs


class RomoNextTimerSensor(RomoEntity, SensorEntity):
    """Next scheduled cleaning time (REST-polled)."""

    _attr_should_poll = True
    _attr_name = "Next scheduled clean"
    _attr_icon = "mdi:calendar-clock"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator, sn, scan_interval: timedelta | None = None):
        super().__init__(coordinator, sn)
        self._attr_unique_id = f"{sn}_next_timer"
        self._timer_data: dict | None = None
        if scan_interval:
            self._attr_scan_interval = scan_interval

    async def async_update(self) -> None:
        try:
            self._timer_data = await self.coordinator.client.async_get_next_timer()
        except Exception:
            pass

    @property
    def native_value(self) -> datetime | None:
        if not self._timer_data:
            return None
        ts = self._timer_data.get("next_time")
        if not ts:
            return None
        return datetime.fromtimestamp(ts / 1000, tz=timezone.utc)

    @property
    def extra_state_attributes(self) -> dict:
        if not self._timer_data:
            return {}
        return {
            "plan_name": self._timer_data.get("plan_name", ""),
            "enabled": self._timer_data.get("open", False),
            "hour": self._timer_data.get("execute_time_hour"),
            "minute": self._timer_data.get("execute_time_min"),
        }

"""Diagnostics support for the DJI Romo integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_USER_TOKEN, DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    s = coordinator.data
    return {
        "config_entry": {
            k: "**REDACTED**" if k == CONF_USER_TOKEN else v
            for k, v in entry.data.items()
        },
        "mqtt_connected": coordinator.connected,
        "device_state": {
            "status": s.status.value if s.status else None,
            "battery": s.battery,
            "charger_connected": s.charger_connected,
            "mission_status": s.mission_status,
            "event_status": s.event_status,
            "battery_care_active": s.battery_care_active,
            "fan_speed": s.fan_speed,
            "clean_mode": s.clean_mode,
            "progress_percent": s.progress_percent,
            "spent_duration": s.spent_duration,
            "error": s.error,
        },
    }

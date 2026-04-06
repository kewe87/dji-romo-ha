"""Data models for DJI Romo robot vacuum state.

All fields verified from live MQTT data capture.

Topics:
  forward/cr800/thing/product/{SN}/property  (device_osd ~1Hz, device_state on change)
  forward/cr800/thing/product/{SN}/events    (room_clean_progress, go_home, drying, brush_clean, hms)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class RomoStatus(StrEnum):
    IDLE = "idle"
    CLEANING = "cleaning"
    PAUSED = "paused"
    RETURNING = "returning"
    DOCKED = "docked"
    ERROR = "error"


# Verified mission_status values from live MQTT
MISSION_STATUS_MAP: dict[int, RomoStatus] = {
    0: RomoStatus.IDLE,
    2: RomoStatus.CLEANING,
    3: RomoStatus.RETURNING,
    5: RomoStatus.CLEANING,  # brush clean active
    8: RomoStatus.DOCKED,  # drying
}

# Verified event_status strings from live MQTT
EVENT_STATUS_MAP: dict[str, RomoStatus] = {
    "in_progress": RomoStatus.CLEANING,
    "paused": RomoStatus.PAUSED,
    "canceled": RomoStatus.IDLE,
    "ok": RomoStatus.IDLE,
    "idle": RomoStatus.IDLE,
    "returning": RomoStatus.RETURNING,
    "drying": RomoStatus.DOCKED,
    "error": RomoStatus.ERROR,
}

# Verified: 1=Quiet, 2=Standard, 3=Max (app UI order + MQTT data)
FAN_SPEED_NAMES: dict[int, str] = {1: "quiet", 2: "standard", 3: "max"}

# Verified: app UI order + clean_mode=2 confirmed as "Vacuum"
CLEAN_MODE_NAMES: dict[int, str] = {
    0: "vacuum_and_mop",
    1: "vacuum_then_mop",
    2: "vacuum",
    3: "mop",
}


@dataclass(slots=True)
class RomoState:
    """Live state of the robot, updated via MQTT push."""

    # --- device_osd (property topic, ~1Hz) ---
    battery: int | None = None
    charger_connected: bool | None = None
    mission_status: int | None = None
    battery_care_active: bool | None = None
    actuator_status: int | None = None
    robot_has_map: bool | None = None
    hatch_status: int | None = None
    dust_bag_uv_enable: bool | None = None

    # --- room_clean_progress (events topic) ---
    event_status: str | None = None
    progress_percent: int | None = None
    spent_duration: int | None = None
    estimated_remaining: int | None = None
    fan_speed: int | None = None
    clean_mode: int | None = None
    clean_speed: int | None = None
    startup_type: str | None = None

    # --- sub-job detail ---
    sub_job_name: str | None = None  # cur_submission: idle, exit_base, cover_tree, dust_collect, go_home, drying, base_inject_water
    sub_job_state: str | None = None  # running, paused, stopping

    # --- device_state (property topic, on change) / REST settings ---
    device_volume: int | None = None
    device_language: str | None = None
    battery_care_setting: bool | None = None
    carpet_mode: bool | None = None
    ai_recognition: bool | None = None
    hot_water_mop: bool | None = None
    no_disturb: bool | None = None
    child_lock: bool | None = None
    enhance_particle_clean: bool | None = None
    pet_care: bool | None = None
    stair_mode: bool | None = None

    # --- extended settings (from REST /settings) ---
    liquid_avoid: bool | None = None
    carpet_deep_clean: bool | None = None
    auto_dust_collect: bool | None = None
    auto_dry: bool | None = None
    auto_add_solution: bool | None = None
    auto_wash_mop: bool | None = None
    dnd_start_hour: int | None = None
    dnd_start_min: int | None = None
    dnd_end_hour: int | None = None
    dnd_end_min: int | None = None
    wash_back_area: int | None = None
    drying_mode: int | None = None
    dust_collect_mode: int | None = None

    # --- consumables (from device_state) ---
    dust_bag_life: int | None = None
    dust_box_filter_life: int | None = None
    mid_brush_runtime: int | None = None
    mop_runtime: int | None = None
    side_brush_runtime: int | None = None
    self_clean_count: int | None = None

    # --- hms ---
    hms_alerts: list | None = None

    # --- REST consumable percentages (server-calculated, more accurate) ---
    consumable_rest_pct: dict[str, int] = field(default_factory=dict)

    # --- cleaning statistics (from REST) ---
    total_cleans: int | None = None
    total_area: int | None = None  # m² (total_acreage)
    total_duration: int | None = None  # seconds

    # --- error ---
    error: str | None = None

    @property
    def status(self) -> RomoStatus | None:
        if self.event_status:
            return EVENT_STATUS_MAP.get(self.event_status)
        if self.charger_connected:
            return RomoStatus.DOCKED
        if self.mission_status is not None:
            return MISSION_STATUS_MAP.get(self.mission_status)
        return None

    @property
    def is_docked(self) -> bool | None:
        if self.charger_connected is not None:
            return self.charger_connected
        return None

    @property
    def is_cleaning(self) -> bool | None:
        s = self.status
        return s == RomoStatus.CLEANING if s else None

    # Max consumable values (calculated from app display vs raw MQTT values)
    # Max values in seconds. Verified against REST API percentages (2026-04-06):
    # mop=120h, side_brush=180h, filter=180h, mid_brush=300h
    _CONSUMABLE_MAX = {
        "mop_runtime": 432000,       # 120h
        "side_brush_runtime": 648000, # 180h
        "dust_box_filter_life": 648000, # 180h
        "mid_brush_runtime": 1080000, # 300h
    }

    def consumable_percent(self, attr: str) -> int | None:
        """Remaining percentage for a consumable.

        Prefers server-calculated percentages from REST API.
        Falls back to local calculation from MQTT runtime values.
        """
        if attr in self.consumable_rest_pct:
            return self.consumable_rest_pct[attr]
        val = getattr(self, attr, None)
        max_val = self._CONSUMABLE_MAX.get(attr)
        if val is None or max_val is None:
            return None
        used_pct = min(100, int(val / max_val * 100))
        return max(0, 100 - used_pct)

    @property
    def fan_speed_name(self) -> str | None:
        return FAN_SPEED_NAMES.get(self.fan_speed) if self.fan_speed is not None else None

    @property
    def clean_mode_name(self) -> str | None:
        return CLEAN_MODE_NAMES.get(self.clean_mode) if self.clean_mode is not None else None

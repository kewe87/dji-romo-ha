"""Camera platform for DJI Romo – renders the floor plan as a PNG.

Shows room polygons from the REST map API. During cleaning, overlays
the robot position from MQTT state.
"""

from __future__ import annotations

import asyncio
import io
import logging
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from . import RomoStateCoordinator
from .const import CONF_DEVICE_SN, DOMAIN
from .entity import RomoEntity

from datetime import timedelta

_LOGGER = logging.getLogger(__name__)

# Rotating palette for rooms (assigned by poly_index order, works for any home)
ROOM_PALETTE: list[tuple[int, int, int]] = [
    (130, 190, 230),  # blue
    (180, 220, 160),  # green
    (230, 170, 130),  # orange
    (200, 170, 220),  # purple
    (220, 200, 140),  # yellow
    (160, 210, 200),  # teal
    (220, 160, 180),  # pink
    (190, 190, 160),  # olive
    (170, 190, 230),  # light blue
    (220, 180, 160),  # salmon
]

# Map rendering settings
MAP_IMAGE_WIDTH = 600
MAP_PADDING = 20


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: RomoStateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([RomoMapCamera(coordinator, entry.data[CONF_DEVICE_SN])])


class RomoMapCamera(RomoEntity, Camera):
    """Camera entity that renders the vacuum map as PNG."""

    _attr_name = "Map"
    _attr_frame_interval = 30

    def __init__(self, coordinator: RomoStateCoordinator, device_sn: str) -> None:
        RomoEntity.__init__(self, coordinator, device_sn)
        Camera.__init__(self)
        self._attr_unique_id = f"{device_sn}_map"
        self._image: bytes | None = None
        self._map_data: dict[str, Any] | None = None
        self._map_info: dict[str, Any] | None = None
        self._rooms: list[dict[str, Any]] = []

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Fetch map on startup
        await self._async_update_map()
        # Refresh map every 5 minutes (handles map version changes)
        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._async_scheduled_update, timedelta(minutes=5)
            )
        )

    async def _async_scheduled_update(self, _now=None) -> None:
        await self._async_update_map()

    async def _async_update_map(self) -> None:
        """Fetch map data from REST API and render."""
        try:
            data = await self.coordinator.client.async_get_map_data()
            if not data:
                return
            self._map_data = data
            self._map_info = (
                data.get("grid_map", {}).get("map_info", {})
            )
            self._rooms = data.get("seg_map", {}).get("poly_info", [])
            self._render()
        except Exception:
            _LOGGER.exception("Failed to update map")

    def _render(self) -> None:
        """Render room polygons to PNG."""
        if not self._rooms or not self._map_info:
            return

        # Collect all vertices to compute bounding box
        all_x: list[float] = []
        all_y: list[float] = []
        for room in self._rooms:
            for v in room.get("vertices", []):
                all_x.append(v["x"])
                all_y.append(v["y"])

        if not all_x:
            return

        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)

        # Compute scale to fit in image
        map_w = max_x - min_x
        map_h = max_y - min_y
        if map_w <= 0 or map_h <= 0:
            return

        scale = (MAP_IMAGE_WIDTH - 2 * MAP_PADDING) / max(map_w, map_h)
        img_w = int(map_w * scale) + 2 * MAP_PADDING
        img_h = int(map_h * scale) + 2 * MAP_PADDING

        img = Image.new("RGB", (img_w, img_h), (40, 40, 45))
        draw = ImageDraw.Draw(img)

        # Draw carpet areas (subtle background)
        carpet_data = self._map_data.get("carpet_layer", {})
        if carpet_data:
            for carpet in carpet_data.get("data", []):
                verts = carpet.get("vertices", [])
                if len(verts) >= 3:
                    pts = [self._to_pixel(v, min_x, min_y, scale) for v in verts]
                    draw.polygon(pts, fill=(60, 55, 50))

        # Draw room polygons (color by index, not label – works for any home)
        for i, room in enumerate(self._rooms):
            verts = room.get("vertices", [])
            if len(verts) < 3:
                continue
            color = ROOM_PALETTE[i % len(ROOM_PALETTE)]
            pts = [self._to_pixel(v, min_x, min_y, scale) for v in verts]
            draw.polygon(pts, fill=color, outline=(255, 255, 255))

        # Draw room borders (thicker, from border_vertices)
        for room in self._rooms:
            border = room.get("border_vertices", [])
            if len(border) >= 2:
                pts = [self._to_pixel(v, min_x, min_y, scale) for v in border]
                pts.append(pts[0])  # close the polygon
                draw.line(pts, fill=(80, 80, 85), width=2)

        # Draw restricted zones
        restricted = self._map_data.get("restricted_layer")
        if restricted:
            for zone in restricted.get("data", []) if isinstance(restricted, dict) else []:
                verts = zone.get("vertices", [])
                if len(verts) >= 3:
                    pts = [self._to_pixel(v, min_x, min_y, scale) for v in verts]
                    draw.polygon(pts, fill=(180, 60, 60, 128), outline=(200, 40, 40))

        # Draw virtual walls
        walls = self._map_data.get("virtual_wall")
        if walls:
            for wall in walls.get("data", []) if isinstance(walls, dict) else []:
                verts = wall.get("vertices", [])
                if len(verts) >= 2:
                    pts = [self._to_pixel(v, min_x, min_y, scale) for v in verts]
                    draw.line(pts, fill=(200, 40, 40), width=3)

        # Draw dock position (origin is typically dock location)
        dock_x = self._map_info.get("origin_x", 0)
        dock_y = self._map_info.get("origin_y", 0)
        # Only draw if dock is within map bounds
        if min_x <= dock_x <= max_x and min_y <= dock_y <= max_y:
            dx, dy = self._to_pixel({"x": dock_x, "y": dock_y}, min_x, min_y, scale)
            draw.ellipse([dx - 6, dy - 6, dx + 6, dy + 6], fill=(50, 200, 100))

        # Export as PNG
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        self._image = buf.getvalue()
        self.async_write_ha_state()

    def _to_pixel(
        self, v: dict[str, float], min_x: float, min_y: float, scale: float
    ) -> tuple[int, int]:
        """Convert meter coordinates to pixel coordinates."""
        x = int((v["x"] - min_x) * scale) + MAP_PADDING
        y = int((v["y"] - min_y) * scale) + MAP_PADDING
        return (x, y)

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        return self._image

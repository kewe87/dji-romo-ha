"""Constants for the DJI Romo integration."""

from typing import Final

DOMAIN: Final = "dji_romo"

CONF_USER_TOKEN: Final = "user_token"
CONF_DEVICE_SN: Final = "device_sn"

# Options (poll intervals in seconds)
OPT_POSITION_INTERVAL: Final = "position_interval"
OPT_MAP_INTERVAL: Final = "map_interval"
OPT_DOCK_INTERVAL: Final = "dock_interval"

DEFAULT_POSITION_INTERVAL: Final = 10
DEFAULT_MAP_INTERVAL: Final = 300
DEFAULT_DOCK_INTERVAL: Final = 300

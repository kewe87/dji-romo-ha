# DJI Home REST API Documentation

Captured from DJI Home app v1.5.15 (com.dji.home) communicating with `home-api.djigate.com`.

All endpoints require these headers:

```
Content-Type: application/json
x-member-token: <auth_token>
version-name: 1.5.15
version-code: 17821
package-name: com.dji.home
platform: android
language: de
life-cycle-id: <uuid>
x-request-id: <uuid>
x-request-start: <timestamp_ms>
```

## Authentication

| Method | Endpoint | Host |
|--------|----------|------|
| POST | `/apis/apprest/v1/validate_token` | `account.dji.com` |
| GET | `/app/api/v1/users/auth/token?reason=GetMqttTokenReason.login` | `home-api.djigate.com` |
| GET | `/app/api/v1/users/welcome/region` | `home-api.djigate.com` |

## Device Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/app/api/v1/users/devices/list` | List all devices |
| GET | `/app/api/v1/devices/{sn}/hello?client_id={uuid}` | Device heartbeat/hello |
| GET | `/cr/app/api/v1/devices/{sn}/things/properties` | Device properties |
| GET | `/cr/app/api/v1/devices/{sn}/firmwares/compatibilities` | Firmware info |
| GET | `/cr/app/api/v1/devices/{sn}/moduleFile/status?module_type=voicepack_de` | Voice pack status |

## Cleaning

### Start Clean

```
POST /cr/app/api/v1/devices/{sn}/jobs/cleans/start
```

**Request Body:**

```json
{
  "sn": "<device_serial>",
  "job_timeout": 3600,
  "method": "room_clean",
  "data": {
    "action": "start",
    "name": "Saugen",
    "plan_name_key": "",
    "plan_uuid": "<uuid>",
    "plan_type": 2,
    "clean_area_type": 2,
    "is_valid": true,
    "plan_area_configs": [
      {
        "config_uuid": "<uuid>",
        "clean_mode": 2,
        "fan_speed": 2,
        "water_level": 2,
        "clean_num": 1,
        "storm_mode": 0,
        "secondary_clean_num": 1,
        "clean_speed": 2,
        "order_id": 1,
        "poly_type": 2,
        "poly_index": 0,
        "poly_label": 0,
        "user_label": 7,
        "poly_name_index": 0,
        "skip_area": 0,
        "floor_cleaner_type": 0,
        "repeat_mop": false
      }
    ],
    "room_map": {
      "map_index": 1773256628,
      "map_version": 26,
      "file_id": "<map_file_hash>",
      "slot_id": 0
    },
    "area_config_type": 0
  }
}
```

**Field reference:**

| Field | Values | Description |
|-------|--------|-------------|
| `method` | `"room_clean"` | Cleaning method |
| `clean_mode` | 0=Vacuum+Mop, 1=Vacuum then Mop, 2=Vacuum only, 3=Mop only | Cleaning mode |
| `fan_speed` | 1=Quiet, 2=Standard, 3=Max | Suction power |
| `water_level` | 1-3 | Mopping water level |
| `clean_num` | 1-3 | Number of cleaning passes |
| `storm_mode` | 0=Off | Intensive mode |
| `clean_speed` | 1-3 | Mopping speed |
| `order_id` | 1-N | Room cleaning order |
| `poly_type` | 2 | Polygon type (room) |
| `poly_index` | 0-N | Room index on the map |
| `user_label` | N | Room label ID (user-assigned) |
| `skip_area` | 0=Clean, 1=Skip | Skip this room |
| `repeat_mop` | true/false | Repeat mopping pass |
| `plan_type` | 2 | Plan type |
| `clean_area_type` | 2 | Area type (rooms) |

### Stop Clean

```
POST /cr/app/api/v1/devices/{sn}/jobs/cleans/{job_uuid}/stop
```

No request body required.

### Get Clean Job Status

```
GET /cr/app/api/v1/devices/{sn}/jobs/cleans/{job_uuid}?sn={sn}&uuid={job_uuid}
```

### Get Live Map During Clean

```
GET /cr/app/api/v1/devices/{sn}/jobs/liveMap/{job_uuid}
```

## Map & Rooms

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/cr/app/api/v1/devices/{sn}/maps/list?map_data_version=N` | List maps (includes S3 download URL) |
| GET | `/cr/app/api/v1/devices/{sn}/shortcuts/list?plan_data_version=N&slot_id=0` | List cleaning shortcuts/presets |

### Map Data (from S3)

The `maps/list` response includes `file_url` (pre-signed S3 URL) and `file_header` (AES256 SSE-C headers).
Download with those headers returns JSON:

- `seg_map.poly_info[]` — room polygons with `vertices` in meters, `poly_index`, `user_label`, `order_id`
- `grid_map.map_info` — dimensions (448x512), resolution (0.046875 m/px), origin (-6, -15)
- `grid_map.map_data[]` — base64-encoded grid tiles (compress_method=2)
- `carpet_layer.data[]` — carpet polygon vertices
- `restricted_layer` / `virtual_wall` — zone restrictions
- `obstacle_layer` / `pet_layer` — detected objects

### Live Map During Clean

```
GET /cr/app/api/v1/devices/{sn}/jobs/liveMap/{job_uuid}
```

Returns the live cleaning progress map (robot path, cleaned areas).

## Consumables

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/cr/app/api/v1/devices/{sn}/consumables` | Consumable status |
| GET | `/cr/app/api/v1/devices/{sn}/consumables/dock` | Dock consumables |
| GET | `/cr/app/api/v1/devices/{sn}/consumables/notifications?notify_type=N` | Consumable alerts (0=general, 1=during clean) |

## Scheduling

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/cr/app/api/v1/devices/{sn}/timers/next?slot_id=0` | Next scheduled timer |

## Reports & Messages

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/cr/app/api/v1/devices/{sn}/reports/unread` | Unread reports |
| GET | `/app/api/v1/messages/users/unread/count` | Unread message count |
| GET | `/app/api/v1/messages/users/list/unpop` | Unpopped messages |
| GET | `/app/api/v1/activity/list` | Activity log |

## Job History

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/cr/app/api/v1/devices/{sn}/jobs/{job_uuid}` | Get job details |

## Other

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/app/api/v1/users/upgrade/check` | Check for app updates |

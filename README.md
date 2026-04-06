# DJI Romo – Home Assistant Integration

> **Disclaimer:** This project uses an unofficial, reverse-engineered API. It is not endorsed by or affiliated with DJI. Use at your own risk. The authors are not responsible for any damage to your device, data loss, or warranty issues. The API may change at any time without notice, which could break this integration. This integration is in an early stage of development — bugs and breaking changes may occur.

Custom Home Assistant integration for the **DJI Romo** robot vacuum using the unofficial, reverse-engineered DJI cloud API.

> **Version:** 0.2.0-beta

---

## Features

### Vacuum Control

| Action | Type | Description |
|---|---|---|
| Start cleaning | Vacuum entity | Start with selected program or all rooms |
| Pause | Vacuum entity | Pause active cleaning job |
| Stop | Vacuum entity | Stop/cancel active cleaning job |
| Return to base | Vacuum entity + Button | Send robot home |
| Fan speed | Vacuum entity | Quiet / Standard / Max |
| Wash mop pads | Button | Start mop pad cleaning |
| Dust collection | Button | Start dust bag collection |
| Drying | Button | Start mop pad drying |

### Cleaning Programs

| Entity | Type | Description |
|---|---|---|
| Cleaning program | `select` | Choose from app-configured cleaning presets |

Programs are fetched from the DJI cloud (same as configured in the DJI Home app). Each program contains per-room settings like cleaning mode, fan speed, water level, and room order. Selecting a program and pressing Start uses those exact settings.

### Map

| Entity | Type | Description |
|---|---|---|
| Map | `camera` | Floor plan with room polygons rendered as PNG |

The map is downloaded from the DJI cloud as JSON with room polygon coordinates. It shows rooms, carpet areas, restricted zones, virtual walls, and the dock position. Refreshes every 5 minutes.

### Real-time Sensors via MQTT

| Entity | Type | Description |
|---|---|---|
| Vacuum | `vacuum` | Status, battery, start, pause, stop, return, fan speed |
| Battery | `sensor` | Battery level (%) |
| Suction power | `sensor` | Quiet / Standard / Max |
| Cleaning mode | `sensor` | Vacuum / Mop / Vacuum & Mop / Vacuum then Mop |
| Progress | `sensor` | Cleaning progress (%) |
| Clean duration | `sensor` | Time spent cleaning |
| Remaining time | `sensor` | Estimated time remaining |
| Current task | `sensor` | Sub-job detail (dust collection, drying, etc.) |
| Consumables | `sensor` | Dust bag, filter, brushes, mop pad lifetime |
| Statistics | `sensor` | Total cleans, total area, total duration |
| Volume | `sensor` | Device volume |
| Language | `sensor` | Device language |
| HMS alerts | `sensor` | Health management alerts |
| MQTT status | `sensor` | Connection state |
| Last update | `sensor` | Timestamp of last data |
| Docked | `binary_sensor` | On charging dock |
| Charging | `binary_sensor` | Battery charging |
| Cleaning | `binary_sensor` | Currently cleaning |
| Battery care | `binary_sensor` | Battery care active / setting |
| Carpet mode | `binary_sensor` | Setting |
| AI detection | `binary_sensor` | Obstacle detection setting |
| Hot water mop | `binary_sensor` | Setting |
| Do not disturb | `binary_sensor` | Setting |
| Child lock | `binary_sensor` | Setting |
| Particle clean | `binary_sensor` | Setting |
| Pet care | `binary_sensor` | Setting |
| Stair avoidance | `binary_sensor` | Setting |

### Architecture

- **MQTT push** for device state (~1 update per second, no polling)
- **REST API** for authentication, commands, map data, and cleaning programs
- MQTT token auto-refreshes every ~4 hours
- Map data stored on AWS S3 with AES256 encryption (decrypted transparently)
- All data verified with live device capture

---

## Prerequisites

You need two values from the DJI Home app:

| Value | Format | Example |
|---|---|---|
| **User Token** | Starts with `US_` | `US_abc123def456...` |
| **Device Serial Number** | Alphanumeric | `1ABCD2345678` |

### Extracting credentials

#### Option A: Manual extraction (rooted Android)

1. Enable **Wireless Debugging** in Developer Options
2. Connect via ADB:
   ```bash
   adb pair <IP>:<PAIRING_PORT>    # enter 6-digit code
   adb connect <IP>:<PORT>         # main port, NOT pairing port
   ```
3. Extract:
   ```bash
   adb shell
   su
   pid=$(pidof com.dji.home)
   dd if=/proc/$pid/mem bs=1M skip=32 count=480 of=/data/local/tmp/heap.bin 2>/dev/null
   strings /data/local/tmp/heap.bin | grep -oE 'US_[A-Za-z0-9_-]{50,}' | head -1
   strings /data/local/tmp/heap.bin | grep -oE '"sn":"[A-Za-z0-9]+"' | head -1
   rm /data/local/tmp/heap.bin
   ```

#### Option B: Emulator (no root needed, macOS only)

Use the [dji-home-credential-extractor](https://github.com/xn0tsa/dji-home-credential-extractor).

---

## Installation

### HACS (recommended)

1. Add this repository as a custom repository in HACS
2. Search for **DJI Romo** and install
3. Restart Home Assistant

### Manual

1. Copy `custom_components/dji_romo/` into your HA `config/custom_components/` folder
2. Restart Home Assistant

---

## Setup

1. **Settings > Devices & Services > Add Integration**
2. Search for **DJI Romo**
3. Enter **User Token** and **Device Serial Number**
4. Done — entities appear immediately with live data

---

## API Documentation

See [API.md](API.md) for the full REST API reference including all discovered endpoints, request/response formats, and map data structure.

---

## References

- [flutter-ssl-keylog](https://github.com/kewe87/flutter-ssl-keylog) — Frida-based TLS key extraction used to reverse-engineer the DJI Home app API
- [dji-romo-video-control](https://github.com/yamasammy/dji-romo-video-control) — Original reverse-engineering of DJI Romo API (REST endpoints, Agora video)
- [dji-home-credential-extractor](https://github.com/xn0tsa/dji-home-credential-extractor) — Tool for extracting DJI Home app credentials via Android emulator
- [DJI Cloud API](https://github.com/dji-sdk/Cloud-API-Doc) — Official DJI MQTT "thing model" architecture (same pattern used by Romo)
- [Cosmo-Edge: DJI Romo MQTT/BOLA Flaw](https://cosmo-edge.com/dji-romo-security-mqtt-bola-flaw/) — Security research that led to the MQTT discovery
- [HA Vacuum Entity Docs](https://developers.home-assistant.io/docs/core/entity/vacuum/) — Home Assistant StateVacuumEntity API

## License

MIT

---

# DJI Romo – Home Assistant Integration (Deutsch)

> **Haftungsausschluss:** Dieses Projekt nutzt eine inoffizielle, reverse-engineerte API. Es besteht keine Verbindung zu DJI. Die Nutzung erfolgt auf eigene Gefahr. Die Autoren haften nicht für Schäden am Gerät, Datenverlust oder Garantieverlust. Die API kann sich jederzeit ohne Vorankündigung ändern. Diese Integration befindet sich in einem frühen Entwicklungsstadium — Fehler und Breaking Changes sind möglich.

Custom Home Assistant Integration für den **DJI Romo** Saugroboter über die inoffizielle, reverse-engineerte DJI Cloud API.

> **Version:** 0.2.0-beta

---

## Funktionen

### Steuerung

| Aktion | Typ | Beschreibung |
|---|---|---|
| Reinigung starten | Vacuum Entity | Startet mit gewähltem Programm oder allen Räumen |
| Pause | Vacuum Entity | Reinigung pausieren |
| Stop | Vacuum Entity | Reinigung abbrechen |
| Zurück zur Basis | Vacuum Entity + Button | Roboter zurückschicken |
| Saugstärke | Vacuum Entity | Leise / Standard / Max |
| Wischpads reinigen | Button | Mopp-Reinigung starten |
| Absaugen | Button | Staubsammlung starten |
| Trocknen | Button | Mopp-Trocknung starten |

### Reinigungsprogramme

| Entity | Typ | Beschreibung |
|---|---|---|
| Reinigungsprogramm | `select` | Auswahl aus in der App konfigurierten Programmen |

Die Programme werden aus der DJI Cloud geladen (identisch mit der DJI Home App). Jedes Programm enthält Raum-spezifische Einstellungen wie Reinigungsmodus, Saugstärke, Wassermenge und Raumreihenfolge.

### Karte

| Entity | Typ | Beschreibung |
|---|---|---|
| Karte | `camera` | Grundriss mit Raum-Polygonen als PNG |

Die Karte wird als JSON aus der DJI Cloud geladen und zeigt Räume, Teppichbereiche, Sperrzonen, virtuelle Wände und die Dockposition. Aktualisiert sich alle 5 Minuten.

### Echtzeit-Sensoren via MQTT

| Entity | Typ | Beschreibung |
|---|---|---|
| Staubsauger | `vacuum` | Status, Akku, Start, Pause, Stop, Zurück, Saugstärke |
| Akkustand | `sensor` | Akkustand in % |
| Saugstärke | `sensor` | Leise / Standard / Max |
| Reinigungsmodus | `sensor` | Saugen / Wischen / Saugen & Wischen / Erst saugen dann wischen |
| Fortschritt | `sensor` | Reinigungsfortschritt in % |
| Reinigungsdauer | `sensor` | Bisherige Reinigungszeit |
| Restzeit | `sensor` | Geschätzte Restzeit |
| Aktuelle Aufgabe | `sensor` | Sub-Job Detail (Staubsammlung, Trocknung, etc.) |
| Verbrauchsmaterial | `sensor` | Staubbeutel, Filter, Bürsten, Wischpad |
| Statistiken | `sensor` | Reinigungen gesamt, Fläche gesamt, Zeit gesamt |
| Lautstärke | `sensor` | Gerätelautstärke |
| Sprache | `sensor` | Gerätesprache |
| Warnmeldungen | `sensor` | HMS-Fehlermeldungen |
| MQTT-Status | `sensor` | Verbindungsstatus |
| Letzte Aktualisierung | `sensor` | Zeitstempel |
| Angedockt | `binary_sensor` | Auf der Ladestation |
| Wird geladen | `binary_sensor` | Akku wird geladen |
| Reinigt | `binary_sensor` | Reinigung aktiv |
| Akkuschutz | `binary_sensor` | Akkuschutz aktiv / Einstellung |
| Teppichmodus | `binary_sensor` | Einstellung |
| KI-Erkennung | `binary_sensor` | Hinderniserkennung |
| Heißwasser | `binary_sensor` | Einstellung |
| Nicht stören | `binary_sensor` | Einstellung |
| Kindersicherung | `binary_sensor` | Einstellung |
| Partikelerkennung | `binary_sensor` | Einstellung |
| Tierpflege | `binary_sensor` | Einstellung |
| Treppenvermeidung | `binary_sensor` | Einstellung |

### Architektur

- **MQTT Push** für Gerätestatus (~1 Update pro Sekunde, kein Polling)
- **REST API** für Authentifizierung, Befehle, Kartendaten und Reinigungsprogramme
- MQTT-Token erneuert sich automatisch alle ~4 Stunden
- Kartendaten auf AWS S3 mit AES256-Verschlüsselung (wird transparent entschlüsselt)

---

## Voraussetzungen

Du brauchst zwei Werte aus der DJI Home App:

| Wert | Format | Beispiel |
|---|---|---|
| **User Token** | Beginnt mit `US_` | `US_abc123def456...` |
| **Geräte-Seriennummer** | Alphanumerisch | `1ABCD2345678` |

### Zugangsdaten extrahieren

#### Option A: Manuell (gerootetes Android)

1. **Kabelloses Debugging** in den Entwickleroptionen aktivieren
2. Über ADB verbinden:
   ```bash
   adb pair <IP>:<KOPPLUNGS-PORT>    # 6-stelligen Code eingeben
   adb connect <IP>:<PORT>            # Hauptport, NICHT der Kopplungsport
   ```
3. Extrahieren:
   ```bash
   adb shell
   su
   pid=$(pidof com.dji.home)
   dd if=/proc/$pid/mem bs=1M skip=32 count=480 of=/data/local/tmp/heap.bin 2>/dev/null
   strings /data/local/tmp/heap.bin | grep -oE 'US_[A-Za-z0-9_-]{50,}' | head -1
   strings /data/local/tmp/heap.bin | grep -oE '"sn":"[A-Za-z0-9]+"' | head -1
   rm /data/local/tmp/heap.bin
   ```

#### Option B: Emulator (kein Root nötig, nur macOS)

Nutze den [dji-home-credential-extractor](https://github.com/xn0tsa/dji-home-credential-extractor).

---

## Installation

### HACS

1. Dieses Repository als Custom Repository in HACS hinzufügen
2. Nach **DJI Romo** suchen und installieren
3. Home Assistant neustarten

### Manuell

1. `custom_components/dji_romo/` in den HA `config/custom_components/` Ordner kopieren
2. Home Assistant neustarten

---

## Einrichtung

1. **Einstellungen > Geräte & Dienste > Integration hinzufügen**
2. Nach **DJI Romo** suchen
3. **User Token** und **Geräte-Seriennummer** eingeben
4. Fertig — Entities erscheinen sofort mit Live-Daten

---

## API-Dokumentation

Siehe [API.md](API.md) für die vollständige REST API Referenz mit allen entdeckten Endpoints, Request/Response-Formaten und Kartenstruktur.

---

## Referenzen

- [flutter-ssl-keylog](https://github.com/kewe87/flutter-ssl-keylog) — Frida-basierte TLS-Key-Extraktion zum Reverse-Engineering der DJI Home App API
- [dji-romo-video-control](https://github.com/yamasammy/dji-romo-video-control) — Original Reverse-Engineering der DJI Romo API
- [dji-home-credential-extractor](https://github.com/xn0tsa/dji-home-credential-extractor) — Credential-Extraktion über Android-Emulator
- [DJI Cloud API](https://github.com/dji-sdk/Cloud-API-Doc) — Offizielles DJI MQTT "Thing Model" (gleiches Muster wie Romo)
- [Cosmo-Edge: DJI Romo MQTT/BOLA](https://cosmo-edge.com/dji-romo-security-mqtt-bola-flaw/) �� Sicherheitsforschung die zur MQTT-Entdeckung führte
- [HA Vacuum Entity Docs](https://developers.home-assistant.io/docs/core/entity/vacuum/)

## Lizenz

MIT

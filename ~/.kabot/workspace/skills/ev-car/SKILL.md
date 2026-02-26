---
name: ev-car
description: Query EV car data — battery status, range, charging info
---

# EV Car API Skill

## Overview
Connects to EV car telematics APIs to check battery, range, and charging status.

## Supported APIs
- Tesla (via unofficial API)
- Generic OBD-II / MQTT bridges

## Usage
When the user asks about their EV car status, battery, or charging:

### Check Battery Status
Use `web_fetch` tool:
```json
{
  "url": "https://[configured_host]/api/v1/vehicles/[vehicle_id]/data",
  "method": "GET",
  "headers": {"Authorization": "Bearer [stored_api_key]"}
}
```

### Response Format
Present the data as:
- 🔋 Battery: [level]%
- 📏 Range: [range] km
- ⚡ Charging: [status]
- 🌡️ Battery Temp: [temp]°C

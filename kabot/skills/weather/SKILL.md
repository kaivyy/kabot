---
name: weather
description: Use when users ask about current weather, temperature, rain, or near-term forecasts for a real location. Not for historical weather archives, official severe-weather alerts, aviation, marine, or climate-trend analysis.
homepage: https://open-meteo.com/en/docs
metadata: {"kabot":{"emoji":"🌤️","requires":{"bins":["curl"]}}}
---

# Weather Skill

Get current weather and forecasts with **Open-Meteo as the primary source** and `wttr.in` as a fast human-readable fallback.

## When to Use

Use this skill when the user asks things like:

- "What's the weather in Tokyo?"
- "Will it rain today in Cilacap?"
- "Temperature in London right now"
- "Forecast for the next 3-7 days"
- Travel planning with weather context

Do not use this skill for:

- Historical weather data
- Severe weather alerts or emergency warnings
- Aviation or marine weather
- Climate analysis or long-term trends
- Hyper-local sensor-grade measurements

## Location

Always ground the request to a real location.

- If the user already gave a city/region/airport code, use it.
- If the follow-up omits the location, reuse the last grounded weather location.
- If no location can be grounded, ask briefly for one instead of guessing.

## Open-Meteo (Primary)

Prefer Open-Meteo for current conditions and forecast data because it is structured, keyless, and easy to audit.

### Geocoding

```bash
curl -s "https://geocoding-api.open-meteo.com/v1/search?name=London&count=1&language=en&format=json"
```

### Current Weather

```bash
curl -s "https://api.open-meteo.com/v1/forecast?latitude=51.5072&longitude=-0.1276&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,wind_direction_10m&timezone=auto"
```

### Hourly Rain / Next Few Hours

```bash
curl -s "https://api.open-meteo.com/v1/forecast?latitude=51.5072&longitude=-0.1276&hourly=temperature_2m,precipitation_probability,precipitation,weather_code,wind_speed_10m&forecast_days=2&timezone=auto"
```

### Daily Forecast

```bash
curl -s "https://api.open-meteo.com/v1/forecast?latitude=51.5072&longitude=-0.1276&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max&forecast_days=7&timezone=auto"
```

## wttr.in (Fallback / Quick Readable Output)

Use `wttr.in` when you need a quick readable summary, a simple terminal forecast, or an image output.

### One-Line Summary

```bash
curl -s "wttr.in/London?format=%l:+%c+%t+(feels+like+%f),+%w+wind,+%h+humidity"
```

### Rain Shortcut

```bash
curl -s "wttr.in/London?format=%l:+%c+%p"
```

### Quick Forecast

```bash
curl -s "wttr.in/London?format=v2"
```

### PNG

```bash
curl -s "wttr.in/London.png" -o weather.png
```

## Quick Response Rules

- For **current weather**: prefer Open-Meteo current data.
- For **"will it rain?"**: prefer Open-Meteo hourly precipitation probability.
- For **3-7 day forecast**: prefer Open-Meteo daily forecast.
- For **quick terminal-friendly summary**: `wttr.in` is acceptable as fallback.
- If the user asks for a concise answer, summarize the useful fields instead of dumping raw JSON.

## Response Templates

Use short, grounded answers in the user's language. Prefer concrete fields over vague wording.

### Current Weather

```text
[Location]: [Condition] [Temperature]
Feels like: [FeelsLike]
Wind: [Wind]
Humidity: [Humidity]
Source: Open-Meteo
```

### Rain / Next Few Hours

```text
For [Location], rain chance in the next few hours is [Probability].
If relevant, mention the highest nearby precipitation window instead of guessing.
Source: Open-Meteo
```

### Daily Forecast

```text
[Location] forecast:
- Today: [Condition], [Min]-[Max]
- Tomorrow: [Condition], [Min]-[Max]
- Next: [Condition], [Min]-[Max]
Source: Open-Meteo
```

### If Location Is Missing

```text
Ask briefly for the city/region instead of guessing.
Example: "Kota atau wilayahnya di mana?"
```

## Notes

- No API key is required.
- Open-Meteo should be treated as the default primary source.
- `wttr.in` is best treated as fallback, quick summary, or image output.
- Do not invent locations.
- For official warnings, use the relevant national meteorological authority instead of this skill alone.

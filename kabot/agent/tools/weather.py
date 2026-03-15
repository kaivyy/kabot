"""Weather tool for fetching weather information."""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import httpx
from loguru import logger

from kabot.agent.cron_fallback_nlp import extract_weather_location
from kabot.agent.fallback_i18n import detect_language
from kabot.agent.fallback_i18n import t as i18n_t
from kabot.agent.tools.base import Tool

_WTTR_FORMATS = {
    "simple": "%l:+%c+%t",
    "full": "%l:+%c+%t+%h+%w",
}

_WEATHER_REQUEST_TIMEOUT_SECONDS = 3.0

_EMOJI_MAP = {
    "\u2600\ufe0f": "[Sunny]",
    "\u2600": "[Sunny]",
    "\U0001F324\ufe0f": "[Partly Cloudy]",
    "\U0001F324": "[Partly Cloudy]",
    "\u26C5": "[Partly Cloudy]",
    "\U0001F325\ufe0f": "[Cloudy]",
    "\U0001F325": "[Cloudy]",
    "\u2601\ufe0f": "[Cloudy]",
    "\u2601": "[Cloudy]",
    "\U0001F326\ufe0f": "[Rainy]",
    "\U0001F326": "[Rainy]",
    "\U0001F327\ufe0f": "[Rainy]",
    "\U0001F327": "[Rainy]",
    "\U0001F329\ufe0f": "[Stormy]",
    "\U0001F329": "[Stormy]",
    "\u26C8\ufe0f": "[Stormy]",
    "\u26C8": "[Stormy]",
    "\u2744\ufe0f": "[Snowy]",
    "\u2744": "[Snowy]",
    "\U0001F328\ufe0f": "[Snowy]",
    "\U0001F328": "[Snowy]",
    "\U0001F32B\ufe0f": "[Foggy]",
    "\U0001F32B": "[Foggy]",
    "\U0001F319": "[Clear Night]",
}

_WTTR_ERROR_HINTS = (
    "unknown location",
    "sorry",
    "not found",
    "error",
)

_WEATHER_CODE_LABELS = {
    0: "[Clear]",
    1: "[Partly Cloudy]",
    2: "[Partly Cloudy]",
    3: "[Cloudy]",
    45: "[Foggy]",
    48: "[Foggy]",
    51: "[Rainy]",
    53: "[Rainy]",
    55: "[Rainy]",
    61: "[Rainy]",
    63: "[Rainy]",
    65: "[Rainy]",
    71: "[Snowy]",
    73: "[Snowy]",
    75: "[Snowy]",
    95: "[Stormy]",
    96: "[Stormy]",
    99: "[Stormy]",
}

_TEMP_RE = re.compile(r"([+-]?\d+(?:\.\d+)?)\s*°?\s*C", re.IGNORECASE)
_CONDITION_RE = re.compile(r"\[([^\]]+)\]")
_LOCATION_ALIAS_VARIANTS: dict[str, tuple[str, ...]] = {
    "東京": ("Tokyo",),
    "東京都": ("Tokyo",),
    "北京": ("Beijing",),
    "北京市": ("Beijing",),
    "กรุงเทพ": ("Bangkok",),
    "กรุงเทพฯ": ("Bangkok",),
    "กรุงเทพมหานคร": ("Bangkok",),
}

_WEATHER_ALIAS_ENV_PATH = "KABOT_WEATHER_ALIASES_PATH"
_WEATHER_ALIAS_FILENAME = "weather_aliases.json"
_WEATHER_HOURLY_WINDOW_RE = re.compile(
    r"(?i)\b(?:next\s+)?(\d{1,2})\s*(?:-|to|until)\s*(\d{1,2})\s*(?:hours?)\b"
)
_WEATHER_SINGLE_HOURS_RE = re.compile(
    r"(?i)\b(?:next|for the next)\s*(\d{1,2})\s*(?:hours?)\b"
)
_WEATHER_DAILY_MARKERS = (
    "tomorrow",
    "week",
    "weekly",
    "7 day",
    "7-day",
    "daily",
)
_WEATHER_FORECAST_MARKERS = (
    "forecast",
    "hourly",
    "next few hours",
    "next hours",
    "will it rain",
)


def _format_openmeteo_wind_suffix(current: dict[str, Any]) -> str:
    wind_speed = current.get("windspeed")
    wind_direction = current.get("winddirection")
    if wind_speed is None:
        return ""
    try:
        speed_value = float(wind_speed)
    except Exception:
        return ""
    if wind_direction is None:
        return f" | Wind: {speed_value:.1f} km/h"
    try:
        direction_value = float(wind_direction)
    except Exception:
        return f" | Wind: {speed_value:.1f} km/h"
    return f" | Wind: {speed_value:.1f} km/h @ {direction_value:.0f}°"

_CARE_COPY = {
    "en": {
        "prefix": "Care tip",
        "extreme_hot": "Extreme heat: risk of heatstroke, stay in shade, hydrate often, and limit outdoor activity at noon.",
        "very_hot": "Very hot weather: apply sunscreen, hydrate often, and avoid direct noon sun.",
        "hot": "Warm to hot weather: use sunscreen and keep drinking water.",
        "cold": "Cool weather: wear a jacket to stay comfortable.",
        "very_cold": "Cold weather: wear a thicker jacket and keep your body warm.",
        "rainy": "Bring an umbrella and be careful on slippery roads.",
        "stormy": "Storm risk: avoid open outdoor areas when possible.",
        "foggy": "Low visibility: be extra careful when riding or driving.",
        "default": "Adjust clothing and hydration to stay comfortable.",
    },
    "id": {
        "prefix": "Saran",
        "extreme_hot": "Panas ekstrem: ada risiko heatstroke, cari tempat teduh, sering minum, dan batasi aktivitas luar saat siang.",
        "very_hot": "Cuaca sangat panas: pakai sunscreen, sering minum air, dan hindari terik siang.",
        "hot": "Cuaca hangat-panas: pakai sunscreen dan tetap cukup minum.",
        "cold": "Cuaca sejuk: pakai jaket agar tetap nyaman.",
        "very_cold": "Cuaca dingin: pakai jaket lebih tebal supaya tetap hangat.",
        "rainy": "Bawa payung dan hati-hati jalanan licin.",
        "stormy": "Risiko badai: hindari area terbuka saat di luar.",
        "foggy": "Jarak pandang rendah: lebih hati-hati saat berkendara.",
        "default": "Sesuaikan pakaian dan hidrasi agar tetap nyaman.",
    },
    "ms": {
        "prefix": "Saran",
        "extreme_hot": "Panas melampau: risiko heatstroke, cari tempat teduh, minum air kerap, dan kurangkan aktiviti luar waktu tengah hari.",
        "very_hot": "Cuaca sangat panas: pakai sunscreen, minum air dengan kerap, dan elak matahari tengah hari.",
        "hot": "Cuaca panas: pakai sunscreen dan pastikan cukup minum air.",
        "cold": "Cuaca sejuk: pakai jaket supaya lebih selesa.",
        "very_cold": "Cuaca sejuk dingin: pakai jaket lebih tebal untuk kekal hangat.",
        "rainy": "Bawa payung dan berhati-hati di jalan licin.",
        "stormy": "Risiko ribut: elakkan kawasan terbuka jika boleh.",
        "foggy": "Jarak penglihatan rendah: pandu dengan lebih berhati-hati.",
        "default": "Laraskan pakaian dan hidrasi supaya kekal selesa.",
    },
    "th": {
        "prefix": "\u0e04\u0e33\u0e41\u0e19\u0e30\u0e19\u0e33",
        "very_hot": "\u0e2d\u0e32\u0e01\u0e32\u0e28\u0e23\u0e49\u0e2d\u0e19\u0e21\u0e32\u0e01 \u0e17\u0e32 sunscreen \u0e14\u0e37\u0e48\u0e21\u0e19\u0e49\u0e33\u0e1a\u0e48\u0e2d\u0e22 \u0e41\u0e25\u0e30\u0e2b\u0e25\u0e35\u0e01\u0e41\u0e14\u0e14\u0e41\u0e23\u0e07\u0e0a\u0e48\u0e27\u0e07\u0e40\u0e17\u0e35\u0e48\u0e22\u0e07",
        "hot": "\u0e2d\u0e32\u0e01\u0e32\u0e28\u0e23\u0e49\u0e2d\u0e19 \u0e04\u0e27\u0e23\u0e17\u0e32 sunscreen \u0e41\u0e25\u0e30\u0e14\u0e37\u0e48\u0e21\u0e19\u0e49\u0e33\u0e43\u0e2b\u0e49\u0e1e\u0e2d",
        "cold": "\u0e2d\u0e32\u0e01\u0e32\u0e28\u0e40\u0e22\u0e47\u0e19 \u0e04\u0e27\u0e23\u0e43\u0e2a\u0e48\u0e40\u0e2a\u0e37\u0e49\u0e2d\u0e01\u0e31\u0e19\u0e2b\u0e19\u0e32\u0e27",
        "very_cold": "\u0e2d\u0e32\u0e01\u0e32\u0e28\u0e2b\u0e19\u0e32\u0e27 \u0e04\u0e27\u0e23\u0e43\u0e2a\u0e48\u0e40\u0e2a\u0e37\u0e49\u0e2d\u0e01\u0e31\u0e19\u0e2b\u0e19\u0e32\u0e27\u0e2b\u0e19\u0e32\u0e02\u0e36\u0e49\u0e19",
        "rainy": "\u0e04\u0e27\u0e23\u0e1e\u0e01\u0e23\u0e48\u0e21\u0e41\u0e25\u0e30\u0e23\u0e30\u0e27\u0e31\u0e07\u0e16\u0e19\u0e19\u0e25\u0e37\u0e48\u0e19",
        "stormy": "\u0e21\u0e35\u0e42\u0e2d\u0e01\u0e32\u0e2a\u0e40\u0e01\u0e34\u0e14\u0e1e\u0e32\u0e22\u0e38 \u0e04\u0e27\u0e23\u0e2b\u0e25\u0e35\u0e01\u0e40\u0e25\u0e35\u0e48\u0e22\u0e07\u0e1e\u0e37\u0e49\u0e19\u0e17\u0e35\u0e48\u0e42\u0e25\u0e48\u0e07",
        "foggy": "\u0e17\u0e31\u0e28\u0e19\u0e27\u0e34\u0e2a\u0e31\u0e22\u0e15\u0e48\u0e33 \u0e02\u0e31\u0e1a\u0e02\u0e35\u0e48\u0e14\u0e49\u0e27\u0e22\u0e04\u0e27\u0e32\u0e21\u0e23\u0e30\u0e21\u0e31\u0e14\u0e23\u0e30\u0e27\u0e31\u0e07",
        "default": "\u0e1b\u0e23\u0e31\u0e1a\u0e40\u0e2a\u0e37\u0e49\u0e2d\u0e1c\u0e49\u0e32\u0e41\u0e25\u0e30\u0e14\u0e37\u0e48\u0e21\u0e19\u0e49\u0e33\u0e43\u0e2b\u0e49\u0e40\u0e2b\u0e21\u0e32\u0e30\u0e2a\u0e21",
    },
    "zh": {
        "prefix": "\u5efa\u8bae",
        "very_hot": "\u5929\u6c14\u5f88\u70ed\uff0c\u8bb0\u5f97\u6d82\u9632\u6652\u971c\uff0c\u591a\u8865\u6c34\uff0c\u5c11\u6674\u5929\u6b63\u5348\u66b4\u6652\u3002",
        "hot": "\u5929\u6c14\u504f\u70ed\uff0c\u5efa\u8bae\u6d82\u9632\u6652\u5e76\u4fdd\u6301\u8865\u6c34\u3002",
        "cold": "\u5929\u6c14\u8f83\u51c9\uff0c\u5efa\u8bae\u7a7f\u5916\u5957\u4fdd\u6696\u3002",
        "very_cold": "\u5929\u6c14\u8f83\u51b7\uff0c\u5efa\u8bae\u7a7f\u66f4\u539a\u7684\u5916\u5957\u3002",
        "rainy": "\u51fa\u95e8\u8bf7\u5e26\u4f1e\uff0c\u6ce8\u610f\u8def\u9762\u6e7f\u6ed1\u3002",
        "stormy": "\u6709\u98ce\u66b4\u98ce\u9669\uff0c\u5c3d\u91cf\u907f\u514d\u7a7a\u65f7\u5730\u533a\u3002",
        "foggy": "\u80fd\u89c1\u5ea6\u8f83\u4f4e\uff0c\u9a91\u884c\u6216\u5f00\u8f66\u8bf7\u66f4\u52a0\u5c0f\u5fc3\u3002",
        "default": "\u8bf7\u6839\u636e\u6e29\u5ea6\u9002\u5f53\u589e\u51cf\u8863\u7269\u5e76\u4fdd\u6301\u8865\u6c34\u3002",
    },
}


def clean_emoji(text: str) -> str:
    """Replace common weather emoji with plain text labels."""
    value = text
    for emoji, replacement in _EMOJI_MAP.items():
        value = value.replace(emoji, replacement)
    value = re.sub(r"[^\x00-\x7F]", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def normalize_location(location: str) -> str:
    """Normalize noisy user/model location text into city-like value."""
    raw = (location or "").strip()
    if not raw:
        return ""
    raw = raw.replace("+", " ")

    candidate = extract_weather_location(raw) or raw
    candidate = re.sub(
        r"(?i)\b(?:right now|today|now|how much)\b",
        " ",
        candidate,
    )
    candidate = re.sub(
        r"(?i)\b(?:city|regency|district|county|municipality|province)\b$",
        " ",
        candidate,
    )
    candidate = re.sub(r"\s+", " ", candidate).strip(" .,!?:;")
    return candidate or raw


def _normalize_alias_values(value: Any) -> list[str]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list):
        values = [str(item).strip() for item in value]
    else:
        return []

    deduped: list[str] = []
    seen: set[str] = set()
    for item in values:
        cleaned = str(item or "").strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)
    return deduped


def _parse_alias_payload(payload: Any) -> dict[str, list[str]]:
    source = (
        payload.get("aliases")
        if isinstance(payload, dict) and isinstance(payload.get("aliases"), dict)
        else payload
    )
    if not isinstance(source, dict):
        return {}

    parsed: dict[str, list[str]] = {}
    for raw_key, raw_value in source.items():
        key = str(raw_key or "").strip()
        if not key:
            continue
        values = _normalize_alias_values(raw_value)
        if values:
            parsed[key] = values
    return parsed


def _get_user_weather_alias_path() -> Path:
    override = str(os.environ.get(_WEATHER_ALIAS_ENV_PATH, "") or "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".kabot" / _WEATHER_ALIAS_FILENAME


def _load_user_weather_aliases() -> dict[str, list[str]]:
    path = _get_user_weather_alias_path()
    if not path.is_file():
        return {}
    try:
        with open(path, encoding="utf-8-sig") as handle:
            return _parse_alias_payload(json.load(handle))
    except Exception:
        return {}


def _load_weather_alias_map() -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {
        key: list(values) for key, values in _LOCATION_ALIAS_VARIANTS.items()
    }
    for key, values in _load_user_weather_aliases().items():
        merged[key] = values
    return merged


def _extract_weather_result_location(weather_text: str) -> str:
    raw = str(weather_text or "").strip()
    if not raw:
        return ""
    return raw.split(":", 1)[0].strip()


def _should_persist_weather_alias(raw_location: str, resolved_location: str) -> bool:
    raw = str(raw_location or "").strip()
    resolved = str(resolved_location or "").strip()
    if not raw or not resolved:
        return False
    if raw.casefold() == resolved.casefold():
        return False
    if len(raw) > 64 or len(resolved) > 64:
        return False
    if not re.search(r"[^\x00-\x7F]", raw):
        return False
    return True


def _persist_user_weather_alias(raw_location: str, resolved_location: str) -> None:
    if not _should_persist_weather_alias(raw_location, resolved_location):
        return

    path = _get_user_weather_alias_path()
    current = _load_user_weather_aliases()
    existing = current.get(raw_location, [])
    existing_keys = {item.casefold() for item in existing}
    if resolved_location.casefold() in existing_keys:
        return

    current[raw_location] = (existing + [resolved_location])[:4]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"aliases": current}, handle, ensure_ascii=False, indent=2)


def _weather_location_variants(location: str) -> list[str]:
    """Generate compact fallback variants for noisy free-form locations."""
    normalized = normalize_location(location)
    if not normalized:
        return []

    variants: list[str] = [normalized]
    for alias in _load_weather_alias_map().get(normalized, []):
        variants.append(alias)
    tokens = normalized.split()

    if len(tokens) >= 2 and "," not in normalized:
        variants.append(f"{tokens[0]}, {' '.join(tokens[1:])}")

    if len(tokens) >= 2:
        variants.append(tokens[0])

    if "," in normalized:
        head = normalized.split(",", 1)[0].strip()
        if head:
            variants.append(head)

    deduped: list[str] = []
    seen: set[str] = set()
    for item in variants:
        key = item.strip()
        if not key:
            continue
        key_l = key.lower()
        if key_l in seen:
            continue
        seen.add(key_l)
        deduped.append(key)
        if len(deduped) >= 4:
            break
    return deduped


def _looks_like_wttr_error(text: str) -> bool:
    lower = (text or "").lower()
    return any(hint in lower for hint in _WTTR_ERROR_HINTS)


def _extract_temperature_c(weather_text: str) -> float | None:
    match = _TEMP_RE.search(weather_text or "")
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _extract_condition(weather_text: str) -> str:
    match = _CONDITION_RE.search(weather_text or "")
    if not match:
        return ""
    return match.group(1).strip().lower()


def _pick_copy(lang: str) -> dict[str, str]:
    return _CARE_COPY.get(lang, _CARE_COPY["en"])


def build_care_advice(weather_text: str, language_text: str | None) -> str:
    """Build concise, practical advice based on parsed weather output."""
    lang = detect_language(language_text)
    copy = _pick_copy(lang)

    temp_c = _extract_temperature_c(weather_text)
    condition = _extract_condition(weather_text)
    tips: list[str] = []

    if temp_c is not None:
        if temp_c >= 36:
            tips.append(copy.get("extreme_hot", copy["very_hot"]))
        elif temp_c >= 33:
            tips.append(copy["very_hot"])
        elif temp_c >= 28:
            tips.append(copy["hot"])
        elif temp_c <= 12:
            tips.append(copy["very_cold"])
        elif temp_c <= 18:
            tips.append(copy["cold"])

    if "storm" in condition:
        tips.append(copy["stormy"])
    elif "rain" in condition or "drizzle" in condition:
        tips.append(copy["rainy"])
    elif "fog" in condition:
        tips.append(copy["foggy"])

    if not tips:
        tips.append(copy["default"])

    # Keep answers compact and practical.
    advice = " ".join(tips[:2])
    return f"{copy['prefix']}: {advice}"


def attach_care_advice(weather_text: str, language_text: str | None) -> str:
    """Append one practical-care line to a weather result."""
    if not weather_text.strip():
        return weather_text
    advice = build_care_advice(weather_text, language_text)
    return f"{weather_text}\n{advice}"


def attach_source(weather_text: str, source_name: str) -> str:
    """Attach source line for transparency."""
    if not weather_text.strip():
        return weather_text
    return f"{weather_text}\nSource: {source_name}"


def infer_weather_request_profile(
    text: str | None,
    *,
    mode: str | None = None,
    hours_ahead_start: int | None = None,
    hours_ahead_end: int | None = None,
) -> tuple[str, int | None, int | None]:
    """Infer whether a weather request needs current, hourly, or daily data."""
    normalized_mode = str(mode or "").strip().lower()
    raw_text = " ".join(str(text or "").strip().lower().split())

    start = hours_ahead_start
    end = hours_ahead_end

    match = _WEATHER_HOURLY_WINDOW_RE.search(raw_text)
    if match:
        try:
            parsed_start = int(match.group(1))
            parsed_end = int(match.group(2))
            start = min(parsed_start, parsed_end)
            end = max(parsed_start, parsed_end)
        except Exception:
            start = start
            end = end
    elif start is None and end is None:
        single_match = _WEATHER_SINGLE_HOURS_RE.search(raw_text)
        if single_match:
            try:
                parsed_end = max(int(single_match.group(1)), 1)
                start = 1
                end = parsed_end
            except Exception:
                start = start
                end = end

    if normalized_mode not in {"current", "hourly", "daily"}:
        if start is not None or end is not None:
            normalized_mode = "hourly"
        elif any(marker in raw_text for marker in _WEATHER_DAILY_MARKERS):
            normalized_mode = "daily"
        elif any(marker in raw_text for marker in _WEATHER_FORECAST_MARKERS):
            normalized_mode = "hourly"
        else:
            normalized_mode = "current"

    if normalized_mode == "hourly":
        start = max(1, int(start or 1))
        end = max(start, int(end or 6))
    else:
        start = None
        end = None

    return normalized_mode, start, end


async def _geocode_openmeteo(
    location: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> tuple[str, float, float] | None:
    encoded = quote_plus(location)
    geo_url = (
        "https://geocoding-api.open-meteo.com/v1/search"
        f"?name={encoded}&count=1&language=en&format=json"
    )
    async def _run(active_client: httpx.AsyncClient) -> tuple[str, float, float] | None:
        geo_response = await active_client.get(geo_url, timeout=_WEATHER_REQUEST_TIMEOUT_SECONDS)
        if geo_response.status_code != 200:
            logger.debug(
                "Weather geocode failed status={} location={}",
                geo_response.status_code,
                location,
            )
            return None

        geo_data = geo_response.json()
        results = geo_data.get("results") or []
        if not results:
            logger.debug("Weather geocode no results for location={}", location)
            return None

        match = results[0]
        lat = float(match["latitude"])
        lon = float(match["longitude"])
        city_name = str(match.get("name", location)).strip() or location
        return city_name, lat, lon

    if client is not None:
        return await _run(client)
    async with _weather_client() as owned_client:
        return await _run(owned_client)


def _weather_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={"User-Agent": "kabot-weather/1.0"},
        follow_redirects=True,
    )


async def fetch_wttr(location: str, format: str = "simple") -> str | None:
    """Fetch weather from wttr.in. Returns None if fails."""
    if format == "png":
        return f"https://wttr.in/{quote_plus(location)}.png"

    wttr_format = _WTTR_FORMATS.get(format)
    if not wttr_format:
        return None

    try:
        encoded = quote_plus(location)
        url = f"https://wttr.in/{encoded}?format={wttr_format}"
        async with _weather_client() as client:
            response = await client.get(url, timeout=_WEATHER_REQUEST_TIMEOUT_SECONDS)
            if response.status_code != 200:
                logger.debug(
                    "Weather wttr failed status={} location={}",
                    response.status_code,
                    location,
                )
                return None
            cleaned = clean_emoji(response.text.strip())
            if not cleaned or _looks_like_wttr_error(cleaned):
                logger.debug("Weather wttr returned non-usable body for location={}", location)
                return None
            return cleaned
    except Exception as exc:
        logger.debug("Weather wttr exception for location={}: {}", location, exc)
        return None


async def fetch_openmeteo(location: str) -> str | None:
    """Fetch weather from Open-Meteo as fallback. Returns None if fails."""
    try:
        async with _weather_client() as client:
            geo = await _geocode_openmeteo(location, client=client)
            if not geo:
                return None
            city_name, lat, lon = geo
            weather_url = (
                "https://api.open-meteo.com/v1/forecast"
                f"?latitude={lat}&longitude={lon}&current_weather=true"
            )
            weather_response = await client.get(weather_url, timeout=_WEATHER_REQUEST_TIMEOUT_SECONDS)
            if weather_response.status_code != 200:
                logger.debug(
                    "Weather forecast failed status={} location={}",
                    weather_response.status_code,
                    location,
                )
                return None

            weather_data = weather_response.json()
            current = weather_data.get("current_weather") or {}
            temp = current.get("temperature")
            code = int(current.get("weathercode", 0))
            condition = _WEATHER_CODE_LABELS.get(code, "[Unknown]")

            if temp is None:
                return None
            return f"{city_name}: {condition} +{temp}C{_format_openmeteo_wind_suffix(current)}"
    except Exception as exc:
        logger.debug("Weather Open-Meteo exception for location={}: {}", location, exc)
        return None


async def fetch_openmeteo_forecast(
    location: str,
    *,
    mode: str = "hourly",
    hours_ahead_start: int | None = None,
    hours_ahead_end: int | None = None,
) -> str | None:
    """Fetch hourly or daily weather forecasts from Open-Meteo."""
    normalized_mode = str(mode or "").strip().lower()
    if normalized_mode not in {"hourly", "daily"}:
        return None

    try:
        async with _weather_client() as client:
            geo = await _geocode_openmeteo(location, client=client)
            if not geo:
                return None
            city_name, lat, lon = geo
            if normalized_mode == "hourly":
                weather_url = (
                    "https://api.open-meteo.com/v1/forecast"
                    f"?latitude={lat}&longitude={lon}"
                    "&hourly=temperature_2m,precipitation_probability,precipitation,weather_code,wind_speed_10m"
                    "&forecast_days=2&timezone=auto"
                )
                response = await client.get(weather_url, timeout=_WEATHER_REQUEST_TIMEOUT_SECONDS)
                if response.status_code != 200:
                    logger.debug(
                        "Weather hourly forecast failed status={} location={}",
                        response.status_code,
                        location,
                    )
                    return None
                payload = response.json()
                hourly = payload.get("hourly") or {}
                temperatures = list(hourly.get("temperature_2m") or [])
                rain_probs = list(hourly.get("precipitation_probability") or [])
                rain_amounts = list(hourly.get("precipitation") or [])
                weather_codes = list(hourly.get("weather_code") or [])
                wind_speeds = list(hourly.get("wind_speed_10m") or [])
                if not temperatures:
                    return None

                start = max(1, int(hours_ahead_start or 1))
                end = max(start, int(hours_ahead_end or 6))
                last_index = min(
                    len(temperatures),
                    len(rain_probs) or len(temperatures),
                    len(rain_amounts) or len(temperatures),
                    len(weather_codes) or len(temperatures),
                    len(wind_speeds) or len(temperatures),
                ) - 1
                if last_index < start:
                    start = 0
                end = min(end, last_index)

                lines = [f"{city_name} forecast (next {start}-{end} hours):"]
                for index in range(start, end + 1):
                    temp = temperatures[index] if index < len(temperatures) else "?"
                    rain_prob = rain_probs[index] if index < len(rain_probs) else "?"
                    rain_amount = rain_amounts[index] if index < len(rain_amounts) else "?"
                    weather_code = int(weather_codes[index]) if index < len(weather_codes) else -1
                    wind_speed = wind_speeds[index] if index < len(wind_speeds) else "?"
                    condition = _WEATHER_CODE_LABELS.get(weather_code, "[Unknown]")
                    lines.append(
                        f"- +{index}h: {condition} {temp}C | Rain: {rain_prob}% ({rain_amount} mm) | Wind: {wind_speed} km/h"
                    )
                return "\n".join(lines)

            weather_url = (
                "https://api.open-meteo.com/v1/forecast"
                f"?latitude={lat}&longitude={lon}"
                "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"
                "&forecast_days=7&timezone=auto"
            )
            response = await client.get(weather_url, timeout=_WEATHER_REQUEST_TIMEOUT_SECONDS)
            if response.status_code != 200:
                logger.debug(
                    "Weather daily forecast failed status={} location={}",
                    response.status_code,
                    location,
                )
                return None
            payload = response.json()
            daily = payload.get("daily") or {}
            dates = list(daily.get("time") or [])
            max_temps = list(daily.get("temperature_2m_max") or [])
            min_temps = list(daily.get("temperature_2m_min") or [])
            rain_probs = list(daily.get("precipitation_probability_max") or [])
            weather_codes = list(daily.get("weather_code") or [])
            if not dates:
                return None
            lines = [f"{city_name} forecast:"]
            for index in range(0, min(3, len(dates))):
                condition = _WEATHER_CODE_LABELS.get(int(weather_codes[index]), "[Unknown]")
                lines.append(
                    f"- {dates[index]}: {condition}, {min_temps[index]}-{max_temps[index]}C, rain {rain_probs[index]}%"
                )
            return "\n".join(lines)
    except Exception as exc:
        logger.debug("Weather Open-Meteo forecast exception for location={}: {}", location, exc)
        return None


class WeatherTool(Tool):
    """Get current weather and forecast for a location."""

    name = "weather"
    description = (
        "Get CURRENT weather or short-term forecast information for a location using Open-Meteo as the primary source "
        "with wttr.in fallback "
        "(no API key required). ALWAYS use this tool when the user asks about weather, "
        "temperature, rain chance, forecast, or climate conditions. Do not use training data - always fetch "
        "real-time data from this tool. IMPORTANT: The tool output includes a care "
        "advice/suggestion (e.g., 'Saran: ...'). You MUST include this advice in your response."
    )
    parameters = {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": (
                    "City name, airport code, or location "
                    "(e.g., 'London', 'JFK', 'Cilacap', 'Kyoto')"
                ),
            },
            "format": {
                "type": "string",
                "description": (
                    "Output format: 'simple' (compact), 'full' (detailed), or 'png' (image URL)"
                ),
                "enum": ["simple", "full", "png"],
                "default": "simple",
            },
            "mode": {
                "type": "string",
                "description": "Weather mode: 'current', 'hourly', or 'daily'. If omitted, infer from the user request.",
                "enum": ["current", "hourly", "daily"],
            },
            "hours_ahead_start": {
                "type": "integer",
                "description": "Optional starting hour offset for hourly forecasts, e.g. 3 for +3h.",
                "minimum": 0,
            },
            "hours_ahead_end": {
                "type": "integer",
                "description": "Optional ending hour offset for hourly forecasts, e.g. 6 for +6h.",
                "minimum": 0,
            },
        },
        "required": ["location"],
    }

    async def execute(
        self,
        location: str,
        format: str = "simple",
        mode: str | None = None,
        hours_ahead_start: int | None = None,
        hours_ahead_end: int | None = None,
        context_text: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Fetch weather for the given location."""
        candidates = _weather_location_variants(location)
        if not candidates:
            return i18n_t("weather.need_location", context_text or location)

        normalized = candidates[0]
        request_profile = context_text or location
        resolved_mode, resolved_hours_start, resolved_hours_end = infer_weather_request_profile(
            request_profile,
            mode=mode,
            hours_ahead_start=hours_ahead_start,
            hours_ahead_end=hours_ahead_end,
        )

        try:
            pending_wttr_result: str | None = None
            for candidate in candidates:
                if resolved_mode in {"hourly", "daily"} and format == "simple":
                    forecast_result = await fetch_openmeteo_forecast(
                        candidate,
                        mode=resolved_mode,
                        hours_ahead_start=resolved_hours_start,
                        hours_ahead_end=resolved_hours_end,
                    )
                    if forecast_result:
                        _persist_user_weather_alias(
                            normalized,
                            _extract_weather_result_location(forecast_result),
                        )
                        result = attach_source(forecast_result, f"Open-Meteo ({resolved_mode} forecast)")
                        return attach_care_advice(result, context_text or location)
                if format == "simple":
                    # Run providers in parallel to reduce tail latency on slow networks.
                    openmeteo_result, wttr_result = await asyncio.gather(
                        fetch_openmeteo(candidate),
                        fetch_wttr(candidate, format),
                        return_exceptions=False,
                    )
                    if openmeteo_result:
                        _persist_user_weather_alias(
                            normalized,
                            _extract_weather_result_location(openmeteo_result),
                        )
                        result = attach_source(openmeteo_result, "Open-Meteo (current_weather)")
                        return attach_care_advice(result, context_text or location)
                    if wttr_result and not str(wttr_result).startswith("Error"):
                        pending_wttr_result = str(wttr_result)
                else:
                    result = await fetch_wttr(candidate, format)
                    if result and not result.startswith("Error"):
                        _persist_user_weather_alias(
                            normalized,
                            _extract_weather_result_location(result),
                        )
                        if format == "png":
                            return result
                        result = attach_source(result, "wttr.in")
                        return attach_care_advice(result, context_text or location)

            if pending_wttr_result:
                _persist_user_weather_alias(
                    normalized,
                    _extract_weather_result_location(str(pending_wttr_result)),
                )
                result = attach_source(str(pending_wttr_result), "wttr.in")
                return attach_care_advice(result, context_text or location)

            return i18n_t("weather.fetch_failed", context_text or location, location=normalized)
        except Exception as exc:
            return i18n_t("weather.error", context_text or location, error=str(exc))

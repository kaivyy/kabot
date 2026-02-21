"""Weather tool for fetching weather information."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote_plus

import httpx
from loguru import logger

from kabot.agent.cron_fallback_nlp import extract_weather_location
from kabot.agent.fallback_i18n import detect_language
from kabot.agent.tools.base import Tool

_WTTR_FORMATS = {
    "simple": "%l:+%c+%t",
    "full": "%l:+%c+%t+%h+%w",
}

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

    candidate = extract_weather_location(raw) or raw
    candidate = re.sub(
        r"(?i)\b(?:right now|saat ini|hari ini|today|sekarang|now|berapa|how much)\b",
        " ",
        candidate,
    )
    candidate = re.sub(
        r"(?i)\b(?:kota|city|kabupaten|regency|district|county|municipality|province|provinsi)\b$",
        " ",
        candidate,
    )
    candidate = re.sub(r"\s+", " ", candidate).strip(" .,!?:;")
    return candidate or raw


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
            response = await client.get(url, timeout=8.0)
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
        encoded = quote_plus(location)
        geo_url = (
            "https://geocoding-api.open-meteo.com/v1/search"
            f"?name={encoded}&count=1&language=en&format=json"
        )
        async with _weather_client() as client:
            geo_response = await client.get(geo_url, timeout=8.0)
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
            lat = match["latitude"]
            lon = match["longitude"]
            city_name = str(match.get("name", location)).strip() or location

            weather_url = (
                "https://api.open-meteo.com/v1/forecast"
                f"?latitude={lat}&longitude={lon}&current_weather=true"
            )
            weather_response = await client.get(weather_url, timeout=8.0)
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
            return f"{city_name}: {condition} +{temp}C"
    except Exception as exc:
        logger.debug("Weather Open-Meteo exception for location={}: {}", location, exc)
        return None


class WeatherTool(Tool):
    """Get current weather and forecast for a location."""

    name = "weather"
    description = (
        "Get CURRENT weather information for a location using wttr.in or Open-Meteo "
        "(no API key required). ALWAYS use this tool when the user asks about weather, "
        "temperature, or climate conditions. Do not use training data - always fetch "
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
        },
        "required": ["location"],
    }

    async def execute(
        self,
        location: str,
        format: str = "simple",
        context_text: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Fetch weather for the given location."""
        normalized = normalize_location(location)
        if not normalized:
            return "Error: Could not determine weather location. Please provide a city name."

        try:
            if format == "simple":
                # Prefer Open-Meteo for structured and more stable current-weather data.
                result = await fetch_openmeteo(normalized)
                if result:
                    result = attach_source(result, "Open-Meteo (current_weather)")
                    return attach_care_advice(result, context_text or location)
                result = await fetch_wttr(normalized, format)
                if result and not result.startswith("Error"):
                    result = attach_source(result, "wttr.in")
                    return attach_care_advice(result, context_text or location)
            else:
                result = await fetch_wttr(normalized, format)
                if result and not result.startswith("Error"):
                    if format == "png":
                        return result
                    result = attach_source(result, "wttr.in")
                    return attach_care_advice(result, context_text or location)

            return (
                f"Error: Could not fetch weather for {normalized}. "
                "Please try a different city name."
            )
        except Exception as exc:
            return f"Error fetching weather: {str(exc)}"

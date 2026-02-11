"""Weather tool for fetching weather information."""

import httpx
import re
from typing import Any

from kabot.agent.tools.base import Tool


def clean_emoji(text: str) -> str:
    """Remove or replace emoji characters with text equivalents for Windows compatibility."""
    # Weather emoji mapping to text
    weather_map = {
        '☀️': '[Sunny]',
        '☀': '[Sunny]',
        '🌤️': '[Partly Cloudy]',
        '🌤': '[Partly Cloudy]',
        '⛅': '[Partly Cloudy]',
        '🌥️': '[Cloudy]',
        '🌥': '[Cloudy]',
        '☁️': '[Cloudy]',
        '☁': '[Cloudy]',
        '🌦️': '[Rainy]',
        '🌦': '[Rainy]',
        '🌧️': '[Rainy]',
        '🌧': '[Rainy]',
        '🌩️': '[Stormy]',
        '🌩': '[Stormy]',
        '⛈️': '[Stormy]',
        '⛈': '[Stormy]',
        '❄️': '[Snowy]',
        '❄': '[Snowy]',
        '🌨️': '[Snowy]',
        '🌨': '[Snowy]',
        '🌫️': '[Foggy]',
        '🌫': '[Foggy]',
        '🌙': '[Clear Night]',
        '☀': '[Clear]',
    }

    # Replace known weather emojis
    for emoji, text_equiv in weather_map.items():
        text = text.replace(emoji, text_equiv)

    # Remove any remaining emojis (unicode characters above basic multilingual plane)
    text = re.sub(r'[^\x00-\x7F\u2000-\u206F\u2190-\u21FF]', '', text)

    return text.strip()


async def fetch_wttr(location: str, format: str = "simple") -> str | None:
    """Fetch weather from wttr.in. Returns None if fails."""
    try:
        clean_location = location.replace(" ", "+")

        if format == "simple":
            url = f"https://wttr.in/{clean_location}?format=%l:+%c+%t"
        elif format == "full":
            url = f"https://wttr.in/{clean_location}?format=%l:+%c+%t+%h+%w"
        else:
            return None

        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=8.0)
            if response.status_code == 200:
                return clean_emoji(response.text.strip())
    except Exception:
        pass
    return None


async def fetch_openmeteo(location: str) -> str | None:
    """Fetch weather from Open-Meteo as fallback. Returns None if fails."""
    try:
        # First, geocode the location to get lat/lon
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={location.replace(' ', '+')}&count=1&language=en&format=json"

        async with httpx.AsyncClient() as client:
            geo_response = await client.get(geo_url, timeout=8.0)
            if geo_response.status_code != 200:
                return None

            geo_data = geo_response.json()
            if not geo_data.get('results'):
                return None

            result = geo_data['results'][0]
            lat = result['latitude']
            lon = result['longitude']
            city_name = result.get('name', location)

            # Now fetch weather
            weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
            weather_response = await client.get(weather_url, timeout=8.0)

            if weather_response.status_code != 200:
                return None

            weather_data = weather_response.json()
            current = weather_data.get('current_weather', {})

            temp = current.get('temperature', '?')
            weather_code = current.get('weathercode', 0)

            # Map weather code to condition
            weather_conditions = {
                0: '[Clear]',
                1: '[Partly Cloudy]',
                2: '[Partly Cloudy]',
                3: '[Cloudy]',
                45: '[Foggy]',
                48: '[Foggy]',
                51: '[Rainy]',
                53: '[Rainy]',
                55: '[Rainy]',
                61: '[Rainy]',
                63: '[Rainy]',
                65: '[Rainy]',
                71: '[Snowy]',
                73: '[Snowy]',
                75: '[Snowy]',
                95: '[Stormy]',
                96: '[Stormy]',
                99: '[Stormy]',
            }

            condition = weather_conditions.get(weather_code, '[Unknown]')
            return f"{city_name}: {condition}   +{temp}C"

    except Exception:
        pass
    return None


class WeatherTool(Tool):
    """Get current weather and forecast for a location."""

    name = "weather"
    description = "Get CURRENT weather information for a location using wttr.in or Open-Meteo (no API key required). ALWAYS use this tool when the user asks about weather, temperature, or climate conditions. Do not use training data - always fetch real-time data from this tool."
    parameters = {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "City name, airport code, or location (e.g., 'London', 'JFK', 'Cilacap', 'Kyoto')"
            },
            "format": {
                "type": "string",
                "description": "Output format: 'simple' (compact), 'full' (detailed), or 'png' (image URL)",
                "enum": ["simple", "full", "png"],
                "default": "simple"
            }
        },
        "required": ["location"]
    }

    async def execute(self, location: str, format: str = "simple", **kwargs: Any) -> str:
        """
        Fetch weather for the given location.

        Args:
            location: Location name or airport code
            format: Output format (simple, full, png)

        Returns:
            Weather information as formatted string
        """
        try:
            # Try wttr.in first
            result = await fetch_wttr(location, format)
            if result and not result.startswith("Error"):
                return result

            # Fallback to Open-Meteo for simple format
            if format == "simple":
                result = await fetch_openmeteo(location)
                if result:
                    return result

            return f"Error: Could not fetch weather for {location}. Please try a different city name."

        except Exception as e:
            return f"Error fetching weather: {str(e)}"

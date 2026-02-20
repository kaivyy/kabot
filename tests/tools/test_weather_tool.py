from unittest.mock import AsyncMock

import pytest

import kabot.agent.tools.weather as weather_module
from kabot.agent.tools.weather import WeatherTool


@pytest.mark.asyncio
async def test_weather_tool_normalizes_noisy_location_before_fetch(monkeypatch):
    wttr_mock = AsyncMock(return_value="Cilacap: [Rainy] +32C")
    openmeteo_mock = AsyncMock(return_value="Cilacap: [Cloudy] +31C")

    monkeypatch.setattr(weather_module, "fetch_wttr", wttr_mock)
    monkeypatch.setattr(weather_module, "fetch_openmeteo", openmeteo_mock)

    tool = WeatherTool()
    result = await tool.execute(location="tanggal berapa dan suhu di Cilacap berapa sekarang")

    assert "Cilacap" in result
    assert "[Cloudy]" in result
    openmeteo_mock.assert_awaited_once_with("Cilacap")
    wttr_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_weather_tool_uses_openmeteo_fallback_with_normalized_location(monkeypatch):
    wttr_mock = AsyncMock(return_value=None)
    openmeteo_mock = AsyncMock(return_value="Cilacap: [Cloudy] +31C")

    monkeypatch.setattr(weather_module, "fetch_wttr", wttr_mock)
    monkeypatch.setattr(weather_module, "fetch_openmeteo", openmeteo_mock)

    tool = WeatherTool()
    result = await tool.execute(location="suhu di cilacap sekarang")

    assert "Cilacap" in result
    assert "source: open-meteo" in result.lower()
    openmeteo_mock.assert_awaited_once_with("Cilacap")
    wttr_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_weather_tool_adds_hot_weather_care_advice_in_indonesian(monkeypatch):
    wttr_mock = AsyncMock(return_value=None)
    openmeteo_mock = AsyncMock(return_value="Cilacap: [Clear] +34C")

    monkeypatch.setattr(weather_module, "fetch_wttr", wttr_mock)
    monkeypatch.setattr(weather_module, "fetch_openmeteo", openmeteo_mock)

    tool = WeatherTool()
    result = await tool.execute(
        location="berapa suhu di cilacap sekarang",
        context_text="berapa suhu di cilacap sekarang",
    )

    assert "Cilacap" in result
    assert "sunscreen" in result.lower()
    assert "air" in result.lower()


@pytest.mark.asyncio
async def test_weather_tool_adds_cold_weather_care_advice_in_english(monkeypatch):
    wttr_mock = AsyncMock(return_value=None)
    openmeteo_mock = AsyncMock(return_value="London: [Cloudy] +10C")

    monkeypatch.setattr(weather_module, "fetch_wttr", wttr_mock)
    monkeypatch.setattr(weather_module, "fetch_openmeteo", openmeteo_mock)

    tool = WeatherTool()
    result = await tool.execute(
        location="temperature in london",
        context_text="what is the temperature in london now",
    )

    assert "London" in result
    assert "jacket" in result.lower()


@pytest.mark.asyncio
async def test_weather_tool_adds_extreme_heat_warning_in_english(monkeypatch):
    wttr_mock = AsyncMock(return_value=None)
    openmeteo_mock = AsyncMock(return_value="Jakarta: [Clear] +38C")

    monkeypatch.setattr(weather_module, "fetch_wttr", wttr_mock)
    monkeypatch.setattr(weather_module, "fetch_openmeteo", openmeteo_mock)

    tool = WeatherTool()
    result = await tool.execute(
        location="temperature in jakarta",
        context_text="temperature in jakarta right now",
    )

    assert "Jakarta" in result
    assert "heatstroke" in result.lower()


@pytest.mark.asyncio
async def test_weather_tool_strips_city_suffix_before_openmeteo(monkeypatch):
    wttr_mock = AsyncMock(return_value=None)
    openmeteo_mock = AsyncMock(return_value="Cilacap: [Clear] +29C")

    monkeypatch.setattr(weather_module, "fetch_wttr", wttr_mock)
    monkeypatch.setattr(weather_module, "fetch_openmeteo", openmeteo_mock)

    tool = WeatherTool()
    result = await tool.execute(location="berapa suhu di cilacap kota sekarang")

    assert "Cilacap" in result
    openmeteo_mock.assert_awaited_once_with("Cilacap")
    wttr_mock.assert_not_awaited()

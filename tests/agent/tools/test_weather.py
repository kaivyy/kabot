import pytest

import kabot.agent.tools.weather as weather_mod


def test_weather_location_variants_include_compact_city_fallback():
    variants = weather_mod._weather_location_variants("Purwokerto Jawa Tengah")
    assert variants[0] == "Purwokerto Jawa Tengah"
    assert "Purwokerto, Jawa Tengah" in variants
    assert "Purwokerto" in variants


def test_weather_location_variants_normalize_plus_joined_directional_location():
    variants = weather_mod._weather_location_variants("Cilacap+Utara")
    assert variants[0] == "Cilacap Utara"
    assert "Cilacap, Utara" in variants
    assert "Cilacap" in variants


@pytest.mark.asyncio
async def test_weather_prefers_openmeteo_from_later_location_variant_before_wttr(monkeypatch):
    async def fake_openmeteo(location: str) -> str | None:
        if location == "Cilacap":
            return "Cilacap: [Cloudy] +24.8C | Wind: 3.3 km/h @ 13°"
        return None

    async def fake_wttr(location: str, format: str = "simple") -> str | None:
        if location == "Cilacap Utara":
            return "Cilacap,+Utara: [Rainy] +25C"
        return None

    monkeypatch.setattr(weather_mod, "fetch_openmeteo", fake_openmeteo)
    monkeypatch.setattr(weather_mod, "fetch_wttr", fake_wttr)

    tool = weather_mod.WeatherTool()
    result = await tool.execute(location="Cilacap+Utara", format="simple")

    assert "Source: Open-Meteo (current_weather)" in result
    assert "Cilacap: [Cloudy]" in result
    assert "wttr.in" not in result


def test_weather_location_variants_include_non_latin_alias_fallbacks():
    tokyo_variants = weather_mod._weather_location_variants("東京")
    beijing_variants = weather_mod._weather_location_variants("北京今天怎么样")
    bangkok_variants = weather_mod._weather_location_variants("กรุงเทพ")

    assert "Tokyo" in tokyo_variants
    assert "Beijing" in beijing_variants
    assert "Bangkok" in bangkok_variants


def test_weather_location_variants_include_user_alias_file(monkeypatch, tmp_path):
    alias_file = tmp_path / "weather_aliases.json"
    alias_file.write_text(
        '{"aliases": {"大阪": ["Osaka"]}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("KABOT_WEATHER_ALIASES_PATH", str(alias_file))

    variants = weather_mod._weather_location_variants("大阪")

    assert "Osaka" in variants


@pytest.mark.asyncio
async def test_weather_execute_uses_fallback_variant_when_primary_lookup_fails(monkeypatch):
    attempted_openmeteo: list[str] = []
    attempted_wttr: list[str] = []

    async def fake_openmeteo(location: str) -> str | None:
        attempted_openmeteo.append(location)
        if location == "Purwokerto":
            return "Purwokerto: [Cloudy] +28C"
        return None

    async def fake_wttr(location: str, format: str = "simple") -> str | None:
        attempted_wttr.append(location)
        return None

    monkeypatch.setattr(weather_mod, "fetch_openmeteo", fake_openmeteo)
    monkeypatch.setattr(weather_mod, "fetch_wttr", fake_wttr)

    tool = weather_mod.WeatherTool()
    result = await tool.execute(
        location="Purwokerto Jawa Tengah",
        format="simple",
        context_text="cek suhu purwokerto jawa tengah sekarang",
    )

    assert "Purwokerto: [Cloudy] +28C" in result
    assert "Source: Open-Meteo (current_weather)" in result
    assert "Purwokerto Jawa Tengah" in attempted_openmeteo
    assert "Purwokerto" in attempted_openmeteo
    assert "Purwokerto Jawa Tengah" in attempted_wttr
    assert "Purwokerto" in attempted_wttr


@pytest.mark.asyncio
async def test_weather_execute_uses_transliterated_alias_when_non_latin_lookup_fails(monkeypatch):
    attempted_openmeteo: list[str] = []
    attempted_wttr: list[str] = []

    async def fake_openmeteo(location: str) -> str | None:
        attempted_openmeteo.append(location)
        if location == "Tokyo":
            return "Tokyo: [Cloudy] +12C | Wind: 14.0 km/h @ 90deg"
        return None

    async def fake_wttr(location: str, format: str = "simple") -> str | None:
        attempted_wttr.append(location)
        return None

    monkeypatch.setattr(weather_mod, "fetch_openmeteo", fake_openmeteo)
    monkeypatch.setattr(weather_mod, "fetch_wttr", fake_wttr)

    tool = weather_mod.WeatherTool()
    result = await tool.execute(
        location="東京",
        format="simple",
        context_text="東京の天気どう？",
    )

    assert "Tokyo: [Cloudy] +12C" in result
    assert "東京" in attempted_openmeteo
    assert "Tokyo" in attempted_openmeteo
    assert "東京" in attempted_wttr
    assert "Tokyo" in attempted_wttr


@pytest.mark.asyncio
async def test_weather_execute_learns_alias_file_and_reuses_it(monkeypatch, tmp_path):
    alias_file = tmp_path / "weather_aliases.json"
    monkeypatch.setenv("KABOT_WEATHER_ALIASES_PATH", str(alias_file))

    attempted_openmeteo: list[str] = []

    async def fake_openmeteo_first(location: str) -> str | None:
        attempted_openmeteo.append(location)
        if location == "大阪":
            return "Osaka: [Cloudy] +22C"
        return None

    async def fake_openmeteo_second(location: str) -> str | None:
        attempted_openmeteo.append(location)
        if location == "Osaka":
            return "Osaka: [Cloudy] +22C"
        return None

    async def fake_wttr(location: str, format: str = "simple") -> str | None:
        return None

    monkeypatch.setattr(weather_mod, "fetch_wttr", fake_wttr)
    monkeypatch.setattr(weather_mod, "fetch_openmeteo", fake_openmeteo_first)

    tool = weather_mod.WeatherTool()
    first = await tool.execute(
        location="大阪",
        format="simple",
        context_text="大阪の天気どう？",
    )

    assert "Osaka: [Cloudy] +22C" in first
    assert alias_file.exists()
    assert '"大阪"' in alias_file.read_text(encoding="utf-8")
    assert '"Osaka"' in alias_file.read_text(encoding="utf-8")

    attempted_openmeteo.clear()
    monkeypatch.setattr(weather_mod, "fetch_openmeteo", fake_openmeteo_second)

    second = await tool.execute(
        location="大阪",
        format="simple",
        context_text="大阪の天気どう？",
    )

    assert "Osaka: [Cloudy] +22C" in second
    assert "大阪" in attempted_openmeteo
    assert "Osaka" in attempted_openmeteo

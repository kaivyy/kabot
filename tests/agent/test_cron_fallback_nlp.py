from kabot.agent.cron_fallback_nlp import extract_weather_location


def test_extract_weather_location_handles_mixed_datetime_query():
    query = "tanggal berapa dan suhu di Cilacap berapa sekarang"
    assert extract_weather_location(query) == "Cilacap"


def test_extract_weather_location_handles_english_right_now_phrase():
    query = "weather in Bangkok right now"
    assert extract_weather_location(query) == "Bangkok"


def test_extract_weather_location_strips_city_descriptor():
    query = "berapa suhu di cilacap kota sekarang"
    assert extract_weather_location(query) == "Cilacap"

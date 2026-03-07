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


def test_extract_weather_location_handles_indonesian_conversational_prefix():
    query = "gimana suhu purwokerto hari ini"
    assert extract_weather_location(query) == "Purwokerto"


def test_extract_weather_location_handles_kalau_prefix():
    query = "kalau suhu cilacap berapa sekarang"
    assert extract_weather_location(query) == "Cilacap"


def test_extract_weather_location_handles_confirmation_then_weather_query():
    query = "ya coba cek suhu purwokerto jawa tengah"
    assert extract_weather_location(query) == "Purwokerto Jawa Tengah"


def test_extract_weather_location_handles_reasoning_clause_after_question():
    query = "kenapa gabisa cek suhu purwokerto? kan udah pasti Banyumas jawa tengah"
    assert extract_weather_location(query) == "Purwokerto"


def test_extract_weather_location_handles_degree_phrasing_without_weather_word():
    query = "purwokerto berapa derajat sekarang"
    assert extract_weather_location(query) == "Purwokerto"


def test_extract_weather_location_handles_non_latin_city_name():
    query = "cuaca di 東京 sekarang"
    assert extract_weather_location(query) == "東京"
def test_extract_weather_location_handles_attached_indonesian_di_prefix():
    query = "dibandung berangin apa ga"
    assert extract_weather_location(query) == "Bandung"


def test_extract_weather_location_handles_japanese_compact_weather_question():
    query = "東京の天気どう？"
    assert extract_weather_location(query) == "東京"


def test_extract_weather_location_handles_chinese_compact_weather_question():
    query = "北京今天天气怎么样？"
    assert extract_weather_location(query) == "北京"


def test_extract_weather_location_handles_thai_compact_weather_question():
    query = "อากาศกรุงเทพวันนี้เป็นยังไง"
    assert extract_weather_location(query) == "กรุงเทพ"

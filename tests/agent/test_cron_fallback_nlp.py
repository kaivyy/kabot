from kabot.agent.cron_fallback_nlp import extract_weather_location, required_tool_for_query


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


def test_extract_weather_location_rejects_wind_speed_measurement_as_location():
    query = "kecepatan angin 4.4km/h?"
    assert extract_weather_location(query) is None


def test_extract_weather_location_rejects_long_quoted_health_context_as_location():
    query = """Iya, untuk laki-laki saat lari, HR (detak jantung) sering di atas 160 bpm itu belum tentu berbahaya.

Perhatikan tidur, hidrasi, kafein, suhu cuaca (semua bisa bikin HR naik).

dari sini hitung hr zona saya umur 25 tahun"""
    assert extract_weather_location(query) is None


def test_extract_weather_location_rejects_forecast_keyword_without_real_location():
    assert extract_weather_location("prediksi 3-6 jam ke depan") is None


def test_extract_weather_location_handles_japanese_compact_weather_question():
    query = "東京の天気どう？"
    assert extract_weather_location(query) == "東京"


def test_extract_weather_location_handles_chinese_compact_weather_question():
    query = "北京今天天气怎么样？"
    assert extract_weather_location(query) == "北京"


def test_extract_weather_location_handles_thai_compact_weather_question():
    query = "อากาศกรุงเทพวันนี้เป็นยังไง"
    assert extract_weather_location(query) == "กรุงเทพ"

def test_required_tool_for_query_handles_runtime_server_phrase():
    tool = required_tool_for_query(
        question="cek runtime server saat ini",
        has_weather_tool=False,
        has_cron_tool=False,
        has_system_info_tool=False,
        has_cleanup_tool=False,
        has_speedtest_tool=False,
        has_process_memory_tool=False,
        has_stock_tool=False,
        has_stock_analysis_tool=False,
        has_crypto_tool=False,
        has_server_monitor_tool=True,
        has_web_search_tool=False,
        has_read_file_tool=False,
        has_list_dir_tool=False,
        has_check_update_tool=False,
        has_system_update_tool=False,
    )
    assert tool == "server_monitor"


def test_required_tool_for_query_routes_tolong_ingat_to_save_memory():
    tool = required_tool_for_query(
        question="tolong ingat ini ya",
        has_weather_tool=False,
        has_cron_tool=False,
        has_system_info_tool=False,
        has_cleanup_tool=False,
        has_speedtest_tool=False,
        has_process_memory_tool=False,
        has_save_memory_tool=True,
        has_stock_tool=True,
        has_stock_analysis_tool=True,
        has_crypto_tool=True,
        has_server_monitor_tool=False,
        has_web_search_tool=False,
        has_read_file_tool=False,
        has_list_dir_tool=False,
        has_check_update_tool=False,
        has_system_update_tool=False,
    )
    assert tool == "save_memory"

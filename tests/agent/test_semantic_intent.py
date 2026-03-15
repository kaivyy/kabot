from kabot.agent.semantic_intent import arbitrate_semantic_intent


def test_semantic_intent_detects_not_web_search_chat_correction_as_meta_feedback():
    hint = arbitrate_semantic_intent(
        "sekarang senin woi, ini bukan web search, cuma koreksi chat kita. ngerti?",
        parser_tool=None,
    )

    assert hint.kind == "meta_feedback"
    assert hint.clear_pending is True


def test_semantic_intent_reuses_weather_context_for_japanese_wind_followup():
    hint = arbitrate_semantic_intent(
        "風は強い？",
        parser_tool=None,
        last_tool_context={"tool": "weather", "location": "東京"},
    )

    assert hint.required_tool == "weather"
    assert "東京" in str(hint.required_tool_query)


def test_semantic_intent_detects_japanese_weather_question_with_location():
    hint = arbitrate_semantic_intent(
        "東京の天気どう？",
        parser_tool=None,
    )

    assert hint.kind == "weather_query"
    assert hint.required_tool is None


def test_semantic_intent_reuses_weather_context_for_chinese_wind_followup():
    hint = arbitrate_semantic_intent(
        "风大吗？",
        parser_tool=None,
        last_tool_context={"tool": "weather", "location": "北京"},
    )

    assert hint.required_tool == "weather"
    assert "北京" in str(hint.required_tool_query)


def test_semantic_intent_prefers_clean_weather_location_over_previous_source_blob():
    hint = arbitrate_semantic_intent(
        "风大吗？",
        parser_tool=None,
        last_tool_context={
            "tool": "weather",
            "location": "北京",
            "source": "北京今天天气怎么样？",
        },
    )

    assert hint.required_tool == "weather"
    assert str(hint.required_tool_query).startswith("北京 ")


def test_semantic_intent_reuses_weather_context_for_thai_wind_followup():
    hint = arbitrate_semantic_intent(
        "ลมแรงไหม",
        parser_tool=None,
        last_tool_context={"tool": "weather", "location": "กรุงเทพ"},
    )

    assert hint.required_tool == "weather"
    assert "กรุงเทพ" in str(hint.required_tool_query)


def test_semantic_intent_reuses_stock_context_for_relaxed_idr_followup():
    hint = arbitrate_semantic_intent(
        "kalau dirupiahkan sekarang berapa?",
        parser_tool=None,
        last_tool_context={"tool": "stock", "symbol": "MSFT", "source": "microsoft"},
    )

    assert hint.required_tool == "stock"
    assert "MSFT" in str(hint.required_tool_query)


def test_semantic_intent_reuses_stock_context_for_trend_followup():
    hint = arbitrate_semantic_intent(
        "trend nya naik?",
        parser_tool=None,
        pending_followup_tool="stock",
        pending_followup_source="kalau saham apple berapa sekarang",
        last_tool_context={"tool": "stock", "symbol": "AAPL", "source": "apple"},
    )

    assert hint.required_tool == "stock_analysis"
    assert "apple" in str(hint.required_tool_query).lower()


def test_semantic_intent_keeps_weather_metric_interpretation_ai_driven():
    hint = arbitrate_semantic_intent(
        "kecepatan angin 4.4km/h?",
        parser_tool="weather",
        pending_followup_tool="weather",
        pending_followup_source="cuaca cilacap sekarang",
        last_tool_context={
            "tool": "weather",
            "location": "Cilacap",
            "source": "cuaca cilacap sekarang",
        },
    )

    assert hint.kind == "weather_metric_interpretation"
    assert hint.required_tool is None


def test_semantic_intent_keeps_weather_commentary_ai_driven():
    hint = arbitrate_semantic_intent(
        "suhu purwokerto lumayan hangat ya",
        parser_tool="weather",
        pending_followup_tool="weather",
        pending_followup_source="suhu purwokerto sekarang berapa",
        last_tool_context={
            "tool": "weather",
            "location": "Purwokerto",
            "source": "suhu purwokerto sekarang berapa",
        },
    )

    assert hint.kind == "weather_commentary"
    assert hint.required_tool is None


def test_semantic_intent_keeps_weather_source_followup_ai_driven():
    hint = arbitrate_semantic_intent(
        "wttr.in",
        parser_tool=None,
        pending_followup_tool="weather",
        pending_followup_source="suhu purwokerto sekarang",
        last_tool_context={
            "tool": "weather",
            "location": "Purwokerto",
            "source": "suhu purwokerto sekarang",
        },
    )

    assert hint.kind == "weather_source_followup"
    assert hint.required_tool is None


def test_semantic_intent_does_not_use_parser_tool_alone_for_weather_source_followup():
    hint = arbitrate_semantic_intent(
        "wttr.in",
        parser_tool="weather",
        pending_followup_tool=None,
        pending_followup_source="",
        last_tool_context=None,
    )

    assert hint.kind == "none"
    assert hint.required_tool is None


def test_semantic_intent_does_not_use_parser_tool_alone_for_weather_commentary():
    hint = arbitrate_semantic_intent(
        "lumayan hangat ya",
        parser_tool="weather",
        pending_followup_tool=None,
        pending_followup_source="",
        last_tool_context=None,
    )

    assert hint.kind == "none"
    assert hint.required_tool is None


def test_semantic_intent_clears_weather_parser_for_quoted_hr_zone_request():
    hint = arbitrate_semantic_intent(
        """Iya, untuk laki-laki saat lari, HR (detak jantung) sering di atas 160 bpm itu belum tentu berbahaya.

Perhatikan tidur, hidrasi, kafein, suhu cuaca (semua bisa bikin HR naik).

dari sini hitung hr zona saya umur 25 tahun""",
        parser_tool="weather",
    )

    assert hint.kind == "advice_turn"
    assert hint.required_tool is None


def test_semantic_intent_clears_stale_parser_tool_for_memory_recall_turn():
    hint = arbitrate_semantic_intent(
        "what name did you store for me?",
        parser_tool="stock",
    )

    assert hint.kind == "memory_recall"
    assert hint.required_tool is None


def test_semantic_intent_treats_prior_decision_recall_as_memory_recall_turn():
    hint = arbitrate_semantic_intent(
        "what did we decide earlier?",
        parser_tool="weather",
    )

    assert hint.kind == "memory_recall"
    assert hint.required_tool is None

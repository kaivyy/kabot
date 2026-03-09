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

    assert hint.required_tool == "weather"
    assert "東京" in str(hint.required_tool_query)


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

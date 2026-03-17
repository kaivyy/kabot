from kabot.agent.semantic_intent import arbitrate_semantic_intent


def test_semantic_intent_detects_not_web_search_chat_correction_as_meta_feedback():
    hint = arbitrate_semantic_intent(
        "not web search, just a chat correction",
        parser_tool=None,
    )

    assert hint.kind == "meta_feedback"
    assert hint.clear_pending is True


def test_semantic_intent_ignores_weather_followup_routing_and_leaves_that_to_runtime():
    hint = arbitrate_semantic_intent(
        "風は強い？",
        parser_tool=None,
        last_tool_context={"tool": "weather", "location": "東京"},
    )

    assert hint.kind == "none"
    assert hint.required_tool is None


def test_semantic_intent_ignores_fresh_weather_questions_without_memory_or_meta_signal():
    hint = arbitrate_semantic_intent(
        "東京の天気どう？",
        parser_tool=None,
    )

    assert hint.kind == "none"
    assert hint.required_tool is None


def test_semantic_intent_ignores_stock_conversion_followup_routing():
    hint = arbitrate_semantic_intent(
        "if you convert it to idr now, how much is it?",
        parser_tool=None,
        last_tool_context={"tool": "stock", "symbol": "MSFT", "source": "microsoft"},
    )

    assert hint.kind == "none"
    assert hint.required_tool is None


def test_semantic_intent_ignores_stock_trend_followup_routing():
    hint = arbitrate_semantic_intent(
        "trend nya naik?",
        parser_tool=None,
        pending_followup_tool="stock",
        pending_followup_source="kalau saham apple berapa sekarang",
        last_tool_context={"tool": "stock", "symbol": "AAPL", "source": "apple"},
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

    assert hint.kind == "none"
    assert hint.required_tool is None


def test_semantic_intent_leaves_memory_recall_to_stateful_runtime_classifier():
    hint = arbitrate_semantic_intent(
        "what name did you store for me?",
        parser_tool="stock",
    )

    assert hint.kind == "none"
    assert hint.required_tool is None


def test_semantic_intent_does_not_lexically_route_prior_decision_recall():
    hint = arbitrate_semantic_intent(
        "what did we decide earlier?",
        parser_tool="weather",
    )

    assert hint.kind == "none"
    assert hint.required_tool is None

from kabot.agent.language.lexicon import REMINDER_TERMS, WEATHER_TERMS


def test_lexicon_contains_core_multilingual_terms():
    assert "remind" in REMINDER_TERMS
    assert "ingatkan" in REMINDER_TERMS
    assert "提醒" in REMINDER_TERMS
    assert "weather" in WEATHER_TERMS
    assert "cuaca" in WEATHER_TERMS
    assert "天气" in WEATHER_TERMS

from kabot.i18n.catalog import tr
from kabot.i18n.locale import detect_locale


def test_detect_locale_defaults_to_en():
    assert detect_locale("") == "en"


def test_detect_locale_for_malay_markers():
    assert detect_locale("tolong set peringatan esok") == "ms"


def test_catalog_falls_back_to_english_when_locale_missing():
    message = tr("weather.need_location", locale="de")
    assert "location" in message.lower()

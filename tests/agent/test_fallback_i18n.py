from kabot.agent.fallback_i18n import detect_language, t


def test_detect_language_supports_multiple_languages():
    assert detect_language("please remind me in 2 minutes") == "en"
    assert detect_language("tolong ingatkan saya 2 menit lagi") == "id"
    assert detect_language("jadual kerja syif saya esok") == "ms"
    assert detect_language("ช่วยเตือนฉันอีก 2 นาที") == "th"
    assert detect_language("请两分钟后提醒我吃饭") == "zh"


def test_translation_uses_input_language_for_fallback_messages():
    assert "reminder time" in t("cron_time_unclear", "please remind me tomorrow").lower()
    assert "waktu pengingat" in t("cron_time_unclear", "tolong ingatkan saya besok").lower()
    assert "masa peringatan" in t("cron_time_unclear", "tolong tetapkan peringatan saya").lower()
    assert "เวลาการเตือน" in t("cron_time_unclear", "ช่วยเตือนฉันหน่อย")
    assert "提醒时间" in t("cron_time_unclear", "请提醒我")

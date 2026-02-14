from kabot.cron.delivery import infer_delivery

def test_whatsapp_session():
    result = infer_delivery("whatsapp:628123456")
    assert result == {"channel": "whatsapp", "to": "628123456"}

def test_telegram_session():
    result = infer_delivery("telegram:group:12345")
    assert result == {"channel": "telegram", "to": "group:12345"}

def test_cli_session():
    result = infer_delivery("cli:direct")
    assert result == {"channel": "cli", "to": "direct"}

def test_background_session():
    result = infer_delivery("background:cron:abc123")
    assert result is None  # Background sessions don't deliver

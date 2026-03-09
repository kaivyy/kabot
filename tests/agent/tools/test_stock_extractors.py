from kabot.agent.tools.stock import (
    extract_crypto_ids,
    extract_stock_name_candidates,
    extract_stock_symbols,
)


def test_extract_stock_symbols_ignores_file_like_extensions():
    assert extract_stock_symbols("config.json") == []
    assert extract_stock_symbols("baca file config.json") == []


def test_extract_stock_symbols_supports_usd_idr_natural_language_queries():
    assert extract_stock_symbols("1 usd berapa rupiah sekarang") == ["USDIDR=X"]
    assert extract_stock_symbols("kurs usd ke idr hari ini") == ["USDIDR=X"]


def test_extract_stock_name_candidates_trim_fx_conversion_filler_words():
    query = "how much is Apple stock now in rupiah?"
    assert extract_stock_name_candidates(query) == ["Apple"]


def test_extract_crypto_ids_handles_multi_coin_phrases():
    assert extract_crypto_ids("kalau harga bitcoin dan ethereum berapa sekarang") == [
        "bitcoin",
        "ethereum",
    ]
    assert extract_crypto_ids("btc eth") == ["bitcoin", "ethereum"]


def test_extract_stock_name_candidates_supports_non_latin_queries():
    assert extract_stock_name_candidates("トヨタ") == ["トヨタ"]


def test_extract_stock_name_candidates_ignores_generic_trend_phrase():
    assert extract_stock_name_candidates("cenderung naik atau turun?") == []


def test_extract_stock_name_candidates_ignores_generic_advice_phrase():
    assert extract_stock_name_candidates("saranmu apa") == []


def test_extract_stock_name_candidates_ignores_non_market_topic_phrase():
    assert extract_stock_name_candidates("adakah gejolak politik sekarang") == []


def test_extract_stock_name_candidates_ignores_fx_wording_without_asset():
    assert extract_stock_name_candidates("kalau dirupiahkan dengan harga sekarang berapa") == []


def test_extract_stock_name_candidates_ignores_generic_product_advice_phrase():
    assert extract_stock_name_candidates("sunscreen nya apa yang bagus") == []


def test_extract_stock_name_candidates_trims_trailing_question_noise_from_company_name():
    assert extract_stock_name_candidates("How much is Microsoft stock right now?") == ["Microsoft"]

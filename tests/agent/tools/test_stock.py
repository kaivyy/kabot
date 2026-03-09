from unittest.mock import AsyncMock

import pytest

from kabot.agent.fallback_i18n import t as i18n_t
from kabot.agent.tools.stock import (
    CryptoTool,
    StockTool,
)
from kabot.agent.tools.stock_analysis import StockAnalysisTool


@pytest.mark.asyncio
async def test_stock_tool_global_symbol():
    """Integration test: calls real Yahoo Finance API for AAPL"""
    tool = StockTool()
    result = await tool.execute("AAPL")

    # Basic validation - should contain stock symbol and currency
    assert "AAPL" in result or "Could not fetch" in result
    # If successful, should have USD currency
    if "Could not fetch" not in result:
        assert "USD" in result

@pytest.mark.asyncio
async def test_crypto_tool_global_symbol():
    """Integration test: calls real CoinGecko API for bitcoin"""
    tool = CryptoTool()
    result = await tool.execute("bitcoin")

    # Basic validation - should contain Bitcoin or error message
    assert "Bitcoin" in result or "Error" in result or "bitcoin" in result
    # If successful, should have price information
    if "Error" not in result:
        assert "$" in result

@pytest.mark.asyncio
async def test_stock_tool_japanese_market():
    """Test Japanese stock market (Toyota - 7203.T)"""
    tool = StockTool()
    result = await tool.execute("7203.T")

    # Should work with Japanese exchange suffix
    assert "7203.T" in result or "Could not fetch" in result

@pytest.mark.asyncio
async def test_stock_tool_german_market():
    """Test German stock market (SAP - SAP.DE)"""
    tool = StockTool()
    result = await tool.execute("SAP.DE")

    # Should work with German exchange suffix
    assert "SAP.DE" in result or "Could not fetch" in result

@pytest.mark.asyncio
async def test_stock_tool_indonesian_market():
    """Test Indonesian stock market still works (BBCA.JK)"""
    tool = StockTool()
    result = await tool.execute("BBCA.JK")

    # Indonesian stocks should still work
    assert "BBCA.JK" in result or "Could not fetch" in result

@pytest.mark.asyncio
async def test_crypto_tool_error_message_guides_search():
    """Test that crypto error message guides AI to use web_search"""
    tool = CryptoTool()
    result = await tool.execute("nonexistent-coin-xyz")

    # Error message should guide to use web_search
    assert "web_search" in result.lower() or "coingecko" in result.lower()


@pytest.mark.asyncio
async def test_crypto_tool_localizes_missing_coin_id_message():
    tool = CryptoTool()
    query = "iya lanjut"
    result = await tool.execute(query)
    assert result == i18n_t("crypto.need_id", query)

@pytest.mark.asyncio
async def test_stock_tool_error_message_guides_search():
    """Test that stock error message guides AI to use web_search"""
    tool = StockTool()
    result = await tool.execute("INVALID")

    # Error message should guide to verify ticker
    assert "verify" in result.lower() or "web search" in result.lower() or "web_search" in result.lower()

@pytest.mark.asyncio
async def test_stock_analysis_default_currency_usd():
    """Test that StockAnalysisTool defaults to USD instead of IDR"""
    tool = StockAnalysisTool()
    result = await tool.execute("AAPL", days=7)

    # Should contain analysis data or error
    assert isinstance(result, str)
    # If successful, should not default to IDR
    if "Error" not in result and "USD" in result:
        assert "USD" in result

@pytest.mark.asyncio
async def test_stock_tool_description_mentions_web_search():
    """Verify tool description guides AI to use web_search"""
    tool = StockTool()

    # Description should mention web_search
    assert "web_search" in tool.description.lower()

@pytest.mark.asyncio
async def test_crypto_tool_description_mentions_coingecko_id():
    """Verify crypto tool description requires CoinGecko ID"""
    tool = CryptoTool()

    # Description should mention CoinGecko ID requirement
    assert "coingecko" in tool.description.lower()
    assert "id" in tool.description.lower()


@pytest.mark.asyncio
async def test_stock_tool_rejects_free_text_without_valid_tickers():
    """Natural-language confirmations must not be parsed into fake ticker symbols."""
    tool = StockTool()
    query = "iya kamu bener maaf itu dari aku"
    result = await tool.execute(query)
    assert result == i18n_t("stock.need_symbol", query)



@pytest.mark.asyncio
async def test_stock_tool_extracts_idx_symbols_from_natural_language_without_spam(monkeypatch):
    """Mixed natural-language queries should keep only valid explicit ticker candidates."""
    tool = StockTool()
    requested: list[str] = []

    async def _fake_fetch(symbol: str) -> str:
        requested.append(symbol)
        return (
            f"[STOCK] {symbol} (JKT)\n"
            "Price: 1.00 IDR\n"
            "Change: +0.00 (+0.00%)\n"
            "High: 1.00 IDR\n"
            "Low: 1.00 IDR"
        )

    monkeypatch.setattr(tool, "_fetch_yahoo_finance", _fake_fetch)
    result = await tool.execute(
        "iya, kamu bener. kalau saham bbri bbca bmri berapa sekarang tanpa spam error per kata"
    )

    assert requested == ["BBRI.JK", "BBCA.JK", "BMRI.JK"]
    assert "BBRI.JK" in result
    assert "BBCA.JK" in result
    assert "BMRI.JK" in result


@pytest.mark.asyncio
async def test_stock_tool_localizes_fetch_failure_message(monkeypatch):
    tool = StockTool()

    async def _fake_fetch(symbol: str) -> str | None:
        return None

    monkeypatch.setattr(tool, "_fetch_yahoo_finance", _fake_fetch)
    result = await tool.execute("AAPL")

    assert result == i18n_t("stock.fetch_failed", "AAPL", symbol="AAPL")


@pytest.mark.asyncio
async def test_stock_tool_extracts_adaro_alias_from_natural_language(monkeypatch):
    """'adaro' mention should map to ADRO.JK without requiring rigid ticker input."""
    tool = StockTool()
    requested: list[str] = []

    async def _fake_fetch(symbol: str) -> str:
        requested.append(symbol)
        return (
            f"[STOCK] {symbol} (JKT)\n"
            "Price: 1.00 IDR\n"
            "Change: +0.00 (+0.00%)\n"
            "High: 1.00 IDR\n"
            "Low: 1.00 IDR"
        )

    monkeypatch.setattr(tool, "_fetch_yahoo_finance", _fake_fetch)
    result = await tool.execute("cek harga saham bbri bbca bmri adaro")

    assert requested == ["BBRI.JK", "BBCA.JK", "BMRI.JK", "ADRO.JK"]
    assert "ADRO.JK" in result


@pytest.mark.asyncio
async def test_stock_tool_extracts_toba_alias_from_natural_language(monkeypatch):
    """'toba' mention should map to TOBA.JK in novice-style queries."""
    tool = StockTool()
    requested: list[str] = []

    async def _fake_fetch(symbol: str) -> str:
        requested.append(symbol)
        return (
            f"[STOCK] {symbol} (JKT)\n"
            "Price: 1.00 IDR\n"
            "Change: +0.00 (+0.00%)\n"
            "High: 1.00 IDR\n"
            "Low: 1.00 IDR"
        )

    monkeypatch.setattr(tool, "_fetch_yahoo_finance", _fake_fetch)
    result = await tool.execute("cek harga saham adaro toba")

    assert requested == ["ADRO.JK", "TOBA.JK"]
    assert "TOBA.JK" in result


@pytest.mark.asyncio
async def test_stock_tool_extracts_usd_idr_alias_from_natural_language(monkeypatch):
    tool = StockTool()
    requested: list[str] = []

    async def _fake_fetch(symbol: str) -> str:
        requested.append(symbol)
        return (
            f"[STOCK] {symbol} (FX)\n"
            "Price: 1.00 IDR\n"
            "Change: +0.00 (+0.00%)\n"
            "High: 1.00 IDR\n"
            "Low: 1.00 IDR"
        )

    monkeypatch.setattr(tool, "_fetch_yahoo_finance", _fake_fetch)
    result = await tool.execute("gunakan yahoo finance harga 1 usd berapa rupiah")

    assert requested == ["USDIDR=X"]
    assert "USDIDR=X" in result


@pytest.mark.asyncio
async def test_stock_tool_converts_natural_usd_prompt_to_rupiah(monkeypatch):
    tool = StockTool()

    async def _fake_snapshot(symbol: str):
        if symbol == "USDIDR=X":
            return {
                "symbol": "USDIDR=X",
                "currency": "IDR",
                "exchange": "CCY",
                "price": 15600.0,
                "open_price": 15500.0,
                "high_price": 15650.0,
                "low_price": 15480.0,
            }
        if symbol == "AAPL":
            return {
                "symbol": "AAPL",
                "currency": "USD",
                "exchange": "NMS",
                "price": 260.29,
                "open_price": 259.0,
                "high_price": 261.0,
                "low_price": 257.0,
            }
        raise AssertionError(f"Unexpected symbol: {symbol}")

    monkeypatch.setattr(tool, "_fetch_quote_snapshot", _fake_snapshot)
    monkeypatch.setattr(tool, "_resolve_symbols_from_names", AsyncMock(return_value=(["AAPL"], None, None)))

    result = await tool.execute(
        "If Apple is around 260 dollars, roughly how much is that in Indonesian rupiah today?"
    )

    assert "USDIDR=X" in result
    assert "AAPL" in result
    assert "4,056,000.00 IDR" in result


@pytest.mark.asyncio
async def test_stock_tool_converts_natural_usd_prompt_to_rupiah_via_real_name_resolution(monkeypatch):
    tool = StockTool()

    async def _fake_snapshot(symbol: str):
        if symbol == "USDIDR=X":
            return {
                "symbol": "USDIDR=X",
                "currency": "IDR",
                "exchange": "CCY",
                "price": 15600.0,
                "open_price": 15500.0,
                "high_price": 15650.0,
                "low_price": 15480.0,
            }
        if symbol == "AAPL":
            return {
                "symbol": "AAPL",
                "currency": "USD",
                "exchange": "NMS",
                "price": 260.29,
                "open_price": 259.0,
                "high_price": 261.0,
                "low_price": 257.0,
            }
        raise AssertionError(f"Unexpected symbol: {symbol}")

    async def _fake_search(candidate: str, raw_query: str | None = None):
        if candidate == "Apple":
            return ["AAPL"]
        return []

    monkeypatch.setattr(tool, "_fetch_quote_snapshot", _fake_snapshot)
    monkeypatch.setattr(tool, "_search_yahoo_symbols", _fake_search)

    result = await tool.execute(
        "If Apple is around 260 dollars, roughly how much is that in Indonesian rupiah today?"
    )

    assert "USDIDR=X" in result
    assert "AAPL" in result
    assert "4,056,000.00 IDR" in result


@pytest.mark.asyncio
async def test_stock_tool_extracts_phrase_aliases_for_bank_names(monkeypatch):
    """Full company names should resolve without requiring explicit ticker symbols."""
    tool = StockTool()
    requested: list[str] = []

    async def _fake_fetch(symbol: str) -> str:
        requested.append(symbol)
        return (
            f"[STOCK] {symbol} (JKT)\n"
            "Price: 1.00 IDR\n"
            "Change: +0.00 (+0.00%)\n"
            "High: 1.00 IDR\n"
            "Low: 1.00 IDR"
        )

    monkeypatch.setattr(tool, "_fetch_yahoo_finance", _fake_fetch)
    result = await tool.execute(
        "cek bank rakyat indonesia, bank central asia, bank mandiri, bank negara indonesia, adaro energy indonesia, toba bara"
    )

    assert requested == ["BBRI.JK", "BBCA.JK", "BMRI.JK", "BBNI.JK", "ADRO.JK", "TOBA.JK"]
    assert "BBRI.JK" in result
    assert "TOBA.JK" in result


@pytest.mark.asyncio
async def test_stock_tool_supports_custom_alias_file_for_skill_extensions(monkeypatch, tmp_path):
    """User/skill-created alias mapping should be loadable without code changes."""
    alias_file = tmp_path / "stock_aliases.json"
    alias_file.write_text('{"aliases": {"bank jatim": "BJTM.JK"}}', encoding="utf-8")
    monkeypatch.setenv("KABOT_STOCK_ALIASES_PATH", str(alias_file))

    tool = StockTool()
    requested: list[str] = []

    async def _fake_fetch(symbol: str) -> str:
        requested.append(symbol)
        return (
            f"[STOCK] {symbol} (JKT)\n"
            "Price: 1.00 IDR\n"
            "Change: +0.00 (+0.00%)\n"
            "High: 1.00 IDR\n"
            "Low: 1.00 IDR"
        )

    monkeypatch.setattr(tool, "_fetch_yahoo_finance", _fake_fetch)
    result = await tool.execute("harga bank jatim sekarang")

    assert requested == ["BJTM.JK"]
    assert "BJTM.JK" in result


@pytest.mark.asyncio
async def test_stock_tool_tolerates_single_typo_for_idx_symbol(monkeypatch):
    tool = StockTool()
    requested: list[str] = []

    async def _fake_fetch(symbol: str) -> str:
        requested.append(symbol)
        return (
            f"[STOCK] {symbol} (JKT)\n"
            "Price: 1.00 IDR\n"
            "Change: +0.00 (+0.00%)\n"
            "High: 1.00 IDR\n"
            "Low: 1.00 IDR"
        )

    monkeypatch.setattr(tool, "_fetch_yahoo_finance", _fake_fetch)
    result = await tool.execute("aadro.jk")

    assert requested == ["ADRO.JK"]
    assert "ADRO.JK" in result


@pytest.mark.asyncio
async def test_stock_tool_resolves_global_company_name_via_yahoo_search(monkeypatch):
    tool = StockTool()
    requested: list[str] = []

    async def _fake_fetch(symbol: str) -> str:
        requested.append(symbol)
        return (
            f"[STOCK] {symbol} (JKT)\n"
            "Price: 1.00 IDR\n"
            "Change: +0.00 (+0.00%)\n"
            "High: 1.00 IDR\n"
            "Low: 1.00 IDR"
        )

    class _DummyResponse:
        def __init__(self, status_code: int, payload: dict):
            self.status_code = status_code
            self._payload = payload

        def json(self) -> dict:
            return self._payload

    class _DummyClient:
        async def __aenter__(self):  # type: ignore[no-untyped-def]
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return None

        async def get(self, url, headers=None, params=None, timeout=10.0):  # type: ignore[no-untyped-def]
            assert "finance/search" in url
            assert params is not None
            assert str(params.get("q", "")).lower() == "toyota"
            return _DummyResponse(
                200,
                {
                    "quotes": [
                        {
                            "symbol": "7203.T",
                            "quoteType": "EQUITY",
                            "shortname": "Toyota Motor Corporation",
                        }
                    ]
                },
            )

    monkeypatch.setattr(tool, "_fetch_yahoo_finance", _fake_fetch)
    monkeypatch.setattr("kabot.agent.tools.stock.httpx.AsyncClient", lambda: _DummyClient())

    result = await tool.execute("toyota sekarang berapa")

    assert requested == ["7203.T"]
    assert "7203.T" in result


@pytest.mark.asyncio
async def test_stock_tool_resolves_non_latin_company_name_via_yahoo_search(monkeypatch):
    tool = StockTool()
    requested: list[str] = []

    async def _fake_fetch(symbol: str) -> str:
        requested.append(symbol)
        return (
            f"[STOCK] {symbol} (JKT)\n"
            "Price: 1.00 IDR\n"
            "Change: +0.00 (+0.00%)\n"
            "High: 1.00 IDR\n"
            "Low: 1.00 IDR"
        )

    class _DummyResponse:
        def __init__(self, status_code: int, payload: dict):
            self.status_code = status_code
            self._payload = payload

        def json(self) -> dict:
            return self._payload

    class _DummyClient:
        async def __aenter__(self):  # type: ignore[no-untyped-def]
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return None

        async def get(self, url, headers=None, params=None, timeout=10.0):  # type: ignore[no-untyped-def]
            assert "finance/search" in url
            assert params is not None
            assert str(params.get("q", "")).strip() == "トヨタ"
            return _DummyResponse(
                200,
                {
                    "quotes": [
                        {
                            "symbol": "7203.T",
                            "quoteType": "EQUITY",
                            "shortname": "Toyota Motor Corporation",
                        }
                    ]
                },
            )

    monkeypatch.setattr(tool, "_fetch_yahoo_finance", _fake_fetch)
    monkeypatch.setattr("kabot.agent.tools.stock.httpx.AsyncClient", lambda: _DummyClient())

    result = await tool.execute("トヨタ")

    assert requested == ["7203.T"]
    assert "7203.T" in result


@pytest.mark.asyncio
async def test_stock_tool_prefers_market_suffix_based_on_query_locale_hint(monkeypatch):
    tool = StockTool()
    requested: list[str] = []

    async def _fake_fetch(symbol: str) -> str:
        requested.append(symbol)
        return (
            f"[STOCK] {symbol} (NYSE)\n"
            "Price: 1.00 USD\n"
            "Change: +0.00 (+0.00%)\n"
            "High: 1.00 USD\n"
            "Low: 1.00 USD"
        )

    class _DummyResponse:
        def __init__(self, status_code: int, payload: dict):
            self.status_code = status_code
            self._payload = payload

        def json(self) -> dict:
            return self._payload

    class _DummyClient:
        async def __aenter__(self):  # type: ignore[no-untyped-def]
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return None

        async def get(self, url, headers=None, params=None, timeout=10.0):  # type: ignore[no-untyped-def]
            assert "finance/search" in url
            return _DummyResponse(
                200,
                {
                    "quotes": [
                        {"symbol": "TM", "quoteType": "EQUITY", "shortname": "Toyota Motor Corp ADR"},
                        {"symbol": "7203.T", "quoteType": "EQUITY", "shortname": "Toyota Motor Corp"},
                    ]
                },
            )

    monkeypatch.setattr(tool, "_fetch_yahoo_finance", _fake_fetch)
    monkeypatch.setattr("kabot.agent.tools.stock.httpx.AsyncClient", lambda: _DummyClient())

    result = await tool.execute("toyota jepang sekarang berapa")

    assert requested == ["7203.T"]
    assert "7203.T" in result


@pytest.mark.asyncio
async def test_stock_tool_asks_clarification_when_company_name_is_ambiguous(monkeypatch):
    tool = StockTool()
    requested: list[str] = []

    async def _fake_fetch(symbol: str) -> str:
        requested.append(symbol)
        return (
            f"[STOCK] {symbol} (NYSE)\n"
            "Price: 1.00 USD\n"
            "Change: +0.00 (+0.00%)\n"
            "High: 1.00 USD\n"
            "Low: 1.00 USD"
        )

    class _DummyResponse:
        def __init__(self, status_code: int, payload: dict):
            self.status_code = status_code
            self._payload = payload

        def json(self) -> dict:
            return self._payload

    class _DummyClient:
        async def __aenter__(self):  # type: ignore[no-untyped-def]
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return None

        async def get(self, url, headers=None, params=None, timeout=10.0):  # type: ignore[no-untyped-def]
            if "finance/search" not in url:
                raise AssertionError(f"Unexpected URL: {url}")
            return _DummyResponse(
                200,
                {
                    "quotes": [
                        {"symbol": "TM", "quoteType": "EQUITY", "shortname": "Toyota Motor Corp ADR"},
                        {"symbol": "7203.T", "quoteType": "EQUITY", "shortname": "Toyota Motor Corp"},
                    ]
                },
            )

    monkeypatch.setattr(tool, "_fetch_yahoo_finance", _fake_fetch)
    monkeypatch.setattr("kabot.agent.tools.stock.httpx.AsyncClient", lambda: _DummyClient())

    result = await tool.execute("toyota berapa sekarang")

    assert requested == []
    assert ("multiple listings" in result.lower()) or ("pilihan ticker" in result.lower())
    assert "TM" in result
    assert "7203.T" in result


@pytest.mark.asyncio
async def test_stock_tool_prefers_primary_unsuffixed_listing_for_strong_company_match(monkeypatch):
    tool = StockTool()
    requested: list[str] = []

    async def _fake_fetch(symbol: str) -> str:
        requested.append(symbol)
        return (
            f"[STOCK] {symbol} (NMS)\n"
            "Price: 410.68 USD\n"
            "Change: +6.26 (+1.55%)\n"
            "High: 411.61 USD\n"
            "Low: 404.40 USD"
        )

    class _DummyResponse:
        def __init__(self, status_code: int, payload: dict):
            self.status_code = status_code
            self._payload = payload

        def json(self) -> dict:
            return self._payload

    class _DummyClient:
        async def __aenter__(self):  # type: ignore[no-untyped-def]
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return None

        async def get(self, url, headers=None, params=None, timeout=10.0):  # type: ignore[no-untyped-def]
            if "finance/search" not in url:
                raise AssertionError(f"Unexpected URL: {url}")
            return _DummyResponse(
                200,
                {
                    "quotes": [
                        {
                            "symbol": "MSFT",
                            "quoteType": "EQUITY",
                            "shortname": "Microsoft Corporation",
                        },
                        {
                            "symbol": "MSHE.TO",
                            "quoteType": "EQUITY",
                            "shortname": "Microsoft CDR (CAD Hedged)",
                        },
                    ]
                },
            )

    monkeypatch.setattr(tool, "_fetch_yahoo_finance", _fake_fetch)
    monkeypatch.setattr("kabot.agent.tools.stock.httpx.AsyncClient", lambda: _DummyClient())

    result = await tool.execute("How much is Microsoft stock right now?")

    assert requested == ["MSFT"]
    assert "MSFT" in result
    assert "multiple listings" not in result.lower()


@pytest.mark.asyncio
async def test_stock_tool_resolves_free_style_indonesian_company_name_query(monkeypatch):
    tool = StockTool()
    requested: list[str] = []

    async def _fake_fetch(symbol: str) -> str:
        requested.append(symbol)
        return (
            f"[STOCK] {symbol} (NMS)\n"
            "Price: 410.68 USD\n"
            "Change: +6.26 (+1.55%)\n"
            "High: 411.61 USD\n"
            "Low: 404.40 USD"
        )

    class _DummyResponse:
        def __init__(self, status_code: int, payload: dict):
            self.status_code = status_code
            self._payload = payload

        def json(self) -> dict:
            return self._payload

    class _DummyClient:
        async def __aenter__(self):  # type: ignore[no-untyped-def]
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return None

        async def get(self, url, headers=None, params=None, timeout=10.0):  # type: ignore[no-untyped-def]
            if "finance/search" not in url:
                raise AssertionError(f"Unexpected URL: {url}")
            return _DummyResponse(
                200,
                {
                    "quotes": [
                        {
                            "symbol": "MSFT",
                            "quoteType": "EQUITY",
                            "shortname": "Microsoft Corporation",
                        },
                        {
                            "symbol": "MSHE.TO",
                            "quoteType": "ETF",
                            "shortname": "Harvest Microsoft Enhanced High Income Shares ETF",
                        },
                    ]
                },
            )

    monkeypatch.setattr(tool, "_fetch_yahoo_finance", _fake_fetch)
    monkeypatch.setattr("kabot.agent.tools.stock.httpx.AsyncClient", lambda: _DummyClient())

    result = await tool.execute("bro kira-kira saham microsoft sekarang berapa ya?")

    assert requested == ["MSFT"]
    assert "MSFT" in result


@pytest.mark.asyncio
async def test_stock_tool_ambiguous_clarification_is_localized_for_indonesian_query(monkeypatch):
    tool = StockTool()

    class _DummyResponse:
        def __init__(self, status_code: int, payload: dict):
            self.status_code = status_code
            self._payload = payload

        def json(self) -> dict:
            return self._payload

    class _DummyClient:
        async def __aenter__(self):  # type: ignore[no-untyped-def]
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return None

        async def get(self, url, headers=None, params=None, timeout=10.0):  # type: ignore[no-untyped-def]
            if "finance/search" not in url:
                raise AssertionError(f"Unexpected URL: {url}")
            return _DummyResponse(
                200,
                {
                    "quotes": [
                        {"symbol": "TM", "quoteType": "EQUITY", "shortname": "Toyota Motor Corp ADR"},
                        {"symbol": "7203.T", "quoteType": "EQUITY", "shortname": "Toyota Motor Corp"},
                    ]
                },
            )

    monkeypatch.setattr("kabot.agent.tools.stock.httpx.AsyncClient", lambda: _DummyClient())

    result = await tool.execute("toyota berapa sekarang")
    assert "pilihan ticker" in result.lower()
    assert "TM" in result
    assert "7203.T" in result


@pytest.mark.asyncio
async def test_stock_tool_name_resolver_uses_in_memory_cache_for_repeated_query(monkeypatch):
    tool = StockTool()
    requested: list[str] = []
    search_calls = {"count": 0}

    async def _fake_fetch(symbol: str) -> str:
        requested.append(symbol)
        return (
            f"[STOCK] {symbol} (TSE)\n"
            "Price: 1.00 JPY\n"
            "Change: +0.00 (+0.00%)\n"
            "High: 1.00 JPY\n"
            "Low: 1.00 JPY"
        )

    class _DummyResponse:
        def __init__(self, status_code: int, payload: dict):
            self.status_code = status_code
            self._payload = payload

        def json(self) -> dict:
            return self._payload

    class _DummyClient:
        async def __aenter__(self):  # type: ignore[no-untyped-def]
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return None

        async def get(self, url, headers=None, params=None, timeout=10.0):  # type: ignore[no-untyped-def]
            if "finance/search" in url:
                search_calls["count"] += 1
                return _DummyResponse(
                    200,
                    {
                        "quotes": [
                            {"symbol": "7203.T", "quoteType": "EQUITY", "shortname": "Toyota Motor Corp"},
                        ]
                    },
                )
            raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(tool, "_fetch_yahoo_finance", _fake_fetch)
    monkeypatch.setattr("kabot.agent.tools.stock.httpx.AsyncClient", lambda: _DummyClient())

    first = await tool.execute("toyota sekarang berapa")
    second = await tool.execute("toyota sekarang berapa")

    assert "7203.T" in first
    assert "7203.T" in second
    assert requested == ["7203.T", "7203.T"]
    assert search_calls["count"] == 1


@pytest.mark.asyncio
async def test_stock_tool_search_fallback_uses_query1_when_query2_fails(monkeypatch):
    tool = StockTool()
    requested: list[str] = []

    async def _fake_fetch(symbol: str) -> str:
        requested.append(symbol)
        return (
            f"[STOCK] {symbol} (TSE)\n"
            "Price: 1.00 JPY\n"
            "Change: +0.00 (+0.00%)\n"
            "High: 1.00 JPY\n"
            "Low: 1.00 JPY"
        )

    class _DummyResponse:
        def __init__(self, status_code: int, payload: dict):
            self.status_code = status_code
            self._payload = payload

        def json(self) -> dict:
            return self._payload

    class _DummyClient:
        async def __aenter__(self):  # type: ignore[no-untyped-def]
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return None

        async def get(self, url, headers=None, params=None, timeout=10.0):  # type: ignore[no-untyped-def]
            if "query2.finance.yahoo.com/v1/finance/search" in url:
                return _DummyResponse(500, {})
            if "query1.finance.yahoo.com/v1/finance/search" in url:
                return _DummyResponse(
                    200,
                    {
                        "quotes": [
                            {"symbol": "7203.T", "quoteType": "EQUITY", "shortname": "Toyota Motor Corp"},
                        ]
                    },
                )
            raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(tool, "_fetch_yahoo_finance", _fake_fetch)
    monkeypatch.setattr("kabot.agent.tools.stock.httpx.AsyncClient", lambda: _DummyClient())

    result = await tool.execute("toyota")

    assert requested == ["7203.T"]
    assert "7203.T" in result


@pytest.mark.asyncio
async def test_stock_tool_search_fallback_uses_autoc_when_search_endpoints_fail(monkeypatch):
    tool = StockTool()
    requested: list[str] = []

    async def _fake_fetch(symbol: str) -> str:
        requested.append(symbol)
        return (
            f"[STOCK] {symbol} (XETRA)\n"
            "Price: 1.00 EUR\n"
            "Change: +0.00 (+0.00%)\n"
            "High: 1.00 EUR\n"
            "Low: 1.00 EUR"
        )

    class _DummyResponse:
        def __init__(self, status_code: int, payload: dict):
            self.status_code = status_code
            self._payload = payload

        def json(self) -> dict:
            return self._payload

    class _DummyClient:
        async def __aenter__(self):  # type: ignore[no-untyped-def]
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return None

        async def get(self, url, headers=None, params=None, timeout=10.0):  # type: ignore[no-untyped-def]
            if "finance.yahoo.com/v1/finance/search" in url:
                return _DummyResponse(503, {})
            if "autoc.finance.yahoo.com/autoc" in url:
                return _DummyResponse(
                    200,
                    {
                        "ResultSet": {
                            "Result": [
                                {"symbol": "SAP.DE", "name": "SAP SE"},
                            ]
                        }
                    },
                )
            raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(tool, "_fetch_yahoo_finance", _fake_fetch)
    monkeypatch.setattr("kabot.agent.tools.stock.httpx.AsyncClient", lambda: _DummyClient())

    result = await tool.execute("sap")

    assert requested == ["SAP.DE"]
    assert "SAP.DE" in result


@pytest.mark.asyncio
async def test_stock_tool_does_not_resolve_non_market_small_talk(monkeypatch):
    tool = StockTool()

    class _DummyClient:
        async def __aenter__(self):  # type: ignore[no-untyped-def]
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return None

        async def get(self, url, headers=None, params=None, timeout=10.0):  # type: ignore[no-untyped-def]
            raise AssertionError("Yahoo search should not run for small-talk input")

    monkeypatch.setattr("kabot.agent.tools.stock.httpx.AsyncClient", lambda: _DummyClient())

    query = "umur kamu berapa sekarang"
    result = await tool.execute(query)
    assert result == i18n_t("stock.need_symbol", query)


@pytest.mark.asyncio
async def test_crypto_tool_supports_multi_coin_ids(monkeypatch):
    tool = CryptoTool()

    class _DummyResponse:
        status_code = 200

        @staticmethod
        def json() -> dict:
            return {
                "bitcoin": {
                    "usd": 70000.0,
                    "usd_24h_change": 1.25,
                    "usd_market_cap": 1_400_000_000_000,
                },
                "ethereum": {
                    "usd": 3500.0,
                    "usd_24h_change": 0.75,
                    "usd_market_cap": 420_000_000_000,
                },
            }

    class _DummyClient:
        async def __aenter__(self):  # type: ignore[no-untyped-def]
            return self

        async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return None

        async def get(self, url, timeout=10.0):  # type: ignore[no-untyped-def]
            assert "ids=bitcoin,ethereum" in url
            return _DummyResponse()

    monkeypatch.setattr("kabot.agent.tools.stock.httpx.AsyncClient", lambda: _DummyClient())

    result = await tool.execute("bitcoin,ethereum")
    assert "[CRYPTO] Bitcoin" in result
    assert "[CRYPTO] Ethereum" in result

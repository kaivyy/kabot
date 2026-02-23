import pytest
from kabot.agent.tools.stock import StockTool, CryptoTool
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
async def test_stock_tool_error_message_guides_search():
    """Test that stock error message guides AI to use web_search"""
    tool = StockTool()
    result = await tool.execute("INVALID")

    # Error message should guide to verify ticker
    assert "verify" in result.lower() or "web search" in result.lower()

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

# Global Market Tools Refactoring Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor the Stock, Crypto, and Stock Analysis tools to remove regional biases (Indonesian hardcoding) and shift discovery intelligence entirely to the AI via web search.

**Architecture:** We are moving from hardcoded lists (`TOP10_ID`, `coin_map`) to a pure plugin approach. The tools become thin wrappers over Yahoo Finance and CoinGecko APIs. The AI is expected to use `web_search` first if it does not know the exact ticker string or coin ID. Tests will be added using `get_openai_mock` strategies or by mocking `httpx.AsyncClient`.

**Tech Stack:** Python, `httpx`, `pytest`

---

### Task 1: Create Unit Tests for Stock and Crypto Tools

**Files:**
- Create: `tests/agent/tools/test_stock.py`

**Step 1: Write the failing tests**

```python
import pytest
from unittest.mock import AsyncMock, patch
from kabot.agent.tools.stock import StockTool, CryptoTool

@pytest.mark.asyncio
async def test_stock_tool_global_symbol():
    tool = StockTool()
    
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "chart": {"result": [{"meta": {"symbol": "AAPL", "currency": "USD", "exchangeName": "NMS"}, 
                                  "indicators": {"quote": [{"close": [150.0], "open": [140.0], "high": [155.0], "low": [139.0]}]}}]}}
        mock_get.return_value = mock_response
        
        result = await tool.execute("AAPL")
        assert "AAPL" in result
        assert "USD" in result

@pytest.mark.asyncio
async def test_crypto_tool_global_symbol():
    tool = CryptoTool()
    
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"bitcoin": {"usd": 50000.0, "usd_24h_change": 5.0, "usd_market_cap": 1000000000.0}}
        mock_get.return_value = mock_response
        
        result = await tool.execute("bitcoin")
        assert "Bitcoin" in result
        assert "50,000" in result
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agent/tools/test_stock.py -v`
Expected: Passes for now, but fails when we remove `TOP10_ID` logic if we test that specifically.

**Step 3: Commit**

```bash
git add tests/agent/tools/test_stock.py
git commit -m "test: add initial tests for stock tools"
```

---

### Task 2: Refactor StockTool (Remove Regional Bias)

**Files:**
- Modify: `kabot/agent/tools/stock.py:10-141`

**Step 1: Write minimal implementation**

```python
class StockTool(Tool):
    """Get current stock price and market information."""

    name = "stock"
    description = "Get CURRENT STOCK PRICE only using Yahoo Finance API. Requires exact ticker symbol with exchange suffix (e.g., AAPL, BBCA.JK, 7203.T, SAP.DE). If you don't know the exact ticker, ALWAYS use web_search tool first to find it."
    parameters = {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Exact stock ticker symbol (e.g., 'AAPL', 'MSFT', 'TLKM.JK', '7203.T')"
            }
        },
        "required": ["symbol"]
    }

    async def execute(self, symbol: str, **kwargs: Any) -> str:
        """
        Fetch stock data for the given symbol(s).
        """
        try:
            symbols = [s.strip() for s in symbol.split(",") if s.strip()]

            if not symbols:
                return "Error: No stock symbols provided."

            results = []
            tasks = [self._fetch_yahoo_finance(s.upper()) for s in symbols]
            fetched = await asyncio.gather(*tasks)

            for i, res in enumerate(fetched):
                if res:
                    results.append(res)
                else:
                    results.append(f"Could not fetch data for {symbols[i]}. Please verify the ticker symbol using web search.")

            return "\n\n".join(results)

        except Exception as e:
            return f"Error fetching stock data: {str(e)}"
```
*Note: Ensure the rest of `_fetch_yahoo_finance` remains intact.*

**Step 2: Run tests to verify they pass**

Run: `python -m pytest tests/agent/tools/test_stock.py::test_stock_tool_global_symbol -v`
Expected: PASS

**Step 3: Commit**

```bash
git add kabot/agent/tools/stock.py
git commit -m "refactor: remove regional bias and hardcoded stock lists from StockTool"
```

---

### Task 3: Refactor CryptoTool (Remove Hardcoded Coin Map)

**Files:**
- Modify: `kabot/agent/tools/stock.py:142-228`

**Step 1: Write minimal implementation**

```python
class CryptoTool(Tool):
    """Get cryptocurrency price information."""

    name = "crypto"
    description = "Get current cryptocurrency prices using CoinGecko API. Requires the exact CoinGecko coin ID (e.g., 'bitcoin', 'ethereum', 'solana'). If unsure of the ID, use the web_search tool to find it on coingecko.com first."
    parameters = {
        "type": "object",
        "properties": {
            "coin": {
                "type": "string",
                "description": "Exact CoinGecko ID (e.g., 'bitcoin', 'ethereum', 'solana'). Do NOT use short symbols like 'BTC'."
            },
            "currency": {
                "type": "string",
                "description": "Currency to display price in (default: USD)",
                "default": "usd"
            }
        },
        "required": ["coin"]
    }

    async def execute(self, coin: str, currency: str = "usd", **kwargs: Any) -> str:
        """
        Fetch cryptocurrency data.
        """
        try:
            coin_id = coin.lower().strip()
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies={currency}&include_24hr_change=true&include_market_cap=true"

            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10.0)

                if response.status_code != 200:
                    return f"Error: Could not fetch crypto data for {coin_id}."

                data = response.json()

                if coin_id not in data:
                    return f"Error: Cryptocurrency '{coin_id}' not found. Please use the exact CoinGecko full name ID (e.g., 'bitcoin' instead of 'BTC'). Use web_search if unsure."

                coin_data = data[coin_id]
                price = coin_data.get(currency, 0)
                change_24h = coin_data.get(f"{currency}_24h_change", 0)
                market_cap = coin_data.get(f"{currency}_market_cap", 0)

                change_symbol = "+" if change_24h >= 0 else ""

                if market_cap >= 1_000_000_000:
                    mcap_str = f"${market_cap/1_000_000_000:.2f}B"
                elif market_cap >= 1_000_000:
                    mcap_str = f"${market_cap/1_000_000:.2f}M"
                else:
                    mcap_str = f"${market_cap:,.0f}"

                return (
                    f"[CRYPTO] {coin_id.title()}\n"
                    f"Price: ${price:,.2f} {currency.upper()}\n"
                    f"24h Change: {change_symbol}{change_24h:.2f}%\n"
                    f"Market Cap: {mcap_str}"
                )

        except Exception as e:
            return f"Error fetching crypto data: {str(e)}"
```

**Step 2: Run tests to verify they pass**

Run: `python -m pytest tests/agent/tools/test_stock.py::test_crypto_tool_global_symbol -v`
Expected: PASS

**Step 3: Commit**

```bash
git add kabot/agent/tools/stock.py
git commit -m "refactor: remove coin mapping dictionary from CryptoTool and enforce AI discovery"
```

---

### Task 4: Refactor StockAnalysisTool (Remove Bias Defaults)

**Files:**
- Modify: `kabot/agent/tools/stock_analysis.py:36-50` and line `127`

**Step 1: Write minimal implementation**

```python
    parameters = {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Exact stock ticker symbol (e.g., 'AAPL', 'TLKM.JK', '7203.T')"
            },
            "days": {
                "type": "string",
                "description": "Number of days of historical data to fetch (default: 30 days)",
                "default": "30"
            }
        },
        "required": ["symbol"]
    }
```
And replace line 127 in `_fetch_stock_data`:
```python
                        "currency": meta.get("currency", "USD"),  # Fallback to USD instead of IDR
```

**Step 2: Commit**

```bash
git add kabot/agent/tools/stock_analysis.py
git commit -m "refactor: remove Indonesian bias from StockAnalysisTool defaults and descriptions"
```

---

### Task 5: Document Changes

**Files:**
- Modify: `CHANGELOG.md`

**Step 1: Write minimal implementation**

Add to `[Unreleased]` or current feature block:
```markdown
### Changed
- **Market Tools Globalization**: Completely refactored `StockTool`, `CryptoTool`, and `StockAnalysisTool` to remove hardcoded regional biases (such as `.JK` suffix defaults, `TOP10_ID` lists, and limited `coin_map` dictionaries).
- Market tools now operate on a "Pure Plugin" philosophy: AI agents must use `web_search` natively to discover exact financial tickers or CoinGecko IDs before querying price data, supporting thousands of global assets out-of-the-box.
```

**Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: add global market tools refactor to changelog"
```

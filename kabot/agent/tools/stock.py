"""Stock tool for fetching stock market information."""

from typing import Any

import httpx

from kabot.agent.tools.base import Tool


class StockTool(Tool):
    """Get current stock price and market information."""

    name = "stock"
    description = "Get CURRENT STOCK PRICE only - quick price check using Yahoo Finance API. For ANALYSIS and RECOMMENDATIONS, use stock_analysis tool instead. This tool only returns price, change, high, low - no investment advice."
    parameters = {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Stock ticker symbol (e.g., 'AAPL' for Apple, 'MSFT' for Microsoft, 'TLKM.JK' for Telkom Indonesia, 'BBCA.JK' for BCA)"
            },
            "market": {
                "type": "string",
                "description": "Optional: specify market/exchange (e.g., 'US', 'JK' for Indonesia, 'JKSE' for IDX)",
                "default": ""
            }
        },
        "required": ["symbol"]
    }

    async def execute(self, symbol: str, market: str = "", **kwargs: Any) -> str:
        """
        Fetch stock data for the given symbol.

        Args:
            symbol: Stock ticker symbol
            market: Optional market/exchange code

        Returns:
            Stock information as formatted string
        """
        try:
            # Clean symbol
            clean_symbol = symbol.upper().strip()

            # Try Yahoo Finance API
            result = await self._fetch_yahoo_finance(clean_symbol)
            if result:
                return result

            return f"Error: Could not fetch stock data for {symbol}. Please check the ticker symbol."

        except Exception as e:
            return f"Error fetching stock data: {str(e)}"

    async def _fetch_yahoo_finance(self, symbol: str) -> str | None:
        """Fetch stock data from Yahoo Finance."""
        try:
            # Yahoo Finance chart API (provides real-time data)
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, timeout=10.0)

                if response.status_code != 200:
                    return None

                data = response.json()

                if "chart" not in data or "result" not in data["chart"] or not data["chart"]["result"]:
                    return None

                result = data["chart"]["result"][0]
                meta = result.get("meta", {})

                symbol = meta.get("symbol", symbol)
                currency = meta.get("currency", "USD")
                exchange = meta.get("exchangeName", "Unknown")

                # Get quote data
                quote = result.get("indicators", {}).get("quote", [{}])[0]

                if "close" in quote and quote["close"]:
                    current_price = quote["close"][-1]
                    open_price = quote["open"][0] if "open" in quote and quote["open"] else current_price
                    high_price = max(quote["high"]) if "high" in quote and quote["high"] else current_price
                    low_price = min(quote["low"]) if "low" in quote and quote["low"] else current_price

                    # Calculate change
                    change = current_price - open_price
                    change_percent = (change / open_price) * 100 if open_price else 0

                    change_symbol = "+" if change >= 0 else ""

                    return (
                        f"[STOCK] {symbol} ({exchange})\n"
                        f"Price: {current_price:.2f} {currency}\n"
                        f"Change: {change_symbol}{change:.2f} ({change_symbol}{change_percent:.2f}%)\n"
                        f"High: {high_price:.2f} {currency}\n"
                        f"Low: {low_price:.2f} {currency}"
                    )

                # Fallback to meta data if quote not available
                if "regularMarketPrice" in meta:
                    price = meta["regularMarketPrice"]
                    prev_close = meta.get("previousClose", price)
                    change = price - prev_close
                    change_percent = (change / prev_close) * 100 if prev_close else 0

                    change_symbol = "+" if change >= 0 else ""

                    return (
                        f"[STOCK] {symbol} ({exchange})\n"
                        f"Price: {price:.2f} {currency}\n"
                        f"Change: {change_symbol}{change:.2f} ({change_symbol}{change_percent:.2f}%)\n"
                        f"Market Closed"
                    )

                return None

        except Exception:
            return None


class CryptoTool(Tool):
    """Get cryptocurrency price information."""

    name = "crypto"
    description = "Get current cryptocurrency prices using CoinGecko API (no API key required). Supports Bitcoin, Ethereum, and thousands of other cryptocurrencies."
    parameters = {
        "type": "object",
        "properties": {
            "coin": {
                "type": "string",
                "description": "Cryptocurrency name or symbol (e.g., 'bitcoin', 'ethereum', 'BTC', 'ETH', 'solana', 'cardano')"
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

        Args:
            coin: Cryptocurrency name or symbol
            currency: Currency for price display

        Returns:
            Crypto information as formatted string
        """
        try:
            # Map common symbols to CoinGecko IDs
            coin_map = {
                "BTC": "bitcoin",
                "ETH": "ethereum",
                "SOL": "solana",
                "ADA": "cardano",
                "DOT": "polkadot",
                "DOGE": "dogecoin",
                "XRP": "ripple",
                "BNB": "binancecoin",
                "USDT": "tether",
                "USDC": "usd-coin",
            }

            coin_id = coin_map.get(coin.upper(), coin.lower())

            url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies={currency}&include_24hr_change=true&include_market_cap=true"

            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10.0)

                if response.status_code != 200:
                    return f"Error: Could not fetch crypto data for {coin}."

                data = response.json()

                if coin_id not in data:
                    return f"Error: Cryptocurrency '{coin}' not found. Try using full name (e.g., 'bitcoin') or symbol (e.g., 'BTC')."

                coin_data = data[coin_id]
                price = coin_data.get(currency, 0)
                change_24h = coin_data.get(f"{currency}_24h_change", 0)
                market_cap = coin_data.get(f"{currency}_market_cap", 0)

                change_symbol = "+" if change_24h >= 0 else ""

                # Format market cap
                if market_cap >= 1_000_000_000:
                    mcap_str = f"${market_cap/1_000_000_000:.2f}B"
                elif market_cap >= 1_000_000:
                    mcap_str = f"${market_cap/1_000_000:.2f}M"
                else:
                    mcap_str = f"${market_cap:,.0f}"

                return (
                    f"[CRYPTO] {coin_id.title()} ({coin.upper()})\n"
                    f"Price: ${price:,.2f} {currency.upper()}\n"
                    f"24h Change: {change_symbol}{change_24h:.2f}%\n"
                    f"Market Cap: {mcap_str}"
                )

        except Exception as e:
            return f"Error fetching crypto data: {str(e)}"

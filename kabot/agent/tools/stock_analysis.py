"""Stock analysis tool for AI-powered investment analysis."""

from datetime import datetime
from typing import Any

import httpx

from kabot.agent.tools.base import Tool


class StockAnalysisTool(Tool):
    """Fetch stock data for AI analysis and recommendations."""

    name = "stock_analysis"
    description = """Fetch detailed stock market data for AI-powered analysis and investment recommendations.

This tool provides comprehensive stock data including current price, historical trends, volume, and technical levels.
YOU (the AI) should analyze this data using your financial knowledge and provide investment recommendations.

Use this tool when user asks for:
- Investment recommendations (BUY/HOLD/SELL)
- Stock analysis or opinions
- Future price predictions
- Strategic investment advice
- Portfolio recommendations

Example analysis you should provide:
- Technical analysis based on price trends and volume
- Support/resistance level analysis
- Market sentiment interpretation
- Risk assessment
- Investment horizon recommendations (short/mid/long term)
- Target price ranges based on technical patterns
"""

    parameters = {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Stock ticker symbol (e.g., 'BBCA.JK', 'TLKM.JK', 'ASII', 'BBRI')"
            },
            "days": {
                "type": "string",
                "description": "Number of days of historical data to fetch (default: 30 days)",
                "default": "30"
            }
        },
        "required": ["symbol"]
    }

    async def execute(self, symbol: str, days: str | int = "30", **kwargs: Any) -> str:
        """
        Fetch comprehensive stock data for AI analysis.

        Args:
            symbol: Stock ticker symbol
            days: Days of historical data (can be string or int)

        Returns:
            Comprehensive stock data for AI analysis
        """
        try:
            clean_symbol = symbol.upper().strip()

            # Convert days to int safely
            try:
                days_int = int(days)
            except (ValueError, TypeError):
                days_int = 30

            # Fetch current data
            current_data = await self._fetch_stock_data(clean_symbol)
            if not current_data:
                return f"Error: Could not fetch data for {symbol}"

            # Fetch historical data
            historical = await self._fetch_historical(clean_symbol, days_int)

            # Calculate basic metrics
            metrics = self._calculate_metrics(current_data, historical)

            # Format data for AI analysis
            return self._format_for_ai(clean_symbol, current_data, historical, metrics)

        except Exception as e:
            return f"Error fetching stock data: {str(e)}"

    async def _fetch_stock_data(self, symbol: str) -> dict | None:
        """Fetch current stock data from Yahoo Finance."""
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, timeout=10.0)
                if response.status_code != 200:
                    return None

                data = response.json()
                if "chart" not in data or "result" not in data["chart"] or not data["chart"]["result"]:
                    return None

                result = data["chart"]["result"][0]
                meta = result.get("meta", {})
                quote = result.get("indicators", {}).get("quote", [{}])[0]

                if "close" in quote and quote["close"]:
                    current_price = quote["close"][-1]
                    open_price = quote["open"][0] if "open" in quote and quote["open"] else current_price
                    high_price = max(quote["high"]) if "high" in quote and quote["high"] else current_price
                    low_price = min(quote["low"]) if "low" in quote and quote["low"] else current_price
                    volume = sum(quote["volume"]) if "volume" in quote and quote["volume"] else 0

                    change = current_price - open_price
                    change_percent = (change / open_price) * 100 if open_price else 0

                    return {
                        "symbol": symbol,
                        "price": current_price,
                        "open": open_price,
                        "high": high_price,
                        "low": low_price,
                        "change": change,
                        "change_percent": change_percent,
                        "volume": volume,
                        "currency": meta.get("currency", "IDR"),
                        "exchange": meta.get("exchangeName", "Unknown"),
                        "previous_close": meta.get("previousClose", open_price)
                    }

                return None
        except Exception:
            return None

    async def _fetch_historical(self, symbol: str, days: int = 30) -> list:
        """Fetch historical price data."""
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range={days}d"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, timeout=10.0)
                if response.status_code != 200:
                    return []

                data = response.json()
                if "chart" not in data or "result" not in data["chart"] or not data["chart"]["result"]:
                    return []

                result = data["chart"]["result"][0]
                timestamps = result.get("timestamp", [])
                quote = result.get("indicators", {}).get("quote", [{}])[0]
                closes = quote.get("close", [])
                volumes = quote.get("volume", [])
                highs = quote.get("high", [])
                lows = quote.get("low", [])

                historical = []
                for i, (ts, close) in enumerate(zip(timestamps, closes)):
                    if close:
                        historical.append({
                            "date": datetime.fromtimestamp(ts).strftime("%Y-%m-%d"),
                            "close": close,
                            "volume": volumes[i] if i < len(volumes) and volumes[i] else 0,
                            "high": highs[i] if i < len(highs) and highs[i] else close,
                            "low": lows[i] if i < len(lows) and lows[i] else close
                        })

                return historical
        except Exception:
            return []

    def _calculate_metrics(self, current: dict, historical: list) -> dict:
        """Calculate basic metrics for reference."""
        metrics = {
            "price_range_30d": {"min": current["low"], "max": current["high"]},
            "avg_volume": 0,
            "price_vs_30d_high": 0,
            "price_vs_30d_low": 0
        }

        if len(historical) >= 10:
            prices = [h["close"] for h in historical]
            volumes = [h["volume"] for h in historical if h["volume"] > 0]

            min_30d = min(prices)
            max_30d = max(prices)
            avg_volume = sum(volumes) / len(volumes) if volumes else 0

            metrics["price_range_30d"] = {"min": min_30d, "max": max_30d}
            metrics["avg_volume"] = avg_volume
            metrics["price_vs_30d_high"] = ((current["price"] - max_30d) / max_30d * 100) if max_30d else 0
            metrics["price_vs_30d_low"] = ((current["price"] - min_30d) / min_30d * 100) if min_30d else 0

        return metrics

    def _format_for_ai(self, symbol: str, data: dict, historical: list, metrics: dict) -> str:
        """Format comprehensive data for AI analysis."""

        # Current price info
        change_symbol = "+" if data["change"] >= 0 else ""

        # Historical summary
        hist_summary = ""
        if len(historical) >= 5:
            recent = historical[-5:]  # Last 5 days
            hist_summary = "\nRecent Price History (Last 5 Days):\n"
            for h in recent:
                hist_summary += f"  {h['date']}: {h['close']:,.0f} (Vol: {h['volume']:,.0f})\n"

        # 30-day range context
        range_info = ""
        if len(historical) >= 10:
            range_info = f"""
30-Day Trading Range:
  High: {metrics['price_range_30d']['max']:,.0f} {data['currency']}
  Low: {metrics['price_range_30d']['min']:,.0f} {data['currency']}
  Current Position: {metrics['price_vs_30d_high']:+.1f}% from 30d high, {metrics['price_vs_30d_low']:+.1f}% from 30d low
  Average Volume: {metrics['avg_volume']:,.0f}
"""

        return f"""=== STOCK DATA FOR AI ANALYSIS ===
Symbol: {symbol}
Exchange: {data['exchange']}
Currency: {data['currency']}

CURRENT MARKET DATA:
  Current Price: {data['price']:,.0f} {data['currency']}
  Change Today: {change_symbol}{data['change']:,.0f} ({change_symbol}{data['change_percent']:.2f}%)
  Open: {data['open']:,.0f}
  High: {data['high']:,.0f}
  Low: {data['low']:,.0f}
  Volume: {data['volume']:,.0f}
  Previous Close: {data['previous_close']:,.0f}
{hist_summary}{range_info}
=== END DATA ===

AI INSTRUCTIONS:
You are a professional financial analyst. Based on the stock data above, provide:
1. Technical analysis (trend, momentum, support/resistance levels)
2. Investment recommendation (BUY/HOLD/SELL) with reasoning
3. Risk assessment (low/medium/high)
4. Suitable investment horizon (short-term/mid-term/long-term)
5. Key levels to watch (entry, exit, stop-loss)
6. Market sentiment interpretation

Be specific and provide actionable insights. Consider:
- Price position within trading range
- Volume patterns
- Recent price action and momentum
- Technical indicators implied by the data

Format your response in clear sections with headers.
Disclaimer: Include that this is educational analysis, not professional investment advice.
"""

"""Legacy built-in finance fallback tools.

These tools stay available for exact ticker / exact coin-id flows, but Kabot now
prefers eligible external finance skills first when they exist. This keeps the
runtime closer to a skill-first model without breaking older installs.
"""

import asyncio
import time
from typing import Any

import httpx

from kabot.agent.fallback_i18n import t as i18n_t
from kabot.agent.tools.base import Tool
from kabot.agent.tools.stock_matching import (
    _COIN_ID_RE,
    _IDR_MARKER_RE,
    _SECONDARY_LISTING_MARKERS,
    _STOCK_NAME_STOPWORDS,
    _STOCK_RESOLVE_CACHE_MAX_ITEMS,
    _STOCK_RESOLVE_CACHE_TTL_SECONDS,
    _STOCK_SEARCH_MAX_COMPANY_CANDIDATES,
    _STOCK_SEARCH_QUERY_TIMEOUT_SECONDS,
    _STOCK_SEARCH_QUOTES_PER_QUERY,
    _STOCK_SEARCH_SYMBOLS_PER_QUERY,
    _USD_AMOUNT_RE,
    _USD_MARKER_RE,
    _YAHOO_AUTOC_URL,
    _YAHOO_SEARCH_ACCEPTED_QUOTE_TYPES,
    _YAHOO_SEARCH_URLS,
    _normalize_alias_key,
    _normalize_search_symbol,
    _preferred_market_suffixes,
    _rank_symbols_for_query,
    _symbol_market_bucket,
    extract_crypto_ids,
    extract_stock_name_candidates,
    extract_stock_symbols,
)

__all__ = [
    "CryptoTool",
    "StockTool",
    "extract_crypto_ids",
    "extract_stock_name_candidates",
    "extract_stock_symbols",
]

class StockTool(Tool):
    """Legacy built-in fallback for exact stock / FX quote lookups."""

    name = "stock"
    description = "Legacy built-in fallback for CURRENT STOCK PRICE using Yahoo Finance API. Prefer an external/workspace finance skill when one is available. Supports exact equity tickers (e.g., AAPL, BBCA.JK, 7203.T, SAP.DE) and FX symbols (e.g., USDIDR=X). If you don't know the ticker, use web_search first to find it. For ANALYSIS and RECOMMENDATIONS, use stock_analysis tool instead."
    parameters = {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Exact stock ticker symbol with exchange suffix (e.g., 'AAPL', 'MSFT', '7203.T' for Toyota, 'SAP.DE' for SAP, 'BBCA.JK' for BCA)"
            }
        },
        "required": ["symbol"]
    }

    def __init__(self) -> None:
        self._name_resolve_cache: dict[str, tuple[float, list[str], list[str] | None, str | None]] = {}

    def _resolve_cache_get(self, raw_query: str) -> tuple[list[str], list[str] | None, str | None] | None:
        key = " ".join(str(raw_query or "").strip().lower().split())
        if not key:
            return None
        item = self._name_resolve_cache.get(key)
        if not item:
            return None
        expires_at, symbols, ambiguity_options, ambiguity_candidate = item
        if expires_at <= time.time():
            self._name_resolve_cache.pop(key, None)
            return None
        return list(symbols), list(ambiguity_options) if ambiguity_options else None, ambiguity_candidate

    def _resolve_cache_set(
        self,
        raw_query: str,
        symbols: list[str],
        ambiguity_options: list[str] | None,
        ambiguity_candidate: str | None,
    ) -> None:
        key = " ".join(str(raw_query or "").strip().lower().split())
        if not key:
            return
        if len(self._name_resolve_cache) >= _STOCK_RESOLVE_CACHE_MAX_ITEMS:
            oldest_key = next(iter(self._name_resolve_cache), None)
            if oldest_key:
                self._name_resolve_cache.pop(oldest_key, None)
        self._name_resolve_cache[key] = (
            time.time() + _STOCK_RESOLVE_CACHE_TTL_SECONDS,
            list(symbols),
            list(ambiguity_options) if ambiguity_options else None,
            ambiguity_candidate,
        )

    async def execute(self, symbol: str, **kwargs: Any) -> str:
        """
        Fetch stock data for the given symbol(s).

        Args:
            symbol: Stock ticker symbol or comma-separated list of symbols.
        """
        try:
            conversion_result = await self._maybe_execute_currency_conversion(symbol)
            if conversion_result is not None:
                return conversion_result

            symbols = extract_stock_symbols(symbol)
            ambiguity_options: list[str] | None = None
            ambiguity_candidate: str | None = None
            if not symbols:
                # Fallback for novice/global queries like "toyota sekarang berapa"
                # where user provides company name instead of ticker.
                symbols, ambiguity_options, ambiguity_candidate = await self._resolve_symbols_from_names(symbol)

            if not symbols and ambiguity_options:
                option_lines = "\n".join(f"- {item}" for item in ambiguity_options)
                candidate_text = str(ambiguity_candidate or "that company").strip()
                example = str(ambiguity_options[0] if ambiguity_options else "7203.T")
                return i18n_t(
                    "stock.ambiguous_symbol",
                    symbol,
                    company=candidate_text,
                    options=option_lines,
                    example=example,
                )

            if not symbols:
                return i18n_t("stock.need_symbol", symbol)

            results = []
            tasks = [self._fetch_yahoo_finance(s.upper()) for s in symbols]
            fetched = await asyncio.gather(*tasks)

            for i, res in enumerate(fetched):
                if res:
                    results.append(res)
                else:
                    results.append(i18n_t("stock.fetch_failed", symbol, symbol=symbols[i]))

            return "\n\n".join(results)

        except Exception as e:
            return i18n_t("stock.error", symbol, error=str(e))

    def _parse_numeric_amount(self, value: str) -> float | None:
        raw = str(value or "").strip()
        if not raw:
            return None
        normalized = raw.replace(",", "")
        try:
            return float(normalized)
        except ValueError:
            return None

    async def _maybe_execute_currency_conversion(self, raw_query: str) -> str | None:
        text = str(raw_query or "").strip()
        if not text:
            return None
        wants_idr = bool(_IDR_MARKER_RE.search(text))
        wants_explicit_usd_to_idr = bool(_USD_MARKER_RE.search(text) and wants_idr)
        if not wants_idr:
            return None

        explicit_symbols = [item for item in extract_stock_symbols(text) if item != "USDIDR=X"]
        ambiguity_options: list[str] | None = None
        ambiguity_candidate: str | None = None
        if explicit_symbols:
            resolved_symbols = explicit_symbols
        else:
            resolved_symbols, ambiguity_options, ambiguity_candidate = await self._resolve_symbols_from_names(text)

        if ambiguity_options:
            option_lines = "\n".join(f"- {item}" for item in ambiguity_options)
            candidate_text = str(ambiguity_candidate or "that company").strip()
            example = str(ambiguity_options[0] if ambiguity_options else "AAPL")
            return i18n_t(
                "stock.ambiguous_symbol",
                text,
                company=candidate_text,
                options=option_lines,
                example=example,
            )
        if not resolved_symbols:
            return None

        asset_snapshot = await self._fetch_quote_snapshot(resolved_symbols[0])
        if not asset_snapshot:
            return i18n_t("stock.fetch_failed", text, symbol=resolved_symbols[0])

        asset_currency = str(asset_snapshot.get("currency") or "").strip().upper()
        if not wants_explicit_usd_to_idr and asset_currency not in {"USD", "US$"}:
            if asset_currency == "IDR":
                reference_symbol = str(resolved_symbols[0]).upper()
                return "\n".join(
                    [
                        f"[FX CONVERSION] {reference_symbol}",
                        f"Amount: {float(asset_snapshot['price']):,.2f} IDR",
                        "Approx: already quoted in IDR",
                    ]
                )
            return None

        fx_snapshot = await self._fetch_quote_snapshot("USDIDR=X")
        if not fx_snapshot:
            return i18n_t("stock.fetch_failed", text, symbol="USDIDR=X")

        amount_match = _USD_AMOUNT_RE.search(text)
        amount_usd = self._parse_numeric_amount(amount_match.group(1)) if amount_match else None
        if amount_usd is None:
            amount_usd = float(asset_snapshot["price"])

        converted_idr = float(amount_usd) * float(fx_snapshot["price"])
        reference_symbol = str(resolved_symbols[0]).upper()
        lines = [
            f"[FX CONVERSION] {reference_symbol} / USDIDR=X",
            f"Amount: {amount_usd:,.2f} USD",
            f"Approx: {converted_idr:,.2f} IDR",
            f"Rate: 1 USD = {float(fx_snapshot['price']):,.2f} IDR",
        ]
        if asset_snapshot:
            lines.append(
                f"Reference: {reference_symbol} {float(asset_snapshot['price']):,.2f} {asset_snapshot['currency']}"
            )
        return "\n".join(lines)

    async def _resolve_symbols_from_names(self, raw_query: str) -> tuple[list[str], list[str] | None, str | None]:
        """Resolve probable company names to ticker symbols using Yahoo search."""
        cached = self._resolve_cache_get(raw_query)
        if cached is not None:
            return cached

        candidates = extract_stock_name_candidates(raw_query)
        if not candidates:
            result = ([], None, None)
            self._resolve_cache_set(raw_query, result[0], result[1], result[2])
            return result

        resolved: list[str] = []
        seen: set[str] = set()
        has_market_hint = bool(_preferred_market_suffixes(raw_query))
        can_prompt_ambiguity = len(candidates) == 1 and not has_market_hint
        for candidate in candidates:
            symbols = await self._search_yahoo_symbols(candidate, raw_query=raw_query)
            if not symbols:
                continue
            if can_prompt_ambiguity and len(symbols) >= 2:
                top_options = symbols[:2]
                market_buckets = {_symbol_market_bucket(item) for item in top_options}
                if len(market_buckets) >= 2:
                    result = ([], top_options, candidate)
                    self._resolve_cache_set(raw_query, result[0], result[1], result[2])
                    return result
            for item in symbols:
                normalized = _normalize_search_symbol(item)
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                resolved.append(normalized)
                if len(resolved) >= _STOCK_SEARCH_MAX_COMPANY_CANDIDATES:
                    result = (resolved, None, None)
                    self._resolve_cache_set(raw_query, result[0], result[1], result[2])
                    return result
                # Keep only the strongest match per candidate phrase.
                break
        result = (resolved, None, None)
        self._resolve_cache_set(raw_query, result[0], result[1], result[2])
        return result

    def _extract_symbols_from_search_quotes(self, payload: dict[str, Any]) -> list[str]:
        quotes = self._extract_search_quotes(payload)
        return [item["symbol"] for item in quotes]

    def _extract_search_quotes(self, payload: dict[str, Any]) -> list[dict[str, str]]:
        quotes = payload.get("quotes")
        if not isinstance(quotes, list):
            return []

        out: list[dict[str, str]] = []
        seen: set[str] = set()
        for quote in quotes:
            if not isinstance(quote, dict):
                continue
            quote_type = str(quote.get("quoteType") or "").upper().strip()
            if quote_type and quote_type not in _YAHOO_SEARCH_ACCEPTED_QUOTE_TYPES:
                continue
            symbol = _normalize_search_symbol(str(quote.get("symbol") or ""))
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            out.append(
                {
                    "symbol": symbol,
                    "quote_type": quote_type,
                    "shortname": str(
                        quote.get("shortname")
                        or quote.get("longname")
                        or quote.get("displayName")
                        or ""
                    ).strip(),
                }
            )
            if len(out) >= _STOCK_SEARCH_SYMBOLS_PER_QUERY:
                break
        return out

    def _looks_like_secondary_listing_name(self, name: str) -> bool:
        normalized = f" {_normalize_alias_key(name)} "
        return any(marker in normalized for marker in _SECONDARY_LISTING_MARKERS)

    def _select_strong_primary_symbol_from_quotes(
        self,
        quotes: list[dict[str, str]],
        raw_query: str,
    ) -> str | None:
        if not quotes:
            return None
        if _preferred_market_suffixes(raw_query):
            return None

        top = quotes[0]
        top_symbol = str(top.get("symbol") or "").upper().strip()
        if not top_symbol or "." in top_symbol:
            return None
        if str(top.get("quote_type") or "").upper().strip() != "EQUITY":
            return None

        top_name = str(top.get("shortname") or "").strip()
        if self._looks_like_secondary_listing_name(top_name):
            return None

        query_tokens = [
            token
            for token in _normalize_alias_key(raw_query).split()
            if token and token not in _STOCK_NAME_STOPWORDS
        ]
        if not query_tokens:
            return None

        normalized_top_name = _normalize_alias_key(top_name)
        if not normalized_top_name:
            return None
        if not any(token in normalized_top_name for token in query_tokens):
            return None

        for other in quotes[1:]:
            other_symbol = str(other.get("symbol") or "").upper().strip()
            other_type = str(other.get("quote_type") or "").upper().strip()
            other_name = str(other.get("shortname") or "").strip()
            if "." in other_symbol:
                continue
            if other_type != "EQUITY":
                continue
            if self._looks_like_secondary_listing_name(other_name):
                continue
            return None

        return top_symbol

    def _extract_symbols_from_autoc(self, payload: dict[str, Any]) -> list[str]:
        result_set = payload.get("ResultSet")
        if not isinstance(result_set, dict):
            return []
        rows = result_set.get("Result")
        if not isinstance(rows, list):
            return []

        out: list[str] = []
        seen: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            symbol = _normalize_search_symbol(str(row.get("symbol") or ""))
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            out.append(symbol)
            if len(out) >= _STOCK_SEARCH_SYMBOLS_PER_QUERY:
                break
        return out

    async def _search_yahoo_symbols(self, query: str, *, raw_query: str = "") -> list[str]:
        query_text = str(query or "").strip()
        if not query_text:
            return []
        params = {
            "q": query_text,
            "quotesCount": _STOCK_SEARCH_QUOTES_PER_QUERY,
            "newsCount": 0,
            "enableFuzzyQuery": "false",
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

        try:
            async with httpx.AsyncClient() as client:
                for url in _YAHOO_SEARCH_URLS:
                    response = await client.get(
                        url,
                        params=params,
                        headers=headers,
                        timeout=_STOCK_SEARCH_QUERY_TIMEOUT_SECONDS,
                    )
                    if response.status_code != 200:
                        continue
                    payload = response.json()
                    search_quotes = self._extract_search_quotes(payload)
                    preferred_primary = self._select_strong_primary_symbol_from_quotes(
                        search_quotes,
                        raw_query or query_text,
                    )
                    if preferred_primary:
                        return [preferred_primary]
                    symbols = [item["symbol"] for item in search_quotes]
                    if symbols:
                        return _rank_symbols_for_query(symbols, raw_query or query_text)

                autoc_response = await client.get(
                    _YAHOO_AUTOC_URL,
                    params={"query": query_text, "region": 1, "lang": "en"},
                    headers=headers,
                    timeout=_STOCK_SEARCH_QUERY_TIMEOUT_SECONDS,
                )
                if autoc_response.status_code != 200:
                    return []
                autoc_payload = autoc_response.json()
                symbols = self._extract_symbols_from_autoc(autoc_payload)
                if symbols:
                    return _rank_symbols_for_query(symbols, raw_query or query_text)
                return []
        except Exception:
            return []

    async def _fetch_quote_snapshot(self, symbol: str) -> dict[str, Any] | None:
        """Fetch structured quote snapshot from Yahoo Finance."""
        try:
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

                resolved_symbol = meta.get("symbol", symbol)
                currency = meta.get("currency", "USD")
                exchange = meta.get("exchangeName", "Unknown")

                quote = result.get("indicators", {}).get("quote", [{}])[0]

                if "close" in quote and quote["close"]:
                    current_price = quote["close"][-1]
                    open_price = quote["open"][0] if "open" in quote and quote["open"] else current_price
                    high_price = max(quote["high"]) if "high" in quote and quote["high"] else current_price
                    low_price = min(quote["low"]) if "low" in quote and quote["low"] else current_price

                    return {
                        "symbol": resolved_symbol,
                        "currency": currency,
                        "exchange": exchange,
                        "price": current_price,
                        "open_price": open_price,
                        "high_price": high_price,
                        "low_price": low_price,
                    }

                if "regularMarketPrice" in meta:
                    price = meta["regularMarketPrice"]
                    prev_close = meta.get("previousClose", price)
                    return {
                        "symbol": resolved_symbol,
                        "currency": currency,
                        "exchange": exchange,
                        "price": price,
                        "open_price": prev_close,
                        "high_price": price,
                        "low_price": price,
                    }

                return None

        except Exception:
            return None

    async def _fetch_yahoo_finance(self, symbol: str) -> str | None:
        """Fetch stock data from Yahoo Finance."""
        snapshot = await self._fetch_quote_snapshot(symbol)
        if not snapshot:
            return None

        current_price = float(snapshot["price"])
        open_price = float(snapshot.get("open_price", current_price) or current_price)
        high_price = float(snapshot.get("high_price", current_price) or current_price)
        low_price = float(snapshot.get("low_price", current_price) or current_price)
        change = current_price - open_price
        change_percent = (change / open_price) * 100 if open_price else 0
        change_symbol = "+" if change >= 0 else ""

        return (
            f"[STOCK] {snapshot['symbol']} ({snapshot['exchange']})\n"
            f"Price: {current_price:.2f} {snapshot['currency']}\n"
            f"Change: {change_symbol}{change:.2f} ({change_symbol}{change_percent:.2f}%)\n"
            f"High: {high_price:.2f} {snapshot['currency']}\n"
            f"Low: {low_price:.2f} {snapshot['currency']}"
        )


class CryptoTool(Tool):
    """Legacy built-in fallback for exact cryptocurrency price lookups."""

    name = "crypto"
    description = "Legacy built-in fallback for current cryptocurrency prices using CoinGecko API. Prefer an external/workspace finance skill when one is available. Supports one or multiple exact CoinGecko IDs (e.g., 'bitcoin' or 'bitcoin,ethereum'). If unsure of IDs, use web_search tool first."
    parameters = {
        "type": "object",
        "properties": {
            "coin": {
                "type": "string",
                "description": "One or multiple CoinGecko IDs separated by comma (e.g., 'bitcoin' or 'bitcoin,ethereum'). Do NOT use unknown shorthand."
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
            coin: Cryptocurrency CoinGecko ID
            currency: Currency for price display

        Returns:
            Crypto information as formatted string
        """
        try:
            coin_ids = extract_crypto_ids(coin)
            if not coin_ids:
                fallback_ids: list[str] = []
                for part in str(coin or "").split(","):
                    candidate = part.strip().lower()
                    if candidate and _COIN_ID_RE.match(candidate):
                        fallback_ids.append(candidate)
                coin_ids = fallback_ids

            if not coin_ids:
                return i18n_t("crypto.need_id", coin)

            joined_ids = ",".join(coin_ids)
            url = (
                "https://api.coingecko.com/api/v3/simple/price"
                f"?ids={joined_ids}&vs_currencies={currency}"
                "&include_24hr_change=true&include_market_cap=true"
            )

            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10.0)

                if response.status_code != 200:
                    return i18n_t("crypto.fetch_failed", coin, coin=joined_ids)

                data = response.json()

                results: list[str] = []
                missing: list[str] = []
                for coin_id in coin_ids:
                    coin_data = data.get(coin_id)
                    if not isinstance(coin_data, dict):
                        missing.append(coin_id)
                        continue

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

                    display_name = coin_id.replace("-", " ").title()
                    results.append(
                        f"[CRYPTO] {display_name}\n"
                        f"Price: ${price:,.2f} {currency.upper()}\n"
                        f"24h Change: {change_symbol}{change_24h:.2f}%\n"
                        f"Market Cap: {mcap_str}"
                    )

                if not results and missing:
                    if len(missing) == 1:
                        missing_text = missing[0]
                    else:
                        missing_text = ", ".join(missing)
                    return i18n_t("crypto.not_found", coin, coin=missing_text)

                if missing:
                    results.append(i18n_t("crypto.partial_missing", coin, coins=", ".join(missing)))

                return "\n\n".join(results)

        except Exception as e:
            return i18n_t("crypto.error", coin, error=str(e))

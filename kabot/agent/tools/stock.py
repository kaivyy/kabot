"""Stock tool for fetching stock market information."""

import asyncio
import json
import os
import re
import time
from typing import Any

import httpx

from kabot.agent.fallback_i18n import t as i18n_t
from kabot.agent.tools.base import Tool

_STOCK_STOPWORDS = {
    "STOCK",
    "STOCKS",
    "SAHAM",
    "PRICE",
    "HARGA",
    "MARKET",
    "PASAR",
    "NOW",
    "SEKARANG",
    "TODAY",
    "HARI",
    "INI",
    "BERAPA",
    "CEK",
    "CHECK",
    "TOLONG",
    "PLEASE",
    "KALAU",
    "COBA",
    "DAN",
    "ATAU",
    "BANK",
    "INDONESIA",
    "IDX",
    "IHSG",
    "BEI",
    "JAKARTA",
    "IYA",
    "YA",
    "GAS",
    "LANJUT",
    "OK",
    "OKE",
    "MAAF",
    "KAMU",
    "AKU",
    "BENER",
    "BENAR",
    "BISA",
    "BISAKAH",
}

_BASE_IDX_ALIAS_TO_SYMBOL = {
    "BBCA": "BBCA.JK",
    "BCA": "BBCA.JK",
    "BANK CENTRAL ASIA": "BBCA.JK",
    "BBRI": "BBRI.JK",
    "BRI": "BBRI.JK",
    "BANK RAKYAT INDONESIA": "BBRI.JK",
    "BMRI": "BMRI.JK",
    "MANDIRI": "BMRI.JK",
    "BANK MANDIRI": "BMRI.JK",
    "BBNI": "BBNI.JK",
    "BNI": "BBNI.JK",
    "BANK NEGARA INDONESIA": "BBNI.JK",
    "TLKM": "TLKM.JK",
    "TELKOM": "TLKM.JK",
    "ASII": "ASII.JK",
    "GOTO": "GOTO.JK",
    "ANTM": "ANTM.JK",
    "UNVR": "UNVR.JK",
    "INDF": "INDF.JK",
    "ICBP": "ICBP.JK",
    "ADARO": "ADRO.JK",
    "ADARO ENERGY": "ADRO.JK",
    "ADARO ENERGY INDONESIA": "ADRO.JK",
    "TOBA": "TOBA.JK",
    "TOBA BARA": "TOBA.JK",
    "TOBA BARA SEJAHTRA": "TOBA.JK",
}

_KNOWN_IDX_SYMBOLS = {
    "BBCA",
    "BBRI",
    "BMRI",
    "BBNI",
    "TLKM",
    "ASII",
    "GOTO",
    "ANTM",
    "UNVR",
    "INDF",
    "ICBP",
    "ADRO",
    "TOBA",
    "MDKA",
    "PTBA",
    "ACES",
    "SMGR",
    "EXCL",
    "ISAT",
    "KLBF",
    "SIDO",
    "CPIN",
    "JPFA",
    "AMRT",
    "MAPI",
    "SRTG",
    "TOWR",
}

_KNOWN_GLOBAL_SYMBOLS = {
    "AAPL",
    "MSFT",
    "TSLA",
    "NVDA",
    "META",
    "GOOG",
    "AMZN",
}

_PLACEHOLDER_ROOTS = {"XXXX", "TICKER", "SYMBOL", "EXAMPLE"}
_EXPLICIT_SYMBOL_RE = re.compile(r"^[A-Z0-9]{1,8}\.[A-Z]{1,4}$")
_BARE_SYMBOL_RE = re.compile(r"^[A-Z]{1,5}$")
_GENERAL_SYMBOL_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-^=]{0,14}$")
_COIN_ID_RE = re.compile(r"^[a-z0-9-]{2,64}$")
_ALIAS_KEY_RE = re.compile(r"[^a-z0-9]+")
_STOCK_ALIAS_ENV_PATH = "KABOT_STOCK_ALIASES_PATH"
_STOCK_ALIAS_DEFAULT_PATH = os.path.expanduser("~/.kabot/stock_aliases.json")
_YAHOO_SEARCH_URLS = (
    "https://query2.finance.yahoo.com/v1/finance/search",
    "https://query1.finance.yahoo.com/v1/finance/search",
)
_YAHOO_AUTOC_URL = "https://autoc.finance.yahoo.com/autoc"
_YAHOO_SEARCH_ACCEPTED_QUOTE_TYPES = {"EQUITY", "ETF", "MUTUALFUND", "INDEX"}
_STOCK_SEARCH_QUERY_TIMEOUT_SECONDS = 6.0
_STOCK_SEARCH_MAX_COMPANY_CANDIDATES = 3
_STOCK_SEARCH_QUOTES_PER_QUERY = 8
_STOCK_SEARCH_SYMBOLS_PER_QUERY = 2
_STOCK_RESOLVE_CACHE_TTL_SECONDS = 600
_STOCK_RESOLVE_CACHE_MAX_ITEMS = 256
_MARKET_HINT_SUFFIXES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("jepang", (".T",)),
    ("japan", (".T",)),
    ("tokyo", (".T",)),
    ("indonesia", (".JK",)),
    ("idx", (".JK",)),
    ("jakarta", (".JK",)),
    ("germany", (".DE",)),
    ("jerman", (".DE",)),
    ("deutschland", (".DE",)),
    ("canada", (".TO",)),
    ("toronto", (".TO",)),
    ("uk", (".L",)),
    ("london", (".L",)),
    ("thailand", (".BK",)),
    ("bangkok", (".BK",)),
    ("philippines", (".PS",)),
    ("filipina", (".PS",)),
    ("manila", (".PS",)),
    ("hong kong", (".HK",)),
    ("china", (".HK", ".SS", ".SZ")),
    ("india", (".NS", ".BO")),
    ("us", ("",)),
    ("usa", ("",)),
    ("nyse", ("",)),
    ("nasdaq", ("",)),
)

_STOCK_NAME_STOPWORDS = {
    *(word.lower() for word in _STOCK_STOPWORDS),
    "the",
    "a",
    "an",
    "this",
    "that",
    "is",
    "are",
    "to",
    "for",
    "with",
    "at",
    "on",
    "of",
    "from",
    "dari",
    "yang",
    "itu",
    "ini",
    "saya",
    "anda",
    "kita",
    "kami",
    "bro",
    "sis",
    "broh",
    "umur",
    "age",
    "old",
    "tahun",
    "year",
}
_COMPANY_SPLIT_RE = re.compile(
    r"(?i)[,;]|(?:\b(?:and|dan|atau|or|plus|serta|with|vs)\b)"
)
_COMPANY_TOKEN_RE = re.compile(r"[^\W_][^\s,;:!?]{0,31}", re.UNICODE)
_PERSONAL_CHAT_MARKERS = {
    "umur",
    "age",
    "old",
    "years old",
    "berapa umur",
    "how old",
}
_NON_ASCII_RE = re.compile(r"[^\x00-\x7F]")

_CRYPTO_ALIAS_TO_ID = {
    "BITCOIN": "bitcoin",
    "BTC": "bitcoin",
    "ETHEREUM": "ethereum",
    "ETH": "ethereum",
    "SOLANA": "solana",
    "SOL": "solana",
    "DOGECOIN": "dogecoin",
    "DOGE": "dogecoin",
    "BINANCECOIN": "binancecoin",
    "BNB": "binancecoin",
    "CARDANO": "cardano",
    "ADA": "cardano",
    "RIPPLE": "ripple",
    "XRP": "ripple",
    "LITECOIN": "litecoin",
    "LTC": "litecoin",
}


def _looks_like_free_text(text: str) -> bool:
    tokens = [t for t in re.split(r"\s+", text.strip()) if t]
    if len(tokens) >= 4:
        return True
    return any(ch in text for ch in "?!:;\n")


def _edit_distance_leq_one(left: str, right: str) -> bool:
    if left == right:
        return True
    if abs(len(left) - len(right)) > 1:
        return False
    i = 0
    j = 0
    mismatches = 0
    while i < len(left) and j < len(right):
        if left[i] == right[j]:
            i += 1
            j += 1
            continue
        mismatches += 1
        if mismatches > 1:
            return False
        if len(left) > len(right):
            i += 1
        elif len(left) < len(right):
            j += 1
        else:
            i += 1
            j += 1
    if i < len(left) or j < len(right):
        mismatches += 1
    return mismatches <= 1


def _resolve_idx_typo(symbol: str) -> str | None:
    token = str(symbol or "").upper().strip()
    if not token or len(token) < 3:
        return None
    for known in _KNOWN_IDX_SYMBOLS:
        if _edit_distance_leq_one(token, known):
            return known
    return None


def _normalize_alias_key(value: str) -> str:
    collapsed = _ALIAS_KEY_RE.sub(" ", str(value or "").lower())
    return " ".join(collapsed.split()).strip()


def _normalize_stock_symbol(value: str) -> str | None:
    symbol = str(value or "").upper().strip()
    if not symbol:
        return None
    if _EXPLICIT_SYMBOL_RE.match(symbol):
        left, right = symbol.split(".", 1)
        if right == "JK" and left not in _KNOWN_IDX_SYMBOLS:
            corrected = _resolve_idx_typo(left)
            if corrected:
                return f"{corrected}.JK"
        return symbol
    if symbol in _KNOWN_IDX_SYMBOLS:
        return f"{symbol}.JK"
    if symbol in _KNOWN_GLOBAL_SYMBOLS:
        return symbol
    return None


def _normalize_search_symbol(value: str) -> str | None:
    """Normalize Yahoo search symbol into a safe tradable token."""
    normalized = _normalize_stock_symbol(value)
    if normalized:
        return normalized

    symbol = str(value or "").upper().strip()
    if not symbol:
        return None
    if _GENERAL_SYMBOL_RE.match(symbol):
        if symbol.startswith("^"):
            # Skip indices in this stock tool path; they are not equities.
            return None
        return symbol
    return None


def _preferred_market_suffixes(raw_query: str) -> list[str]:
    normalized = " ".join(str(raw_query or "").strip().lower().split())
    if not normalized:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for hint, suffixes in _MARKET_HINT_SUFFIXES:
        if hint in normalized:
            for suffix in suffixes:
                if suffix in seen:
                    continue
                seen.add(suffix)
                out.append(suffix)
    return out


def _rank_symbols_for_query(symbols: list[str], raw_query: str) -> list[str]:
    preferences = _preferred_market_suffixes(raw_query)
    if not preferences:
        return symbols

    def _score(symbol: str) -> int:
        token = str(symbol or "").upper().strip()
        if not token:
            return -1
        for idx, suffix in enumerate(preferences):
            if suffix == "":
                if "." not in token:
                    return 100 - idx
                continue
            if token.endswith(suffix.upper()):
                return 100 - idx
        return 0

    decorated = [(idx, symbol, _score(symbol)) for idx, symbol in enumerate(symbols)]
    decorated.sort(key=lambda item: (-item[2], item[0]))
    return [symbol for _idx, symbol, _score_value in decorated]


def _symbol_market_bucket(symbol: str) -> str:
    token = str(symbol or "").upper().strip()
    if "." in token:
        return token.rsplit(".", 1)[1]
    return "US"


def _looks_like_personal_small_talk(text: str) -> bool:
    normalized = " ".join(str(text or "").strip().lower().split())
    if not normalized:
        return False
    return any(marker in normalized for marker in _PERSONAL_CHAT_MARKERS)


def _is_non_latin_compact_query(text: str) -> bool:
    """Heuristic for short non-Latin company-name style queries."""
    raw = str(text or "").strip()
    if not raw:
        return False
    if not _NON_ASCII_RE.search(raw):
        return False
    if len(raw) > 80:
        return False
    if re.search(r"(https?://|www\.)", raw, re.IGNORECASE):
        return False
    return True


def extract_stock_name_candidates(raw: str) -> list[str]:
    """
    Extract probable company-name phrases from free-text stock queries.

    This is intentionally conservative to avoid converting generic chat text into
    market lookups.
    """
    text = str(raw or "").strip()
    if not text:
        return []
    if _looks_like_personal_small_talk(text):
        return []
    # If explicit symbols already exist, don't trigger name-based fallback.
    if extract_stock_symbols(text):
        return []

    cleaned = re.sub(r"[\(\)\[\]\{\}\"'`]+", " ", text)
    chunks = [part.strip() for part in _COMPANY_SPLIT_RE.split(cleaned) if part.strip()]

    candidates: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        tokens = [match.group(0) for match in _COMPANY_TOKEN_RE.finditer(chunk)]
        kept: list[str] = []
        for token in tokens:
            token_clean = token.strip(".,:;!?")
            if not token_clean:
                continue
            token_lower = token_clean.lower()
            if token_lower in _STOCK_NAME_STOPWORDS:
                continue
            if re.fullmatch(r"\d+(?:\.\d+)?", token_lower):
                continue
            if len(token_lower) <= 1:
                continue
            kept.append(token_clean)

        if not kept:
            continue
        # Prevent long prose from being sent to market symbol search.
        if len(kept) > 5:
            continue

        phrase = " ".join(kept).strip(" .,:;!?-")
        if not phrase:
            continue
        key = phrase.casefold()
        if key in seen:
            continue
        seen.add(key)
        candidates.append(phrase)
        if len(candidates) >= _STOCK_SEARCH_MAX_COMPANY_CANDIDATES:
            break

    if candidates:
        return candidates

    # Non-Latin fallback: keep compact original phrase so global users can query
    # by company name/script without explicit ticker suffix.
    compact = re.sub(r"\s+", " ", cleaned).strip(" .,:;!?-")
    if _is_non_latin_compact_query(compact):
        return [compact]

    return []


def _load_custom_idx_aliases() -> dict[str, str]:
    """Load optional stock aliases from JSON file for skill/user extensibility."""
    alias_path = str(os.environ.get(_STOCK_ALIAS_ENV_PATH, "") or "").strip()
    candidate_paths = [alias_path] if alias_path else []
    candidate_paths.append(_STOCK_ALIAS_DEFAULT_PATH)

    for path in candidate_paths:
        if not path or not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            continue

        source = payload.get("aliases") if isinstance(payload, dict) and isinstance(payload.get("aliases"), dict) else payload
        if not isinstance(source, dict):
            continue

        parsed: dict[str, str] = {}
        for raw_alias, raw_symbol in source.items():
            alias = _normalize_alias_key(str(raw_alias or ""))
            symbol = _normalize_stock_symbol(str(raw_symbol or ""))
            if alias and symbol:
                parsed[alias] = symbol
        if parsed:
            return parsed
    return {}


def _build_idx_alias_map() -> dict[str, str]:
    alias_map: dict[str, str] = {}
    for raw_alias, raw_symbol in _BASE_IDX_ALIAS_TO_SYMBOL.items():
        alias = _normalize_alias_key(raw_alias)
        symbol = _normalize_stock_symbol(raw_symbol)
        if alias and symbol:
            alias_map[alias] = symbol
    alias_map.update(_load_custom_idx_aliases())
    return alias_map


def _extract_alias_symbols_in_order(normalized_text: str, alias_map: dict[str, str]) -> list[str]:
    hits: list[tuple[int, int, str]] = []
    for alias, symbol in alias_map.items():
        if not alias or not symbol:
            continue
        pattern = re.compile(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])")
        for match in pattern.finditer(normalized_text):
            hits.append((match.start(), len(alias), symbol))
    hits.sort(key=lambda item: (item[0], -item[1]))

    ordered_symbols: list[str] = []
    seen: set[str] = set()
    for _start, _alias_len, symbol in hits:
        if symbol in seen:
            continue
        seen.add(symbol)
        ordered_symbols.append(symbol)
    return ordered_symbols


def extract_stock_symbols(raw: str) -> list[str]:
    text = (raw or "").strip()
    if not text:
        return []

    free_text = _looks_like_free_text(text)
    raw_tokens = [tok for tok in re.split(r"[,\s]+", text) if tok]
    allow_unknown_bare = len(raw_tokens) == 1 or "," in text
    alias_map = _build_idx_alias_map()
    normalized_alias_text = _normalize_alias_key(text)

    result: list[str] = []
    seen: set[str] = set()

    def _add(symbol: str) -> None:
        normalized = symbol.upper().strip()
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        result.append(normalized)

    for mapped in _extract_alias_symbols_in_order(normalized_alias_text, alias_map):
        _add(mapped)

    for token_raw in raw_tokens:
        token = token_raw.strip().strip("()[]{}\"'`")
        token = token.strip(".,;:!?")
        if not token:
            continue

        symbol = token.upper()
        if symbol in _STOCK_STOPWORDS:
            continue

        mapped = alias_map.get(_normalize_alias_key(symbol))
        if mapped:
            _add(mapped)
            continue

        if _EXPLICIT_SYMBOL_RE.match(symbol):
            left, right = symbol.split(".", 1)
            if left in _PLACEHOLDER_ROOTS:
                continue
            if len(set(left)) == 1 and len(left) >= 3:
                continue
            if right == "JK" and left not in _KNOWN_IDX_SYMBOLS:
                corrected = _resolve_idx_typo(left)
                if corrected:
                    _add(f"{corrected}.JK")
                    continue
            _add(symbol)
            continue

        if symbol in _KNOWN_IDX_SYMBOLS:
            _add(f"{symbol}.JK")
            continue

        if symbol in _KNOWN_GLOBAL_SYMBOLS:
            _add(symbol)
            continue

        if (
            allow_unknown_bare
            and not free_text
            and _BARE_SYMBOL_RE.match(symbol)
            and token == token.upper()
        ):
            _add(symbol)

    return result


# Backward-compat alias for older imports/tests.
def _extract_stock_symbols(raw: str) -> list[str]:
    return extract_stock_symbols(raw)


def extract_crypto_ids(raw: str) -> list[str]:
    text = str(raw or "").strip()
    if not text:
        return []

    tokens = [tok for tok in re.split(r"[,\s]+", text) if tok]
    result: list[str] = []
    seen: set[str] = set()

    def _add(coin_id: str) -> None:
        normalized = str(coin_id or "").strip().lower()
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        result.append(normalized)

    for token_raw in tokens:
        token = token_raw.strip().strip("()[]{}\"'`")
        token = token.strip(".,;:!?")
        if not token:
            continue

        mapped = _CRYPTO_ALIAS_TO_ID.get(token.upper())
        if mapped:
            _add(mapped)
            continue

        token_lower = token.lower()
        if token_lower in _CRYPTO_ALIAS_TO_ID.values():
            _add(token_lower)

    return result


class StockTool(Tool):
    """Get current stock price and market information."""

    name = "stock"
    description = "Get CURRENT STOCK PRICE only using Yahoo Finance API. Requires exact ticker symbol with exchange suffix (e.g., AAPL, BBCA.JK, 7203.T, SAP.DE). If you don't know the ticker, use web_search first to find it. For ANALYSIS and RECOMMENDATIONS, use stock_analysis tool instead."
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
        quotes = payload.get("quotes")
        if not isinstance(quotes, list):
            return []

        out: list[str] = []
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
            out.append(symbol)
            if len(out) >= _STOCK_SEARCH_SYMBOLS_PER_QUERY:
                break
        return out

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
                    symbols = self._extract_symbols_from_search_quotes(payload)
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
    description = "Get current cryptocurrency prices using CoinGecko API. Supports one or multiple exact CoinGecko IDs (e.g., 'bitcoin' or 'bitcoin,ethereum'). If unsure of IDs, use web_search tool first."
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

# Global Market Tools — Design Doc

**Date:** 2026-02-23
**Approach:** "The Pure Plugin" (AI Discovery)

## Problem

The `stock`, `stock_analysis`, and `crypto` tools contain hardcoded Indonesian market biases:
- `TOP10_ID` keyword with hardcoded IDX symbols
- `.JK` suffix examples throughout parameter descriptions
- Default currency hardcoded to `IDR`
- `coin_map` dictionary limiting crypto to 10 coins

Kabot is open-source and should support **all global markets** without regional bias.

## Design: AI-First Discovery (OpenClaw Philosophy)

Shift all market intelligence to the AI layer. Tools become **pure data fetchers** with no built-in knowledge of specific markets, tickers, or coins.

### StockTool Changes
1. **Remove** `TOP10_ID` keyword and hardcoded symbol list (lines 42-45)
2. **Update** `description` to guide AI: use `web_search` first if ticker is unknown
3. **Update** `symbol` parameter description with global examples (AAPL, 7203.T, SAP.DE, BBCA.JK)
4. **Remove** `market` parameter (redundant — Yahoo handles exchange suffixes natively)

### StockAnalysisTool Changes
1. **Update** `symbol` description: replace `.JK`-only examples with global examples
2. **Change** default currency fallback from `IDR` to `USD` (line 127)

### CryptoTool Changes
1. **Remove** entire `coin_map` dictionary (lines 176-187)
2. **Update** `description` to guide AI: use full CoinGecko ID (e.g., `bitcoin`, `ethereum`)
3. AI should use `web_search` to find the CoinGecko ID if unsure

### What AI Sees (New Tool Descriptions)

**stock:** *\"Get current stock price from Yahoo Finance. Requires exact ticker symbol with exchange suffix (e.g., AAPL, BBCA.JK, 7203.T, SAP.DE). If you don't know the ticker, use web_search first to find it.\"*

**crypto:** *\"Get cryptocurrency price from CoinGecko. Requires the CoinGecko coin ID (e.g., 'bitcoin', 'ethereum', 'solana'). If unsure of the ID, use web_search to find it on coingecko.com.\"*

## Verification
- Run existing tests (if any)
- Manual test: ask AI \"berapa harga saham Telkom?\" → AI should search ticker first, then call tool
- Manual test: ask AI \"harga Dogecoin\" → AI should know `dogecoin` or search CoinGecko
", "Complexity": 5, "Description": "Design document for globalizing market tools using the Pure Plugin / AI Discovery approach.", "EmptyFile": false, "IsArtifact": false, "Overwrite": true, "TargetFile": "C:\\Users\\Arvy Kairi\\Desktop\\bot\\kabot\\docs\\plans\\2026-02-23-global-market-tools-design.md"
}

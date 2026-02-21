# Military-Grade Progressive Enhancement Design

**Approach:** Opsi 3 — Progressive Enhancement (Hybrid)
**Principle:** If premium API key exists → use military route. If not → fallback to current lightweight route. Zero extra token cost.

---

## 1. Security & SSRF Guard (`web_fetch.py`)

**Current State:** Basic deny-list (localhost, 127.0.0.1, metadata endpoints). Checks hostname string only.

**Enhancement:**
- **DNS Resolution Guard:** Before connecting, resolve hostname → check if resolved IP is private/internal (prevents DNS rebinding attacks where `evil.com` resolves to `127.0.0.1`)
- **Redirect Chain Guard:** On each HTTP redirect hop, re-validate the new URL against SSRF rules
- **External Content Wrapping:** Wrap fetched web content in `[EXTERNAL_CONTENT]` markers so the LLM knows it's untrusted (prevents prompt injection from malicious websites)
- **Response Size Limiter:** Hard cap on response bytes (2MB) before text extraction

**Token Impact:** Zero. All logic runs in Python, invisible to LLM.

**Files Modified:** `kabot/agent/tools/web_fetch.py`

---

## 2. FireCrawl Fallback (`web_fetch.py`)

**Current State:** Uses BeautifulSoup only. JS-heavy sites (React/Next.js) return empty content.

**Enhancement:**
- After BeautifulSoup extraction, if result is suspiciously short (<100 chars) AND `firecrawl_api_key` exists in config → call FireCrawl API as fallback
- FireCrawl renders the page in a headless browser and returns clean markdown
- Add in-memory TTL cache (5 min) to avoid re-fetching same URLs
- Config path: `tools.web.fetch.firecrawl.apiKey` or env `FIRECRAWL_API_KEY`

**Token Impact:** Zero extra prompt tokens. FireCrawl returns cleaner/shorter text than raw HTML, potentially *saving* tokens.

**Files Modified:** `kabot/agent/tools/web_fetch.py`, `kabot/config/schema.py`

---

## 3. Multi-Provider Deep Search (`web_search.py`)

**Current State:** Brave Search only (54 lines).

**Enhancement:**
- Add `provider` field to config: `"brave"` (default), `"perplexity"`, `"grok"`
- **Brave** (default): Current behavior, no change
- **Perplexity**: Calls Perplexity Sonar API for AI-synthesized answers with citations. Needs `PERPLEXITY_API_KEY`
- **Grok**: Calls xAI Responses API with web_search tool. Needs `XAI_API_KEY`
- Auto-detection: If no provider is set but a Perplexity key exists, use Perplexity. Otherwise Brave.
- Add in-memory TTL cache (5 min) for search results
- Config path: `tools.web.search.provider`, `tools.web.search.apiKey`, `tools.web.search.perplexity.apiKey`

**Token Impact:** Zero extra prompt tokens. Perplexity/Grok return pre-synthesized answers (shorter than raw Brave snippets), potentially *saving* tokens.

**Files Modified:** `kabot/agent/tools/web_search.py`, `kabot/config/schema.py`

---

## 4. Advanced Skills Validation (`skills.py`)

**Current State:** Already checks `bins` and `env` requirements. But does NOT report missing dependencies clearly to the LLM.

**Enhancement:**
- When `match_skills()` selects a skill, run requirement check first
- If requirements are unmet, return a clear message: "Skill X needs [ffmpeg, SPOTIFY_API_KEY] — install/configure first"
- Add `install` metadata support: if skill has `install.cmd`, suggest the command
- Enhance `build_skills_summary()` to include availability status in the XML prompt

**Token Impact:** Minimal — only adds a few words per unavailable skill in the summary. Available skills remain unchanged.

**Files Modified:** `kabot/agent/skills.py`

---

## 5. Setup Wizard Integration (`setup_wizard.py`)

**Current State:** No questions about advanced tool API keys.

**Enhancement:**
- Add optional "Advanced Tools (Optional)" section after core setup
- Ask: "Do you have a FireCrawl API key? (skip if no)" → saves to config
- Ask: "Do you have a Perplexity API key? (skip if no)" → saves to config  
- Ask: "Do you have an xAI/Grok API key? (skip if no)" → saves to config
- All questions are skippable (press Enter to skip)
- Display summary: "✅ FireCrawl: configured | ❌ Perplexity: skipped | ❌ Grok: skipped"

**Token Impact:** Zero. Setup wizard runs once at install time.

**Files Modified:** `kabot/cli/setup_wizard.py`, `kabot/config/schema.py`

---

## Config Schema Additions (`config/schema.py`)

```python
# New fields under tools section:
class WebSearchConfig:
    provider: str = "brave"           # "brave" | "perplexity" | "grok"  
    api_key: str = ""                 # Brave API key (existing)
    cache_ttl_minutes: int = 5
    perplexity_api_key: str = ""
    perplexity_model: str = "sonar-pro"
    xai_api_key: str = ""
    xai_model: str = "grok-3-mini"

class WebFetchConfig:
    firecrawl_api_key: str = ""
    firecrawl_base_url: str = "https://api.firecrawl.dev"
    cache_ttl_minutes: int = 5
    max_response_bytes: int = 2_000_000
```

---

## Summary: Token Budget Impact

| Component | Extra Prompt Tokens | Extra API Calls |
|---|---|---|
| SSRF Guard | 0 | 0 |
| FireCrawl fallback | 0 | Only when BS4 fails + key exists |
| Deep Search | 0 | 1 per search (same as now) |
| Skills validation | ~20 words max | 0 |
| Setup Wizard | 0 | 0 |
| **Total** | **~0** | **Same or fewer** |

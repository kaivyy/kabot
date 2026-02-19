# OpenAI Codex OAuth Parity (Design)

## Summary
Align kabot with OpenClaw (code) for OpenAI Codex OAuth while keeping the existing OpenAI API key flow intact. After OAuth login, set the default model order to:

- primary: `openai-codex/gpt-5.3-codex`
- fallbacks: `openai/gpt-5.2-codex`, `openai/gpt-4o-mini`

Additionally, mirror OpenClaw's model normalization (`openai/gpt-5.3-codex` → `openai-codex`) and catalog behavior (`gpt-5.3-codex-spark` fallback).

## Goals
- Support OpenAI Codex OAuth as a first-class provider in kabot.
- Preserve existing OpenAI API key behavior without regression.
- Provide deterministic fallback ordering for codex -> openai models.
- Keep token refresh behavior consistent with existing OAuth refresh service.

## Non-goals
- Do not read or share OpenClaw auth stores.
- Do not add new gateways or external proxy requirements.
- Do not change unrelated providers (Gemini, Anthropic, etc.).

## Current State (Observed)
- kabot has OpenAI OAuth flow (`OpenAIOAuthHandler`) but stores credentials under provider `openai`.
- `openai-codex/gpt-5.3-codex` exists in the catalog but is marked unsupported via provider status.
- OpenClaw treats `openai-codex` as a distinct provider with OAuth and defaults to `openai-codex/gpt-5.3-codex`.
- OpenClaw normalizes `openai/gpt-5.3-codex` to provider `openai-codex` and adds `gpt-5.3-codex-spark` to the catalog when missing.

## Proposed Changes
### Provider Registry
- Add `openai-codex` as a provider spec in `kabot/providers/registry.py`.
- Ensure model resolution preserves the `openai-codex/` prefix when selected.

### Model Status
- Remove `openai-codex` from `UNSUPPORTED_PROVIDERS`.
- Mark `openai-codex/gpt-5.3-codex` as at least `catalog` (or `working` if validation exists).
- Add `openai-codex/gpt-5.3-codex-spark` to the catalog (matching OpenClaw's fallback behavior).

### Model Normalization
- Normalize `openai/gpt-5.3-codex` (and `gpt-5.3-codex*`) to provider `openai-codex` before credential resolution.
- Do not normalize `openai/gpt-5.2-codex` (remains `openai`).

### OAuth Flow
- Update `OpenAIOAuthHandler` to save credentials into `providers.openai-codex` profiles.
- Keep existing OpenAI API key flow and `providers.openai` untouched.

### Default Model & Fallbacks
- After OpenAI OAuth login, set default model order to:
  - `openai-codex/gpt-5.3-codex`
  - `openai/gpt-5.2-codex`
  - `openai/gpt-4o-mini`

### Config Model Type
- Allow `agents.defaults.model` to accept `str | AgentModelConfig` and handle both in summaries and provider matching.

## Data Flow
1) User runs OpenAI OAuth login.
2) OAuth tokens stored in kabot profiles under `openai-codex` provider.
3) `get_api_key(model)` resolves credentials by provider inferred from model (after normalization when applicable).
4) `LiteLLMProvider` executes calls using the selected model; fallbacks applied on failure.

## Error Handling
- Expired OAuth token triggers refresh; on failure, prompt re-login.
- Unsupported model selection warns in wizard and requires confirmation.
- Fallbacks are attempted sequentially for transient errors.
- If user selects `openai/gpt-5.3-codex`, normalize to `openai-codex` and surface a clear auth error if OAuth credentials are missing.

## Testing & Verification
- Unit tests:
  - provider registry includes `openai-codex`.
  - `model_status` reports `openai-codex/gpt-5.3-codex` as supported/catalog.
  - OAuth login persists to `providers.openai-codex` profile.
  - model normalization: `openai/gpt-5.3-codex` routes to `openai-codex`, but `openai/gpt-5.2-codex` stays `openai`.
  - catalog includes `openai-codex/gpt-5.3-codex-spark`.
  - `agents.defaults.model` accepts `str | AgentModelConfig` without breaking summaries/provider matching.
- Manual:
  - Run OAuth login and confirm stored profile.
  - Set default model to `openai-codex/gpt-5.3-codex` and run `kabot agent`.
  - Induce fallback and confirm fallback order.

## Compatibility & Rollout
- Existing OpenAI API key and OAuth flows continue to work for `openai/*` models.
- New OAuth Codex path is opt-in by selecting `openai-codex/*` models (or by normalizing `openai/gpt-5.3-codex`).
- Update kabot docs to reference `openai-codex/gpt-5.3-codex` as the Codex OAuth default (per OpenClaw code).

## Risks
- LiteLLM may not accept `openai-codex` provider identifiers; if so, fallback to `openai/*` mitigates.
- OAuth token scope/format differences could require additional handling.

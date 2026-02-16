# OAuth Infrastructure Implementation Plan (Phase 2)

**Goal:** Implement OAuth callback server, utilities, and OAuth handlers for OpenAI and Google.

**Architecture:** Async HTTP server using `aiohttp` to handle OAuth callbacks. Utilities for browser opening and VPS detection.

---

## Task 16: Implement OAuth Callback Server

**Files:**
- Create: `kabot/auth/oauth_callback.py`
- Create: `tests/auth/test_oauth_callback.py`

**Step 1: Create OAuth Callback Server**

Implement `OAuthCallbackServer` in `kabot/auth/oauth_callback.py`:
- Use `aiohttp` for the web server.
- Generate a secure `state` parameter for CSRF protection.
- Provide a `/callback` endpoint to receive the code/token.
- Return a successful HTML page to the user.
- Add `start_and_wait` method with timeout.

**Step 2: Create Tests**

Create `tests/auth/test_oauth_callback.py`:
- Test server initialization.
- Test state parameter generation.
- Test successful callback handling.
- Test state mismatch handling.

---

## Task 17: Implement OAuth Utilities

**Files:**
- Modify: `kabot/auth/utils.py`
- Create: `tests/auth/utils/test_oauth_flow.py`

**Step 1: Add `run_oauth_flow` to `utils.py`**

- Detect VPS mode (use existing `is_vps`).
- In local mode: Open browser, start `OAuthCallbackServer`, wait for token.
- In VPS mode: Print URL, prompt for manual code entry.

**Step 2: Create Tests**

- Mock `webbrowser` and `OAuthCallbackServer`.
- Test local flow and VPS flow.

---

## Task 18: Create OpenAI OAuth Handler

**Files:**
- Create: `kabot/auth/handlers/openai_oauth.py`
- Create: `tests/auth/handlers/test_openai_oauth.py`

**Step 1: Implement Handler**

- Inherit from `AuthHandler`.
- Build authorization URL with required scopes.
- Use `run_oauth_flow` to get token.
- Return configuration with `oauth_token`.

**Step 2: Create Tests**

- Verify name and structure.
- Mock `run_oauth_flow`.

---

## Task 19: Create Google OAuth Handler

**Files:**
- Create: `kabot/auth/handlers/google_oauth.py`
- Create: `tests/auth/handlers/test_google_oauth.py`

**Step 1: Implement Handler**

- Inherit from `AuthHandler`.
- Build Google OAuth URL.
- Use `run_oauth_flow`.
- Return configuration with `oauth_token`.

**Step 2: Create Tests**

---

## Task 20: Final Integration & Verification

- Update `kabot/auth/handlers/__init__.py`.
- Run full test suite.
- Manual verification of OAuth flow (to URL generation stage).

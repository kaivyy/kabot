"""Shared auth, URL helpers, and utility methods for all handler mixins."""

from __future__ import annotations

import html
import inspect
import json
import time
from typing import Any, Callable
from urllib.parse import quote

from aiohttp import web


class BaseMixin:
    # -- Type stubs for shared instance attrs set by WebhookServer.__init__ --
    auth_token: str
    auth_scopes: set[str]
    meta_verify_token: str
    meta_app_secret: str
    strict_transport_security: bool
    strict_transport_security_value: str
    started_at: float
    status_provider: Callable[[], dict[str, Any]] | None
    chat_history_provider: Callable[[str, int], Any] | None
    control_handler: Callable[[str, dict[str, Any]], Any] | None

    _ROUTE_SCOPE_RULES: tuple[tuple[str, str, str], ...]

    # ── Auth helpers ─────────────────────────────────────────────────

    @staticmethod
    def _parse_auth_token(auth_token: str | None) -> tuple[str, set[str]]:
        raw = str(auth_token or "").strip()
        if not raw:
            return "", set()
        if "|" not in raw:
            return raw, set()
        token, raw_scopes = raw.split("|", 1)
        scopes = {
            item.strip().lower()
            for item in str(raw_scopes or "").split(",")
            if item and item.strip()
        }
        return token.strip(), scopes

    def _extract_bearer(self, request: web.Request) -> str:
        auth_header = request.headers.get("Authorization", "")
        prefix = "Bearer "
        if not auth_header.startswith(prefix):
            return ""
        return auth_header[len(prefix):].strip()

    def _allow_query_token_auth(self, request: web.Request) -> bool:
        path = str(getattr(request, "path", "") or "")
        return path.startswith("/dashboard")

    def _extract_query_token(self, request: web.Request) -> str:
        if not self._allow_query_token_auth(request):
            return ""
        for key in ("token", "auth", "access_token"):
            value = str(request.query.get(key, "") or "").strip()
            if value:
                return value
        return ""

    def _has_scope(self, required_scope: str) -> bool:
        if not required_scope:
            return True
        if not self.auth_scopes:
            # Backward compatibility: plain bearer token grants full access.
            return True
        normalized = str(required_scope).strip().lower()
        family = normalized.split(".", 1)[0] if "." in normalized else normalized
        write_variant = f"{family}.write" if normalized.endswith(".read") else ""
        return (
            normalized in self.auth_scopes
            or "*" in self.auth_scopes
            or "admin" in self.auth_scopes
            or "operator.admin" in self.auth_scopes
            or f"{family}.*" in self.auth_scopes
            or f"{family}.admin" in self.auth_scopes
            or bool(write_variant and write_variant in self.auth_scopes)
        )

    def _authorize(self, request: web.Request, required_scope: str = "") -> web.Response | None:
        if not self.auth_token:
            return None
        bearer = self._extract_bearer(request)
        if not bearer:
            bearer = self._extract_query_token(request)
        if bearer != self.auth_token:
            return web.Response(text="Unauthorized", status=401)
        if required_scope and not self._has_scope(required_scope):
            return web.Response(text="Forbidden", status=403)
        return None

    def _is_https_request(self, request: web.Request) -> bool:
        if bool(getattr(request, "secure", False)):
            return True

        forwarded_proto = request.headers.get("X-Forwarded-Proto", "")
        if forwarded_proto:
            tokens = [token.strip().lower() for token in forwarded_proto.split(",")]
            if "https" in tokens:
                return True

        forwarded = request.headers.get("Forwarded", "").lower()
        if "proto=https" in forwarded:
            return True

        return False

    def _required_scope_for_route(self, request: web.Request) -> str:
        method = str(getattr(request, "method", "")).strip().upper()
        path = str(getattr(request, "path", "")).strip()
        if not method or not path:
            return ""
        for rule_method, rule_path, rule_scope in self._ROUTE_SCOPE_RULES:
            if method != rule_method:
                continue
            if rule_path.endswith("*"):
                if path.startswith(rule_path[:-1]):
                    return rule_scope
                continue
            if path == rule_path:
                return rule_scope
        return ""

    def _authorize_route(self, request: web.Request) -> web.Response | None:
        return self._authorize(request, required_scope=self._required_scope_for_route(request))

    def _request_has_scope(self, request: web.Request, required_scope: str = "") -> bool:
        if not required_scope:
            return True
        if not self.auth_token:
            return True
        bearer = self._extract_bearer(request)
        if not bearer:
            bearer = self._extract_query_token(request)
        if bearer != self.auth_token:
            return False
        return self._has_scope(required_scope)

    def _dashboard_write_enabled(self, request: web.Request) -> bool:
        return callable(self.control_handler) and self._request_has_scope(request, "operator.write")

    # ── Dashboard URL helpers ────────────────────────────────────────

    def _dashboard_token_suffix(self, request: web.Request) -> str:
        token = self._extract_query_token(request)
        if not token:
            return ""
        return f"?token={quote(token, safe='')}"

    def _dashboard_url_with_token(
        self,
        path: str,
        request: web.Request,
        query: dict[str, Any] | None = None,
    ) -> str:
        parts: list[tuple[str, str]] = []
        if isinstance(query, dict):
            for key, value in query.items():
                text = str(value or "").strip()
                if text:
                    parts.append((str(key), text))
        token = self._extract_query_token(request)
        if token:
            parts.append(("token", token))
        if not parts:
            return path
        encoded = "&".join(
            f"{quote(key, safe='')}={quote(val, safe='')}"
            for key, val in parts
        )
        return f"{path}?{encoded}"

    # ── Shared resolve / read helpers ────────────────────────────────

    @staticmethod
    def _resolve_session_key(raw: Any, default: str = "dashboard:web") -> str:
        value = str(raw or "").strip()
        if not value:
            return default
        if len(value) > 160:
            return value[:160]
        return value

    @staticmethod
    def _resolve_history_limit(raw: Any, default: int = 30) -> int:
        try:
            value = int(raw)
        except Exception:
            value = default
        if value < 1:
            return 1
        if value > 200:
            return 200
        return value

    def _read_dashboard_status(self) -> dict[str, Any]:
        payload: dict[str, Any]
        if callable(self.status_provider):
            try:
                payload = self.status_provider() or {}
            except Exception as exc:
                payload = {"status": "error", "error": f"status_provider_failed: {exc}"}
        else:
            payload = {"status": "running"}
        payload.setdefault("status", "running")
        payload.setdefault("uptime_seconds", max(0, int(time.time() - self.started_at)))
        return payload

    async def _read_chat_history(self, session_key: str, limit: int = 30) -> list[dict[str, Any]]:
        raw_items: Any = []
        if callable(self.chat_history_provider):
            try:
                result = self.chat_history_provider(session_key, limit)
                if inspect.isawaitable(result):
                    result = await result
                raw_items = result
            except Exception:
                raw_items = []

        if not isinstance(raw_items, list):
            return []

        items: list[dict[str, Any]] = []
        for item in raw_items[-limit:]:
            if not isinstance(item, dict):
                continue
            metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            role = str(item.get("role") or "").strip().lower() or "assistant"
            content = str(item.get("content") or "")
            timestamp = str(item.get("timestamp") or "").strip()
            items.append(
                {
                    "role": role,
                    "content": content,
                    "timestamp": timestamp,
                    "metadata": metadata,
                }
            )
        return items

    def _status_list(self, key: str) -> list[dict[str, Any]]:
        status = self._read_dashboard_status()
        raw = status.get(key, [])
        if not isinstance(raw, list):
            return []
        out: list[dict[str, Any]] = []
        for item in raw:
            if isinstance(item, dict):
                out.append(item)
        return out

    def _status_config(self) -> dict[str, Any]:
        status = self._read_dashboard_status()
        raw = status.get("config", {})
        return raw if isinstance(raw, dict) else {}

    @staticmethod
    def _read_only_notice_html(subject: str) -> str:
        label = html.escape(str(subject or "Actions"))
        return (
            "<div class='muted' style='margin-top:8px;'>"
            f"Read-only token detected. {label} require "
            "<span class='mono'>operator.write</span>."
            "</div>"
        )

    @staticmethod
    def _result_message_html(result: dict[str, Any] | None, status_code: int, element_id: str) -> str:
        if result is None:
            return f"<div id='{html.escape(element_id)}' class='mono muted mt-2'></div>"
        ok = status_code == 200
        color = "#10b981" if ok else "#ef4444"
        title = "Success" if ok else "Action failed"
        summary = ""
        if isinstance(result.get("message"), str) and str(result.get("message")).strip():
            summary = str(result.get("message")).strip()
        nested = result.get("result")
        if not summary and isinstance(nested, dict) and isinstance(nested.get("message"), str) and str(nested.get("message")).strip():
            summary = str(nested.get("message")).strip()
        if not summary:
            summary = "Action completed." if ok else str(result.get("error") or result.get("message") or "Request failed.")
        payload = html.escape(json.dumps(result, ensure_ascii=False, indent=2))
        return (
            f"<div id='{html.escape(element_id)}' class='mono muted mt-2'>"
            f"<div style='border:1px solid {color};border-radius:10px;padding:10px 12px;background:rgba(0,0,0,.08);'>"
            f"<div style='color:{color};font-weight:700;margin-bottom:4px;'>{html.escape(title)}</div>"
            f"<div style='color:var(--text);font-family:inherit;font-size:12px;'>{html.escape(summary)}</div>"
            f"<details style='margin-top:8px;'>"
            "<summary style='cursor:pointer;color:var(--muted);font-size:11px;'>Details</summary>"
            f"<pre class='mono' style='margin-top:8px;font-size:11px;max-height:180px;overflow:auto;'>{payload}</pre>"
            "</details>"
            "</div>"
            "</div>"
        )

    def _render_sessions_fragment(
        self,
        request: web.Request,
        *,
        action_result: dict[str, Any] | None = None,
        action_status_code: int = 200,
    ) -> str:
        controls_enabled = self._dashboard_write_enabled(request)
        token_suffix = self._dashboard_token_suffix(request)
        action_url = f"/dashboard/partials/sessions{token_suffix}"
        sessions = self._status_list("sessions")[:20]
        rows = []
        for item in sessions:
            key_raw = str(item.get("key", "") or "").strip()
            key = html.escape(key_raw or "-")
            updated = html.escape(str(item.get("updated_at", "-")))
            actions = "<span class='muted'>read-only</span>"
            if controls_enabled and key_raw:
                key_value = html.escape(key_raw)
                actions = (
                    f"<form style='display:inline;' class='mr-2' hx-post='{html.escape(action_url)}' hx-target='#panel-sessions' hx-swap='outerHTML'>"
                    "<input type='hidden' name='action' value='sessions.clear' />"
                    f"<input type='hidden' name='session_key' value='{key_value}' />"
                    "<button type='submit' class='py-1 px-2 text-xs'>Clear</button>"
                    "</form>"
                    f"<form style='display:inline;' hx-post='{html.escape(action_url)}' hx-target='#panel-sessions' hx-swap='outerHTML'>"
                    "<input type='hidden' name='action' value='sessions.delete' />"
                    f"<input type='hidden' name='session_key' value='{key_value}' />"
                    "<button type='submit' class='py-1 px-2 text-xs bg-red-500 hover:bg-red-600'>Delete</button>"
                    "</form>"
                )
            rows.append(f"<tr><td class='mono'>{key}</td><td class='mono'>{updated}</td><td>{actions}</td></tr>")
        if not rows:
            rows.append("<tr><td colspan='3' class='muted'>No sessions available.</td></tr>")
        result_html = self._result_message_html(action_result, action_status_code, "sessions-result")
        access_note = ""
        if callable(self.control_handler) and not self._request_has_scope(request, "operator.write"):
            access_note = self._read_only_notice_html("Session actions")
        return (
            "<h2>Sessions</h2>"
            "<div class='muted'>Recent session activity from runtime state.</div>"
            "<table><tr><th>Session Key</th><th>Updated</th><th>Actions</th></tr>"
            f"{''.join(rows)}"
            "</table>"
            f"{access_note}"
            f"{result_html}"
        )

    def _render_nodes_fragment(
        self,
        request: web.Request,
        *,
        action_result: dict[str, Any] | None = None,
        action_status_code: int = 200,
    ) -> str:
        controls_enabled = self._dashboard_write_enabled(request)
        token_suffix = self._dashboard_token_suffix(request)
        action_url = f"/dashboard/partials/nodes{token_suffix}"
        nodes = self._status_list("nodes")[:30]
        rows = []
        for item in nodes:
            node_id_raw = str(item.get("id", "") or "").strip()
            node_id = html.escape(node_id_raw or "-")
            kind = html.escape(str(item.get("kind", "-")))
            state_raw = str(item.get("state", "") or "").strip().lower()
            state = html.escape(state_raw or "-")
            actions = "<span class='muted'>read-only</span>"
            if controls_enabled and node_id_raw.startswith("channel:"):
                node_value = html.escape(node_id_raw)
                start_disabled = " disabled" if state_raw == "running" else ""
                stop_disabled = " disabled" if state_raw == "stopped" else ""
                actions = (
                    f"<form style='display:inline;' class='mr-2' hx-post='{html.escape(action_url)}' hx-target='#panel-nodes' hx-swap='outerHTML'>"
                    "<input type='hidden' name='action' value='nodes.restart' />"
                    f"<input type='hidden' name='node_id' value='{node_value}' />"
                    "<button type='submit' class='py-1 px-2 text-xs'>Restart</button>"
                    "</form>"
                    f"<form style='display:inline;' class='mr-2' hx-post='{html.escape(action_url)}' hx-target='#panel-nodes' hx-swap='outerHTML'>"
                    "<input type='hidden' name='action' value='nodes.stop' />"
                    f"<input type='hidden' name='node_id' value='{node_value}' />"
                    f"<button type='submit' class='py-1 px-2 text-xs bg-red-500 hover:bg-red-600'{stop_disabled}>Stop</button>"
                    "</form>"
                    f"<form style='display:inline;' hx-post='{html.escape(action_url)}' hx-target='#panel-nodes' hx-swap='outerHTML'>"
                    "<input type='hidden' name='action' value='nodes.start' />"
                    f"<input type='hidden' name='node_id' value='{node_value}' />"
                    f"<button type='submit' class='py-1 px-2 text-xs bg-emerald-500 hover:bg-emerald-600'{start_disabled}>Start</button>"
                    "</form>"
                )
            rows.append(f"<tr><td class='mono'>{node_id}</td><td>{kind}</td><td>{state}</td><td>{actions}</td></tr>")
        if not rows:
            rows.append("<tr><td colspan='4' class='muted'>No nodes available.</td></tr>")
        result_html = self._result_message_html(action_result, action_status_code, "nodes-result")
        access_note = ""
        if callable(self.control_handler) and not self._request_has_scope(request, "operator.write"):
            access_note = self._read_only_notice_html("Node actions")
        return (
            "<h2>Nodes</h2>"
            "<div class='muted'>Runtime components and channel nodes.</div>"
            "<table><tr><th>ID</th><th>Kind</th><th>State</th><th>Actions</th></tr>"
            f"{''.join(rows)}"
            "</table>"
            f"{access_note}"
            f"{result_html}"
        )

    # ── Control action dispatch ──────────────────────────────────────

    def _normalize_control_action(self, action: Any) -> str:
        normalized = str(action or "").strip().lower()
        if not normalized:
            return ""
        allowed = set("abcdefghijklmnopqrstuvwxyz0123456789._-")
        if any(ch not in allowed for ch in normalized):
            return ""
        return normalized

    async def _run_control_action(
        self,
        action: str,
        args: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        normalized_action = self._normalize_control_action(action)
        if not normalized_action:
            return 400, {
                "ok": False,
                "error": "invalid_action",
                "message": "Missing or invalid control action",
            }

        payload_args = args if isinstance(args, dict) else {}
        if not callable(self.control_handler):
            return 501, {
                "ok": False,
                "action": normalized_action,
                "error": "control_unavailable",
                "message": "Control handler is not configured",
            }

        try:
            maybe_result = self.control_handler(normalized_action, payload_args)
            if inspect.isawaitable(maybe_result):
                maybe_result = await maybe_result
            if isinstance(maybe_result, dict) and maybe_result.get("ok") is False:
                status_code = int(maybe_result.get("status_code") or 400)
                payload = dict(maybe_result)
                payload.setdefault("action", normalized_action)
                return status_code, payload
            return 200, {
                "ok": True,
                "action": normalized_action,
                "result": maybe_result if maybe_result is not None else {},
            }
        except Exception as exc:
            return 500, {
                "ok": False,
                "action": normalized_action,
                "error": "control_failed",
                "message": str(exc),
            }

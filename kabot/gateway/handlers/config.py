"""Config render and config update handlers."""

from __future__ import annotations

import html
import json

from aiohttp import web


class ConfigMixin:

    async def handle_dashboard_config(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized
        token_suffix = self._dashboard_token_suffix(request)
        write_enabled = self._dashboard_write_enabled(request)
        config = self._status_config()
        runtime = config.get("runtime", {}) if isinstance(config, dict) else {}
        performance = runtime.get("performance", {}) if isinstance(runtime, dict) else {}
        current_mode = str(performance.get("token_mode", "boros") or "boros").strip().lower()
        if current_mode not in {"boros", "hemat"}:
            current_mode = "boros"

        # Token mode labels in English
        mode_options = {
            "boros": ("Verbose", "Full token output with detailed responses"),
            "hemat": ("Compact", "Minimal token usage for concise replies"),
        }

        pretty = html.escape(json.dumps(config or {}, ensure_ascii=False, indent=2))

        # Build toggle cards for token mode
        mode_cards = []
        for mode_key, (mode_label, mode_desc) in mode_options.items():
            is_active = mode_key == current_mode
            border_color = "var(--accent)" if is_active else "var(--border)"
            bg = "var(--accent-subtle)" if is_active else "var(--bg)"
            click_handler = (
                f"document.getElementById('token-mode-select').value='{mode_key}';"
                f"document.getElementById('token-mode-form').requestSubmit();"
                if write_enabled
                else ""
            )
            cursor = "pointer" if write_enabled else "not-allowed"
            opacity = "1" if write_enabled else ".7"
            check = (
                "<div style='width:18px;height:18px;border-radius:50%;background:var(--accent);"
                "display:flex;align-items:center;justify-content:center;flex-shrink:0;'>"
                "<svg width='10' height='10' fill='white' viewBox='0 0 24 24'><path d='M20.285 2l-11.285 11.567-5.286-5.011-3.714 3.716 9 8.728 15-15.285z'/></svg>"
                "</div>"
            ) if is_active else (
                "<div style='width:18px;height:18px;border-radius:50%;border:2px solid var(--border);flex-shrink:0;'></div>"
            )

            mode_cards.append(
                f"<div onclick=\"{click_handler}\""
                f" style='flex:1;padding:14px;border:1.5px solid {border_color};border-radius:10px;"
                f"background:{bg};cursor:{cursor};opacity:{opacity};transition:all .15s;'"
                f" onmouseover=\"if('{str(write_enabled).lower()}'==='true')this.style.borderColor='var(--accent)'\""
                f" onmouseout=\"this.style.borderColor='{border_color}'\">"
                f"<div style='display:flex;align-items:center;gap:10px;margin-bottom:6px;'>"
                f"{check}"
                f"<span style='font-weight:600;font-size:13px;'>{mode_label}</span>"
                f"<span class='mono' style='font-size:10px;color:var(--muted);'>({mode_key})</span>"
                f"</div>"
                f"<div style='font-size:11px;color:var(--muted);line-height:1.4;'>{mode_desc}</div>"
                f"</div>"
            )

        read_only_note = ""
        if callable(self.control_handler) and not write_enabled:
            read_only_note = self._read_only_notice_html("Runtime config changes")

        fragment = (
            "<div style='padding:18px;'>"
            f"{self._panel_intro_html('Configuration', 'Runtime config preview and quick settings.', eyebrow='Operator Controls')}"

            # Token Mode Section
            "<div style='margin-bottom:20px;'>"
            "<div style='font-size:11px;font-weight:600;color:var(--accent);text-transform:uppercase;"
            "letter-spacing:.06em;margin-bottom:10px;'>Token Mode</div>"
            f"{read_only_note}"
            f"<form id='token-mode-form' hx-post='/dashboard/partials/config{token_suffix}' "
            f"hx-target='#config-result' hx-swap='innerHTML'>"
            "<input type='hidden' name='action' value='config.set_token_mode' />"
            f"<select id='token-mode-select' name='token_mode' style='display:none;'>"
            f"<option value='boros'>boros</option><option value='hemat'>hemat</option>"
            f"</select>"
            "<div style='display:flex;gap:10px;'>"
            f"{''.join(mode_cards)}"
            "</div>"
            "</form>"
            "<div id='config-result' style='margin-top:8px;font-size:11px;font-family:ui-monospace,monospace;"
            "color:var(--muted);min-height:16px;text-align:center;'></div>"
            "</div>"

            # JSON Preview
            "<div>"
            "<div style='display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;'>"
            "<span style='font-size:11px;font-weight:600;color:var(--accent);text-transform:uppercase;"
            "letter-spacing:.06em;'>Config Preview</span>"
            "<span style='font-size:10px;color:var(--muted);'>Live refresh while this tab is open</span>"
            "</div>"
            f"<pre class='mono' style='font-size:11px;max-height:300px;overflow:auto;'>{pretty}</pre>"
            "</div>"

            # Auto-clear result
            "<script>(function(){"
            "var f=document.getElementById('token-mode-form'); if(!f) return;"
            "f.addEventListener('htmx:afterRequest', function(){"
            "  var cr=document.getElementById('config-result');"
            "  if(cr) setTimeout(function(){cr.innerHTML='';}, 3000);"
            "});"
            "})();</script>"
            "</div>"
        )
        return web.Response(text=fragment, content_type="text/html")

    async def handle_dashboard_config_api(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized
        return web.json_response({"config": self._status_config()})

    async def handle_dashboard_config_update_api(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        action = str(payload.get("action") or "config.set_token_mode") if isinstance(payload, dict) else "config.set_token_mode"
        args = payload.get("args", {}) if isinstance(payload, dict) else {}
        status_code, result = await self._run_control_action(action=action, args=args if isinstance(args, dict) else {})
        return web.json_response(result, status=status_code)

    async def handle_dashboard_config_action(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized
        data = await request.post()
        action = str(data.get("action", "") or "config.set_token_mode").strip()
        token_mode = str(data.get("token_mode", "") or "").strip().lower()
        status_code, result = await self._run_control_action(
            action=action,
            args={"token_mode": token_mode},
        )
        message = html.escape(json.dumps(result, ensure_ascii=False))
        if status_code == 200:
            body = (
                "<span style='color:var(--success);font-weight:500;'>"
                f"Success: {message}</span>"
            )
        else:
            body = f"<span style='color:var(--danger);font-weight:500;'>Error: {message}</span>"
        return web.Response(text=body, content_type="text/html", status=status_code)

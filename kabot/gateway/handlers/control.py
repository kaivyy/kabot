"""Control surface handlers."""

from __future__ import annotations

import html
import json

from aiohttp import web


class ControlMixin:

    async def handle_dashboard_control(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized

        token_suffix = self._dashboard_token_suffix(request)
        controls_enabled = callable(self.control_handler)
        write_enabled = self._request_has_scope(request, "operator.write")
        status_dot = (
            "<span style='width:8px;height:8px;border-radius:50%;background:var(--success);"
            "box-shadow:0 0 6px var(--success);display:inline-block;'></span>"
            if controls_enabled and write_enabled else
            "<span style='width:8px;height:8px;border-radius:50%;background:var(--warning);"
            "box-shadow:0 0 6px var(--warning);display:inline-block;'></span>"
            if controls_enabled else
            "<span style='width:8px;height:8px;border-radius:50%;background:var(--danger);"
            "box-shadow:0 0 6px var(--danger);display:inline-block;'></span>"
        )
        status_label = "Active" if controls_enabled and write_enabled else ("Read-only token" if controls_enabled else "Disabled")
        button_disabled = "" if controls_enabled and write_enabled else " disabled"

        # Build action buttons grid
        actions = [
            ("runtime.ping", "Ping", "Test gateway connectivity", "🏓"),
            ("sessions.list", "List Sessions", "Get active sessions", "📋"),
            ("channels.status", "Channel Status", "Check channel health", "📡"),
        ]

        action_btns = []
        for action_id, label, desc, icon in actions:
            action_btns.append(
                f"<form style='display:inline;' hx-post='/dashboard/partials/control{token_suffix}' "
                f"hx-target='#control-result' hx-swap='innerHTML'>"
                f"<input type='hidden' name='action' value='{action_id}' />"
                f"<button type='submit' style='display:flex;align-items:center;gap:8px;padding:10px 14px;"
                f"border-radius:8px;font-size:12px;width:100%;text-align:left;background:var(--bg);"
                f"border:1px solid var(--border);color:var(--text);cursor:pointer;transition:all .15s;'"
                f" onmouseover=\"this.style.borderColor='var(--accent)';this.style.background='var(--accent-subtle)'\""
                f" onmouseout=\"this.style.borderColor='var(--border)';this.style.background='var(--bg)'\""
                f"{button_disabled}>"
                f"<span style='font-size:16px;'>{icon}</span>"
                f"<div style='flex:1;'>"
                f"<div style='font-weight:600;'>{label}</div>"
                f"<div style='font-size:10px;color:var(--muted);margin-top:1px;'>{desc}</div>"
                f"</div>"
                f"</button></form>"
            )

        read_only_note = ""
        if controls_enabled and not write_enabled:
            read_only_note = self._read_only_notice_html("Control actions")

        fragment = (
            "<div style='padding:18px;'>"
            "<div style='display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;'>"
            "<div>"
            "<h2 style='margin:0;font-size:15px;font-weight:600;'>Control Actions</h2>"
            "<div style='font-size:11px;color:var(--muted);margin-top:2px;'>Execute runtime control commands.</div>"
            "</div>"
            f"<div style='display:flex;align-items:center;gap:6px;font-size:11px;'>"
            f"{status_dot} <span style='font-weight:500;'>{status_label}</span></div>"
            "</div>"
            f"{read_only_note}"

            "<div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px;margin-bottom:16px;'>"
            f"{''.join(action_btns)}"
            "</div>"

            "<div id='control-result' style='border:1px solid var(--border);border-radius:8px;padding:12px 14px;"
            "background:var(--bg);min-height:40px;font-size:11px;font-family:ui-monospace,monospace;"
            "color:var(--muted);overflow:auto;max-height:200px;'>"
            "<span style='opacity:.5;'>Response will appear here...</span>"
            "</div>"
            "</div>"
        )
        return web.Response(text=fragment, content_type="text/html")

    async def handle_dashboard_control_info(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized
        return web.json_response(
            {
                "enabled": callable(self.control_handler),
                "actions": [
                    "runtime.ping",
                    "chat.send",
                    "sessions.list",
                    "sessions.clear",
                    "sessions.delete",
                    "nodes.start",
                    "nodes.stop",
                    "nodes.restart",
                    "channels.status",
                    "cron.enable",
                    "cron.disable",
                    "cron.run",
                    "cron.delete",
                    "skills.enable",
                    "skills.disable",
                    "skills.set_api_key",
                    "config.set_token_mode",
                ],
            }
        )

    async def handle_dashboard_control_api(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized

        try:
            payload = await request.json()
        except Exception:
            payload = {}
        status_code, result = await self._run_control_action(
            action=payload.get("action", ""),
            args=payload.get("args", {}) if isinstance(payload, dict) else {},
        )
        return web.json_response(result, status=status_code)

    async def handle_dashboard_control_action(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized

        data = await request.post()
        status_code, result = await self._run_control_action(
            action=data.get("action", ""),
            args={},
        )
        message = html.escape(json.dumps(result, ensure_ascii=False))
        if status_code == 200:
            body = (
                "<div style='color:var(--success);font-weight:500;'>"
                f"Success: Action completed. {message}</div>"
            )
        else:
            body = f"<div style='color:var(--danger);font-weight:500;'>Error: {message}</div>"
        return web.Response(text=body, content_type="text/html", status=status_code)

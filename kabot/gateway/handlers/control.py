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
                f"<form class='kb-control-form' hx-post='/dashboard/partials/control{token_suffix}' "
                f"hx-target='#control-result' hx-swap='innerHTML'>"
                f"<input type='hidden' name='action' value='{action_id}' />"
                f"<button type='submit' class='kb-control-tile'{button_disabled}>"
                f"<span class='kb-control-tile__icon'>{icon}</span>"
                f"<div class='kb-control-tile__body'>"
                f"<div class='kb-control-tile__title'>{label}</div>"
                f"<div class='kb-control-tile__desc'>{desc}</div>"
                f"</div>"
                f"</button></form>"
            )

        read_only_note = ""
        if controls_enabled and not write_enabled:
            read_only_note = self._read_only_notice_html("Control actions")
        status_badge_html = (
            "<div class='kb-inline-status'>"
            f"{status_dot}<span>{html.escape(status_label)}</span>"
            "</div>"
        )

        fragment = (
            "<div style='padding:18px;'>"
            f"{self._panel_intro_html('Control Actions', 'Execute runtime control commands directly from the dashboard.', eyebrow='Operator Actions', actions_html=status_badge_html)}"
            f"{read_only_note}"
            "<div class='kb-control-grid'>"
            f"{''.join(action_btns)}"
            "</div>"
            "<div id='control-result' class='kb-control-result'>"
            "<span class='kb-control-result__placeholder'>Response will appear here...</span>"
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
                "<div class='kb-control-result__success'>"
                f"Success: Action completed. {message}</div>"
            )
        else:
            body = f"<div class='kb-control-result__error'>Error: {message}</div>"
        return web.Response(text=body, content_type="text/html", status=status_code)

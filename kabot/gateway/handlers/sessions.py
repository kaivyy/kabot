"""Session list and session action handlers."""

from __future__ import annotations

from aiohttp import web


class SessionsMixin:

    async def handle_dashboard_sessions_api(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized
        return web.json_response({"sessions": self._status_list("sessions")})

    async def handle_dashboard_sessions(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized
        fragment = f"<div id='panel-sessions' class='config-section-card card overflow-x-auto' hx-get='/dashboard/partials/sessions{self._dashboard_token_suffix(request)}' hx-trigger='load, every 5s' hx-swap='outerHTML'>{self._render_sessions_fragment(request)}</div>"
        return web.Response(text=fragment, content_type="text/html")

    async def handle_dashboard_sessions_update_api(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        action = str(payload.get("action") or "").strip()
        args = payload.get("args", {}) if isinstance(payload, dict) else {}
        if not isinstance(args, dict):
            args = {}
        if isinstance(payload, dict):
            session_key = str(payload.get("session_key") or "").strip()
            if session_key and "session_key" not in args:
                args["session_key"] = session_key
        status_code, result = await self._run_control_action(action=action, args=args)
        return web.json_response(result, status=status_code)

    async def handle_dashboard_sessions_action(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized

        data = await request.post()
        action = str(data.get("action", "") or "").strip()
        session_key = str(data.get("session_key", "") or "").strip()
        status_code, result = await self._run_control_action(
            action=action,
            args={"session_key": session_key},
        )
        fragment = f"<div id='panel-sessions' class='config-section-card card overflow-x-auto' hx-get='/dashboard/partials/sessions{self._dashboard_token_suffix(request)}' hx-trigger='load, every 5s' hx-swap='outerHTML'>{self._render_sessions_fragment(request, action_result=result, action_status_code=status_code)}</div>"
        return web.Response(text=fragment, content_type="text/html", status=status_code)

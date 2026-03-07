"""Node list and node action handlers."""

from __future__ import annotations

from aiohttp import web


class NodesMixin:

    async def handle_dashboard_nodes_api(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized
        return web.json_response({"nodes": self._status_list("nodes")})

    async def handle_dashboard_nodes(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized
        fragment = f"<div id='panel-nodes' class='config-section-card card overflow-x-auto' hx-get='/dashboard/partials/nodes{self._dashboard_token_suffix(request)}' hx-trigger='load, every 5s' hx-swap='outerHTML'>{self._render_nodes_fragment(request)}</div>"
        return web.Response(text=fragment, content_type="text/html")

    async def handle_dashboard_nodes_update_api(self, request: web.Request) -> web.Response:
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
            node_id = str(payload.get("node_id") or "").strip()
            if node_id and "node_id" not in args:
                args["node_id"] = node_id
        status_code, result = await self._run_control_action(action=action, args=args)
        return web.json_response(result, status=status_code)

    async def handle_dashboard_nodes_action(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized

        data = await request.post()
        action = str(data.get("action", "") or "").strip()
        node_id = str(data.get("node_id", "") or "").strip()
        status_code, result = await self._run_control_action(
            action=action,
            args={"node_id": node_id},
        )
        fragment = f"<div id='panel-nodes' class='config-section-card card overflow-x-auto' hx-get='/dashboard/partials/nodes{self._dashboard_token_suffix(request)}' hx-trigger='load, every 5s' hx-swap='outerHTML'>{self._render_nodes_fragment(request, action_result=result, action_status_code=status_code)}</div>"
        return web.Response(text=fragment, content_type="text/html", status=status_code)

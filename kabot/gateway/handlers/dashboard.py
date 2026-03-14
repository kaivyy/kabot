"""Dashboard overview handlers and monitoring panels."""

from __future__ import annotations

import html
import json
import os
import platform
import shutil
import time
from datetime import date, timedelta
from typing import Any

from aiohttp import web

try:
    import psutil  # type: ignore
except ImportError:
    psutil = None


class DashboardMixin:
    _USAGE_WINDOW_OPTIONS = (
        ("7d", "7d", "Last 7 days"),
        ("30d", "30d", "Last 30 days"),
        ("all", "All Time", "All time"),
    )

    async def handle_root(self, _request: web.Request) -> web.Response:
        raise web.HTTPFound("/dashboard")

    async def handle_dashboard(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized

        token_suffix = self._dashboard_token_suffix(request)
        tpl_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
        sections_dir = os.path.join(tpl_dir, "sections")

        def _read(name: str) -> str:
            path = os.path.join(sections_dir, name)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    return fh.read().replace("__TOKEN_SUFFIX__", token_suffix)
            except FileNotFoundError:
                return f"<!-- section template {name} not found -->"

        with open(os.path.join(tpl_dir, "dashboard.html"), "r", encoding="utf-8") as fh:
            template = fh.read()

        body = (
            template
            .replace("__TOKEN_SUFFIX__", token_suffix)
            .replace("__SECTION_OVERVIEW__", _read("overview.html"))
            .replace("__SECTION_CHAT__", _read("chat.html"))
            .replace("__SECTION_ENGINE__", _read("engine.html"))
            .replace("__SECTION_SETTINGS__", _read("settings.html"))
        )
        return web.Response(text=body, content_type="text/html")

    async def handle_dashboard_summary(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized
        status = self._read_dashboard_status()
        channels = status.get("channels_enabled", [])
        if not isinstance(channels, list):
            channels = []
        runtime_models = status.get("runtime_models", [])
        if not isinstance(runtime_models, list):
            runtime_models = []
        runtime_chain = [
            str(item).strip()
            for item in runtime_models
            if str(item).strip()
        ]
        if not runtime_chain:
            runtime_chain = [str(status.get("model", "-")).strip() or "-"]
        model_value = ", ".join(runtime_chain)
        fragment = (
            "<div style='padding:18px;'>"
            "<h2 style='margin:0 0 12px;font-size:15px;font-weight:600;'>System Summary</h2>"
            "<table>"
            f"<tr><th>Status</th><td><span class='kb-badge ok'>{html.escape(str(status.get('status', 'unknown')))}</span></td></tr>"
            f"<tr><th>Uptime</th><td class='mono'>{html.escape(self._format_uptime(int(status.get('uptime_seconds', 0) or 0)))}</td></tr>"
            f"<tr><th>Model</th><td class='mono' style='font-size:11px;'>{html.escape(model_value)}</td></tr>"
            f"<tr><th>Channels</th><td>{html.escape(', '.join(str(v) for v in channels if str(v).strip()) or '-')}</td></tr>"
            f"<tr><th>Cron jobs</th><td class='mono'>{int(status.get('cron_jobs', 0) or 0)}</td></tr>"
            "</table>"
            "</div>"
        )
        return web.Response(text=fragment, content_type="text/html")

    async def handle_dashboard_runtime(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized
        status = self._read_dashboard_status()
        recent_turn = status.get("recent_turn") if isinstance(status.get("recent_turn"), dict) else {}
        extra = {k: v for k, v in status.items() if k not in {"status", "uptime_seconds", "channels_enabled", "cron_jobs", "model"}}
        pretty = html.escape(json.dumps(extra or {}, ensure_ascii=False, indent=2))
        recent_turn_block = ""
        if recent_turn:
            route_decision_snapshot = recent_turn.get("route_decision_snapshot")
            if not isinstance(route_decision_snapshot, dict):
                route_decision_snapshot = {}
            forced_skills = route_decision_snapshot.get("forced_skill_names")
            if not isinstance(forced_skills, list):
                forced_skills = []
            snapshot_rows = ""
            if route_decision_snapshot:
                snapshot_rows = (
                    f"<tr><th style='text-align:left;padding:4px 8px 4px 0;'>Route Snapshot</th><td>{html.escape(str(route_decision_snapshot.get('route_profile') or 'none'))}/{html.escape(str(route_decision_snapshot.get('turn_category') or 'none'))}</td></tr>"
                    f"<tr><th style='text-align:left;padding:4px 8px 4px 0;'>Snapshot Tool</th><td>{html.escape(str(route_decision_snapshot.get('required_tool') or ''))}</td></tr>"
                    f"<tr><th style='text-align:left;padding:4px 8px 4px 0;'>Snapshot Query</th><td>{html.escape(str(route_decision_snapshot.get('required_tool_query') or ''))}</td></tr>"
                    f"<tr><th style='text-align:left;padding:4px 8px 4px 0;'>Snapshot Continuity</th><td>{html.escape(str(route_decision_snapshot.get('continuity_source') or 'none'))}</td></tr>"
                    f"<tr><th style='text-align:left;padding:4px 8px 4px 0;'>Forced Skills</th><td>{html.escape(', '.join(str(item) for item in forced_skills))}</td></tr>"
                )
            recent_turn_block = (
                "<div style='margin:0 0 12px;padding:12px;border:1px solid var(--line);border-radius:12px;background:rgba(15,23,42,.04);'>"
                "<div style='font-size:11px;color:var(--muted);margin-bottom:8px;'>Latest continuity/routing snapshot</div>"
                "<table class='mono' style='width:100%;font-size:11px;border-collapse:collapse;'>"
                f"<tr><th style='text-align:left;padding:4px 8px 4px 0;'>Session</th><td>{html.escape(str(recent_turn.get('session_key') or ''))}</td></tr>"
                f"<tr><th style='text-align:left;padding:4px 8px 4px 0;'>Continuity</th><td>{html.escape(str(recent_turn.get('continuity_source') or 'none'))}</td></tr>"
                f"<tr><th style='text-align:left;padding:4px 8px 4px 0;'>Route</th><td>{html.escape(str(recent_turn.get('route_profile') or ''))}</td></tr>"
                f"<tr><th style='text-align:left;padding:4px 8px 4px 0;'>Tool</th><td>{html.escape(str(recent_turn.get('required_tool') or ''))}</td></tr>"
                f"{snapshot_rows}"
                "</table>"
                "</div>"
            )
        fragment = (
            "<div style='padding:18px;'>"
            "<h2 style='margin:0 0 12px;font-size:15px;font-weight:600;'>Runtime Details</h2>"
            "<div style='font-size:11px;color:var(--muted);margin-bottom:8px;'>Structured payload from runtime status provider.</div>"
            f"{recent_turn_block}"
            f"<pre class='mono' style='font-size:11px;max-height:250px;overflow:auto;'>{pretty}</pre>"
            "</div>"
        )
        return web.Response(text=fragment, content_type="text/html")

    async def handle_dashboard_status_api(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized
        return web.json_response(self._read_dashboard_status())

    async def handle_dashboard_metrics(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized
        status = self._read_dashboard_status()
        sys_metrics = self._collect_system_metrics()

        def bar(pct: int) -> str:
            cls = "ok" if pct < 70 else ("warn" if pct < 90 else "crit")
            return f"<div class='kb-metric-bar'><div class='kb-metric-fill {cls}' style='width:{pct}%'></div></div>"

        uptime = self._format_uptime(int(time.time() - self.started_at))
        state = str(status.get("status", "running"))
        dot_cls = "ok" if state in {"running", "ok", "online"} else "err"
        fragment = (
            f"<span class='kb-metric'><span class='kb-badge {dot_cls}'>{html.escape(state)}</span></span>"
            f"<span class='kb-metric'>CPU <span class='kb-metric-val'>{sys_metrics['cpu']}%</span>{bar(int(sys_metrics['cpu']))}</span>"
            f"<span class='kb-metric'>RAM <span class='kb-metric-val'>{sys_metrics['ram']}%</span>{bar(int(sys_metrics['ram']))}</span>"
            f"<span class='kb-metric'>Disk <span class='kb-metric-val'>{sys_metrics['disk']}%</span>{bar(int(sys_metrics['disk']))}</span>"
            f"<span class='kb-metric'>Uptime <span class='kb-metric-val'>{html.escape(uptime)}</span></span>"
            f"<span class='kb-metric'>PID <span class='kb-metric-val'>{int(sys_metrics['pid'])}</span></span>"
            f"<span class='kb-metric'>MEM <span class='kb-metric-val'>{int(sys_metrics['mem_mb'])}MB</span></span>"
            f"<span class='kb-version'>Kabot {html.escape(str(status.get('version', 'dev')))} · {html.escape(str(sys_metrics['os']))}</span>"
        )
        return web.Response(text=fragment, content_type="text/html")

    async def handle_dashboard_alerts(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized
        status = self._read_dashboard_status()
        sys_metrics = self._collect_system_metrics()
        alerts: list[str] = []
        if int(sys_metrics["cpu"] or 0) > 90:
            alerts.append(f"<div class='kb-alert crit'>High CPU usage: {int(sys_metrics['cpu'])}%</div>")
        if int(sys_metrics["ram"] or 0) > 90:
            alerts.append(f"<div class='kb-alert crit'>High RAM usage: {int(sys_metrics['ram'])}%</div>")
        if int(sys_metrics["disk"] or 0) > 90:
            alerts.append(f"<div class='kb-alert warn'>Disk usage is high: {int(sys_metrics['disk'])}%</div>")
        if str(status.get("status", "running")) in {"error", "offline", "stopped"}:
            alerts.append(f"<div class='kb-alert crit'>Gateway status: {html.escape(str(status.get('status')))}</div>")
        costs = status.get("costs", {})
        if isinstance(costs, dict) and float(costs.get("projected_monthly", 0) or 0) >= 100:
            alerts.append(f"<div class='kb-alert warn'>Projected monthly cost is high: ${float(costs.get('projected_monthly', 0) or 0):.2f}</div>")
        cron_jobs = status.get("cron_jobs_list", [])
        if isinstance(cron_jobs, list):
            failing = [str(item.get("name") or item.get("id") or "cron") for item in cron_jobs if isinstance(item, dict) and str(item.get("last_status", "")).lower() in {"error", "failed"}]
            if failing:
                alerts.append(f"<div class='kb-alert crit'>Cron failure detected: {html.escape(', '.join(failing[:3]))}</div>")
        custom_alerts = status.get("alerts", [])
        if isinstance(custom_alerts, list):
            for alert in custom_alerts[:5]:
                if not isinstance(alert, dict):
                    continue
                level = str(alert.get("level", "info")).strip().lower()
                msg = html.escape(str(alert.get("message", "")))
                cls = "crit" if level in {"critical", "error", "crit"} else ("warn" if level == "warning" else "info")
                if msg:
                    alerts.append(f"<div class='kb-alert {cls}'>{msg}</div>")
        if not alerts:
            alerts.append("<div class='kb-alert info'>No active alerts.</div>")
        return web.Response(text="".join(alerts), content_type="text/html")

    async def handle_dashboard_health(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized
        status = self._read_dashboard_status()
        system = status.get("system", {}) if isinstance(status, dict) else {}
        if not isinstance(system, dict):
            system = {}

        def card(label: str, value: str, sub: str = "") -> str:
            sub_html = f"<div class='kb-stat-sub'>{html.escape(sub)}</div>" if sub else ""
            return f"<div class='kb-stat-card'><div class='kb-stat-label'>{html.escape(label)}</div><div class='kb-stat-value'>{value}</div>{sub_html}</div>"

        uptime_seconds = int(status.get("uptime_seconds", 0) or 0)
        uptime_formatted = html.escape(self._format_uptime(uptime_seconds))
        uptime_card = (
            f"<div class='kb-stat-card'><div class='kb-stat-label'>Uptime</div>"
            f"<div class='kb-stat-value' id='kb-overview-uptime' data-uptime-seconds='{uptime_seconds}'>{uptime_formatted}</div></div>"
        )

        channels = status.get("channels_enabled", [])
        fragment = (
            card("Status", f"<span style='color:var(--success);'>{html.escape(str(status.get('status', 'running')))}</span>")
            + uptime_card
            + card("Sessions", str(len(self._status_list("sessions"))), "active sessions")
            + card("Nodes", str(len(self._status_list("nodes"))), "runtime components")
            + card("Channels", str(len(channels) if isinstance(channels, list) else 0), "enabled")
            + card("Cron Jobs", str(int(status.get("cron_jobs", 0) or 0)), "scheduled")
            + card("PID", html.escape(str(system.get("pid", "-"))), "process id")
            + card("Memory", f"{html.escape(str(system.get('memory_mb', '-')))} MB", "reported usage")
        )
        return web.Response(text=fragment, content_type="text/html")

    async def handle_dashboard_cost(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized
        body = self._render_cost_fragment(request)
        fragment = self._render_dashboard_panel(
            request,
            panel_id="panel-cost",
            path="/dashboard/partials/cost",
            trigger="load",
            query={"window": self._resolve_usage_window(request)},
            body=body,
        )
        return web.Response(text=fragment, content_type="text/html")

    def _render_cost_fragment(self, request: web.Request) -> str:
        status = self._read_dashboard_status()
        window_key = self._resolve_usage_window(request)
        costs = status.get("costs", {}) if isinstance(status, dict) else {}
        if not isinstance(costs, dict):
            costs = {}
        tokens = status.get("token_usage", {}) if isinstance(status, dict) else {}
        if not isinstance(tokens, dict):
            tokens = {}
        model_usage = status.get("model_usage", {}) if isinstance(status, dict) else {}
        if not isinstance(model_usage, dict):
            model_usage = {}
        by_model = costs.get("by_model", {})
        if not isinstance(by_model, dict):
            by_model = {}
        window_payload = self._select_usage_window(status, window_key)
        window_tokens = window_payload.get("token_usage", {})
        if not isinstance(window_tokens, dict):
            window_tokens = {}
        window_model_usage = window_payload.get("model_usage", {})
        if not isinstance(window_model_usage, dict):
            window_model_usage = {}
        window_costs = window_payload.get("costs", {})
        if not isinstance(window_costs, dict):
            window_costs = {}
        window_by_model = window_costs.get("by_model", {})
        if not isinstance(window_by_model, dict):
            window_by_model = {}
        runtime_models = status.get("runtime_models", []) if isinstance(status, dict) else []
        if not isinstance(runtime_models, list):
            runtime_models = []

        rows = []
        ordered_models: list[str] = []
        for candidate in runtime_models:
            name = str(candidate).strip()
            if name and name not in ordered_models:
                ordered_models.append(name)
        extra_models = sorted(
            {
                str(name).strip()
                for name in list(window_by_model.keys()) + list(window_model_usage.keys())
                if str(name).strip() and str(name).strip() not in ordered_models
            }
        )
        model_names = ordered_models + extra_models
        for name in model_names[:8]:
            rows.append(
                "<tr>"
                f"<td class='mono' style='font-size:11px;'>{html.escape(name)}</td>"
                f"<td class='mono'>${float(window_by_model.get(name, 0) or 0):.4f}</td>"
                f"<td class='mono'>{int(window_model_usage.get(name, 0) or 0):,}</td>"
                "</tr>"
            )
        if not rows:
            rows.append("<tr><td colspan='3' style='color:var(--muted);text-align:center;padding:14px;'>No per-model usage yet.</td></tr>")

        fragment = (
            "<div style='padding:18px;'>"
            "<div style='display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;margin-bottom:14px;'>"
            "<div>"
            "<h2 style='margin:0 0 6px;font-size:15px;font-weight:600;'>Cost & Usage</h2>"
            f"<div style='font-size:11px;color:var(--muted);'>Breakdown Window: {html.escape(self._usage_window_title(window_key))}</div>"
            "</div>"
            f"{self._render_usage_window_tabs(request, panel_id='panel-cost', path='/dashboard/partials/cost', active_window=window_key)}"
            "</div>"
            "<div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:12px;margin-bottom:16px;'>"
            f"<div class='kb-stat-card'><div class='kb-stat-label'>Today</div><div class='kb-stat-value' style='color:var(--accent);'>${float(costs.get('today', 0) or 0):.4f}</div></div>"
            f"<div class='kb-stat-card'><div class='kb-stat-label'>All Time</div><div class='kb-stat-value'>${float(costs.get('total', 0) or 0):.4f}</div></div>"
            f"<div class='kb-stat-card'><div class='kb-stat-label'>Projected/Mo</div><div class='kb-stat-value'>${float(costs.get('projected_monthly', 0) or 0):.2f}</div></div>"
            f"<div class='kb-stat-card'><div class='kb-stat-label'>{html.escape(self._usage_window_badge(window_key))}</div><div class='kb-stat-value'>${float(window_costs.get('total', 0) or 0):.4f}</div></div>"
            "</div>"
            "<div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;'>"
            f"<div><div style='font-size:11px;color:var(--muted);margin-bottom:8px;'>Token Usage · {html.escape(self._usage_window_badge(window_key))}</div><table>"
            f"<tr><th>Input tokens</th><td class='mono'>{int(window_tokens.get('input', tokens.get('input', 0)) or 0):,}</td></tr>"
            f"<tr><th>Output tokens</th><td class='mono'>{int(window_tokens.get('output', tokens.get('output', 0)) or 0):,}</td></tr>"
            f"<tr><th>Total</th><td class='mono' style='font-weight:600;'>{int(window_tokens.get('total', int(window_tokens.get('input', 0) or 0) + int(window_tokens.get('output', 0) or 0)) or 0):,}</td></tr>"
            "</table></div>"
            f"<div><div style='font-size:11px;color:var(--muted);margin-bottom:8px;'>Per-Model Breakdown · {html.escape(self._usage_window_badge(window_key))}</div><table><tr><th>Model</th><th>Cost</th><th>Tokens</th></tr>"
            f"{''.join(rows)}"
            "</table></div></div></div>"
        )
        return fragment

    async def handle_dashboard_charts(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized
        body = self._render_charts_fragment(request)
        fragment = self._render_dashboard_panel(
            request,
            panel_id="panel-charts",
            path="/dashboard/partials/charts",
            trigger="load",
            query={"window": self._resolve_usage_window(request)},
            body=body,
        )
        return web.Response(text=fragment, content_type="text/html")

    def _render_charts_fragment(self, request: web.Request) -> str:
        status = self._read_dashboard_status()
        window_key = self._resolve_usage_window(request)
        window_payload = self._select_usage_window(status, window_key)
        model_usage = window_payload.get("model_usage", status.get("model_usage", {}) if isinstance(status, dict) else {})
        if not isinstance(model_usage, dict):
            model_usage = {}
        cost_history = window_payload.get("cost_history", status.get("cost_history", []) if isinstance(status, dict) else [])
        if not isinstance(cost_history, list):
            cost_history = []

        sections: list[str] = []
        history_items = [item for item in cost_history[:30] if isinstance(item, dict)]
        if history_items:
            width, height = 320, 120
            max_cost = max((float(item.get("cost", 0) or 0) for item in history_items), default=0.0) or 1.0
            points = []
            labels = []
            for idx, item in enumerate(history_items):
                denom = max(1, len(history_items) - 1)
                x = 16 + int(idx * ((width - 32) / denom))
                y = height - 16 - int((float(item.get("cost", 0) or 0) / max_cost) * (height - 32))
                points.append(f"{x},{y}")
                labels.append(f"<text x='{x}' y='{height}' fill='var(--muted)' font-size='9' text-anchor='middle'>{html.escape(str(item.get('date', ''))[-5:] or f'D{idx + 1}')}</text>")
            svg = f"<svg viewBox='0 0 {width} {height + 12}' xmlns='http://www.w3.org/2000/svg'><polyline fill='none' stroke='var(--accent)' stroke-width='3' points='{' '.join(points)}' />{''.join(labels)}</svg>"
            sections.append("<div><h2 style='margin:0 0 10px;font-size:15px;font-weight:600;'>Cost Trend</h2>" + f"<div class='kb-chart-area'>{svg}</div></div>")

        if model_usage:
            max_val = max(int(value or 0) for value in model_usage.values()) or 1
            colors = ["#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#ec4899", "#64748b"]
            bars = []
            y = 20
            for idx, (name, count) in enumerate(list(model_usage.items())[:6]):
                pct = min(100, int((int(count or 0) / max_val) * 100)) if max_val else 0
                bars.append(
                    f"<text x='0' y='{y}' fill='var(--muted)' font-size='10'>{html.escape(str(name)[:28])}</text>"
                    f"<rect x='0' y='{y + 4}' width='{pct * 2.5}' height='12' rx='3' fill='{colors[idx % len(colors)]}' opacity='.85'/>"
                    f"<text x='{pct * 2.5 + 6}' y='{y + 13}' fill='var(--text)' font-size='10'>{int(count or 0)}</text>"
                )
                y += 34
            sections.append("<div><h2 style='margin:0 0 10px;font-size:15px;font-weight:600;'>Model Usage</h2>" + f"<div class='kb-chart-area'><svg viewBox='0 0 320 {y + 10}' xmlns='http://www.w3.org/2000/svg'>{''.join(bars)}</svg></div></div>")

        if not sections:
            sections.append("<div style='text-align:center;padding:24px;color:var(--muted);font-size:12px;'>No chart data available yet. Provide model_usage or cost_history in the status payload.</div>")
        return (
            "<div style='padding:18px;display:grid;gap:18px;'>"
            "<div style='display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;'>"
            "<div>"
            "<h2 style='margin:0 0 6px;font-size:15px;font-weight:600;'>Charts & Trends</h2>"
            f"<div style='font-size:11px;color:var(--muted);'>Window: {html.escape(self._usage_window_title(window_key))}</div>"
            "</div>"
            f"{self._render_usage_window_tabs(request, panel_id='panel-charts', path='/dashboard/partials/charts', active_window=window_key)}"
            "</div>"
            + "".join(sections)
            + "</div>"
        )

    async def handle_dashboard_channels(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized
        status = self._read_dashboard_status()
        channels = status.get("channels_enabled", [])
        if not isinstance(channels, list):
            channels = []
        details = status.get("channels", [])
        if not isinstance(details, list):
            details = []
        rows = []
        if details:
            for ch in details[:20]:
                if not isinstance(ch, dict):
                    continue
                state = str(ch.get("state", "unknown")).lower()
                badge_cls = "ok" if state in {"running", "connected", "online"} else ("warn" if state == "idle" else "err")
                rows.append(f"<tr><td class='mono'>{html.escape(str(ch.get('name', '-')))}</td><td>{html.escape(str(ch.get('type', '-')))}</td><td><span class='kb-badge {badge_cls}'>{html.escape(state)}</span></td></tr>")
        elif channels:
            for name in channels[:20]:
                rows.append(f"<tr><td class='mono'>{html.escape(str(name))}</td><td>-</td><td><span class='kb-badge ok'>enabled</span></td></tr>")
        if not rows:
            rows.append("<tr><td colspan='3' style='color:var(--muted);text-align:center;padding:20px;'>No channels configured.</td></tr>")
        fragment = "<div style='padding:18px;'><h2 style='margin:0 0 12px;font-size:15px;font-weight:600;'>Channels</h2><table><tr><th>Name</th><th>Type</th><th>State</th></tr>" + "".join(rows) + "</table></div>"
        return web.Response(text=fragment, content_type="text/html")

    async def handle_dashboard_cron(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized
        return web.Response(text=self._render_dashboard_panel(request, panel_id="panel-cron", path="/dashboard/partials/cron", trigger="load", body=self._render_cron_fragment(request)), content_type="text/html")

    async def handle_dashboard_cron_action(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized
        data = await request.post()
        status_code, result = await self._run_control_action(action=str(data.get("action", "") or "").strip(), args={"job_id": str(data.get("job_id", "") or "").strip()})
        fragment = self._render_dashboard_panel(request, panel_id="panel-cron", path="/dashboard/partials/cron", trigger="load", body=self._render_cron_fragment(request, action_result=result, action_status_code=status_code))
        return web.Response(text=fragment, content_type="text/html", status=status_code)

    async def handle_dashboard_models(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized
        config = self._status_config()
        providers = config.get("providers", {}) if isinstance(config, dict) else {}
        models_by_provider = providers.get("models_by_provider", {}) if isinstance(providers, dict) else {}
        configured = providers.get("configured", []) if isinstance(providers, dict) else []
        if not isinstance(models_by_provider, dict):
            models_by_provider = {}
        if not isinstance(configured, list):
            configured = []
        configured_set = {str(v).lower() for v in configured}
        sections = []
        for provider, models in models_by_provider.items():
            badge = "<span class='kb-badge ok'>configured</span>" if str(provider).lower() in configured_set else "<span class='kb-badge'>available</span>"
            tags = "".join(f"<span style='display:inline-block;padding:3px 8px;margin:2px;border-radius:4px;background:var(--bg);border:1px solid var(--border);font-size:10px;font-family:ui-monospace,monospace;'>{html.escape(str(model)[:50])}</span>" for model in models[:20]) if isinstance(models, list) else "<span style='color:var(--muted);font-size:11px;'>No models listed</span>"
            sections.append("<div style='margin-bottom:12px;padding:12px;border:1px solid var(--border);border-radius:8px;background:var(--bg);'><div style='display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;'><span style='font-weight:600;font-size:12px;'>" + html.escape(str(provider)) + f"</span>{badge}</div><div style='display:flex;flex-wrap:wrap;gap:2px;'>{tags}</div></div>")
        if not sections:
            sections.append("<div style='text-align:center;padding:24px;color:var(--muted);font-size:12px;'>No model data available. Configure providers in your status provider.</div>")
        return web.Response(text="<div style='padding:18px;'><h2 style='margin:0 0 12px;font-size:15px;font-weight:600;'>Available Models</h2>" + "".join(sections) + "</div>", content_type="text/html")

    async def handle_dashboard_skills(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized
        return web.Response(text=self._render_dashboard_panel(request, panel_id="panel-skills", path="/dashboard/partials/skills", trigger="load", body=self._render_skills_fragment(request)), content_type="text/html")

    async def handle_dashboard_commands(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized
        return web.Response(
            text=self._render_dashboard_panel(
                request,
                panel_id="panel-commands",
                path="/dashboard/partials/commands",
                trigger="load",
                body=self._render_commands_fragment(),
            ),
            content_type="text/html",
        )

    async def handle_dashboard_skills_action(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized
        data = await request.post()
        args: dict[str, Any] = {"skill_key": str(data.get("skill_key", "") or "").strip()}
        api_key = str(data.get("api_key", "") or "").strip()
        if api_key:
            args["api_key"] = api_key
        status_code, result = await self._run_control_action(action=str(data.get("action", "") or "").strip(), args=args)
        fragment = self._render_dashboard_panel(request, panel_id="panel-skills", path="/dashboard/partials/skills", trigger="load", body=self._render_skills_fragment(request, action_result=result, action_status_code=status_code))
        return web.Response(text=fragment, content_type="text/html", status=status_code)

    async def handle_dashboard_subagents(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized
        return web.Response(text=self._render_dashboard_panel(request, panel_id="panel-subagents", path="/dashboard/partials/subagents", trigger="load", body=self._render_subagents_fragment()), content_type="text/html")

    async def handle_dashboard_git(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized
        return web.Response(text=self._render_dashboard_panel(request, panel_id="panel-git", path="/dashboard/partials/git", trigger="load", body=self._render_git_fragment()), content_type="text/html")

    def _render_cron_fragment(
        self,
        request: web.Request,
        *,
        action_result: dict[str, Any] | None = None,
        action_status_code: int = 200,
    ) -> str:
        controls_enabled = self._dashboard_write_enabled(request)
        write_access = self._request_has_scope(request, "operator.write")
        action_url = f"/dashboard/partials/cron{self._dashboard_token_suffix(request)}"
        status = self._read_dashboard_status()
        cron_list = status.get("cron_jobs_list", [])
        if not isinstance(cron_list, list):
            cron_list = []
        rows = []
        for job in cron_list[:30]:
            if not isinstance(job, dict):
                continue
            job_id_raw = str(job.get("id", "") or "").strip()
            state_raw = str(job.get("state", "unknown") or "unknown").strip().lower()
            last_status_raw = str(job.get("last_status", "") or "").strip().lower()
            duration_ms = int(job.get("duration_ms", 0) or 0)
            state_cls = "ok" if state_raw in {"active", "enabled", "running"} else ("warn" if state_raw in {"idle", "paused"} else "err")
            run_cls = "err" if last_status_raw in {"error", "failed"} else ("ok" if last_status_raw in {"ok", "success", "completed"} else "warn")
            details = []
            if str(job.get("channel", "")).strip() or str(job.get("to", "")).strip():
                details.append(html.escape(" -> ".join(v for v in [str(job.get("channel", "")).strip(), str(job.get("to", "")).strip()] if v)))
            if str(job.get("last_error", "")).strip():
                details.append("err: " + html.escape(str(job.get("last_error", ""))))
            details_html = f"<div class='muted' style='margin-top:4px;font-size:10px;'>{' | '.join(details)}</div>" if details else ""
            actions = "<span style='color:var(--muted);font-size:12px;'>read-only</span>"
            if controls_enabled and job_id_raw:
                toggle_action = "cron.disable" if state_raw in {"active", "enabled", "running"} else "cron.enable"
                toggle_label = "Disable" if toggle_action == "cron.disable" else "Enable"
                job_id = html.escape(job_id_raw)
                actions = (
                    f"<form style='display:inline;margin-right:6px;' hx-post='{html.escape(action_url)}' hx-target='#panel-cron' hx-swap='outerHTML'><input type='hidden' name='action' value='cron.run' /><input type='hidden' name='job_id' value='{job_id}' /><button type='submit' style='padding:4px 8px;font-size:11px;border-radius:6px;'>Run</button></form>"
                    f"<form style='display:inline;margin-right:6px;' hx-post='{html.escape(action_url)}' hx-target='#panel-cron' hx-swap='outerHTML'><input type='hidden' name='action' value='{toggle_action}' /><input type='hidden' name='job_id' value='{job_id}' /><button type='submit' style='padding:4px 8px;font-size:11px;border-radius:6px;background:var(--bg-hover);color:var(--text);'>{toggle_label}</button></form>"
                    f"<form style='display:inline;' hx-post='{html.escape(action_url)}' hx-target='#panel-cron' hx-swap='outerHTML'><input type='hidden' name='action' value='cron.delete' /><input type='hidden' name='job_id' value='{job_id}' /><button type='submit' style='padding:4px 8px;font-size:11px;border-radius:6px;background:var(--danger);color:#fff;'>Delete</button></form>"
                )
            rows.append(
                "<tr>"
                f"<td class='mono'>{html.escape(str(job.get('name', '-')))}{details_html}</td>"
                f"<td class='mono' style='font-size:11px;'>{html.escape(str(job.get('schedule', '-')))}</td>"
                f"<td><span class='kb-badge {state_cls}'>{html.escape(state_raw)}</span></td>"
                f"<td><span class='kb-badge {run_cls}'>{html.escape(last_status_raw or '-')}</span></td>"
                f"<td style='font-size:11px;'>{html.escape(str(job.get('last_run', '-')))}</td>"
                f"<td style='font-size:11px;'>{html.escape(str(job.get('next_run', '-')))}</td>"
                f"<td class='mono'>{self._format_duration_ms(duration_ms)}</td>"
                f"<td>{actions}</td>"
                "</tr>"
            )
        if not rows:
            rows.append("<tr><td colspan='8' style='color:var(--muted);text-align:center;padding:20px;'>No cron jobs configured. Add cron_jobs_list to your status payload to see them here.</td></tr>")
        access_note = ""
        if callable(self.control_handler) and not write_access:
            access_note = self._read_only_notice_html("Cron actions")
        return (
            f"{self._panel_intro_html('Cron Jobs', 'Schedule, status, timing, and quick actions for background jobs.', eyebrow='Automation')}"
            "<table><tr><th>Name</th><th>Schedule</th><th>State</th><th>Last</th><th>Last Run</th><th>Next Run</th><th>Duration</th><th>Actions</th></tr>"
            + "".join(rows)
            + "</table>"
            + access_note
            + self._result_message_html(action_result, action_status_code, "cron-result")
        )

    def _render_skills_fragment(
        self,
        request: web.Request,
        *,
        action_result: dict[str, Any] | None = None,
        action_status_code: int = 200,
    ) -> str:
        controls_enabled = self._dashboard_write_enabled(request)
        write_access = self._request_has_scope(request, "operator.write")
        action_url = f"/dashboard/partials/skills{self._dashboard_token_suffix(request)}"
        status = self._read_dashboard_status()
        skills = status.get("skills", [])
        if not isinstance(skills, list):
            skills = []
        rows = []
        for skill in skills[:30]:
            if not isinstance(skill, dict):
                continue
            skill_key_raw = str(skill.get("skill_key") or skill.get("name") or "").strip()
            state_raw = str(skill.get("state", "available") or "available").strip().lower()
            disabled_raw = bool(skill.get("disabled", False))
            primary_env = str(skill.get("primary_env", "") or "").strip()
            missing_env = skill.get("missing_env", [])
            if not isinstance(missing_env, list):
                missing_env = []
            env_names = [str(item).strip() for item in missing_env if str(item).strip()]
            env_hint = primary_env or (env_names[0] if env_names else "")
            badge_cls = "ok" if state_raw in {"enabled", "active"} else ("warn" if "missing" in state_raw else "err")
            enabled_badge = "<span class='kb-badge ok'>enabled</span>" if not disabled_raw else "<span class='kb-badge err'>disabled</span>"
            meta_bits = []
            if str(skill.get("description", "")).strip():
                meta_bits.append(html.escape(str(skill.get("description", ""))))
            if primary_env:
                meta_bits.append("env: " + html.escape(primary_env))
            elif env_names:
                meta_bits.append("missing: " + html.escape(", ".join(env_names)))
            meta_html = f"<div class='muted' style='margin-top:4px;font-size:10px;'>{' | '.join(meta_bits)}</div>" if meta_bits else ""
            actions = "<span style='color:var(--muted);font-size:12px;'>read-only</span>"
            if controls_enabled and skill_key_raw:
                skill_key = html.escape(skill_key_raw)
                toggle_action = "skills.enable" if disabled_raw else "skills.disable"
                toggle_label = "Disable" if toggle_action == "skills.disable" else "Enable"
                toggle_form = f"<form style='display:inline;margin-right:6px;' hx-post='{html.escape(action_url)}' hx-target='#panel-skills' hx-swap='outerHTML'><input type='hidden' name='action' value='{toggle_action}' /><input type='hidden' name='skill_key' value='{skill_key}' /><button type='submit' style='padding:4px 8px;font-size:11px;border-radius:6px;background:var(--bg-hover);color:var(--text);'>{toggle_label}</button></form>"
                api_form = ""
                if env_hint:
                    api_form = f"<form style='display:inline-flex;gap:6px;align-items:center;flex-wrap:wrap;' hx-post='{html.escape(action_url)}' hx-target='#panel-skills' hx-swap='outerHTML'><input type='hidden' name='action' value='skills.set_api_key' /><input type='hidden' name='skill_key' value='{skill_key}' /><input type='password' name='api_key' placeholder='{html.escape(env_hint)}' style='min-width:140px;padding:4px 6px;border:1px solid var(--border);border-radius:6px;background:var(--bg-soft, var(--bg));color:var(--text);' /><button type='submit' style='padding:4px 8px;font-size:11px;border-radius:6px;'>Save Key</button></form>"
                actions = toggle_form + api_form
            rows.append("<div class='kb-list-card'><div style='display:flex;align-items:flex-start;justify-content:space-between;gap:12px;'><div><div class='mono' style='font-size:12px;font-weight:600;'>" + html.escape(str(skill.get("name", "-"))) + f"</div>{meta_html}</div><div style='display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end;'><span class='kb-badge {badge_cls}'>" + html.escape(state_raw.replace("_", " ")) + "</span>" + enabled_badge + "</div></div><div style='margin-top:10px;display:flex;gap:8px;flex-wrap:wrap;align-items:center;'>" + actions + "</div></div>")
        if not rows:
            rows.append("<div class='kb-panel-empty'>No skills registered. Add skill snapshots to your status payload to see them here.</div>")
        access_note = ""
        if callable(self.control_handler) and not write_access:
            access_note = self._read_only_notice_html("Skill actions")
        return (
            f"{self._panel_intro_html('Skills', 'Installed skill status, environment readiness, and quick toggles.', eyebrow='Extensions')}"
            "<div class='kb-stack-list'>"
            + "".join(rows)
            + "</div>"
            + access_note
            + self._result_message_html(action_result, action_status_code, "skills-result")
        )

    def _render_commands_fragment(self) -> str:
        status = self._read_dashboard_status()
        commands = status.get("command_surface", [])
        if not isinstance(commands, list):
            commands = []
        rows = []
        for item in commands[:60]:
            if not isinstance(item, dict):
                continue
            source_raw = str(item.get("source", "unknown") or "unknown").strip().lower()
            badge_cls = "ok" if source_raw == "skill" else ("warn" if source_raw == "router" else "")
            admin_only = bool(item.get("admin_only", False))
            skill_name = str(item.get("skill_name", "") or "").strip()
            meta_bits = [html.escape(source_raw)]
            if skill_name:
                meta_bits.append("skill: " + html.escape(skill_name))
            if admin_only:
                meta_bits.append("admin only")
            meta_html = f"<div class='muted' style='margin-top:4px;font-size:10px;'>{' | '.join(meta_bits)}</div>"
            rows.append(
                "<div class='kb-list-card'>"
                "<div style='display:flex;align-items:flex-start;justify-content:space-between;gap:12px;'>"
                f"<div><div class='mono' style='font-size:12px;font-weight:600;'>/{html.escape(str(item.get('name', '-') or '-'))}</div>"
                f"<div style='margin-top:4px;font-size:12px;'>{html.escape(str(item.get('description', '') or ''))}</div>{meta_html}</div>"
                f"<div><span class='kb-badge {badge_cls}'>{html.escape(source_raw)}</span></div>"
                "</div></div>"
            )
        if not rows:
            rows.append("<div class='kb-panel-empty'>No command surface available yet.</div>")
        return (
            f"{self._panel_intro_html('Commands', 'Merged slash-command surface from static commands, router commands, and workspace skills.', eyebrow='Surface Map')}"
            "<div class='kb-stack-list'>"
            + "".join(rows)
            + "</div>"
        )

    def _render_subagents_fragment(self) -> str:
        status = self._read_dashboard_status()
        runs = status.get("subagent_activity", [])
        if not isinstance(runs, list):
            runs = []
        rows = []
        for item in runs[:10]:
            if not isinstance(item, dict):
                continue
            state_raw = str(item.get("status", "unknown") or "unknown").strip().lower()
            badge_cls = "ok" if state_raw in {"completed", "success", "ok"} else ("warn" if state_raw in {"running", "queued"} else "err")
            extra = html.escape(str(item.get("error") or item.get("result") or ""))
            if len(extra) > 80:
                extra = extra[:77] + "..."
            extra_html = f"<div class='muted' style='font-size:10px;'>{extra}</div>" if extra else ""
            rows.append(
                "<tr>"
                f"<td><div class='mono'>{html.escape(str(item.get('label') or item.get('task') or item.get('run_id') or '-'))}</div><div class='muted' style='font-size:10px;'>{html.escape(str(item.get('run_id', '-')))}</div>{extra_html}</td>"
                f"<td><span class='kb-badge {badge_cls}'>{html.escape(state_raw)}</span></td>"
                f"<td class='mono'>{self._format_duration_ms(item.get('duration_ms'))}</td>"
                f"<td class='mono' style='font-size:11px;'>{html.escape(self._format_dashboard_datetime(item.get('created_at')))}</td>"
                "</tr>"
            )
        if not rows:
            rows.append("<tr><td colspan='4' style='color:var(--muted);text-align:center;padding:18px;'>No sub-agent activity recorded yet.</td></tr>")
        return (
            f"{self._panel_intro_html('Sub-Agent Activity', 'Recent delegated runs, duration, and outcome snapshots.', eyebrow='Delegation')}"
            "<table><tr><th>Run</th><th>Status</th><th>Duration</th><th>Started</th></tr>"
            + "".join(rows)
            + "</table>"
        )

    def _render_git_fragment(self) -> str:
        status = self._read_dashboard_status()
        entries = status.get("git_log", [])
        if not isinstance(entries, list):
            entries = []
        rows = []
        for item in entries[:8]:
            if not isinstance(item, dict):
                continue
            rows.append(f"<tr><td class='mono'>{html.escape(str(item.get('sha', '-')))}</td><td>{html.escape(str(item.get('subject', '-')))}</td><td>{html.escape(str(item.get('author', '-')))}</td><td class='mono' style='font-size:11px;'>{html.escape(str(item.get('timestamp', '-')))}</td></tr>")
        if not rows:
            rows.append("<tr><td colspan='4' style='color:var(--muted);text-align:center;padding:18px;'>No git history available.</td></tr>")
        return (
            f"{self._panel_intro_html('Recent Commits', 'Latest repository activity visible from the current workspace.', eyebrow='Workspace Git')}"
            "<table><tr><th>SHA</th><th>Subject</th><th>Author</th><th>When</th></tr>"
            + "".join(rows)
            + "</table>"
        )

    def _render_dashboard_panel(
        self,
        request: web.Request,
        *,
        panel_id: str,
        path: str,
        trigger: str,
        body: str,
        query: dict[str, Any] | None = None,
    ) -> str:
        url = self._dashboard_url_with_token(path, request, query=query)
        return f"<div id='{html.escape(panel_id)}' class='config-section-card card overflow-x-auto' hx-get='{html.escape(url)}' hx-trigger='{html.escape(trigger)}' hx-swap='outerHTML'>{body}</div>"

    @classmethod
    def _resolve_usage_window(cls, request: web.Request) -> str:
        raw = str(request.query.get("window", "") or "").strip().lower()
        allowed = {key for key, _label, _title in cls._USAGE_WINDOW_OPTIONS}
        return raw if raw in allowed else "7d"

    @classmethod
    def _usage_window_title(cls, window_key: str) -> str:
        for key, _label, title in cls._USAGE_WINDOW_OPTIONS:
            if key == window_key:
                return title
        return "Last 7 days"

    @classmethod
    def _usage_window_badge(cls, window_key: str) -> str:
        for key, label, _title in cls._USAGE_WINDOW_OPTIONS:
            if key == window_key:
                return label
        return "7d"

    def _render_usage_window_tabs(
        self,
        request: web.Request,
        *,
        panel_id: str,
        path: str,
        active_window: str,
    ) -> str:
        buttons: list[str] = []
        for key, label, _title in self._USAGE_WINDOW_OPTIONS:
            url = self._dashboard_url_with_token(path, request, query={"window": key})
            active = key == active_window
            btn_cls = "kb-panel-tab kb-panel-tab--active" if active else "kb-panel-tab"
            buttons.append(
                f"<button type='button' hx-get='{html.escape(url)}' hx-target='#{html.escape(panel_id)}' hx-swap='outerHTML' "
                f"class='{btn_cls}'>{html.escape(label)}</button>"
            )
        return "<div class='kb-panel-tabs'>" + "".join(buttons) + "</div>"

    @classmethod
    def _select_usage_window(cls, status: dict[str, Any], window_key: str) -> dict[str, Any]:
        usage_windows = status.get("usage_windows", {}) if isinstance(status, dict) else {}
        if isinstance(usage_windows, dict):
            selected = usage_windows.get(window_key, {})
            if isinstance(selected, dict) and selected:
                return selected

        costs = status.get("costs", {}) if isinstance(status, dict) else {}
        if not isinstance(costs, dict):
            costs = {}
        tokens = status.get("token_usage", {}) if isinstance(status, dict) else {}
        if not isinstance(tokens, dict):
            tokens = {}
        model_usage = status.get("model_usage", {}) if isinstance(status, dict) else {}
        if not isinstance(model_usage, dict):
            model_usage = {}
        by_model = costs.get("by_model", {})
        if not isinstance(by_model, dict):
            by_model = {}
        cost_history = status.get("cost_history", []) if isinstance(status, dict) else []
        if not isinstance(cost_history, list):
            cost_history = []
        filtered_history = cls._filter_cost_history_window(cost_history, window_key)
        return {
            "label": window_key,
            "token_usage": tokens,
            "model_usage": model_usage,
            "costs": {
                "total": float(costs.get("total", 0) or 0),
                "by_model": by_model,
            },
            "cost_history": filtered_history,
        }

    @classmethod
    def _filter_cost_history_window(cls, raw_history: list[Any], window_key: str) -> list[dict[str, Any]]:
        if window_key == "all":
            return [item for item in raw_history if isinstance(item, dict)]
        cutoff = date.today() - timedelta(days=6 if window_key == "7d" else 29)
        filtered: list[dict[str, Any]] = []
        for item in raw_history:
            if not isinstance(item, dict):
                continue
            raw_date = str(item.get("date") or "").strip()
            try:
                parsed = date.fromisoformat(raw_date)
            except ValueError:
                continue
            if parsed >= cutoff:
                filtered.append(item)
        return filtered

    @staticmethod
    def _format_duration_ms(duration_ms: Any) -> str:
        try:
            value = int(duration_ms or 0)
        except Exception:
            return "-"
        if value <= 0:
            return "-"
        if value < 1000:
            return f"{value}ms"
        seconds = value / 1000.0
        if seconds < 60:
            return f"{seconds:.1f}s"
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"

    @staticmethod
    def _format_dashboard_datetime(value: Any) -> str:
        if value in (None, "", 0):
            return "-"
        if isinstance(value, (int, float)):
            try:
                return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(value)))
            except Exception:
                return "-"
        return str(value)

    @staticmethod
    def _format_uptime(seconds: int) -> str:
        if seconds < 60:
            return f"{seconds}s"
        if seconds < 3600:
            return f"{seconds // 60}m {seconds % 60}s"
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        if hours < 24:
            return f"{hours}h {mins}m"
        return f"{hours // 24}d {hours % 24}h"

    def _collect_system_metrics(self) -> dict[str, Any]:
        res: dict[str, Any] = {"cpu": 0, "ram": 0, "disk": 0, "os": platform.system(), "pid": os.getpid(), "mem_mb": 0}
        if psutil:
            try:
                res["cpu"] = int(psutil.cpu_percent())
                res["ram"] = int(psutil.virtual_memory().percent)
                res["mem_mb"] = int(psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024)
            except Exception:
                pass
        try:
            total, used, _free = shutil.disk_usage("/")
            res["disk"] = int((used / total) * 100) if total else 0
        except Exception:
            pass
        return res

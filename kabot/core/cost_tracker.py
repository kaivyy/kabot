"""Cost tracking and aggregation for Kabot."""

from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict

from loguru import logger

from kabot.core.costs import estimate_cost_usd


class CostTracker:
    """Aggregates cost and usage data from session logs."""

    def __init__(self, sessions_dir: Path):
        self.sessions_dir = sessions_dir

    def get_summary(self) -> Dict[str, Any]:
        """
        Scan all session logs and produce a summary of costs and usage.

        Returns:
            {
                "today": float (USD),
                "total": float (USD),
                "projected_monthly": float (USD),
                "token_usage": {
                    "input": int,
                    "output": int,
                    "total": int
                }
            }
        """
        today_date = date.today()
        today_usd = 0.0
        total_usd = 0.0
        input_tokens = 0
        output_tokens = 0
        model_usage: dict[str, int] = {}
        model_costs: dict[str, float] = {}
        cost_history: dict[str, dict[str, Any]] = {}
        daily_usage: dict[str, dict[str, Any]] = {}

        first_seen_ts = time.time()

        if not self.sessions_dir.exists():
            return self._empty_summary()

        for log_file in self.sessions_dir.glob("*.jsonl"):
            try:
                mtime = log_file.stat().st_mtime
                if mtime < first_seen_ts:
                    first_seen_ts = mtime

                with open(log_file, "r", encoding="utf-8") as fh:
                    for line in fh:
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        entry = self._extract_assistant_usage_entry(data)
                        if entry is None:
                            continue

                        input_count = int(entry["input_tokens"])
                        output_count = int(entry["output_tokens"])
                        total_count = int(entry["total_tokens"])
                        cost = float(entry["cost"])
                        model_id = str(entry["model"])

                        total_usd += cost
                        input_tokens += input_count
                        output_tokens += output_count
                        model_usage[model_id] = model_usage.get(model_id, 0) + total_count
                        model_costs[model_id] = model_costs.get(model_id, 0.0) + cost

                        ts_date = self._parse_timestamp_date(entry.get("timestamp"))
                        if ts_date is None:
                            continue
                        if ts_date == today_date:
                            today_usd += cost
                        day_key = ts_date.isoformat()
                        bucket = cost_history.setdefault(
                            day_key,
                            {"date": day_key, "cost": 0.0, "tokens": 0},
                        )
                        bucket["cost"] += cost
                        bucket["tokens"] += total_count

                        daily_bucket = daily_usage.setdefault(
                            day_key,
                            {
                                "date": day_key,
                                "cost": 0.0,
                                "tokens": 0,
                                "input": 0,
                                "output": 0,
                                "model_usage": {},
                                "model_costs": {},
                            },
                        )
                        daily_bucket["cost"] += cost
                        daily_bucket["tokens"] += total_count
                        daily_bucket["input"] += input_count
                        daily_bucket["output"] += output_count
                        daily_bucket["model_usage"][model_id] = (
                            int(daily_bucket["model_usage"].get(model_id, 0) or 0) + total_count
                        )
                        daily_bucket["model_costs"][model_id] = (
                            float(daily_bucket["model_costs"].get(model_id, 0.0) or 0.0) + cost
                        )
            except Exception as exc:
                logger.warning(f"Error parsing log file {log_file}: {exc}")

        days_active = max(1, (time.time() - first_seen_ts) / 86400)
        daily_avg = total_usd / days_active
        projected = daily_avg * 30.44

        return {
            "today": today_usd,
            "total": total_usd,
            "projected_monthly": projected,
            "token_usage": {
                "input": input_tokens,
                "output": output_tokens,
                "total": input_tokens + output_tokens,
            },
            "model_usage": {
                model: tokens
                for model, tokens in sorted(
                    model_usage.items(),
                    key=lambda item: (-item[1], item[0]),
                )
            },
            "model_costs": {
                model: value
                for model, value in sorted(
                    model_costs.items(),
                    key=lambda item: (-item[1], item[0]),
                )
            },
            "cost_history": [cost_history[key] for key in sorted(cost_history.keys())],
            "usage_windows": self._build_usage_windows(
                daily_usage=daily_usage,
                today_date=today_date,
            ),
        }

    def _empty_summary(self) -> Dict[str, Any]:
        return {
            "today": 0.0,
            "total": 0.0,
            "projected_monthly": 0.0,
            "token_usage": {
                "input": 0,
                "output": 0,
                "total": 0,
            },
            "model_usage": {},
            "model_costs": {},
            "cost_history": [],
            "usage_windows": self._empty_usage_windows(),
        }

    @classmethod
    def _empty_usage_windows(cls) -> dict[str, Any]:
        return {
            key: cls._build_window_summary([], label=key)
            for key in ("7d", "30d", "all")
        }

    @classmethod
    def _build_usage_windows(
        cls,
        *,
        daily_usage: dict[str, dict[str, Any]],
        today_date: date,
    ) -> dict[str, Any]:
        if not daily_usage:
            return cls._empty_usage_windows()

        entries: list[dict[str, Any]] = []
        for day_key in sorted(daily_usage.keys()):
            raw = daily_usage.get(day_key, {})
            if not isinstance(raw, dict):
                continue
            entry = {
                "date": str(raw.get("date") or day_key),
                "cost": float(raw.get("cost", 0) or 0),
                "tokens": int(raw.get("tokens", 0) or 0),
                "input": int(raw.get("input", 0) or 0),
                "output": int(raw.get("output", 0) or 0),
                "model_usage": cls._sort_int_map(raw.get("model_usage")),
                "model_costs": cls._sort_float_map(raw.get("model_costs")),
            }
            entries.append(entry)

        seven_day_start = today_date - timedelta(days=6)
        thirty_day_start = today_date - timedelta(days=29)

        return {
            "7d": cls._build_window_summary(
                [entry for entry in entries if cls._entry_date(entry) >= seven_day_start],
                label="7d",
            ),
            "30d": cls._build_window_summary(
                [entry for entry in entries if cls._entry_date(entry) >= thirty_day_start],
                label="30d",
            ),
            "all": cls._build_window_summary(entries, label="all"),
        }

    @classmethod
    def _build_window_summary(
        cls,
        entries: list[dict[str, Any]],
        *,
        label: str,
    ) -> dict[str, Any]:
        input_tokens = 0
        output_tokens = 0
        model_usage: dict[str, int] = {}
        model_costs: dict[str, float] = {}
        cost_history: list[dict[str, Any]] = []
        total_cost = 0.0

        for entry in entries:
            input_tokens += int(entry.get("input", 0) or 0)
            output_tokens += int(entry.get("output", 0) or 0)
            total_cost += float(entry.get("cost", 0) or 0)
            cost_history.append(
                {
                    "date": str(entry.get("date") or ""),
                    "cost": float(entry.get("cost", 0) or 0),
                    "tokens": int(entry.get("tokens", 0) or 0),
                }
            )
            for model, tokens in cls._as_dict(entry.get("model_usage")).items():
                name = str(model).strip()
                if not name:
                    continue
                model_usage[name] = model_usage.get(name, 0) + int(tokens or 0)
            for model, cost in cls._as_dict(entry.get("model_costs")).items():
                name = str(model).strip()
                if not name:
                    continue
                model_costs[name] = model_costs.get(name, 0.0) + float(cost or 0.0)

        total_tokens = input_tokens + output_tokens
        return {
            "label": label,
            "token_usage": {
                "input": input_tokens,
                "output": output_tokens,
                "total": total_tokens,
            },
            "model_usage": cls._sort_int_map(model_usage),
            "model_costs": cls._sort_float_map(model_costs),
            "costs": {
                "total": total_cost,
                "by_model": cls._sort_float_map(model_costs),
            },
            "cost_history": cost_history,
        }

    @staticmethod
    def _entry_date(entry: dict[str, Any]) -> date:
        raw = str(entry.get("date") or "").strip()
        try:
            return date.fromisoformat(raw)
        except ValueError:
            return date.min

    @staticmethod
    def _sort_int_map(raw: Any) -> dict[str, int]:
        items = []
        for model, tokens in CostTracker._as_dict(raw).items():
            name = str(model).strip()
            if not name:
                continue
            items.append((name, int(tokens or 0)))
        return {
            model: value
            for model, value in sorted(items, key=lambda item: (-item[1], item[0]))
        }

    @staticmethod
    def _sort_float_map(raw: Any) -> dict[str, float]:
        items = []
        for model, cost in CostTracker._as_dict(raw).items():
            name = str(model).strip()
            if not name:
                continue
            items.append((name, float(cost or 0)))
        return {
            model: value
            for model, value in sorted(items, key=lambda item: (-item[1], item[0]))
        }

    @staticmethod
    def _as_dict(value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    @classmethod
    def _extract_assistant_usage_entry(cls, data: Any) -> dict[str, Any] | None:
        if not isinstance(data, dict):
            return None
        if str(data.get("_type") or "").strip().lower() == "metadata":
            return None

        message = cls._as_dict(data.get("message"))
        role = str(message.get("role") or data.get("role") or "").strip().lower()
        if role != "assistant":
            return None

        usage = cls._as_dict(data.get("usage"))
        if not usage:
            usage = cls._as_dict(message.get("usage"))
        if not usage:
            return None

        input_tokens = cls._coerce_int(
            usage.get("prompt_tokens"),
            usage.get("input"),
            usage.get("input_tokens"),
        )
        output_tokens = cls._coerce_int(
            usage.get("completion_tokens"),
            usage.get("output"),
            usage.get("output_tokens"),
        )
        total_tokens = cls._coerce_int(
            usage.get("total_tokens"),
            usage.get("total"),
            input_tokens + output_tokens,
        )

        provider = str(data.get("provider") or message.get("provider") or "").strip().lower()
        raw_model = str(data.get("model") or message.get("model") or usage.get("model") or "default").strip()
        model = cls._compose_model_id(provider=provider, model=raw_model)
        cost = cls._extract_cost(usage=usage, model=model, input_tokens=input_tokens, output_tokens=output_tokens)

        return {
            "timestamp": data.get("timestamp") or message.get("timestamp"),
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cost": cost,
        }

    @staticmethod
    def _coerce_int(*values: Any) -> int:
        for value in values:
            if value is None:
                continue
            try:
                return max(0, int(value))
            except Exception:
                continue
        return 0

    @classmethod
    def _extract_cost(
        cls,
        *,
        usage: dict[str, Any],
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        cost_payload = cls._as_dict(usage.get("cost"))
        for candidate in (cost_payload.get("total"), usage.get("estimated_cost_usd")):
            try:
                value = float(candidate)
            except Exception:
                continue
            if value >= 0:
                return value
        return float(estimate_cost_usd(model, input_tokens, output_tokens))

    @staticmethod
    def _compose_model_id(*, provider: str, model: str) -> str:
        model_text = str(model or "").strip()
        provider_text = str(provider or "").strip().lower()
        if not model_text:
            return "default"
        if "/" in model_text or not provider_text:
            return model_text
        return f"{provider_text}/{model_text}"

    @staticmethod
    def _parse_timestamp_date(raw_timestamp: Any) -> date | None:
        if isinstance(raw_timestamp, (int, float)):
            try:
                timestamp = float(raw_timestamp)
                if timestamp > 1_000_000_000_000:
                    timestamp = timestamp / 1000.0
                return datetime.fromtimestamp(timestamp).date()
            except Exception:
                return None

        text = str(raw_timestamp or "").strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except ValueError:
            return None

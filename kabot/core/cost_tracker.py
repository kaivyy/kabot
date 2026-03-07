"""Cost tracking and aggregation for Kabot."""

import json
import time
from datetime import date, datetime
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

        # Track first seen for projection
        first_seen_ts = time.time()

        if not self.sessions_dir.exists():
            return self._empty_summary()

        for log_file in self.sessions_dir.glob("*.jsonl"):
            try:
                # Basic check for file age
                mtime = log_file.stat().st_mtime
                if mtime < first_seen_ts:
                    first_seen_ts = mtime

                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            data = json.loads(line)
                            if data.get("role") != "assistant":
                                continue

                            usage = data.get("usage")
                            if not isinstance(usage, dict):
                                continue

                            i = int(usage.get("prompt_tokens", 0) or 0)
                            o = int(usage.get("completion_tokens", 0) or 0)
                            model = data.get("model") or usage.get("model") or "default"

                            cost = estimate_cost_usd(model, i, o)
                            total_tokens = i + o

                            total_usd += cost
                            input_tokens += i
                            output_tokens += o
                            model_usage[str(model)] = model_usage.get(str(model), 0) + total_tokens
                            model_costs[str(model)] = model_costs.get(str(model), 0.0) + cost

                            # Check if today
                            ts_str = data.get("timestamp")
                            if ts_str:
                                ts_date = self._parse_timestamp_date(ts_str)
                                if ts_date:
                                    if ts_date == today_date:
                                        today_usd += cost
                                    day_key = ts_date.isoformat()
                                    bucket = cost_history.setdefault(
                                        day_key,
                                        {"date": day_key, "cost": 0.0, "tokens": 0},
                                    )
                                    bucket["cost"] += cost
                                    bucket["tokens"] += total_tokens

                        except (json.JSONDecodeError, ValueError):
                            continue
            except Exception as e:
                logger.warning(f"Error parsing log file {log_file}: {e}")

        # Calculate projection
        days_active = max(1, (time.time() - first_seen_ts) / 86400)
        daily_avg = total_usd / days_active
        projected = daily_avg * 30.44 # Average days per month

        return {
            "today": today_usd,
            "total": total_usd,
            "projected_monthly": projected,
            "token_usage": {
                "input": input_tokens,
                "output": output_tokens,
                "total": input_tokens + output_tokens
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
            "cost_history": [
                cost_history[key]
                for key in sorted(cost_history.keys())
            ],
        }

    def _empty_summary(self) -> Dict[str, Any]:
        return {
            "today": 0.0,
            "total": 0.0,
            "projected_monthly": 0.0,
            "token_usage": {
                "input": 0,
                "output": 0,
                "total": 0
            },
            "model_usage": {},
            "model_costs": {},
            "cost_history": [],
        }

    @staticmethod
    def _parse_timestamp_date(raw_timestamp: Any) -> date | None:
        text = str(raw_timestamp or "").strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except ValueError:
            return None

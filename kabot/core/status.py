"""
Status and Benchmark services for Kabot.

Provides system health information and LLM performance benchmarking.
"""

import logging
import platform
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

# (Lazy) System metrics below




class StatusService:
    """Collects and formats system health information."""

    def __init__(self, agent_loop: Any = None):
        self._start_time = time.time()
        self._agent_loop = agent_loop
        self._request_count = 0
        self._error_count = 0
        self._last_latencies: list[float] = []

    def record_request(self, latency_ms: float = 0, error: bool = False) -> None:
        """Record a request for stats tracking."""
        self._request_count += 1
        if error:
            self._error_count += 1
        if latency_ms > 0:
            self._last_latencies.append(latency_ms)
            if len(self._last_latencies) > 50:
                self._last_latencies = self._last_latencies[-50:]

    def get_status(self) -> str:
        """Generate a comprehensive status report."""
        uptime = timedelta(seconds=int(time.time() - self._start_time))
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        lines = [
            "📊 *Kabot System Status*",
            "─────────────────────────",
            f"⏱ *Uptime*: {uptime}",
            f"🕐 *Time*: {now}",
            f"🐍 *Python*: {sys.version.split()[0]}",
            f"💻 *Platform*: {platform.system()} {platform.release()}",
        ]

        # System metrics (lazy import psutil)
        try:
            import psutil
            proc = psutil.Process()
            mem = proc.memory_info()
            cpu = psutil.cpu_percent(interval=0.1)
            lines.extend([
                "",
                "🖥 *System Resources*",
                f"  CPU: {cpu}%",
                f"  RAM (bot): {mem.rss / 1024 / 1024:.1f} MB",
                f"  RAM (total): {psutil.virtual_memory().percent}%",
            ])
        except ImportError:
            pass

        # Request stats
        avg_latency = (
            sum(self._last_latencies) / len(self._last_latencies)
            if self._last_latencies else 0
        )
        error_rate = (
            (self._error_count / self._request_count * 100)
            if self._request_count > 0 else 0
        )
        lines.extend([
            "",
            "📈 *Request Stats*",
            f"  Total: {self._request_count}",
            f"  Errors: {self._error_count} ({error_rate:.1f}%)",
            f"  Avg Latency: {avg_latency:.0f}ms",
        ])

        # Model info
        if self._agent_loop:
            model = getattr(self._agent_loop, 'model', 'unknown')
            last_used = getattr(self._agent_loop, 'last_model_used', model)
            fallback_used = getattr(self._agent_loop, 'last_fallback_used', False)
            chain = getattr(self._agent_loop, 'last_model_chain', [model])
            provider = getattr(self._agent_loop, 'provider', None)
            provider_name = type(provider).__name__ if provider else 'unknown'
            lines.extend([
                "",
                "🧠 *Active Model*",
                f"  Provider: {provider_name}",
                f"  Configured: {model}",
                f"  Last used: {last_used}",
                f"  Fallback used: {'yes' if fallback_used else 'no'}",
                f"  Chain: {' -> '.join(chain)}",
            ])

        return "\n".join(lines)


class BenchmarkService:
    """Runs LLM performance benchmarks."""

    def __init__(self, provider: Any, models: list[str] | None = None):
        self._provider = provider
        self._models = models or []

    async def run_benchmark(self, models: list[str] | None = None) -> str:
        """
        Run a standardized benchmark against one or more models.

        Args:
            models: List of model names to benchmark. Uses defaults if None.

        Returns:
            Formatted benchmark results table.
        """
        target_models = models or self._models
        if not target_models:
            # Use the provider's default model
            default = getattr(self._provider, 'get_default_model', lambda: 'unknown')()
            target_models = [default]

        prompt = "Calculate the 10th Fibonacci number. Reply with just the number."
        results = []

        for model in target_models:
            try:
                # Measure TTFT and total time
                start = time.monotonic()
                response = await self._provider.chat(
                    messages=[{"role": "user", "content": prompt}],
                    model=model,
                    max_tokens=50,
                    temperature=0.0,
                )
                total_ms = (time.monotonic() - start) * 1000

                # Estimate tokens
                content = getattr(response, 'content', str(response))
                token_count = len(content.split())
                tps = token_count / (total_ms / 1000) if total_ms > 0 else 0

                # Status emoji
                if total_ms < 500:
                    status = "🟢 Fast"
                elif total_ms < 1500:
                    status = "🟡 OK"
                else:
                    status = "🔴 Slow"

                results.append({
                    "model": model,
                    "total_ms": total_ms,
                    "tps": tps,
                    "status": status,
                })
            except Exception as e:
                results.append({
                    "model": model,
                    "total_ms": -1,
                    "tps": 0,
                    "status": f"❌ {str(e)[:30]}",
                })

        # Format as table
        lines = [
            "🏎 *Benchmark Results*",
            "",
            "| Model | Latency | TPS | Status |",
            "| :--- | :--- | :--- | :--- |",
        ]
        for r in results:
            latency = f"{r['total_ms']:.0f}ms" if r['total_ms'] >= 0 else "N/A"
            tps = f"{r['tps']:.1f}" if r['tps'] > 0 else "N/A"
            lines.append(f"| {r['model']} | {latency} | {tps} | {r['status']} |")

        return "\n".join(lines)

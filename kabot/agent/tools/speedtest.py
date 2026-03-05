"""Speedtest tool for checking internet connection quality."""

import asyncio
from typing import Any

from loguru import logger

from kabot.agent.fallback_i18n import t as i18n_t
from kabot.agent.tools.base import Tool


class SpeedtestTool(Tool):
    """Tool to perform internet speed test (Ping, Download, Upload)."""

    name = "speedtest"
    description = "Test internet connection speed (Ping, Download, Upload)."
    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }

    async def execute(self, **kwargs: Any) -> str:
        """Run speedtest. This takes about 20-30 seconds."""
        context_text = str(kwargs.get("context_text") or "").strip()
        try:
            logger.info("Starting internet speedtest...")

            # Run speedtest in a thread pool to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._run_speedtest)

            return result
        except Exception as e:
            logger.error(f"Speedtest failed: {e}")
            return i18n_t("speedtest.failed", context_text, error=str(e))

    def _run_speedtest(self) -> str:
        """Synchronous speedtest execution using speedtest-cli library."""
        try:
            import speedtest

            s = speedtest.Speedtest()
            logger.info("Speedtest: Selecting best server...")
            s.get_best_server()

            logger.info("Speedtest: Testing download...")
            s.download()

            logger.info("Speedtest: Testing upload...")
            s.upload()

            results = s.results.dict()

            # Format numbers
            download_mbps = results['download'] / 1_000_000
            upload_mbps = results['upload'] / 1_000_000
            ping = results['ping']
            server = results['server']['sponsor']
            location = results['server']['name']
            country = results['server']['country']

            output = [
                "### Speedtest Results",
                f"• **Ping**: {ping:.1f} ms",
                f"• **Download**: {download_mbps:.2f} Mbps",
                f"• **Upload**: {upload_mbps:.2f} Mbps",
                f"• **Server**: {server} ({location}, {country})"
            ]

            return "\n".join(output)

        except ImportError:
            return i18n_t("speedtest.missing_dependency")
        except Exception as e:
            return i18n_t("speedtest.error", error=str(e))

"""Speedtest tool for checking internet connection quality."""

from typing import Any, Dict
import asyncio
from loguru import logger
from kabot.agent.tools.base import BaseTool

class SpeedtestTool(BaseTool):
    """Tool to perform internet speed test (Ping, Download, Upload)."""

    def __init__(self, workspace_path: str):
        super().__init__(workspace_path)
        self._name = "speedtest"
        self._description = "Test internet connection speed (Ping, Download, Upload)."

    async def execute(self, params: Dict[str, Any]) -> str:
        """Run speedtest. This takes about 20-30 seconds."""
        try:
            logger.info("Starting internet speedtest...")
            
            # Run speedtest in a thread pool to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._run_speedtest)
            
            return result
        except Exception as e:
            logger.error(f"Speedtest failed: {e}")
            return f"Failed to perform speedtest: {str(e)}"

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
                f"### Speedtest Results",
                f"• **Ping**: {ping:.1f} ms",
                f"• **Download**: {download_mbps:.2f} Mbps",
                f"• **Upload**: {upload_mbps:.2f} Mbps",
                f"• **Server**: {server} ({location}, {country})"
            ]
            
            return "\n".join(output)
            
        except ImportError:
            return "Error: speedtest-cli is not installed. Please run 'pip install speedtest-cli' on the host."
        except Exception as e:
            return f"Error during speedtest: {str(e)}"

    def get_definition(self) -> Dict[str, Any]:
        return {
            "name": self._name,
            "description": self._description,
            "parameters": {
                "type": "object",
                "properties": {},
            },
        }

    def get_name(self) -> str:
        return self._name

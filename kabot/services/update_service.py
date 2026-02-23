"""Update service for handling Kabot restarts."""
import os
import sys
import platform
import subprocess
from pathlib import Path
from loguru import logger


class UpdateService:
    """Service for handling Kabot restart after updates."""

    def __init__(self):
        self.kabot_dir = Path(__file__).parent.parent.parent.resolve()

    def create_restart_script(self) -> Path:
        """Create platform-specific restart script."""
        pid = os.getpid()

        if platform.system() == "Windows":
            script_path = self.kabot_dir / "restart.bat"
            script_content = f"""@echo off
timeout /t 2 /nobreak >nul
taskkill /F /PID {pid} >nul 2>&1
cd /d "{self.kabot_dir}"
python -m kabot
"""
        else:  # Linux/Mac
            script_path = self.kabot_dir / "restart.sh"
            script_content = f"""#!/bin/bash
sleep 2
kill {pid} 2>/dev/null
cd "{self.kabot_dir}"
python -m kabot
"""

        script_path.write_text(script_content)
        if platform.system() != "Windows":
            script_path.chmod(0o755)

        logger.info(f"Created restart script: {script_path}")
        return script_path

    def execute_restart(self, script_path: Path):
        """Execute restart script and exit current process."""
        logger.info("Executing restart script...")

        if platform.system() == "Windows":
            subprocess.Popen([str(script_path)], shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen([str(script_path)], shell=True, start_new_session=True)

        sys.exit(0)

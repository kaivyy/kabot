import os
import re
import shutil
import sys
from pathlib import Path
from typing import Dict, Optional


class ExtractionEngine:
    """Safely extracts secrets from source files using Regex."""

    @staticmethod
    def extract_from_file(file_path: Path, patterns: Dict[str, str]) -> Dict[str, str]:
        """
        Search for patterns in a file and return matches.
        patterns: { "name": "regex_string" }
        """
        results = {}
        if not file_path.exists():
            return results

        try:
            content = file_path.read_text(encoding="utf-8")
            for name, pattern in patterns.items():
                match = re.search(pattern, content)
                if match:
                    # Return the first capture group if present, otherwise whole match
                    results[name] = match.group(1) if match.groups() else match.group(0)
        except Exception:
            pass # Silent failure for file reads
        return results

def get_node_modules_path() -> Optional[Path]:
    """Heuristic scan for global node_modules directory."""
    if sys.platform == "win32":
        # Windows standard path for npm global
        appdata = os.environ.get("APPDATA")
        if appdata:
            path = Path(appdata) / "npm" / "node_modules"
            if path.exists():
                return path
    else:
        # Unix standard paths
        common_paths = [
            Path("/usr/local/lib/node_modules"),
            Path.home() / ".npm-global" / "lib" / "node_modules",
            Path("/usr/lib/node_modules")
        ]
        for p in common_paths:
            if p.exists():
                return p
    return None

def find_node_module(module_name: str) -> Optional[Path]:
    """Find the installation directory of a global npm module."""
    # 1. Try to find the binary first
    binary = shutil.which(module_name.split("/")[-1])
    if binary:
        # Often the node_modules is 2 levels up from the bin folder
        # e.g. .../npm/node_modules/@google/gemini-cli/bin/gemini
        binary_path = Path(binary).resolve()
        # Look for package.json in parent folders
        current = binary_path.parent
        for _ in range(4):
            if (current / "package.json").exists():
                return current
            current = current.parent

    # 2. Try heuristic scan
    base = get_node_modules_path()
    if base:
        module_path = base / module_name
        if module_path.exists():
            return module_path

    return None

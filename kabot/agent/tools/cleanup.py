"""System cleanup tool for safe disk space recovery."""

import asyncio
import platform
from typing import Any

from kabot.agent.tools.base import Tool


class CleanupTool(Tool):
    """Tool to perform safe system cleanup and recover disk space."""

    @property
    def name(self) -> str:
        return "cleanup_system"

    @property
    def description(self) -> str:
        return (
            "Perform safe system cleanup to free disk space. "
            "Cleans temp files, caches, recycle bin, Windows Update cache, "
            "browser caches, and logs. Shows before/after free space. "
            "Works on Windows, Linux, macOS, and Termux."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "level": {
                    "type": "string",
                    "enum": ["quick", "standard", "deep"],
                    "description": (
                        "Cleanup level: "
                        "'quick' = temp files + recycle bin only, "
                        "'standard' = quick + browser cache + Windows Update cache, "
                        "'deep' = standard + DISM component cleanup + log rotation. "
                        "Default: standard"
                    ),
                },
            },
        }

    async def execute(self, level: str = "standard", **kwargs: Any) -> str:
        system = platform.system()
        if system == "Windows":
            return await self._cleanup_windows(level)
        elif system == "Linux":
            return await self._cleanup_linux(level)
        elif system == "Darwin":
            return await self._cleanup_mac(level)
        return f"Cleanup not supported on {system}"

    async def _cleanup_windows(self, level: str) -> str:
        parts = [
            # Measure before
            '$before = (Get-PSDrive C).Free',
            '$cleaned = @()',
        ]

        # --- Quick ---
        parts += [
            # Recycle Bin
            'try { Clear-RecycleBin -Force -ErrorAction SilentlyContinue; $cleaned += "Recycle Bin" } catch {}',
            # User temp
            'try { $c = (Get-ChildItem "$env:TEMP" -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum; '
            'Remove-Item "$env:TEMP\\*" -Force -Recurse -ErrorAction SilentlyContinue; '
            '$cleaned += "User Temp ({0:N0} MB)" -f ($c/1MB) } catch {}',
            # Windows temp
            'try { $c = (Get-ChildItem "C:\\Windows\\Temp" -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum; '
            'Remove-Item "C:\\Windows\\Temp\\*" -Force -Recurse -ErrorAction SilentlyContinue; '
            '$cleaned += "Windows Temp ({0:N0} MB)" -f ($c/1MB) } catch {}',
        ]

        # --- Standard ---
        if level in ("standard", "deep"):
            parts += [
                # Windows Update cache
                'try { Stop-Service wuauserv -Force -ErrorAction SilentlyContinue; '
                'Remove-Item "C:\\Windows\\SoftwareDistribution\\Download\\*" -Force -Recurse -ErrorAction SilentlyContinue; '
                'Start-Service wuauserv -ErrorAction SilentlyContinue; '
                '$cleaned += "Windows Update Cache" } catch {}',
                # Delivery Optimization
                'try { Remove-Item "C:\\Windows\\SoftwareDistribution\\DeliveryOptimization\\*" -Force -Recurse -ErrorAction SilentlyContinue; '
                '$cleaned += "Delivery Optimization" } catch {}',
                # Prefetch
                'try { Remove-Item "C:\\Windows\\Prefetch\\*" -Force -ErrorAction SilentlyContinue; '
                '$cleaned += "Prefetch" } catch {}',
                # Thumbnail cache
                'try { Remove-Item "$env:LOCALAPPDATA\\Microsoft\\Windows\\Explorer\\thumbcache_*.db" -Force -ErrorAction SilentlyContinue; '
                '$cleaned += "Thumbnail Cache" } catch {}',
                # Browser caches (Edge, Chrome)
                'try { '
                'Remove-Item "$env:LOCALAPPDATA\\Microsoft\\Edge\\User Data\\Default\\Cache\\*" -Force -Recurse -ErrorAction SilentlyContinue; '
                'Remove-Item "$env:LOCALAPPDATA\\Google\\Chrome\\User Data\\Default\\Cache\\*" -Force -Recurse -ErrorAction SilentlyContinue; '
                '$cleaned += "Browser Caches" } catch {}',
            ]

        # --- Deep ---
        if level == "deep":
            parts += [
                # DISM component cleanup
                'try { $null = DISM /Online /Cleanup-Image /StartComponentCleanup /ResetBase 2>&1; '
                '$cleaned += "DISM Component Cleanup" } catch {}',
                # Old Windows logs
                'try { Remove-Item "C:\\Windows\\Logs\\CBS\\*.log" -Force -ErrorAction SilentlyContinue; '
                '$cleaned += "CBS Logs" } catch {}',
            ]

        # Measure after
        parts += [
            '$after = (Get-PSDrive C).Free',
            '$freed = $after - $before',
            '"### 🧹 System Cleanup Complete (Level: ' + level + ')"',
            '"**Before:** {0:N2} GB free" -f ($before/1GB)',
            '"**After:** {0:N2} GB free" -f ($after/1GB)',
            '"**Freed:** {0:N2} GB" -f ($freed/1GB)',
            '""',
            '"**Cleaned:**"',
            '$cleaned | ForEach-Object { "- $_" }',
        ]

        script = "; ".join(parts)
        return await self._run_powershell(script)

    async def _cleanup_linux(self, level: str) -> str:
        import os
        is_termux = "com.termux" in os.environ.get("PREFIX", "")

        if is_termux:
            script = """
            before=$(df /data 2>/dev/null | awk 'NR==2{print $4}' || echo "0")
            rm -rf "$TMPDIR"/* 2>/dev/null
            rm -rf ~/.cache/* 2>/dev/null
            pkg clean -y 2>/dev/null
            after=$(df /data 2>/dev/null | awk 'NR==2{print $4}' || echo "0")
            echo "### 🧹 Termux Cleanup Complete"
            echo "Cleaned: tmp, cache, pkg cache"
            echo "Free space change: ${before}K -> ${after}K"
            """
        else:
            cmds = [
                "before=$(df / --output=avail | tail -1)",
                "sudo rm -rf /tmp/* 2>/dev/null || rm -rf /tmp/* 2>/dev/null",
                "rm -rf ~/.cache/* 2>/dev/null",
            ]
            if level in ("standard", "deep"):
                cmds += [
                    "sudo apt-get clean 2>/dev/null || true",
                    "sudo journalctl --vacuum-time=3d 2>/dev/null || true",
                ]
            if level == "deep":
                cmds += [
                    "sudo apt-get autoremove -y 2>/dev/null || true",
                ]
            cmds += [
                'after=$(df / --output=avail | tail -1)',
                'echo "### 🧹 Linux Cleanup Complete (Level: ' + level + ')"',
                'echo "Free space: ${before}K -> ${after}K"',
            ]
            script = "\n".join(cmds)

        return await self._run_shell(script)

    async def _cleanup_mac(self, level: str) -> str:
        cmds = [
            "before=$(df / | awk 'NR==2{print $4}')",
            "rm -rf ~/Library/Caches/* 2>/dev/null",
            "rm -rf /tmp/* 2>/dev/null",
        ]
        if level in ("standard", "deep"):
            cmds += [
                "rm -rf ~/Library/Logs/* 2>/dev/null",
                "rm -rf ~/Downloads/*.dmg 2>/dev/null",
            ]
        if level == "deep":
            cmds += [
                "sudo periodic daily weekly monthly 2>/dev/null || true",
            ]
        cmds += [
            "after=$(df / | awk 'NR==2{print $4}')",
            'echo "### 🧹 macOS Cleanup Complete (Level: ' + level + ')"',
            'echo "Free space: ${before} -> ${after} (512-byte blocks)"',
        ]
        return await self._run_shell("\n".join(cmds))

    async def _run_powershell(self, script: str) -> str:
        try:
            process = await asyncio.create_subprocess_exec(
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy", "Bypass",
                "-Command",
                script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=120
            )
            out = stdout.decode("utf-8", errors="replace").strip()
            if not out and stderr:
                err = stderr.decode("utf-8", errors="replace").strip()
                return f"Cleanup ran but returned warnings:\n{err}"
            return out or "Cleanup completed (no output captured)"
        except asyncio.TimeoutError:
            return "Cleanup timed out after 120s (DISM can take a while). Check disk space manually."
        except Exception as e:
            return f"Cleanup failed: {e}"

    async def _run_shell(self, script: str) -> str:
        try:
            process = await asyncio.create_subprocess_shell(
                script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=120
            )
            out = stdout.decode("utf-8", errors="replace").strip()
            if not out and stderr:
                return f"Cleanup warnings:\n{stderr.decode('utf-8', errors='replace').strip()}"
            return out or "Cleanup completed"
        except Exception as e:
            return f"Cleanup failed: {e}"

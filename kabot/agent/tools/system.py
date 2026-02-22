"""System hardware information tool."""

import asyncio
import platform
from typing import Any

from kabot.agent.tools.base import Tool


class SystemInfoTool(Tool):
    """Tool to retrieve detailed hardware and OS specifications."""

    @property
    def name(self) -> str:
        return "get_system_info"

    @property
    def description(self) -> str:
        return "Get comprehensive hardware (CPU, RAM, GPU, Disk) and OS specifications of the host machine."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self, **kwargs: Any) -> str:
        if platform.system() == "Windows":
            return await self._get_windows_specs()
        elif platform.system() == "Linux":
             return await self._get_linux_specs()
        elif platform.system() == "Darwin":
             return await self._get_mac_specs()
        return f"System info not fully supported for OS: {platform.system()}"

    async def _get_windows_specs(self) -> str:
        script = """
        $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
        $cs = Get-CimInstance Win32_ComputerSystem | Select-Object -First 1
        $ram = Get-CimInstance Win32_PhysicalMemory
        $gpu = Get-CimInstance Win32_VideoController
        $disks = Get-CimInstance Win32_DiskDrive
        $os = Get-CimInstance Win32_OperatingSystem | Select-Object -First 1

        $cpuStr = "$($cpu.Name) ($($cpu.NumberOfCores) Cores, $($cpu.NumberOfLogicalProcessors) Threads)"
        $ramTotal = [math]::Round($cs.TotalPhysicalMemory / 1GB, 2)
        $ramStr = "$ramTotal GB Total`n" + ($ram | ForEach-Object { "  - $($_.Capacity / 1GB)GB $($_.Manufacturer) @ $($_.Speed)MHz" } | Out-String)
        $gpuStr = ($gpu | ForEach-Object { "- $($_.Name) ($([math]::Round($_.AdapterRAM / 1GB, 2))GB VRAM)" } | Out-String)
        $diskStr = ($disks | ForEach-Object { "- $($_.Model) ($([math]::Round($_.Size / 1GB, 2))GB)" } | Out-String)
        $osStr = "$($os.Caption) $($os.OSArchitecture) (Build $($os.BuildNumber))"

        @"
### 💻 Hardware Specifications
**CPU:** $cpuStr
**RAM:** $ramStr
**GPU:**
$gpuStr
**Storage:**
$diskStr
**OS:** $osStr
"@
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
            if process.returncode != 0:
                err = stderr.decode("utf-8", errors="replace").strip()
                return f"Error executing spec check: {err}"
            return stdout.decode("utf-8", errors="replace").strip()
        except Exception as e:
            return f"Failed to retrieve Windows specs: {e}"

    async def _get_linux_specs(self) -> str:
        # Check if running in Termux (Android)
        import os
        is_termux = "com.termux" in os.environ.get("PREFIX", "")

        if is_termux:
            script = """
            cpu=$(lscpu | grep "Model name:" | sed 's/Model name://' | xargs || getprop ro.soc.model || echo "ARM Processor")
            cores=$(nproc)
            ram=$(free -m | awk '/Mem:/ {printf "%.2f GB", $2/1024}')
            storage=$(df -h /data | awk 'NR==2 {print $2}')
            os_ver=$(getprop ro.build.version.release || termux-info | grep "Android version:" | cut -d: -f2 | xargs)
            echo "### 📱 Termux / Android Specifications"
            echo "**CPU:** $cpu ($cores Cores)"
            echo "**RAM:** $ram Total"
            echo "**Storage (Data):** $storage"
            echo "**OS:** Android $os_ver (Termux Environment)"
            """
        else:
            script = """
            cpu=$(lscpu | grep -E "^Model name:|^CPU.s.:" | sed -E 's/.*: +//' | head -n 1)
            cores=$(nproc)
            ram=$(free -g | awk '/Mem:/ {print $2}')
            gpu=$(lspci | grep -i vga | awk -F': ' '{print $2}' || lshw -C display 2>/dev/null | grep product | awk -F': ' '{print $2}' | xargs || echo "Unknown GPU")
            disk=$(lsblk -d -o NAME,SIZE,MODEL | grep -v "loop" | awk 'NR>1 {print "- " $1 " (" $2 ") " $3}')
            os=$(grep PRETTY_NAME /etc/os-release | cut -d= -f2 | tr -d '"')

            echo "### 🐧 Linux Hardware Specifications"
            echo "**CPU:** $cpu ($cores Cores)"
            echo "**RAM:** ~${ram}GB Total"
            echo "**GPU:** $gpu"
            echo "**Storage:**"
            echo "$disk"
            echo "**OS:** $os"
            """
        return await self._run_shell(script)

    async def _get_mac_specs(self) -> str:
        script = """
        cpu=$(sysctl -n machdep.cpu.brand_string || sysctl -n machdep.cpu.model)
        cores=$(sysctl -n hw.ncpu)
        ram=$(expr $(sysctl -n hw.memsize) / 1073741824)
        gpu=$(system_profiler SPDisplaysDataType | grep "Chipset Model" | awk -F': ' '{print $2}' || echo "Apple / Unknown GPU")
        disk=$(system_profiler SPStorageDataType | awk '/Capacity:/ {print "- " $2 " " $3}' | head -n 1)
        os=$(sw_vers -productName)
        os_ver=$(sw_vers -productVersion)

        echo "### 🍎 macOS Hardware Specifications"
        echo "**CPU:** $cpu ($cores Cores)"
        echo "**RAM:** ${ram}GB Total"
        echo "**GPU:** $gpu"
        echo "**Storage:**"
        echo "$disk"
        echo "**OS:** $os $os_ver"
        """
        return await self._run_shell(script)

    async def _run_shell(self, script: str) -> str:
        try:
            process = await asyncio.create_subprocess_shell(
                script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10)
            if process.returncode != 0 and not stdout:
                return f"Error executing check: {stderr.decode('utf-8', errors='replace').strip()}"
            return stdout.decode("utf-8", errors="replace").strip()
        except Exception as e:
            return f"Failed to retrieve specs: {e}"

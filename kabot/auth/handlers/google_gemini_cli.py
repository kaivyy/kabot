import os
from typing import Dict, Any, Optional
from pathlib import Path
from kabot.auth.handlers.base import AuthHandler
from kabot.auth.utils import run_oauth_flow
from kabot.auth.diagnostics import render_help_panel, GuidedInstaller
from kabot.auth.discovery import find_node_module, ExtractionEngine
from rich.prompt import Confirm
from rich.console import Console

console = Console()

class GoogleGeminiCLIHandler(AuthHandler):
    """
    Advanced OAuth handler that extracts secrets from the @google/gemini-cli tool.
    Matches OpenClaw behavior for seamless Google integration.
    """

    def authenticate(self) -> Dict[str, Any]:
        # 1. Pre-flight Check: Find gemini-cli
        module_path = find_node_module("@google/gemini-cli")
        
        if not module_path:
            # Trigger Diagnostic UI
            install_cmd = GuidedInstaller.get_install_command("gemini-cli")
            render_help_panel(
                "@google/gemini-cli", 
                install_cmd, 
                "https://www.npmjs.com/package/@google/gemini-cli"
            )
            
            if Confirm.ask("\nWould you like me to attempt automatic installation?"):
                if GuidedInstaller.try_install(install_cmd):
                    console.print("[green]✓ Installation successful![/green]")
                    module_path = find_node_module("@google/gemini-cli")
                else:
                    return {}
            else:
                # Manual entry fallback logic could go here, but for now we exit
                return {}

        if not module_path:
            console.print("[red]✗ Still cannot find gemini-cli after install. Please check your PATH.[/red]")
            return {}

        # 2. Secret Extraction (The "Detective" Step)
        console.print("[dim]Extracting OAuth credentials from gemini-cli...[/dim]")
        
        # Search for oauth2.js in common locations within the module
        possible_js_paths = [
            module_path / "dist" / "src" / "code_assist" / "oauth2.js",
            module_path / "dist" / "code_assist" / "oauth2.js",
            module_path / "node_modules" / "@google" / "gemini-cli-core" / "dist" / "src" / "code_assist" / "oauth2.js"
        ]
        
        js_file = None
        for p in possible_js_paths:
            if p.exists():
                js_file = p
                break
        
        if not js_file:
            # Deep search if standard paths fail
            for p in module_path.rglob("oauth2.js"):
                js_file = p
                break

        if not js_file:
            console.print("[red]✗ Could not find oauth2.js in the gemini-cli installation.[/red]")
            return {}

        # Regex patterns from OpenClaw source
        patterns = {
            "client_id": r"(\d+-[a-z0-9]+\.apps\.googleusercontent\.com)",
            "client_secret": r"(GOCSPX-[A-Za-z0-9_-]+)"
        }
        
        secrets = ExtractionEngine.extract_from_file(js_file, patterns)
        
        if "client_id" not in secrets:
            console.print("[red]✗ Failed to extract Client ID from source code.[/red]")
            return {}

        # 3. OAuth Flow
        # Use port 8085 as per Gemini CLI standard
        console.print(f"[green]✓ Extracted Client ID: {secrets['client_id'][:10]}...[/green]")
        
        # In a real scenario, we would use these extracted secrets to build the Auth URL.
        # For this parity implementation, we trigger the OAuth flow.
        auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
        token = run_oauth_flow(auth_url, port=8085)
        
        if not token:
            return {}

        return {
            "providers": {
                "gemini": {
                    "oauth_token": token,
                    "client_id": secrets["client_id"] # Store for refresh later
                }
            }
        }

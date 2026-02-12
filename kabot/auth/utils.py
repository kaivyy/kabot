import os
import webbrowser
from rich.prompt import Prompt

def is_vps() -> bool:
    """
    Detect if running in a VPS/Headless environment.
    Checks for SSH environment variables or CI flags.
    """
    # Common indicators of SSH sessions
    ssh_client = os.environ.get("SSH_CLIENT")
    ssh_tty = os.environ.get("SSH_TTY")

    # Common indicators of CI/CD environments
    ci = os.environ.get("CI")

    # Check if running in Docker (optional, but often correlates with headless)
    is_docker = os.path.exists("/.dockerenv")

    return any([ssh_client, ssh_tty, ci, is_docker])

def open_browser(url: str):
    """
    Open a URL in the browser if local, or print it if on VPS.
    """
    if is_vps():
        print(f"\n[bold yellow]Please open this URL in your browser:[/bold yellow]\n{url}\n")
    else:
        print(f"Opening browser to: {url}")
        try:
            webbrowser.open(url)
        except Exception:
            # Fallback if browser opening fails
            print(f"\n[bold yellow]Could not open browser. Please open this URL:[/bold yellow]\n{url}\n")

def secure_input(prompt_text: str) -> str:
    """
    Securely prompt for input (masks characters).
    """
    return Prompt.ask(prompt_text, password=True)

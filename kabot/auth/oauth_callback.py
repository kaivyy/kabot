import asyncio
import secrets

from aiohttp import web


class OAuthCallbackServer:
    """Local HTTP server to handle OAuth callbacks."""

    def __init__(self, port: int = 8765):
        self.port = port
        self.token = None
        self.state = secrets.token_urlsafe(32)
        self.app = web.Application()
        self.app.router.add_get('/callback', self.handle_callback)

    async def handle_callback(self, request):
        """Handle OAuth callback and extract token."""
        # Verify state to prevent CSRF
        received_state = request.query.get('state')
        if received_state != self.state:
            return web.Response(
                text="Invalid state parameter (CSRF protection)",
                status=400
            )

        # Extract token/code
        self.token = request.query.get('code') or request.query.get('token')

        if not self.token:
            return web.Response(
                text="Authentication failed: No code or token found in request",
                status=400
            )

        # Return success page
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authentication Successful</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                    text-align: center;
                    padding: 50px;
                    background: #f5f5f5;
                }
                .success {
                    background: white;
                    padding: 40px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    max-width: 500px;
                    margin: 0 auto;
                }
                h1 { color: #22c55e; }
            </style>
        </head>
        <body>
            <div class="success">
                <h1>✓ Authentication Successful</h1>
                <p>You can close this window and return to the terminal.</p>
            </div>
        </body>
        </html>
        """
        return web.Response(text=html, content_type='text/html')

    async def start_and_wait(self, timeout: int = 300):
        """Start server and wait for callback."""
        runner = web.AppRunner(self.app)
        await runner.setup()

        # Try to bind to the port, with a fallback if busy
        max_retries = 5
        current_port = self.port
        site = None

        for i in range(max_retries):
            try:
                site = web.TCPSite(runner, 'localhost', current_port)
                await site.start()
                self.port = current_port
                break
            except OSError:
                if i == max_retries - 1:
                    await runner.cleanup()
                    raise
                current_port += 1

        from rich.console import Console
        console = Console()
        console.print(f"[dim]Waiting for OAuth callback on port {self.port}...[/dim]")

        # Wait for token with timeout
        try:
            for _ in range(timeout):
                if self.token:
                    return self.token
                await asyncio.sleep(1)
            raise TimeoutError(f"OAuth callback timed out after {timeout} seconds")
        finally:
            await runner.cleanup()

    def get_auth_url(self, base_url: str, params: dict) -> str:
        """Build OAuth authorization URL with state and redirect_uri."""
        params['state'] = self.state
        params['redirect_uri'] = f"http://localhost:{self.port}/callback"

        from urllib.parse import urlencode
        query = urlencode(params)
        return f"{base_url}?{query}"

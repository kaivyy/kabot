"""Tiny local MCP echo server used for smoke tests."""

from mcp.server.fastmcp import FastMCP

app = FastMCP("Kabot Local Echo")


@app.tool()
def echo(text: str) -> str:
    """Echo text back unchanged."""

    return text


if __name__ == "__main__":
    app.run("stdio")

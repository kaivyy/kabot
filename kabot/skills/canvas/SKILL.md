---
name: canvas
description: "Present, navigate, hide, eval, and snapshot HTML content on connected Kabot nodes (Mac, iOS, Android). Use when the user wants to display games, dashboards, visualizations, or any HTML on a connected device."
---

# Canvas Skill

Use the `canvas` tool to present web content on any connected Kabot node's canvas view.

## Actions

| Action     | Description                          |
| ---------- | ------------------------------------ |
| `present`  | Show canvas with optional target URL |
| `hide`     | Hide the canvas                      |
| `navigate` | Navigate to a new URL                |
| `eval`     | Execute JavaScript in the canvas     |
| `snapshot` | Capture screenshot of canvas         |

## Workflow

### 1. Create HTML content

Place files in the canvas root directory (default `~/clawd/canvas/`):

```bash
cat > ~/clawd/canvas/my-game.html << 'HTML'
<!DOCTYPE html>
<html>
<head><title>My Game</title></head>
<body>
  <h1>Hello Canvas!</h1>
</body>
</html>
HTML
```

### 2. Determine the canvas host URL

Check the bind mode to construct the correct URL:

```bash
cat ~/.kabot/kabot.json | jq '.gateway.bind'
```

- **loopback**: `http://127.0.0.1:18793/__kabot__/canvas/<file>.html`
- **lan/tailnet/auto**: `http://<hostname>:18793/__kabot__/canvas/<file>.html`

For Tailscale hostname: `tailscale status --json | jq -r '.Self.DNSName' | sed 's/\.$//'`

### 3. Find connected nodes

```bash
kabot nodes list
```

Look for nodes with canvas capability.

### 4. Present content

```
canvas action:present node:<node-id> target:<full-url>
```

**Example:**

```
canvas action:present node:mac-63599bc4-b54d-4392-9048-b97abd58343a target:http://peters-mac-studio-1.sheep-coho.ts.net:18793/__kabot__/canvas/snake.html
```

### 5. Verify with snapshot

```
canvas action:snapshot node:<node-id>
```

Check the screenshot to confirm content loaded correctly.

### 6. Navigate or hide

```
canvas action:navigate node:<node-id> url:<new-url>
canvas action:hide node:<node-id>
```

## Configuration

In `~/.kabot/kabot.json`:

```json
{
  "canvasHost": {
    "enabled": true,
    "port": 18793,
    "root": "/Users/you/clawd/canvas",
    "liveReload": true
  },
  "gateway": {
    "bind": "auto"
  }
}
```

When `liveReload: true` (default), the canvas host watches for file changes and automatically reloads connected canvases.

## Troubleshooting

- **White screen**: URL mismatch — use the full hostname matching your bind mode, not localhost. Test with `curl http://<hostname>:18793/__kabot__/canvas/<file>.html`.
- **"node required" error**: Always specify `node:<node-id>`.
- **"node not connected"**: Node is offline — check with `kabot nodes list`.
- **Content not updating**: Verify `liveReload: true` in config and that the file is in the canvas root.

## Tips

- Keep HTML self-contained (inline CSS/JS) for best results.
- The canvas persists until you `hide` it or navigate away.
- The URL prefix is `/__kabot__/canvas/` — maps to the configured root directory.

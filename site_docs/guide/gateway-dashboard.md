# Gateway and Dashboard Guide

The gateway is Kabot's HTTP surface for dashboard access, webhook ingress, and operator actions.

## Start The Gateway

```bash
kabot gateway
```

By default, Kabot uses the configured gateway port unless you override it for a single run.

## Dashboard Access

Without auth token:

```text
http://127.0.0.1:<port>/dashboard
```

With auth token enabled:
- use the dashboard tokenized URL pattern
- or use bearer auth for API clients

## What The Dashboard Is For

The dashboard is the operator surface for:
- runtime visibility
- quick chat
- sessions and nodes management
- config inspection
- cron and skills controls
- usage and model monitoring

## Auth Scope Model

Kabot supports scoped gateway auth tokens.

Important scope families:
- `operator.read`
- `operator.write`
- `ingress.write`

Practical meaning:
- `operator.read` lets you see dashboard/status surfaces
- `operator.write` lets you perform dashboard write actions
- `ingress.write` controls webhook ingress routes

## Important Dashboard Panels

### Overview
Health, metrics, alerts, uptime, sessions, nodes, cost windows.

### Chat
Operator chat with model routing and fallback control.

### Sessions and Nodes
Runtime visibility and action buttons where permitted by scope.

### Settings / Config / Control
Useful for checking token mode, control surfaces, and read-only versus write-capable behavior.

### Monitoring Panels
Recent parity work added panels for:
- health
- cost and usage
- charts
- channels
- cron jobs
- models
- skills
- sub-agent activity
- git log snapshots

## Performance Notes

The dashboard is designed to avoid unnecessary full reloads.

Recent improvements include:
- cached status snapshots for bursts of panel requests
- active-tab preservation during auto-refresh
- sticky chat scroll behavior
- SSE-backed chat updates
- centralized refresh behavior instead of every panel polling independently

## Security Recommendations

- enable gateway auth token for any non-trivial deployment
- do not expose write-capable routes unnecessarily
- use Tailscale or a reverse proxy rather than a broad open bind when possible
- prefer least-privilege scoped tokens

## Related References

- [Dashboard routes reference](../reference/dashboard-routes.md)
- [Security guide](security.md)
- [Configuration guide](configuration.md)

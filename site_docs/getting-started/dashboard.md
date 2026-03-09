# Dashboard For Beginners

The Kabot dashboard is the operator web surface for monitoring, chat, and quick actions.

## What You Will See

Common sections include:
- overview and runtime health
- chat panel
- sessions
- nodes
- config snapshot
- control actions
- cost and usage panels
- charts and model breakdowns
- channels, cron jobs, skills, and models

## Opening The Dashboard

```text
http://127.0.0.1:<port>/dashboard
```

If auth is enabled, use the dashboard token flow documented in the gateway guide.

## What Beginners Should Use First

### Overview
Use this to confirm:
- gateway is alive
- uptime is moving
- sessions and nodes exist
- alerts are clear

### Chat
Use this when you want:
- a browser-based operator chat panel
- model override tests
- prompt/send flow without leaving the dashboard

### Settings
Use this to:
- inspect config
- review control actions
- understand which routes are read-only versus write-capable

## Good Beginner Habits

- Start with read-only observation first.
- Use write actions only after you understand your auth scope.
- Keep one stable test session for verifying behavior after config changes.

## Next Reading

Move to the full [Gateway and Dashboard guide](../guide/gateway-dashboard.md) when you are ready for auth scopes, operator actions, and panel details.

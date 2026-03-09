# Dashboard Routes Reference

This page summarizes the main dashboard-facing routes and their purpose.

## Main Surface

- `/dashboard`

This is the browser-facing shell for the operator UI.

## Common JSON / operator endpoints

Examples include surfaces for:
- status
- chat history
- SSE chat stream
- sessions
- nodes
- config
- control

Representative routes include:

```text
/dashboard/api/status
/dashboard/api/chat/history
/dashboard/api/chat/stream
/dashboard/api/sessions
/dashboard/api/nodes
/dashboard/api/config
/dashboard/api/control
```

## Common Mutation Endpoints

Examples of dashboard-driven mutation flows include:
- sessions clear/delete
- node start/stop/restart
- chat send
- control actions
- cron and skill operator actions through partial-driven routes

These should be treated as operator write surfaces, not casual public endpoints.

## Partial Routes

Kabot uses partial routes for panel updates in the dashboard, including families such as:
- metrics
- alerts
- health
- cost
- charts
- channels
- cron
- models
- skills
- sub-agent activity
- git log style operator panels

These partials are important because they allow:
- in-place refresh
- lower UI cost
- better dashboard responsiveness than full-page reload loops

## Scope Expectations

Typically:
- `operator.read` is enough for visibility routes
- `operator.write` is required for mutation routes
- `ingress.write` is for webhook ingestion, not normal dashboard browsing

## Recommended Security Model

For a real deployment:

### Read-only operator

Use:
- `operator.read`

Good for:
- dashboards
- observers
- on-call status viewers

### Active operator

Use:
- `operator.read`
- `operator.write`

Good for:
- admins
- maintainers
- people who need to trigger actions

### Ingress-only integration

Use:
- `ingress.write`

Good for:
- webhook producers
- adapter/bridge integrations

## Query Token Note

Dashboard token-in-query usage is intentionally limited to dashboard-facing routes.

Do not assume that same convenience path should be used for generic ingress/webhook surfaces.

## Panel Families You Should Know

| Family | Typical Purpose |
| --- | --- |
| metrics | top bar CPU/RAM/disk/runtime health |
| alerts | operator warning banner |
| health | system/gateway state summary |
| cost | cost and token usage windows |
| charts | historical visual breakdowns |
| channels | configured channel surface |
| cron | job visibility and actions |
| models | available/runtime model visibility |
| skills | skill state and actions |

## Operational Advice

- never expose dashboard write routes casually
- separate read viewers from write operators where possible
- prefer scoped tokens over broad legacy full-access tokens
- combine dashboard protection with network protection, not just token protection

## Recommendation

Treat dashboard URLs as an operator surface and protect them accordingly.

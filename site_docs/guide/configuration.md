# Configuration Guide

This page explains how to think about Kabot configuration, not just where to click.

## Main Entry Point

```bash
kabot config
```

That wizard is the canonical setup path for most users.

## Core Configuration Areas

### Model / Auth
Controls:
- provider login
- model selection
- fallback chains
- provider-specific auth methods

Key idea:
- get one provider working first
- add fallback after success
- only then fine-tune overrides

### Gateway
Controls:
- bind host and port
- auth token and scopes
- exposure mode
- dashboard availability
- Tailscale-related deployment behavior

### Skills
Controls:
- skill enable and disable state
- skill env variables
- install/setup planning for third-party dependencies

### Channels
Controls:
- bot/channel credentials
- `allowFrom` access rules
- multi-bot and instance workflows
- channel-to-agent bindings

### Memory
Controls:
- memory backend choices
- persistence behavior
- hybrid or lightweight paths depending on machine limits

## Good Beginner Defaults

- one primary model
- one fallback model
- gateway auth token enabled
- strict or balanced execution policy
- start with one channel only
- enable more advanced surfaces only after a stable first run

## Where Config Matters Most

| Area | Why it matters |
| --- | --- |
| Model/Auth | determines whether Kabot can answer at all |
| Gateway | controls operator access and web runtime |
| Channels | controls who can talk to Kabot |
| Memory | changes performance and recall behavior |
| Skills | changes which advanced capabilities can activate |

## Safe Change Workflow

1. Make one config change.
2. Save.
3. Run a quick smoke check.
4. Test one real prompt.
5. Only then move to the next change.

```bash
kabot doctor --fix
kabot agent -m "say hello in one line"
```

## Related Pages

- [Authentication reference](../reference/authentication.md)
- [CLI guide](cli.md)
- [Gateway and dashboard guide](gateway-dashboard.md)

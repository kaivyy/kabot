# Configuration Reference

This page summarizes the most important configuration domains.

## Runtime Themes

Kabot configuration usually clusters into these groups:
- models and auth
- gateway and exposure
- channels and bindings
- skills and env values
- memory and persistence
- agent routing
- security and trust

## High-Value Areas To Know

### Model/Auth
Defines:
- provider login state
- primary model
- fallback chain
- provider-specific auth method

### Gateway
Defines:
- port
- bind behavior
- auth token and scopes
- optional Tailscale-related runtime mode

### Skills
Defines:
- entries
- enabled/disabled state
- env values
- install/setup choices

### Channels
Defines:
- credentials
- `allowFrom`
- channel instance settings
- channel-to-agent relationships

### Agents
Defines:
- agent IDs and names
- workspace path
- model assignment
- default agent
- channel bindings

### Memory
Defines:
- memory mode and footprint
- retrieval strategy expectations
- persistence behavior

## Recommendation

Learn the wizard first, then map the wizard menus back to the underlying config concepts.
